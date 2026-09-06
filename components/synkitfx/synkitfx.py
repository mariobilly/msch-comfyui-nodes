"""
ComfyUI-SynkitFX
================
Recreates the Synkit "metablob + tracker" look as two chainable ComfyUI nodes
that output an animated VIDEO (plus the raw IMAGE frame batch).

  1. SynkitFX Metablob
     A grid of dots whose radius follows image brightness (or darkness /
     saturation). Neighbouring dots are merged with a metaball field, so above
     a threshold they fuse into solid blobby regions. Animates by pulsing,
     breathing per dot and drifting the grid.

  2. SynkitFX Tracker
     Detects corner features and draws HUD style tracking boxes: corner
     brackets, index + pixel-coordinate readouts, crosshairs and thin wires.
     Animates by hopping between features, wandering, jittering and flickering.
     On real footage it can also follow the frames with optical flow.

Give either node a single still + `frames` > 1 and it renders that many
animated frames. Give it a video batch and it processes every frame.
Chain Metablob -> Tracker -> Save Video to stack the two filters.

Plain numpy + OpenCV, CPU only. No models.
"""

import math
from fractions import Fraction

import numpy as np
import torch
import cv2

try:  # ComfyUI VIDEO type (new API). Falls back gracefully on old builds.
    from comfy_api.latest import InputImpl, Types
    HAS_VIDEO = True
except Exception:  # pragma: no cover
    HAS_VIDEO = False


# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------
def _hex_to_rgb(s, default=(0.78, 1.0, 0.0)):
    s = (s or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        return default
    try:
        return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return default


def _lum(img):
    return img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114


def _sat(img):
    mx = img.max(axis=2)
    mn = img.min(axis=2)
    return np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)


def _expand_batch(image, frames):
    """Still + frames>1 -> repeat it. Video batch -> keep as is."""
    imgs = image.detach().cpu().numpy().astype(np.float32)
    if imgs.shape[0] == 1 and frames > 1:
        imgs = np.repeat(imgs, frames, axis=0)
    return imgs


def _make_video(frames_tensor, fps):
    if not HAS_VIDEO:
        return None
    return InputImpl.VideoFromComponents(
        Types.VideoComponents(images=frames_tensor, audio=None, frame_rate=Fraction(fps))
    )


PALETTES = {
    "neon": [(0.70, 1.00, 0.00), (0.00, 1.00, 1.00), (1.00, 0.20, 0.80),
             (1.00, 0.90, 0.10), (0.55, 0.40, 1.00), (1.00, 0.55, 0.10),
             (0.30, 1.00, 0.55), (1.00, 1.00, 1.00)],
    "pastel": [(1.00, 0.75, 0.80), (0.75, 0.90, 1.00), (0.85, 1.00, 0.80),
               (1.00, 0.95, 0.70), (0.90, 0.80, 1.00), (1.00, 0.85, 0.70)],
    "cmyk": [(0.00, 0.85, 1.00), (1.00, 0.00, 0.60), (1.00, 0.95, 0.00), (0.10, 0.10, 0.10)],
    "rgb": [(1.00, 0.20, 0.20), (0.20, 1.00, 0.20), (0.30, 0.50, 1.00)],
    "mono_white": [(1.0, 1.0, 1.0)],
}


# -----------------------------------------------------------------------------
# METABLOB
# -----------------------------------------------------------------------------
class SynkitMetablob:
    """Dot grid driven by image brightness, merged into metaballs. Outputs video."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "frames": ("INT", {"default": 48, "min": 1, "max": 4096, "step": 1,
                                   "tooltip": "Frames to render from a still. Ignored when the input is already a video batch."}),
                "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 1.0}),
                "cell_size": ("INT", {"default": 14, "min": 3, "max": 128, "step": 1,
                                      "tooltip": "Grid spacing in pixels. Smaller = more dots."}),
                "drive": (["dark", "bright", "saturation", "edges"], {"default": "dark",
                          "tooltip": "What makes a dot grow: dark areas, bright areas, colour saturation or edges."}),
                "threshold": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 1.0, "step": 0.01,
                                        "tooltip": "Input values below this produce no dot. Raise to keep only strong areas."}),
                "dot_size": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 4.0, "step": 0.05,
                                       "tooltip": "Dot radius multiplier relative to the cell size."}),
                "merge": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01,
                                    "tooltip": "0 = clean separated dots, 1 = dots melt into big blobs."}),
                "contrast": ("FLOAT", {"default": 1.5, "min": 0.2, "max": 5.0, "step": 0.05,
                                       "tooltip": "Gamma on the drive signal. Higher = only the strongest areas get dots."}),
                "softness": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 3.0, "step": 0.05,
                                       "tooltip": "Edge anti-aliasing in pixels."}),
                "color": ("STRING", {"default": "#C6FF00", "tooltip": "Blob colour as hex."}),
                "opacity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "background": (["original", "black", "white", "transparent_black"], {"default": "original",
                               "tooltip": "What the blobs are drawn on. 'transparent_black' = blobs on black, use the MASK output for alpha."}),
                "grid": (["square", "hex"], {"default": "square"}),
                "animate": (["off", "pulse", "breathe", "drift", "pulse+drift", "breathe+drift", "flicker"],
                            {"default": "breathe+drift",
                             "tooltip": "pulse = all dots grow/shrink together. breathe = every dot on its own rhythm. "
                                        "drift = grid slides. flicker = random dots pop in and out."}),
                "anim_speed": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.05,
                                         "tooltip": "Cycles per second."}),
                "anim_amount": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 1.0, "step": 0.01}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF}),
            },
            "optional": {
                "mask": ("MASK",),
            },
        }

    RETURN_TYPES = ("VIDEO", "IMAGE", "MASK")
    RETURN_NAMES = ("video", "frames", "blob_mask")
    FUNCTION = "run"
    CATEGORY = "SynkitFX"

    # -- field --------------------------------------------------------------
    @staticmethod
    def _drive_signal(img, drive):
        if drive == "dark":
            s = 1.0 - _lum(img)
        elif drive == "bright":
            s = _lum(img)
        elif drive == "saturation":
            s = _sat(img)
        else:  # edges
            g = (_lum(img) * 255).astype(np.uint8)
            gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
            s = np.sqrt(gx * gx + gy * gy) / 255.0
            s = cv2.GaussianBlur(s, (0, 0), 2.0)
            s = np.clip(s * 2.0, 0, 1)
        return s.astype(np.float32)

    @staticmethod
    def _kernel(cell, merge):
        # metaball kernel: 1/(d^2 + 1), truncated. Larger reach for more merging.
        reach = int(cell * (1.0 + 2.5 * merge)) + 1
        d = np.arange(-reach, reach + 1, dtype=np.float32)
        dy, dx = np.meshgrid(d, d, indexing="ij")
        d2 = dy * dy + dx * dx
        ker = 1.0 / (d2 + 1.0)
        ker[d2 > reach * reach] = 0.0
        return ker

    @staticmethod
    def _field(blur, ker, cell, threshold, dot_size, contrast, hex_grid, ox, oy, per_dot):
        """blur: cell-averaged drive signal. per_dot(gy_idx, gx_idx) -> multiplier array."""
        H, W = blur.shape
        ys = np.arange(oy % cell, H, cell)
        xs = np.arange(ox % cell, W, cell)
        if len(ys) == 0 or len(xs) == 0:
            return np.zeros((H, W), np.float32)
        gy, gx = np.meshgrid(ys, xs, indexing="ij")
        if hex_grid:
            odd = (np.arange(len(ys)) % 2 == 1)[:, None]
            gx = gx + np.where(odd, cell // 2, 0)
            gx = np.clip(gx, 0, W - 1)
        v = blur[gy, gx]
        v = np.clip((v - threshold) / max(1e-6, 1.0 - threshold), 0, 1) ** contrast
        v = v * per_dot(gy // cell, gx // cell)
        r = np.clip(v, 0, None) * dot_size * cell * 0.5
        imp = np.zeros((H, W), np.float32)
        np.add.at(imp, (gy.ravel(), gx.ravel()), (r * r).ravel())
        # filter2D switches to a DFT for large kernels, so this stays fast on CPU
        return cv2.filter2D(imp, -1, ker, borderType=cv2.BORDER_CONSTANT)

    # -- main ---------------------------------------------------------------
    def run(self, image, frames, fps, cell_size, drive, threshold, dot_size, merge, contrast, softness,
            color, opacity, background, grid, animate, anim_speed, anim_amount, seed, mask=None):
        imgs = _expand_batch(image, frames)
        B, H, W, C = imgs.shape
        col = np.array(_hex_to_rgb(color), np.float32)
        rng = np.random.RandomState(seed)
        base_ox, base_oy = rng.randint(0, cell_size), rng.randint(0, cell_size)
        hex_grid = grid == "hex"
        ker = self._kernel(cell_size, merge)

        # per-cell random phase / flicker tables (indexed by cell row/col)
        ncy, ncx = H // cell_size + 4, W // cell_size + 4
        phase_tab = rng.uniform(0, 2 * math.pi, (ncy, ncx)).astype(np.float32)
        flick_tab = rng.uniform(0, 1, (ncy, ncx)).astype(np.float32)

        still = image.shape[0] == 1
        blur = None

        out_imgs, out_masks = [], []
        for b in range(B):
            img = imgs[b][..., :3]
            t = b / fps * anim_speed * 2 * math.pi
            ox, oy = base_ox, base_oy
            if "drift" in animate:
                ox = int(base_ox + anim_amount * cell_size * 2 * math.cos(t * 0.5))
                oy = int(base_oy + anim_amount * cell_size * 2 * math.sin(t * 0.5))

            if animate.startswith("pulse"):
                gain = 1.0 + anim_amount * math.sin(t)
                per_dot = lambda cy, cx, g=gain: g
            elif animate.startswith("breathe"):
                per_dot = lambda cy, cx, tt=t: 1.0 + anim_amount * np.sin(
                    tt + phase_tab[np.clip(cy, 0, ncy - 1), np.clip(cx, 0, ncx - 1)])
            elif animate == "flicker":
                # each dot has a random phase; it is "off" for a fraction of the cycle
                def per_dot(cy, cx, tt=t):
                    ph = (tt / (2 * math.pi) + flick_tab[np.clip(cy, 0, ncy - 1), np.clip(cx, 0, ncx - 1)]) % 1.0
                    return (ph > anim_amount * 0.9).astype(np.float32)
            else:
                per_dot = lambda cy, cx: 1.0

            # cache the cell-averaged signal for stills (same every frame)
            if not still or blur is None:
                sig = self._drive_signal(img, drive)
                blur = cv2.blur(sig, (cell_size, cell_size))
            fld = self._field(blur, ker, cell_size, threshold, dot_size, contrast, hex_grid, ox, oy, per_dot)

            # A lone dot of radius r gives field ~= 1 at distance r. Iso 1.0 keeps
            # isolated dots at their radius; overlapping dots sum and fuse.
            iso = 1.0 - 0.6 * merge
            if softness > 0:
                alpha = np.clip((fld - iso) / (softness * 0.35) + 0.5, 0, 1)
            else:
                alpha = (fld > iso).astype(np.float32)
            alpha = alpha.astype(np.float32)

            if mask is not None:
                m = mask[min(b, mask.shape[0] - 1)].detach().cpu().numpy().astype(np.float32)
                if m.shape != (H, W):
                    m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
                alpha = alpha * m

            alpha_o = alpha * opacity
            if background == "original":
                base = img
            elif background == "white":
                base = np.ones_like(img)
            else:
                base = np.zeros_like(img)
            comp = base * (1 - alpha_o[..., None]) + col[None, None, :] * alpha_o[..., None]
            out_imgs.append(np.clip(comp, 0, 1))
            out_masks.append(alpha)

        out = torch.from_numpy(np.stack(out_imgs))
        msk = torch.from_numpy(np.stack(out_masks))
        return (_make_video(out, fps), out, msk)


# -----------------------------------------------------------------------------
# TRACKER
# -----------------------------------------------------------------------------
class SynkitTracker:
    """HUD style feature-tracking boxes with labels and wires. Outputs video."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "frames": ("INT", {"default": 48, "min": 1, "max": 4096, "step": 1,
                                   "tooltip": "Frames to render from a still. Ignored when the input is already a video batch."}),
                "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 1.0}),
                "count": ("INT", {"default": 12, "min": 1, "max": 200, "step": 1,
                                  "tooltip": "Number of tracker boxes."}),
                "detector": (["corners", "random", "grid_jitter"], {"default": "corners",
                             "tooltip": "corners = lock onto real image features. random = anywhere."}),
                "min_distance": ("INT", {"default": 60, "min": 4, "max": 1000, "step": 1,
                                         "tooltip": "Minimum pixel distance between boxes."}),
                "box_min": ("INT", {"default": 40, "min": 4, "max": 2000, "step": 1}),
                "box_max": ("INT", {"default": 140, "min": 4, "max": 4000, "step": 1}),
                "bracket_length": ("FLOAT", {"default": 0.3, "min": 0.05, "max": 0.5, "step": 0.01,
                                             "tooltip": "Corner bracket length as a fraction of the box side. 0.5 = full box."}),
                "line_width": ("INT", {"default": 1, "min": 1, "max": 8}),
                "color_mode": (["single", "palette", "random_hue"], {"default": "palette"}),
                "color": ("STRING", {"default": "#C6FF00"}),
                "palette": (list(PALETTES.keys()), {"default": "neon"}),
                "show_labels": ("BOOLEAN", {"default": True}),
                "label_style": (["index+coords", "coords", "index", "hex"], {"default": "index+coords"}),
                "font_scale": ("FLOAT", {"default": 1.0, "min": 0.3, "max": 4.0, "step": 0.05}),
                "crosshairs": ("FLOAT", {"default": 0.4, "min": 0.0, "max": 1.0, "step": 0.05,
                                         "tooltip": "Fraction of boxes that also get a small '+' marker."}),
                "connections": ("INT", {"default": 8, "min": 0, "max": 400, "step": 1,
                                        "tooltip": "Number of thin wires drawn between boxes."}),
                "connect_mode": (["nearest", "random", "chain"], {"default": "random"}),
                "opacity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "background": (["original", "black", "transparent_black"], {"default": "original"}),
                "animate": (["off", "hop", "hop+jitter", "wander", "wander+jitter", "jitter", "track", "track+jitter"],
                            {"default": "hop+jitter",
                             "tooltip": "hop = boxes jump to new features every 'hop_every' frames (works on stills). "
                                        "wander = boxes glide around. jitter = per-frame twitch. "
                                        "track = follow real footage with optical flow (video input only)."}),
                "hop_every": ("INT", {"default": 12, "min": 1, "max": 600, "step": 1,
                                      "tooltip": "Frames between hops. Each box has its own offset so they don't all jump at once."}),
                "jitter": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 50.0, "step": 0.5,
                                     "tooltip": "Pixels of per-frame twitch when jitter is on."}),
                "flicker": ("FLOAT", {"default": 0.1, "min": 0.0, "max": 1.0, "step": 0.01,
                                      "tooltip": "Probability a box is hidden on a given frame."}),
                "rewire_every": ("INT", {"default": 6, "min": 0, "max": 600, "step": 1,
                                         "tooltip": "Frames between re-rolling the wires. 0 = wires stay fixed."}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF}),
            },
            "optional": {
                "mask": ("MASK",),
            },
        }

    RETURN_TYPES = ("VIDEO", "IMAGE", "MASK")
    RETURN_NAMES = ("video", "frames", "overlay_mask")
    FUNCTION = "run"
    CATEGORY = "SynkitFX"

    # -- detection ----------------------------------------------------------
    @staticmethod
    def _feature_pool(gray_u8, n, min_dist, roi_mask=None):
        m = (roi_mask > 0.5).astype(np.uint8) if roi_mask is not None else None
        found = cv2.goodFeaturesToTrack(gray_u8, maxCorners=n, qualityLevel=0.01,
                                        minDistance=min_dist, blockSize=7, mask=m)
        if found is None or len(found) == 0:
            return np.zeros((0, 2), np.float32)
        return found.reshape(-1, 2).astype(np.float32)

    @classmethod
    def _detect(cls, gray_u8, count, min_dist, detector, rng, roi_mask=None):
        H, W = gray_u8.shape
        pts = None
        if detector == "corners":
            pool = cls._feature_pool(gray_u8, count * 4, min_dist, roi_mask)
            if len(pool):
                idx = np.arange(len(pool))
                rng.shuffle(idx[: max(1, len(pool) // 2)])
                pts = pool[idx][:count]
        if pts is None or len(pts) == 0 or detector == "random":
            acc = []
            for _ in range(count * 60):
                if len(acc) >= count:
                    break
                p = np.array([rng.uniform(0, W), rng.uniform(0, H)], np.float32)
                if roi_mask is not None and roi_mask[int(p[1]), int(p[0])] < 0.5:
                    continue
                if all(np.hypot(*(p - q)) >= min_dist for q in acc):
                    acc.append(p)
            pts = np.array(acc, np.float32) if acc else np.zeros((0, 2), np.float32)
        if detector == "grid_jitter":
            n = int(math.ceil(math.sqrt(count)))
            xs = (np.arange(n) + 0.5) / n * W
            ys = (np.arange(n) + 0.5) / n * H
            gx, gy = np.meshgrid(xs, ys)
            pts = np.stack([gx.ravel(), gy.ravel()], 1).astype(np.float32)
            pts += rng.uniform(-W / n / 3, W / n / 3, pts.shape).astype(np.float32)
            rng.shuffle(pts)
            pts = pts[:count]
        return pts

    # -- drawing ------------------------------------------------------------
    @staticmethod
    def _draw(H, W, pts, sizes, cols, ids, vis, cfg, pairs, corner_sel):
        """Returns (overlay float RGB, alpha float)."""
        lw = cfg["line_width"]
        frac = cfg["bracket_length"]
        fs = cfg["font_scale"]
        overlay = np.zeros((H, W, 3), np.uint8)
        alpha = np.zeros((H, W), np.uint8)

        def rgb255(c):
            return (int(float(c[0]) * 255), int(float(c[1]) * 255), int(float(c[2]) * 255))

        def line(p, q, c, w=lw):
            a = (int(round(p[0])), int(round(p[1])))
            b = (int(round(q[0])), int(round(q[1])))
            cv2.line(overlay, a, b, rgb255(c), w, cv2.LINE_AA)
            cv2.line(alpha, a, b, 255, w, cv2.LINE_AA)

        def text(s, org, c, scale, thick=1):
            cv2.putText(overlay, s, org, cv2.FONT_HERSHEY_PLAIN, scale, rgb255(c), thick, cv2.LINE_AA)
            cv2.putText(alpha, s, org, cv2.FONT_HERSHEY_PLAIN, scale, 255, thick, cv2.LINE_AA)

        # wires first so boxes sit on top
        for k, (a, b) in enumerate(pairs):
            if not (vis[a] and vis[b]):
                continue
            sa, sb = sizes[a], sizes[b]
            (sxa, sya, sxb, syb) = corner_sel[k]
            ca = pts[a] + np.array([sxa * sa[0] / 2, sya * sa[1] / 2])
            cb = pts[b] + np.array([sxb * sb[0] / 2, syb * sb[1] / 2])
            line(ca, cb, cols[a], 1)

        n = len(pts)
        for i in range(n):
            if not vis[i]:
                continue
            cx, cy = pts[i]
            bw, bh = sizes[i]
            x0, y0, x1, y1 = cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2
            c = cols[i]
            lx, ly = bw * frac, bh * frac
            for (px, py, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
                line((px, py), (px + sx * lx, py), c)
                line((px, py), (px, py + sy * ly), c)
            if cfg["cross"][i]:
                r = max(3, int(min(bw, bh) * 0.08))
                line((cx - r, cy), (cx + r, cy), c, 1)
                line((cx, cy - r), (cx, cy + r), c, 1)
            if cfg["show_labels"]:
                style = cfg["label_style"]
                sc = 0.9 * fs * max(1.0, max(H, W) / 1080.0)
                lh = int(11 * sc) + 2
                lines_out = []
                if style in ("index+coords", "index"):
                    lines_out.append(f"{ids[i]}")
                if style in ("index+coords", "coords"):
                    lines_out.append(f"{int(cx)}")
                    lines_out.append(f"{int(cy)}")
                if style == "hex":
                    lines_out.append(f"{ids[i]:02X}:{int(cx):04X}")
                    lines_out.append(f"{int(cy):04X}")
                tx = int(x1) + 4
                ty = int(y0) + lh
                if tx > W - 40:
                    tx = int(x0) - 40
                for k, s in enumerate(lines_out):
                    text(s, (tx, ty + k * lh), c, sc)

        return overlay.astype(np.float32) / 255.0, alpha.astype(np.float32) / 255.0

    @staticmethod
    def _make_pairs(visible_idx, n_conn, mode, pts, rng):
        pairs = []
        vis = list(visible_idx)
        if n_conn <= 0 or len(vis) < 2:
            return pairs, []
        if mode == "chain":
            pairs = list(zip(vis[:-1], vis[1:]))[:n_conn]
        elif mode == "nearest":
            for i in vis:
                d = sorted((np.hypot(*(pts[i] - pts[j])), j) for j in vis if j != i)
                for _, j in d[:2]:
                    if (j, i) not in pairs:
                        pairs.append((i, j))
            pairs = pairs[:n_conn]
        else:
            for _ in range(n_conn):
                a, b = rng.choice(vis, 2, replace=False)
                pairs.append((int(a), int(b)))
        corner_sel = [tuple(rng.choice([-1, 1], 4)) for _ in pairs]
        return pairs, corner_sel

    # -- main ---------------------------------------------------------------
    def run(self, image, frames, fps, count, detector, min_distance, box_min, box_max, bracket_length,
            line_width, color_mode, color, palette, show_labels, label_style, font_scale, crosshairs,
            connections, connect_mode, opacity, background, animate, hop_every, jitter, flicker,
            rewire_every, seed, mask=None):
        imgs = _expand_batch(image, frames)
        B, H, W, C = imgs.shape
        still = image.shape[0] == 1
        rng = np.random.RandomState(seed)
        box_min, box_max = min(box_min, box_max), max(box_min, box_max)

        def gray_of(i):
            return (np.clip(_lum(imgs[i][..., :3]), 0, 1) * 255).astype(np.uint8)

        def mask_of(i):
            if mask is None:
                return None
            m = mask[min(i, mask.shape[0] - 1)].detach().cpu().numpy().astype(np.float32)
            if m.shape != (H, W):
                m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
            return m

        def rand_size(r, k=1):
            s = np.stack([r.uniform(box_min, box_max, k), r.uniform(box_min, box_max, k)], 1)
            sq = r.rand(k) < 0.5
            s[sq, 1] = s[sq, 0]
            return s

        # initial state on frame 0
        g0 = gray_of(0)
        pts = self._detect(g0, count, min_distance, detector, rng, mask_of(0)).astype(np.float32)
        n = len(pts)
        sizes = rand_size(rng, n) if n else np.zeros((0, 2))
        ids = rng.permutation(np.arange(1, n + 1)) if n else np.zeros(0, int)
        cross = rng.rand(n) < crosshairs
        hop_offset = rng.randint(0, max(1, hop_every), n) if n else np.zeros(0, int)
        vel = rng.uniform(-1, 1, (n, 2)).astype(np.float32) * (W / 400.0)

        if color_mode == "single":
            cols = [_hex_to_rgb(color)] * n
        elif color_mode == "palette":
            pal = PALETTES[palette]
            cols = [pal[int(rng.randint(len(pal)))] for _ in range(n)]
        else:
            cols = []
            for _ in range(n):
                hsv = np.uint8([[[int(rng.randint(180)), 200, 255]]])
                r, g, b = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)[0, 0]
                cols.append((r / 255, g / 255, b / 255))

        cfg = dict(line_width=line_width, bracket_length=bracket_length, font_scale=font_scale,
                   show_labels=show_labels, label_style=label_style, cross=cross)

        do_track = "track" in animate and not still
        do_jit = "jitter" in animate
        do_hop = "hop" in animate
        do_wander = "wander" in animate
        animated = animate != "off"

        # feature pool for hopping (recomputed periodically on real video)
        pool = self._feature_pool(g0, max(count * 6, 64), min_distance, mask_of(0)) if do_hop else None
        conn_rng = np.random.RandomState(rng.randint(0, 2**31 - 1))
        pairs, corner_sel = self._make_pairs(range(n), connections, connect_mode, pts, conn_rng)

        out_imgs, out_masks = [], []
        prev_gray = g0
        for b in range(B):
            img = imgs[b][..., :3]
            g = g0 if still else gray_of(b)

            # --- optical flow tracking on real footage
            if b > 0 and do_track and n > 0:
                p_in = pts.reshape(-1, 1, 2).astype(np.float32)
                p_out, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, g, p_in, None, winSize=(21, 21), maxLevel=3)
                if p_out is not None:
                    st = st.reshape(-1).astype(bool)
                    p_out = p_out.reshape(-1, 2)
                    inside = (p_out[:, 0] >= 0) & (p_out[:, 0] < W) & (p_out[:, 1] >= 0) & (p_out[:, 1] < H)
                    ok = st & inside
                    pts[ok] = p_out[ok]
                    lost = ~ok
                    if lost.any():
                        fresh = self._detect(g, int(lost.sum()) + 4, min_distance, "corners",
                                             np.random.RandomState(seed + b), mask_of(b))
                        for k, i in enumerate(np.where(lost)[0]):
                            pts[i] = fresh[k] if k < len(fresh) else [rng.uniform(0, W), rng.uniform(0, H)]
            prev_gray = g

            # --- hop: each box jumps to a new feature on its own schedule
            if do_hop and n > 0 and b > 0:
                if not still and b % hop_every == 0:
                    pool = self._feature_pool(g, max(count * 6, 64), min_distance, mask_of(b))
                hr = np.random.RandomState(seed * 31337 + b)
                for i in range(n):
                    if (b + hop_offset[i]) % hop_every == 0:
                        if pool is not None and len(pool):
                            cand = pool[hr.randint(len(pool))]
                        else:
                            cand = np.array([hr.uniform(0, W), hr.uniform(0, H)], np.float32)
                        pts[i] = cand
                        sizes[i] = rand_size(hr, 1)[0]
                        ids[i] = hr.randint(1, 999)

            # --- wander: smooth random walk with edge bounce
            if do_wander and n > 0 and b > 0:
                wr = np.random.RandomState(seed * 7 + b)
                vel += wr.uniform(-0.4, 0.4, vel.shape).astype(np.float32) * (W / 400.0)
                vel = np.clip(vel, -W / 150.0, W / 150.0)
                pts += vel
                for d, lim in ((0, W), (1, H)):
                    out_of = (pts[:, d] < 0) | (pts[:, d] > lim - 1)
                    vel[out_of, d] *= -1
                    pts[:, d] = np.clip(pts[:, d], 0, lim - 1)

            draw_pts = pts.copy()
            if do_jit and n > 0:
                jr = np.random.RandomState(seed * 7919 + b)
                draw_pts += jr.uniform(-jitter, jitter, draw_pts.shape).astype(np.float32)

            vis = np.ones(n, bool)
            if animated and flicker > 0 and n > 0:
                fr = np.random.RandomState(seed * 104729 + b)
                vis = fr.rand(n) >= flicker

            if animated and rewire_every > 0 and b > 0 and b % rewire_every == 0:
                pairs, corner_sel = self._make_pairs(range(n), connections, connect_mode, pts, conn_rng)

            overlay, alpha = self._draw(H, W, draw_pts, sizes, cols, ids, vis, cfg, pairs, corner_sel)

            m = mask_of(b)
            if m is not None:
                alpha = alpha * m
            a = (alpha * opacity)[..., None]
            base_img = img if background == "original" else np.zeros_like(img)
            comp = base_img * (1 - a) + overlay * a
            out_imgs.append(np.clip(comp, 0, 1))
            out_masks.append(alpha)

        out = torch.from_numpy(np.stack(out_imgs))
        msk = torch.from_numpy(np.stack(out_masks))
        return (_make_video(out, fps), out, msk)


NODE_CLASS_MAPPINGS = {
    "SynkitMetablob": SynkitMetablob,
    "SynkitTracker": SynkitTracker,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SynkitMetablob": "SynkitFX Metablob",
    "SynkitTracker": "SynkitFX Tracker",
}

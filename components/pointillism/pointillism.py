"""
ComfyUI-Pointillism
-------------------
Recreates the effect.app "Pointillism" look as a VIDEO:
  1. boost saturation / contrast of the source
  2. scatter thousands of small dots, each coloured from the source pixel under it
  3. hide the source image (white paper) or keep it as the backdrop
  4. vary the dot size, crank density
  5. paper texture + distortion field that breaks the perfect circles into ink blots
  6. animate the random seed every frame (with an optional frame-drop stutter)
     and pack the frames into a video

Feed a single image to get N animated frames, or feed a frame batch (a video)
to stylise every frame. Pure torch, runs on GPU when available.
"""

import math
from fractions import Fraction

import torch
import torch.nn.functional as F

try:
    import comfy.model_management as mm
    _DEVICE = mm.get_torch_device()
except Exception:  # standalone / testing
    _DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

try:
    from comfy_api.input_impl import VideoFromComponents
    from comfy_api.util import VideoComponents
    _HAS_VIDEO = True
except Exception:  # standalone / testing
    VideoFromComponents = None
    VideoComponents = None
    _HAS_VIDEO = False

try:
    from comfy.utils import ProgressBar
except Exception:
    ProgressBar = None


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _parse_hex(s, default=(1.0, 1.0, 1.0)):
    s = (s or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        return default
    try:
        return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return default


def _adjust(img, saturation, contrast):
    """img: (H,W,3) float 0..1"""
    lum = (img * torch.tensor([0.299, 0.587, 0.114], device=img.device)).sum(-1, keepdim=True)
    img = lum + (img - lum) * saturation
    img = (img - 0.5) * contrast + 0.5
    return img.clamp(0, 1)


def _gaussian_blur(x, sigma):
    """x: (C,H,W). Separable gaussian blur."""
    if sigma <= 0.05:
        return x
    k = int(2 * math.ceil(3 * sigma) + 1)
    t = torch.arange(k, device=x.device, dtype=x.dtype) - (k - 1) / 2
    g = torch.exp(-0.5 * (t / sigma) ** 2)
    g = g / g.sum()
    c = x.shape[0]
    x = x[None]
    x = F.conv2d(x, g.view(1, 1, 1, k).expand(c, 1, 1, k), padding=(0, k // 2), groups=c)
    x = F.conv2d(x, g.view(1, 1, k, 1).expand(c, 1, k, 1), padding=(k // 2, 0), groups=c)
    return x[0]


def _smooth_noise(H, W, scale, gen, device, channels=2):
    """Smooth random field (channels,H,W) with features ~scale px, unit-ish std."""
    scale = max(float(scale), 1.0)
    gh = int(math.ceil(H / scale)) + 2
    gw = int(math.ceil(W / scale)) + 2
    n = torch.randn(1, channels, gh, gw, generator=gen, device=device)
    n = F.interpolate(n, size=(H, W), mode="bicubic", align_corners=False)
    return n[0]


def _splat_dots(H, W, xs, ys, rs, cols, softness, device):
    """
    Rasterise N soft discs. Deterministic "last dot on top" via a scatter amax key.
    Returns premultiplied RGBA layer (4,H,W).
    """
    N = xs.numel()
    if N == 0:
        return torch.zeros(4, H, W, device=device)

    edge_w = 0.7 + softness * rs                      # per-dot anti-alias width (px)
    R = int(math.ceil(float((rs + edge_w * 0.5).max().item())))
    R = max(R, 1)
    offs = torch.arange(-R, R + 1, device=device)
    dy, dx = torch.meshgrid(offs, offs, indexing="ij")
    dy = dy.reshape(-1)
    dx = dx.reshape(-1)
    PP = dy.numel()

    key = torch.full((H * W,), -1, dtype=torch.int64, device=device)
    alpha = torch.zeros(H * W, dtype=torch.float32, device=device)

    chunk = max(1, 4_000_000 // PP)
    for i in range(0, N, chunk):
        cx = xs[i:i + chunk]
        cy = ys[i:i + chunk]
        r = rs[i:i + chunk]
        ew = edge_w[i:i + chunk]
        n = cx.numel()

        px = cx.round().long()[:, None] + dx[None, :]
        py = cy.round().long()[:, None] + dy[None, :]
        d = torch.sqrt((px.float() - cx[:, None]) ** 2 + (py.float() - cy[:, None]) ** 2)
        a = ((r[:, None] - d) / ew[:, None] + 0.5).clamp(0, 1)

        valid = (px >= 0) & (px < W) & (py >= 0) & (py < H) & (a > 0)
        idx = (py * W + px)[valid]
        a = a[valid]
        di = torch.arange(i, i + n, device=device)[:, None].expand(n, PP)[valid]
        # solid-core pixels beat soft-edge pixels; later dots beat earlier ones
        k = di + N * (a >= 0.5).long()

        key.scatter_reduce_(0, idx, k, reduce="amax")
        alpha.scatter_reduce_(0, idx, a, reduce="amax")

    has = key >= 0
    dot_i = torch.where(has, key % N, torch.zeros_like(key))
    rgb = cols[dot_i]                                   # (H*W,3)
    alpha = torch.where(has, alpha, torch.zeros_like(alpha))
    layer = torch.cat([rgb * alpha[:, None], alpha[:, None]], dim=1)  # premultiplied
    return layer.T.reshape(4, H, W)


def _render_frame(img, p, seed):
    """img: (H,W,3) float on device. Returns (rgb (H,W,3), alpha (H,W))."""
    device = img.device
    H, W, _ = img.shape
    gen = torch.Generator(device=device)
    gen.manual_seed(int(seed) % (2 ** 63 - 1))

    src = _adjust(img, p["saturation"], p["contrast"])

    # ---- dot positions ----------------------------------------------------
    if p["distribution"] == "jittered_grid":
        spacing = math.sqrt(1000.0 / p["density"])
        gy = torch.arange(0, H, spacing, device=device)
        gx = torch.arange(0, W, spacing, device=device)
        yy, xx = torch.meshgrid(gy, gx, indexing="ij")
        xs = xx.reshape(-1) + spacing * 0.5
        ys = yy.reshape(-1) + spacing * 0.5
        N = xs.numel()
        xs = xs + (torch.rand(N, generator=gen, device=device) - 0.5) * spacing
        ys = ys + (torch.rand(N, generator=gen, device=device) - 0.5) * spacing
        perm = torch.randperm(N, generator=gen, device=device)
        xs, ys = xs[perm], ys[perm]
    else:
        N = max(int(p["density"] * H * W / 1000.0), 1)
        xs = torch.rand(N, generator=gen, device=device) * W
        ys = torch.rand(N, generator=gen, device=device) * H

    xs = xs.clamp(0, W - 1)
    ys = ys.clamp(0, H - 1)

    # ---- colours ----------------------------------------------------------
    iy = ys.round().long().clamp(0, H - 1)
    ix = xs.round().long().clamp(0, W - 1)
    cols = src[iy, ix]
    if p["color_jitter"] > 0:
        jit = (torch.rand(N, 3, generator=gen, device=device) - 0.5) * 2 * p["color_jitter"] * 0.25
        cols = (cols + jit).clamp(0, 1)

    # ---- radii ------------------------------------------------------------
    rs = torch.full((N,), float(p["point_size"]), device=device)
    if p["size_variation"] > 0:
        v = (torch.rand(N, generator=gen, device=device) * 2 - 1) * p["size_variation"]
        rs = rs * (1 + v)
    if p["size_by_darkness"] > 0:
        lum = (cols * torch.tensor([0.299, 0.587, 0.114], device=device)).sum(-1)
        rs = rs * (1 + p["size_by_darkness"] * (0.5 - lum) * 2)
    rs = rs.clamp(min=0.35)

    # ---- rasterise --------------------------------------------------------
    layer = _splat_dots(H, W, xs, ys, rs, cols, p["edge_softness"], device)
    if p["dot_opacity"] < 1:
        layer = layer * p["dot_opacity"]

    # ---- ink bleed --------------------------------------------------------
    if p["ink_bleed"] > 0:
        layer = _gaussian_blur(layer, p["ink_bleed"] * 1.2)

    # ---- paper distortion ------------------------------------------------
    if p["distortion"] > 0:
        amp = p["distortion"] * (1.5 + 2.0 * p["point_size"])          # px
        field = _smooth_noise(H, W, p["distortion_scale"], gen, device)
        field = field + 0.35 * _smooth_noise(H, W, max(p["distortion_scale"] / 3.0, 1.0), gen, device)
        field = field / (field.std() + 1e-6) * amp
        yy, xx = torch.meshgrid(torch.arange(H, device=device, dtype=torch.float32),
                                torch.arange(W, device=device, dtype=torch.float32), indexing="ij")
        gx = (xx + field[0]) / max(W - 1, 1) * 2 - 1
        gy = (yy + field[1]) / max(H - 1, 1) * 2 - 1
        grid = torch.stack([gx, gy], dim=-1)[None]
        layer = F.grid_sample(layer[None], grid, mode="bilinear",
                              padding_mode="zeros", align_corners=True)[0]

    # ---- composite --------------------------------------------------------
    bg_mode = p["background"]
    if bg_mode == "original":
        bg = img.permute(2, 0, 1)
    else:
        if bg_mode == "white":
            c = (1.0, 1.0, 1.0)
        elif bg_mode == "black":
            c = (0.0, 0.0, 0.0)
        else:
            c = _parse_hex(p["background_color"])
        bg = torch.tensor(c, device=device).view(3, 1, 1).expand(3, H, W)

    a = layer[3:4].clamp(0, 1)
    out = bg * (1 - a) + layer[:3]

    # ---- paper grain ------------------------------------------------------
    if p["paper_grain"] > 0:
        g = torch.randn(1, H, W, generator=gen, device=device)
        g = _gaussian_blur(g, 0.6)
        g = g / (g.std() + 1e-6)
        out = out * (1 - p["paper_grain"] * 0.18 * g)

    return out.clamp(0, 1).permute(1, 2, 0), a[0].clamp(0, 1)


# --------------------------------------------------------------------------- #
# the node
# --------------------------------------------------------------------------- #
class PointillismEffect:
    CATEGORY = "video/stylize"
    FUNCTION = "apply"
    RETURN_TYPES = ("VIDEO", "IMAGE", "MASK")
    RETURN_NAMES = ("video", "frames", "dots_mask")
    OUTPUT_TOOLTIPS = ("Connect to Save Video.",
                       "The same frames as an IMAGE batch (for Create Video / Video Combine).",
                       "Per-frame dot coverage (1 = dot, 0 = paper).")
    DESCRIPTION = ("effect.app style Pointillism as a video: thousands of colour-sampled dots "
                   "re-scattered every frame over paper. Give it a still image to animate it, "
                   "or a frame batch to stylise a clip.")

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE", {"tooltip": "A still image (animated for `frames` frames) or a frame batch."}),
                # -- animation --
                "frames": ("INT", {"default": 48, "min": 1, "max": 4096,
                                   "tooltip": "Frames to generate from a still image. Ignored when the input is already a batch."}),
                "fps": ("FLOAT", {"default": 24.0, "min": 1.0, "max": 120.0, "step": 1.0}),
                "hold_frames": ("INT", {"default": 2, "min": 1, "max": 30,
                                        "tooltip": "Keep each dot layout for this many frames. 1 = new dots every frame, 2-3 = the post's frame-drop stutter."}),
                "frame_drop": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 0.9, "step": 0.01,
                                         "tooltip": "Random chance a frame repeats the previous layout (irregular stutter)."}),
                # -- source prep --
                "saturation": ("FLOAT", {"default": 1.35, "min": 0.0, "max": 3.0, "step": 0.05,
                                         "tooltip": "Boost colours before sampling (the post says: more colour, better)."}),
                "contrast": ("FLOAT", {"default": 1.15, "min": 0.2, "max": 3.0, "step": 0.05}),
                # -- dots --
                "density": ("FLOAT", {"default": 40.0, "min": 0.5, "max": 500.0, "step": 0.5,
                                      "tooltip": "Dots per 1000 pixels. 1024x1024 @ 40 = ~42k dots."}),
                "point_size": ("FLOAT", {"default": 2.5, "min": 0.5, "max": 64.0, "step": 0.1,
                                         "tooltip": "Dot radius in pixels."}),
                "size_variation": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01,
                                             "tooltip": "Random +/- radius variation (width variation)."}),
                "size_by_darkness": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.01,
                                               "tooltip": "Bigger dots in dark areas, smaller in light (stipple feel)."}),
                "edge_softness": ("FLOAT", {"default": 0.3, "min": 0.0, "max": 1.0, "step": 0.01}),
                "color_jitter": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0, "step": 0.01,
                                           "tooltip": "Random per-dot colour variation."}),
                "dot_opacity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "distribution": (["random", "jittered_grid"], {"default": "random"}),
                # -- background --
                "background": (["white", "black", "original", "custom"],
                               {"default": "white",
                                "tooltip": "white = the post's Hidden image mode. original keeps the photo under the dots."}),
                "background_color": ("STRING", {"default": "#FFFFFF"}),
                # -- paper --
                "distortion": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 1.0, "step": 0.01,
                                         "tooltip": "Warps the dots with a paper-fibre field so they stop being perfect circles."}),
                "distortion_scale": ("FLOAT", {"default": 3.5, "min": 1.0, "max": 200.0, "step": 0.5,
                                               "tooltip": "Size in px of the warp features."}),
                "ink_bleed": ("FLOAT", {"default": 0.15, "min": 0.0, "max": 1.0, "step": 0.01,
                                        "tooltip": "Softens dots like ink soaking into paper."}),
                "paper_grain": ("FLOAT", {"default": 0.12, "min": 0.0, "max": 1.0, "step": 0.01}),
                # -- randomness --
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFFFFFFFFFF}),
                "animate_seed": ("BOOLEAN", {"default": True,
                                             "tooltip": "Re-scatter the dots over time (the animate-random-seed step). Off = frozen dot layout."}),
            },
            "optional": {
                "audio": ("AUDIO", {"tooltip": "Optional soundtrack muxed into the video output."}),
            },
        }

    # ------------------------------------------------------------------ #
    def apply(self, image, frames, fps, hold_frames, frame_drop, saturation, contrast,
              density, point_size, size_variation, size_by_darkness, edge_softness,
              color_jitter, dot_opacity, distribution, background, background_color,
              distortion, distortion_scale, ink_bleed, paper_grain, seed, animate_seed,
              audio=None):
        p = dict(saturation=saturation, contrast=contrast, density=density,
                 point_size=point_size, size_variation=size_variation,
                 size_by_darkness=size_by_darkness, edge_softness=edge_softness,
                 color_jitter=color_jitter, dot_opacity=dot_opacity, distribution=distribution,
                 background=background, background_color=background_color,
                 distortion=distortion, distortion_scale=distortion_scale,
                 ink_bleed=ink_bleed, paper_grain=paper_grain)

        device = _DEVICE
        B, H, W = image.shape[0], image.shape[1], image.shape[2]
        # H.264 / most video encoders need even dimensions; trim a pixel if needed
        H2, W2 = H - (H % 2), W - (W % 2)
        if (H2, W2) != (H, W):
            image = image[:, :H2, :W2]
        total = B if B > 1 else int(frames)

        # per-frame layout schedule: which dot-seed each output frame uses
        drop_gen = torch.Generator().manual_seed((int(seed) ^ 0x5EED) % (2 ** 63 - 1))
        layout_ids = []
        cur = 0
        for f in range(total):
            if f > 0 and animate_seed:
                advance = (f % max(int(hold_frames), 1) == 0)
                if advance and frame_drop > 0 and torch.rand(1, generator=drop_gen).item() < frame_drop:
                    advance = False
                if advance:
                    cur += 1
            layout_ids.append(cur)

        pbar = ProgressBar(total) if ProgressBar is not None else None
        outs, masks = [], []
        cache = {}  # (src_index, layout_id) -> (rgb, mask) so held frames are not re-rendered
        for f in range(total):
            si = f if B > 1 else 0
            lid = layout_ids[f]
            key = (si, lid)
            if key in cache:
                o, m = cache[key]
            else:
                frame = image[si, :, :, :3].to(device=device, dtype=torch.float32)
                o, m = _render_frame(frame, p, int(seed) + lid)
                o, m = o.cpu(), m.cpu()
                cache = {key: (o, m)}          # only the latest layout is ever reused
            outs.append(o)
            masks.append(m)
            if pbar is not None:
                pbar.update(1)

        frames_t = torch.stack(outs, 0)
        masks_t = torch.stack(masks, 0)

        video = None
        if _HAS_VIDEO:
            video = VideoFromComponents(
                VideoComponents(images=frames_t, audio=audio, frame_rate=Fraction(fps)))
        return video, frames_t, masks_t


NODE_CLASS_MAPPINGS = {"PointillismEffect": PointillismEffect}
NODE_DISPLAY_NAME_MAPPINGS = {"PointillismEffect": "Pointillism Effect (Video)"}

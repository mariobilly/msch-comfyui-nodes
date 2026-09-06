"""
ComfyUI-TimeSlice  ·  temporal displacement / time-slicing glitch
=================================================================
Each band (or cube) of the output frame samples a DIFFERENT moment in time of
the input clip, so moving subjects melt / echo through time.

Extras:
  - pixelate / jitter        -> datamosh tearing
  - chroma_spread            -> per-RGB-channel time offset = colorful chromatic
                                fringing along the axis ("colors on the axis")
  - cubic_px / cubic_lateral -> 2D TIME-CUBES: time flows in both axes, a mosaic
                                of blocks each frozen at a different moment
  - tint_mode / tint_strength-> map the time-offset to a color ramp (rainbow /
                                thermal / ice / neon) so faster-displaced regions
                                glow a different hue

Pure numpy/torch (+cv2 for the color ramps, already in ComfyUI). Operates on a
whole IMAGE batch.
"""

import numpy as np
import torch


def _to_np(images):
    return (images.clamp(0, 1).cpu().numpy() * 255.0).astype(np.uint8)


def _to_tensor(arr):
    return torch.from_numpy(arr.astype(np.float32) / 255.0)


def _row_offsets(L, band, span, anchor, curve):
    """Per-line integer frame offset (length L)."""
    y = np.arange(L, dtype=np.float32)
    if band > 1:
        y = (y // band) * band
    t = y / max(1.0, L - 1) - anchor
    if curve == "ease":
        t = np.sign(t) * (np.abs(t) ** 1.6)
    return np.rint(t * span).astype(np.int64)


def _cube_offsets(L, M, cube, span, anchor, curve, lateral):
    """2D per-cube integer frame offset map, shape (L, M)."""
    yb = (np.arange(L) // cube) * cube
    xb = (np.arange(M) // cube) * cube
    ty = yb / max(1.0, L - 1) - anchor
    tx = xb / max(1.0, M - 1) - 0.5
    if curve == "ease":
        ty = np.sign(ty) * (np.abs(ty) ** 1.6)
    field = ty[:, None] + lateral * tx[None, :]      # (L, M)
    return np.rint(field * span).astype(np.int64)


_CMAPS = {"rainbow": "HSV", "thermal": "INFERNO", "ice": "OCEAN", "neon": "PLASMA"}


def _tint_rgb(norm, mode):
    """norm: (L,M) in 0..1 -> RGB uint8 (L,M,3) via a cv2 colormap."""
    import cv2
    u = (np.clip(norm, 0.0, 1.0) * 255).astype(np.uint8)
    cm = getattr(cv2, "COLORMAP_" + _CMAPS.get(mode, "HSV"))
    return cv2.applyColorMap(u, cm)[..., ::-1].copy()   # BGR -> RGB


def _edge(src, B, mode):
    if mode == "wrap":
        return np.mod(src, B)
    if mode == "mirror":
        p = B - 1
        return np.abs(np.mod(src, 2 * p) - p)
    return np.clip(src, 0, B - 1)


class TimeSlice:
    """Temporal displacement with chromatic + cubic + color-ramp options."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "axis": (["vertical", "horizontal"], {"default": "vertical"}),
                "span_frames": ("INT", {"default": 16, "min": 0, "max": 240,
                    "tooltip": "Frames of time spread across the frame. Bigger = more smear."}),
                "band_px": ("INT", {"default": 1, "min": 1, "max": 256,
                    "tooltip": "1 = smooth slit-scan; larger = chunky constant-time bands."}),
                "anchor": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Where the zero-time line sits (0=top, .5=middle, 1=bottom)."}),
                "curve": (["linear", "ease"], {"default": "linear"}),
                "edge": (["clamp", "wrap", "mirror"], {"default": "clamp"}),
            },
            "optional": {
                "pixelate_px": ("INT", {"default": 0, "min": 0, "max": 64,
                    "tooltip": "0=off. Downsample each band into NxN blocks (datamosh)."}),
                "jitter_px": ("INT", {"default": 0, "min": 0, "max": 200,
                    "tooltip": "Max random sideways shift per band (deterministic by seed)."}),
                "jitter_seed": ("INT", {"default": 0, "min": 0, "max": 2**31 - 1}),
                # ---- NEW: color on the axis ----
                "chroma_spread": ("INT", {"default": 0, "min": 0, "max": 60,
                    "tooltip": "Per-RGB-channel time offset. >0 = colorful chromatic fringing along the slice."}),
                # ---- NEW: cubic time-mosaic ----
                "cubic_px": ("INT", {"default": 0, "min": 0, "max": 256,
                    "tooltip": "0=off (flat bands). >0 = 2D TIME-CUBES of this size; time flows in both axes."}),
                "cubic_lateral": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 3.0, "step": 0.1,
                    "tooltip": "How much time also flows sideways across cubes (cubic mode only)."}),
                # ---- NEW: color ramp keyed to the time-offset ----
                "tint_mode": (["off", "rainbow", "thermal", "ice", "neon"], {"default": "off"}),
                "tint_strength": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05,
                    "tooltip": "Blend a color ramp keyed to each band/cube's time-offset."}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "apply"
    CATEGORY = "TimeSlice"

    def apply(self, images, axis, span_frames, band_px, anchor, curve, edge,
              pixelate_px=0, jitter_px=0, jitter_seed=0,
              chroma_spread=0, cubic_px=0, cubic_lateral=1.0,
              tint_mode="off", tint_strength=0.0):
        F = _to_np(images)
        B, H, W, C = F.shape
        if B < 2 or span_frames == 0:
            return (images,)

        horizontal = (axis == "horizontal")
        Fw = F.transpose(0, 2, 1, 3) if horizontal else F   # [B, L, M, C]
        L, M = Fw.shape[1], Fw.shape[2]

        # ---- build the per-pixel time-offset map (L, M) ----
        if cubic_px and cubic_px > 1:
            offmap = _cube_offsets(L, M, cubic_px, span_frames, anchor, curve, cubic_lateral)
        else:
            offmap = np.broadcast_to(
                _row_offsets(L, band_px, span_frames, anchor, curve)[:, None], (L, M))

        YS = np.broadcast_to(np.arange(L)[:, None], (L, M))
        XS = np.broadcast_to(np.arange(M)[None, :], (L, M))

        # per-channel chroma deltas (R leads, B trails) -> colorful fringing
        cdelta = [chroma_spread, 0, -chroma_spread] if chroma_spread > 0 else None

        # tint ramp keyed to normalized offset (computed once, stable across frames)
        tint_img = None
        if tint_mode != "off" and tint_strength > 0:
            lo, hi = offmap.min(), offmap.max()
            norm = (offmap - lo) / (hi - lo) if hi > lo else np.zeros((L, M), np.float32)
            tint_img = _tint_rgb(norm, tint_mode).astype(np.float32)

        rng = np.random.RandomState(int(jitter_seed)) if jitter_px > 0 else None
        bstep = cubic_px if (cubic_px and cubic_px > 1) else band_px
        n_bands = int(np.ceil(L / max(1, bstep)))
        band_jit = (rng.randint(-jitter_px, jitter_px + 1, size=n_bands)
                    if rng is not None else None)

        out = np.empty_like(Fw)
        for t in range(B):
            if cdelta is None:
                src = _edge(t + offmap, B, edge)
                frame = Fw[src, YS, XS, :]                    # (L, M, C)
            else:
                frame = np.empty((L, M, C), Fw.dtype)
                for ch in range(min(3, C)):
                    src = _edge(t + offmap + cdelta[ch], B, edge)
                    frame[..., ch] = Fw[src, YS, XS, ch]
                for ch in range(3, C):                        # alpha etc.
                    frame[..., ch] = Fw[_edge(t + offmap, B, edge), YS, XS, ch]

            if pixelate_px and pixelate_px > 1:
                p = pixelate_px; Lc = (L // p) * p; Mc = (M // p) * p
                if Lc and Mc:
                    blk = frame[:Lc, :Mc].reshape(Lc//p, p, Mc//p, p, C).mean(axis=(1, 3), keepdims=True)
                    frame[:Lc, :Mc] = np.broadcast_to(blk.astype(frame.dtype),
                                                      (Lc//p, p, Mc//p, p, C)).reshape(Lc, Mc, C)

            if band_jit is not None:
                for bi in range(n_bands):
                    y0 = bi * bstep; y1 = min(L, y0 + bstep); sh = int(band_jit[bi])
                    if sh:
                        frame[y0:y1] = np.roll(frame[y0:y1], sh, axis=1)

            if tint_img is not None:
                lum = frame.astype(np.float32).mean(axis=2, keepdims=True) / 255.0
                tinted = tint_img * lum                        # hue modulated by brightness
                frame = ((1.0 - tint_strength) * frame + tint_strength * tinted
                         ).clip(0, 255).astype(frame.dtype)

            out[t] = frame

        if horizontal:
            out = out.transpose(0, 2, 1, 3)
        return (_to_tensor(out),)


NODE_CLASS_MAPPINGS = {"TimeSlice": TimeSlice}
NODE_DISPLAY_NAME_MAPPINGS = {"TimeSlice": "TimeSlice ▸ Temporal Displacement"}

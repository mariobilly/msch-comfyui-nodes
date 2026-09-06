"""
WarpWiggle Stylize node for ComfyUI.

Single-clip version: applies the TimeSlice warp/wiggle displacement continuously
across every frame of one IMAGE batch (no transition, no second clip). The warp
animates over time and can either stay constant or breathe in "pulses" (calm ->
warp -> calm, repeating) like the reference montage.

Chain a HUD Overlay node after this for the full @thesystms look.

Input/Output: IMAGE ([N, H, W, C] float32 0..1).
"""

import math
import torch
import torch.nn.functional as F

from .warp_wiggle import _value_noise, _block_noise


def _sample_chroma(img, base, dx, dy, edge_mode, ca):
    pad = {"zeros": "zeros", "border": "border", "reflection": "reflection"}[edge_mode]
    C = img.shape[1]
    if ca <= 0 or C < 3:
        grid = torch.stack([base[..., 0] + dx, base[..., 1] + dy], dim=-1).unsqueeze(0)
        return F.grid_sample(img, grid, mode="bilinear", padding_mode=pad, align_corners=False)
    outs = []
    scales = [1.0 + ca, 1.0, 1.0 - ca]
    for ci in range(C):
        s = scales[ci] if ci < 3 else 1.0
        grid = torch.stack([base[..., 0] + dx * s, base[..., 1] + dy * s], dim=-1).unsqueeze(0)
        outs.append(F.grid_sample(img[:, ci:ci + 1], grid, mode="bilinear",
                                  padding_mode=pad, align_corners=False))
    return torch.cat(outs, dim=1)


class WarpWiggleStylize:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "warp_pattern": (
                    ["horizontal_bands", "vertical_bands", "blocks",
                     "radial", "slit_scan"],
                    {"default": "horizontal_bands"},
                ),
                "warp_strength": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0, "step": 0.01}),
                "warp_frequency": ("FLOAT", {"default": 4.0, "min": 0.5, "max": 60.0, "step": 0.5}),
                "wiggle_amplitude": ("FLOAT", {"default": 0.02, "min": 0.0, "max": 1.0, "step": 0.01}),
                "wiggle_frequency": ("FLOAT", {"default": 6.0, "min": 0.5, "max": 60.0, "step": 0.5}),
                "wiggle_axis": (["horizontal", "vertical", "both"], {"default": "both"}),
                "block_size": ("INT", {"default": 48, "min": 4, "max": 512}),
                "noise_amount": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0, "step": 0.01}),
                "motion_speed": ("FLOAT", {"default": 0.15, "min": 0.0, "max": 2.0, "step": 0.01}),
                "intensity_mode": (["constant", "pulse"], {"default": "constant"}),
                "pulse_count": ("FLOAT", {"default": 4.0, "min": 0.1, "max": 60.0, "step": 0.1}),
                "pulse_depth": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 1.0, "step": 0.05}),
                "chromatic_aberration": ("FLOAT", {"default": 0.06, "min": 0.0, "max": 1.0, "step": 0.01}),
                "edge_mode": (["reflection", "border", "zeros"], {"default": "reflection"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "render"
    CATEGORY = "WarpWiggle"

    def render(self, images, warp_pattern, warp_strength, warp_frequency,
               wiggle_amplitude, wiggle_frequency, wiggle_axis, block_size,
               noise_amount, motion_speed, intensity_mode, pulse_count,
               pulse_depth, chromatic_aberration, edge_mode, seed):

        dev = images.device
        imgs = images.float()
        N, H, W, C = imgs.shape

        nx = _value_noise(H, W, max(4, (H + W) // (2 * block_size)), seed, dev)
        ny = _value_noise(H, W, max(4, (H + W) // (2 * block_size)), seed + 101, dev)
        blkx = _block_noise(H, W, block_size, seed + 7, dev)
        blky = _block_noise(H, W, block_size, seed + 13, dev)

        ysn = torch.linspace(0.0, 1.0, H, device=dev).view(H, 1).expand(H, W)
        xsn = torch.linspace(0.0, 1.0, W, device=dev).view(1, W).expand(H, W)
        ysg = torch.linspace(-1.0, 1.0, H, device=dev).view(H, 1).expand(H, W)
        xsg = torch.linspace(-1.0, 1.0, W, device=dev).view(1, W).expand(H, W)
        base = torch.stack([xsg, ysg], dim=-1)

        # gentler scaling than the transition node: this is applied to EVERY
        # frame, so full-slider values stay strong-but-legible, not destructive.
        STR = warp_strength * 0.5
        WA = wiggle_amplitude * 0.5
        na = noise_amount * 0.5

        out = torch.empty_like(imgs)
        for i in range(N):
            phase = 2.0 * math.pi * motion_speed * i
            if intensity_mode == "pulse":
                lfo = 0.5 + 0.5 * math.sin(2.0 * math.pi * pulse_count * (i / max(1, N)))
                env = (1.0 - pulse_depth) + pulse_depth * lfo
            else:
                env = 1.0

            dx = torch.zeros((H, W), device=dev)
            dy = torch.zeros((H, W), device=dev)

            if warp_pattern == "horizontal_bands":
                dx = dx + STR * torch.sin(2 * math.pi * warp_frequency * ysn + phase)
            elif warp_pattern == "vertical_bands":
                dy = dy + STR * torch.sin(2 * math.pi * warp_frequency * xsn + phase)
            elif warp_pattern == "blocks":
                m = 0.6 + 0.4 * math.sin(phase)
                dx = dx + STR * blkx * m
                dy = dy + STR * blky * m
            elif warp_pattern == "radial":
                cx, cy = xsn - 0.5, ysn - 0.5
                r = torch.sqrt(cx * cx + cy * cy) + 1e-6
                wave = STR * torch.sin(2 * math.pi * warp_frequency * r - phase)
                dx = dx + wave * (cx / r)
                dy = dy + wave * (cy / r)
            elif warp_pattern == "slit_scan":
                band = torch.floor(ysn * warp_frequency) / max(1.0, warp_frequency)
                dx = dx + STR * (band - 0.5) * 2.0 * math.sin(phase)
                dy = dy + STR * 0.5 * torch.sin(2 * math.pi * warp_frequency * ysn + phase)

            if wiggle_axis in ("horizontal", "both"):
                dx = dx + WA * torch.sin(2 * math.pi * wiggle_frequency * ysn + phase * 1.7)
            if wiggle_axis in ("vertical", "both"):
                dy = dy + WA * torch.sin(2 * math.pi * wiggle_frequency * xsn + phase * 1.3)

            if na > 0:
                dx = dx + na * nx
                dy = dy + na * ny

            dx = dx * env
            dy = dy * env

            fi = imgs[i].permute(2, 0, 1).unsqueeze(0)
            w = _sample_chroma(fi, base, dx, dy, edge_mode, chromatic_aberration)
            out[i] = w.squeeze(0).permute(1, 2, 0)

        return (out.clamp(0.0, 1.0),)

"""Contour-oriented ASCII graphics. No model downloads or font dependencies."""

import re
from functools import lru_cache

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFilter


def _color(value):
    value = value.strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        raise ValueError("Colors must contain six hex digits, e.g. #FFFF00.")
    return np.array([int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)


@lru_cache(maxsize=32)
def _glyphs(size, thickness, length):
    """Supersampled geometric glyphs stay consistent across operating systems."""
    scale = 4
    extent = size * scale
    center = (extent - 1) / 2
    half = size * length * scale / 2
    width = max(1, round(thickness * scale))
    atlas = []
    # Blank, horizontal, backslash, vertical, slash, then six tone levels.
    for index in range(11):
        tile = Image.new("L", (extent, extent))
        draw = ImageDraw.Draw(tile)
        if 1 <= index <= 4:
            angle = (index - 1) * np.pi / 4
            dx, dy = np.cos(angle) * half, np.sin(angle) * half
            draw.line((center - dx, center - dy, center + dx, center + dy), fill=255, width=width)
        elif index in (5, 6, 7):
            dot = size * (0.10, 0.18, 0.29)[index - 5] * scale
            for x in (extent * 0.25, extent * 0.75):
                for y in (extent * 0.25, extent * 0.75):
                    draw.rectangle((x - dot / 2, y - dot / 2, x + dot / 2, y + dot / 2), fill=255)
        elif index in (8, 9):
            stripe_width = max(width, round(extent * (0.12 if index == 8 else 0.25)))
            for y in (extent * 0.25, extent * 0.75):
                draw.line((0, y, extent - 1, y), fill=255, width=stripe_width)
        elif index == 10:
            draw.rectangle((0, 0, extent - 1, extent - 1), fill=255)
        atlas.append(np.asarray(tile.resize((size, size), Image.Resampling.LANCZOS), dtype=np.float32) / 255)
    return np.stack(atlas)


def _pool(values, size):
    h, w = values.shape
    padded = np.pad(values, ((0, (-h) % size), (0, (-w) % size)), mode="edge")
    return padded.reshape(padded.shape[0] // size, size, padded.shape[1] // size, size).mean(axis=(1, 3))


def _analyze(rgb, size, blur):
    gray = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    detection = rgb
    if blur > 0:
        detection = np.asarray(Image.fromarray(np.uint8(np.clip(rgb, 0, 1) * 255)).filter(
            ImageFilter.GaussianBlur(blur)), dtype=np.float32) / 255
    p = np.pad(detection, ((1, 1), (1, 1), (0, 0)), mode="edge")
    gx = (p[:-2, 2:] + 2 * p[1:-1, 2:] + p[2:, 2:]
          - p[:-2, :-2] - 2 * p[1:-1, :-2] - p[2:, :-2]) / 4
    gy = (p[2:, :-2] + 2 * p[2:, 1:-1] + p[2:, 2:]
          - p[:-2, :-2] - 2 * p[:-2, 1:-1] - p[:-2, 2:]) / 4
    # Structure tensors avoid opposite gradients cancelling in a single cell.
    # Color-channel energy also finds boundaries with similar luminance.
    xx = _pool(np.mean(gx * gx, axis=2), size)
    yy = _pool(np.mean(gy * gy, axis=2), size)
    xy = _pool(np.mean(gx * gy, axis=2), size)
    energy = xx + yy
    coherence = np.sqrt((xx - yy) ** 2 + 4 * xy ** 2) / (energy + 1e-8)
    strength = np.sqrt(energy)
    # The contour tangent is perpendicular to the image gradient.
    tangent = 0.5 * np.arctan2(2 * xy, xx - yy) + np.pi / 2
    orientation = np.floor((tangent % np.pi) / (np.pi / 4) + 0.5).astype(np.int32) % 4 + 1
    return _pool(gray, size), strength, coherence, orientation


def _render_mask(rgb, mode, cell_size, line_width, line_length, edge_threshold,
                 edge_coherence, blur, tone_gamma, fill_amount, invert_tones):
    tone, strength, coherence, orientation = _analyze(rgb, cell_size, blur)
    edges = (strength >= edge_threshold) & (strength > 1e-6) & (coherence >= edge_coherence)
    brightness = np.clip(tone, 0, 1)
    if invert_tones:
        brightness = 1 - brightness
    brightness = brightness ** (1 / tone_gamma)
    tone_ids = np.minimum((brightness * 6).astype(np.int32), 5) + 5
    ids = np.where(edges, orientation, 0)
    gains = np.ones(tone.shape, dtype=np.float32)
    if mode == "full_ascii":
        ids = np.where(edges, orientation, tone_ids)
        gains = np.where(edges, 1.0, fill_amount).astype(np.float32)
    elif mode == "mixed":
        # Put dot/checker texture in shadows; leave faces/highlights open.
        fill = (~edges) & (brightness < fill_amount)
        ids = np.where(fill, np.where(brightness < fill_amount * 0.55, 7, 6), ids)
    atlas = _glyphs(cell_size, line_width, line_length)
    h, w = rgb.shape[:2]
    result = np.empty((h, w), dtype=np.float32)
    # Render one tile row at a time to bound temporary memory on large images.
    for row in range(ids.shape[0]):
        tiles = atlas[ids[row]] * gains[row, :, None, None]
        strip = tiles.transpose(1, 0, 2).reshape(cell_size, -1)
        start = row * cell_size
        count = min(cell_size, h - start)
        result[start:start + count] = strip[:count, :w]
    return np.clip(result, 0, 1)


class EdgeASCII:
    CATEGORY = "image/effects"
    FUNCTION = "apply"
    RETURN_TYPES = ("IMAGE", "MASK")
    RETURN_NAMES = ("image", "effect_mask")
    DESCRIPTION = "Overlay contour-aligned ASCII strokes and optional halftone patterns. Works on image batches."
    SEARCH_ALIASES = ["edge ascii", "ascii", "contour", "halftone"]

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",),
            "mode": (["edge_only", "full_ascii", "mixed"],),
            "cell_size": ("INT", {"default": 16, "min": 4, "max": 128, "step": 1,
                                   "tooltip": "Grid spacing in pixels. Scale this with image resolution."}),
            "color": ("STRING", {"default": "#FFFF00"}),
            "opacity": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.05}),
            "line_width": ("FLOAT", {"default": 1.6, "min": 0.5, "max": 16.0, "step": 0.1}),
            "line_length": ("FLOAT", {"default": 0.85, "min": 0.1, "max": 1.0, "step": 0.05}),
            "edge_threshold": ("FLOAT", {"default": 0.055, "min": 0.0, "max": 1.0, "step": 0.005,
                                        "tooltip": "Lower values create more strokes; higher values keep stronger contours."}),
            "edge_coherence": ("FLOAT", {"default": 0.25, "min": 0.0, "max": 1.0, "step": 0.05,
                                        "tooltip": "Raise to remove strokes from noisy areas with conflicting directions."}),
            "blur": ("FLOAT", {"default": 1.2, "min": 0.0, "max": 12.0, "step": 0.1,
                              "tooltip": "Smooth the detection image only; the original photo stays sharp."}),
            "tone_gamma": ("FLOAT", {"default": 1.6, "min": 0.1, "max": 4.0, "step": 0.1}),
            "fill_amount": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05,
                                     "tooltip": "Full ASCII: tone-pattern opacity (use 1 for dense yellow). Mixed: shadow coverage. Edge only: unused."}),
            "invert_tones": ("BOOLEAN", {"default": False}),
            "background": (["original", "solid"],),
            "background_color": ("STRING", {"default": "#000000"}),
        }, "optional": {"mask": ("MASK", {"tooltip": "White permits the effect, black excludes it. Single mask broadcasts over the batch."})}}

    @classmethod
    def VALIDATE_INPUTS(cls, color, background_color):
        try:
            _color(color)
            _color(background_color)
        except (ValueError, AttributeError) as exc:
            return str(exc)
        return True

    def apply(self, image, mode="edge_only", cell_size=16, color="#FFFF00", opacity=1.0,
              line_width=1.6, line_length=0.85, edge_threshold=0.055, edge_coherence=0.25,
              blur=1.2, tone_gamma=1.6, fill_amount=0.5, invert_tones=False,
              background="original", background_color="#000000", mask=None):
        if image.ndim != 4 or image.shape[-1] != 3 or min(image.shape[:3]) < 1:
            raise ValueError("image must be a nonempty ComfyUI IMAGE tensor [batch, height, width, 3].")
        if mode not in ("edge_only", "full_ascii", "mixed") or background not in ("original", "solid"):
            raise ValueError("Unknown effect mode or background.")
        if not 4 <= cell_size <= 128 or tone_gamma <= 0 or blur < 0:
            raise ValueError("Use cell_size 4..128, positive tone_gamma, and nonnegative blur.")
        foreground, bg_color = _color(color), _color(background_color)
        batch, h, w, _ = image.shape
        selection = None
        if mask is not None:
            selection = mask.detach().to(device="cpu", dtype=torch.float32)
            if selection.ndim == 2:
                selection = selection.unsqueeze(0)
            if selection.ndim != 3 or selection.shape[0] not in (1, batch) or min(selection.shape) < 1:
                raise ValueError("mask must have shape [H,W], [1,H,W], or [batch,H,W].")
            if selection.shape[1:] != (h, w):
                selection = F.interpolate(selection[:, None], size=(h, w), mode="bilinear", align_corners=False)[:, 0]
            selection = torch.nan_to_num(selection, nan=0.0).clamp(0, 1).numpy()
        outputs, masks = [], []
        for i in range(batch):
            rgb = image[i].detach().to(device="cpu", dtype=torch.float32).numpy()
            rgb = np.clip(np.nan_to_num(rgb, nan=0.0), 0, 1)
            alpha = _render_mask(rgb, mode, cell_size, line_width, line_length,
                                 edge_threshold, edge_coherence, blur, tone_gamma,
                                 fill_amount, invert_tones) * np.clip(opacity, 0, 1)
            region = selection[0 if len(selection) == 1 else i] if selection is not None else None
            if region is not None:
                alpha *= region
            base = rgb if background == "original" else np.broadcast_to(bg_color, rgb.shape)
            if background == "solid" and region is not None:
                base = rgb * (1 - region[..., None]) + base * region[..., None]
            outputs.append(torch.from_numpy(np.asarray(base * (1 - alpha[..., None]) + foreground * alpha[..., None], dtype=np.float32)))
            masks.append(torch.from_numpy(np.asarray(alpha, dtype=np.float32)))
        return torch.stack(outputs).to(image.device), torch.stack(masks).to(image.device)

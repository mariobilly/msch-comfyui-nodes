"""
Code Matrix (ASCII) node for ComfyUI.

Turns a video (IMAGE batch) into green monospace "code" art on black: each frame
is rebuilt from text glyphs whose density/brightness follows the image. Supports
a full ASCII ramp (the classic ASCII-portrait look), a true binary 0/1 mode, and
a random matrix code-rain mode.

Fully vectorized: glyphs are rendered once into an atlas, then placed with numpy
fancy-indexing — fast even on long clips.

Input/Output: IMAGE ([N, H, W, C] float32 0..1).
"""

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw, ImageFont


# dark -> light ramps (first char is a space so dark areas read as background)
RAMP_DENSE = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
RAMP_SIMPLE = " .:-=+*#%@"
POOL_BINARY = "01"
POOL_MATRIX = "0123456789Z:.=*+<>|"

COLOR_PRESETS = {
    "green":  (60, 255, 90),
    "amber":  (255, 176, 0),
    "cyan":   (80, 255, 220),
    "white":  (210, 255, 210),
}


def _font(size):
    for name in ("consola.ttf", "cour.ttf", "DejaVuSansMono.ttf", "lucon.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _hex_rgb(s, fallback):
    s = (s or "").strip().lstrip("#")
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except Exception:
        return fallback


class CodeMatrixASCII:
    def __init__(self):
        self._atlas_cache = {}

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "char_set": (["ascii_dense", "ascii_simple", "binary", "matrix", "custom"],
                             {"default": "ascii_dense"}),
                "char_pick": (["by_brightness", "random"], {"default": "by_brightness"}),
                "custom_chars": ("STRING", {"default": "01", "multiline": False}),
                "columns": ("INT", {"default": 140, "min": 16, "max": 600}),
                "color_mode": (["green", "amber", "cyan", "white", "custom", "original"],
                               {"default": "green"}),
                "custom_color": ("STRING", {"default": "#33FF66", "multiline": False}),
                "background": ("STRING", {"default": "#000000", "multiline": False}),
                "gamma": ("FLOAT", {"default": 1.0, "min": 0.2, "max": 4.0, "step": 0.05}),
                "contrast": ("FLOAT", {"default": 1.0, "min": 0.2, "max": 3.0, "step": 0.05}),
                "invert": ("BOOLEAN", {"default": False}),
                "threshold": ("FLOAT", {"default": 0.12, "min": 0.0, "max": 1.0, "step": 0.01}),
                "flicker": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "bold": ("BOOLEAN", {"default": False}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "render"
    CATEGORY = "CodeMatrix"

    # ------------------------------------------------------------------
    def _atlas(self, glyphs, cw, ch, bold):
        key = (glyphs, cw, ch, bold)
        if key in self._atlas_cache:
            return self._atlas_cache[key]
        fs = max(4, int(ch * 0.95))
        font = _font(fs)
        atlas = np.zeros((len(glyphs), ch, cw), dtype=np.float32)
        for k, c in enumerate(glyphs):
            tile = Image.new("L", (cw, ch), 0)
            d = ImageDraw.Draw(tile)
            try:
                d.text((cw / 2, ch / 2), c, font=font, fill=255, anchor="mm")
                if bold:
                    d.text((cw / 2 + 1, ch / 2), c, font=font, fill=255, anchor="mm")
            except Exception:
                d.text((1, 0), c, font=font, fill=255)
            atlas[k] = np.asarray(tile, dtype=np.float32) / 255.0
        self._atlas_cache[key] = atlas
        return atlas

    # ------------------------------------------------------------------
    def render(self, images, char_set, char_pick, custom_chars, columns,
               color_mode, custom_color, background, gamma, contrast, invert,
               threshold, flicker, bold, seed):

        imgs = images.float().clamp(0, 1)
        N, H, W, C = imgs.shape
        if C == 1:
            imgs = imgs.repeat(1, 1, 1, 3); C = 3

        # choose glyph list
        if char_set == "ascii_dense":
            base = RAMP_DENSE
        elif char_set == "ascii_simple":
            base = RAMP_SIMPLE
        elif char_set == "binary":
            base = POOL_BINARY
        elif char_set == "matrix":
            base = POOL_MATRIX
        else:
            base = custom_chars if custom_chars else "01"

        if char_pick == "by_brightness":
            glyphs = base if base.startswith(" ") else (" " + base)
        else:  # random: space + pool (no leading-space dependence)
            pool = base.replace(" ", "")
            if not pool:
                pool = "01"
            glyphs = " " + pool
        L = len(glyphs)

        # cell geometry (chars are ~2x taller than wide)
        cw = max(3, round(W / columns))
        chh = max(5, round(cw * 2))
        cols_eff = max(1, W // cw)
        rows = max(1, H // chh)

        atlas = self._atlas(glyphs, cw, chh, bold)

        bg = np.array(_hex_rgb(background, (0, 0, 0)), dtype=np.float32) / 255.0
        if color_mode == "custom":
            col = np.array(_hex_rgb(custom_color, (51, 255, 102)), dtype=np.float32) / 255.0
        elif color_mode in COLOR_PRESETS:
            col = np.array(COLOR_PRESETS[color_mode], dtype=np.float32) / 255.0
        else:
            col = None  # original

        # luminance + (optional) per-cell color, sampled to the char grid
        lum = (imgs[..., 0] * 0.299 + imgs[..., 1] * 0.587 + imgs[..., 2] * 0.114)
        lum_s = F.interpolate(lum.unsqueeze(1), size=(rows, cols_eff), mode="area").squeeze(1)
        lum_s = lum_s.cpu().numpy()
        if col is None:
            rgb_s = F.interpolate(imgs.permute(0, 3, 1, 2), size=(rows, cols_eff),
                                  mode="area").permute(0, 2, 3, 1).cpu().numpy()

        # base random index field (stable across frames unless flicker reshuffles)
        rng0 = np.random.default_rng(seed)
        base_idx = rng0.integers(1, L, size=(rows, cols_eff)) if char_pick == "random" else None

        oy = (H - rows * chh) // 2
        ox = (W - cols_eff * cw) // 2
        out = np.empty((N, H, W, 3), dtype=np.float32)

        for i in range(N):
            g = lum_s[i].copy()
            g = np.clip((g - 0.5) * contrast + 0.5, 0.0, 1.0)
            g = np.power(g, gamma)
            if invert:
                g = 1.0 - g

            if char_pick == "by_brightness":
                idx = np.rint(g * (L - 1)).astype(np.int64)
                bright = g
            else:
                idx = base_idx.copy()
                if flicker > 0:
                    rngf = np.random.default_rng(seed * 2654435761 + i + 1)
                    m = rngf.random((rows, cols_eff)) < flicker
                    idx[m] = rngf.integers(1, L, size=int(m.sum()))
                blank = g < threshold
                idx[blank] = 0
                bright = 0.55 + 0.45 * g
                bright[blank] = 0.0

            glyph_sel = atlas[idx]                       # [rows, cols, ch, cw]
            tiles = glyph_sel * bright[:, :, None, None]
            mask = tiles.transpose(0, 2, 1, 3).reshape(rows * chh, cols_eff * cw)

            canvas = np.empty((H, W, 3), dtype=np.float32)
            canvas[:] = bg
            if col is not None:
                block = mask[:, :, None] * col[None, None, :]
            else:
                cellcol = rgb_s[i]                       # [rows, cols, 3]
                colored = glyph_sel[:, :, :, :, None] * (bright[:, :, None, None, None]) \
                    * cellcol[:, :, None, None, :]
                block = colored.transpose(0, 2, 1, 3, 4).reshape(rows * chh, cols_eff * cw, 3)
            # alpha-composite glyphs over the background
            mh, mw = block.shape[0], block.shape[1]
            region = canvas[oy:oy + mh, ox:ox + mw]
            a = mask[:, :, None] if col is not None else np.clip(block.sum(-1, keepdims=True), 0, 1)
            canvas[oy:oy + mh, ox:ox + mw] = region * (1 - a) + block
            out[i] = np.clip(canvas, 0, 1)

        return (torch.from_numpy(out).to(imgs.device),)

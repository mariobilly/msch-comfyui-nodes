"""
HUD Overlay node for ComfyUI.

Draws an animated technical "HUD" layer over an image sequence: X crosshair
markers, thin colored bars/scanlines, corner brackets and small glitch text —
the @thesystms HUD look. Per-frame jitter + flicker makes it feel live.

Input/Output: IMAGE ([N, H, W, C] float32 0..1).
"""

import random
import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont


_HUD_COLORS = {
    "rgb_glitch": [(255, 40, 40), (40, 120, 255), (40, 255, 120),
                   (255, 40, 220), (255, 255, 255)],
    "red":        [(255, 40, 40), (200, 0, 0), (255, 120, 120)],
    "green":      [(40, 255, 120), (0, 200, 60), (160, 255, 200)],
    "mono":       [(235, 235, 235), (180, 180, 180), (120, 120, 120)],
}


def _font(size):
    for name in ("consola.ttf", "cour.ttf", "arial.ttf", "DejaVuSansMono.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_x(draw, cx, cy, r, color, width):
    draw.line([(cx - r, cy - r), (cx + r, cy + r)], fill=color, width=width)
    draw.line([(cx - r, cy + r), (cx + r, cy - r)], fill=color, width=width)


class HUDOverlay:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "color_scheme": (["rgb_glitch", "red", "green", "mono"], {"default": "rgb_glitch"}),
                "opacity": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 1.0, "step": 0.05}),
                "crosshair_count": ("INT", {"default": 6, "min": 0, "max": 60}),
                "bar_count": ("INT", {"default": 8, "min": 0, "max": 80}),
                "corner_brackets": ("BOOLEAN", {"default": True}),
                "scanlines": ("BOOLEAN", {"default": False}),
                "glitch_text": ("BOOLEAN", {"default": True}),
                "text": ("STRING", {"default": "REC ● SYS//TIMESLICE", "multiline": False}),
                "jitter": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05}),
                "flicker": ("FLOAT", {"default": 0.25, "min": 0.0, "max": 1.0, "step": 0.05}),
                "line_width": ("INT", {"default": 2, "min": 1, "max": 8}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xFFFFFFFF}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "render"
    CATEGORY = "WarpWiggle"

    def render(self, images, color_scheme, opacity, crosshair_count, bar_count,
               corner_brackets, scanlines, glitch_text, text, jitter, flicker,
               line_width, seed):

        imgs = images.float().clamp(0, 1)
        N, H, W, C = imgs.shape
        colors = _HUD_COLORS.get(color_scheme, _HUD_COLORS["rgb_glitch"])
        base_rng = random.Random(seed)

        # stable base layout (positions jitter per-frame around these)
        cross = [(base_rng.random(), base_rng.random(),
                  base_rng.choice(colors),
                  base_rng.randint(int(min(H, W) * 0.02), int(min(H, W) * 0.06)))
                 for _ in range(crosshair_count)]
        bars = [(base_rng.random(), base_rng.random() * 0.4 + 0.1,
                 base_rng.choice(colors), base_rng.random())
                for _ in range(bar_count)]

        jit_px = jitter * min(H, W) * 0.02
        font_s = max(10, int(H * 0.022))
        font = _font(font_s)
        sfont = _font(max(9, int(H * 0.016)))

        out = torch.empty_like(imgs)
        for f in range(N):
            arr = (imgs[f].cpu().numpy() * 255.0).round().astype(np.uint8)
            mode = "RGBA" if C == 4 else "RGB"
            if C == 1:
                arr = np.repeat(arr, 3, axis=2)
                mode = "RGB"
            pim = Image.fromarray(arr[..., :3] if C >= 3 else arr, "RGB").convert("RGBA")
            layer = Image.new("RGBA", pim.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            frng = random.Random(seed * 131 + f)

            def jx():
                return (frng.random() * 2 - 1) * jit_px

            a = int(255 * opacity)

            # crosshairs
            for (px, py, col, r) in cross:
                if frng.random() < flicker:
                    continue
                cx = int(px * W + jx())
                cy = int(py * H + jx())
                _draw_x(d, cx, cy, r, col + (a,), line_width)

            # bars / scanlines
            for (py, ww, col, xoff) in bars:
                if frng.random() < flicker:
                    continue
                y = int(py * H + jx())
                x0 = int(xoff * W * 0.5)
                x1 = int(min(W, x0 + ww * W))
                d.rectangle([x0, y, x1, y + max(1, line_width)], fill=col + (a,))

            if scanlines:
                for y in range(0, H, 3):
                    d.line([(0, y), (W, y)], fill=(0, 0, 0, int(40 * opacity)), width=1)

            # corner brackets
            if corner_brackets:
                m = int(min(H, W) * 0.05)
                pad = int(min(H, W) * 0.04)
                col = colors[0] + (a,)
                for (ox, oy, sx, sy) in [(pad, pad, 1, 1), (W - pad, pad, -1, 1),
                                          (pad, H - pad, 1, -1), (W - pad, H - pad, -1, -1)]:
                    d.line([(ox, oy), (ox + sx * m, oy)], fill=col, width=line_width)
                    d.line([(ox, oy), (ox, oy + sy * m)], fill=col, width=line_width)

            # glitch text
            if glitch_text:
                tx = int(min(H, W) * 0.04 + jx())
                ty = int(min(H, W) * 0.035 + jx())
                d.text((tx, ty), text, font=font, fill=colors[0] + (a,))
                tc = frng.choice(["0x%04X" % frng.randint(0, 0xFFFF),
                                  "%02d:%02d:%02d" % (frng.randint(0, 23), frng.randint(0, 59), f % 60),
                                  "FRM %04d" % f, "ISO%d" % frng.choice([200, 400, 800])])
                d.text((tx, ty + font_s + 4), tc, font=sfont, fill=colors[-1] + (a,))

            comp = Image.alpha_composite(pim, layer).convert("RGB")
            t = torch.from_numpy(np.asarray(comp).astype(np.float32) / 255.0)
            if C == 4:
                alpha = imgs[f, ..., 3:4]
                t = torch.cat([t, alpha.cpu()], dim=-1)
            out[f] = t.to(imgs.device)

        return (out,)

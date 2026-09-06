"""LyricSyncMosaic node — rebuild a video as a scrolling grid of Arabic letters
with flickering colour cells, lyric-synced word boxes, and the subject rendered
as a fine grayscale figure on top."""

import json

from .mosaic import render_mosaic_batch, DEFAULT_PALETTE


class LyricSyncMosaic:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "timing": ("LYRIC_TIMING",),
                "frame_rate": ("FLOAT", {"default": 25.0, "min": 1.0, "max": 240.0, "step": 0.001}),
                # --- letter grid (background) ---
                "cols": ("INT", {"default": 56, "min": 10, "max": 220,
                                 "tooltip": "Letter cells across the frame (higher = finer/denser)."}),
                "font_path": ("STRING", {"default": r"C:\Windows\Fonts\tahoma.ttf"}),
                "letter_scale": ("FLOAT", {"default": 0.72, "min": 0.3, "max": 1.0, "step": 0.02}),
                "scroll_dir": (["down", "up", "left", "right", "none"], {"default": "down"}),
                "scroll_speed": ("FLOAT", {"default": 0.12, "min": 0.0, "max": 1.0, "step": 0.01,
                                "tooltip": "Cells per frame the grid drifts."}),
                "color_density": ("FLOAT", {"default": 0.13, "min": 0.0, "max": 0.6, "step": 0.01,
                                "tooltip": "Fraction of letter cells that light up with colour."}),
                "flicker_period": ("INT", {"default": 4, "min": 1, "max": 60,
                                "tooltip": "Frames between colour-cell flicker changes (lower = faster)."}),
                # --- lyric-synced word boxes ---
                "wordbox_density": ("FLOAT", {"default": 0.6, "min": 0.0, "max": 1.0, "step": 0.05,
                                "tooltip": "How many of the current line's word boxes show at once."}),
                "wordbox_scale": ("FLOAT", {"default": 2.3, "min": 1.0, "max": 5.0, "step": 0.1,
                                "tooltip": "Word-box height relative to a letter cell."}),
                # --- subject masking ---
                "bg_key": ("BOOLEAN", {"default": True,
                                "tooltip": "Key out the backdrop to find the subject (best for plain backgrounds)."}),
                "bg_tol": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.02,
                                "tooltip": "0 = auto. Lower keeps more of the frame as subject."}),
                "threshold_bias": ("FLOAT", {"default": 0.0, "min": -0.4, "max": 0.4, "step": 0.02}),
                "invert_subject": ("BOOLEAN", {"default": False}),
                # --- subject look ---
                "fg_detail": ("FLOAT", {"default": 3.0, "min": 1.0, "max": 6.0, "step": 0.5}),
                "posterize": ("INT", {"default": 7, "min": 2, "max": 32}),
                "subject_max": ("FLOAT", {"default": 0.95, "min": 0.2, "max": 1.0, "step": 0.02}),
                "subject_gamma": ("FLOAT", {"default": 0.6, "min": 0.3, "max": 3.0, "step": 0.05,
                                "tooltip": "<1 brightens a dark subject; >1 darkens."}),
                "fg_gap": ("INT", {"default": 0, "min": 0, "max": 4}),
                # --- misc ---
                "text_color": ("STRING", {"default": "#15151E"}),
                "seed": ("INT", {"default": 7, "min": 0, "max": 99999}),
            },
            "optional": {
                "palette_in": ("PALETTE", {"tooltip": "Connect a 🎨 Lyric Sync — Palette node (overrides the text below)."}),
                "palette": ("STRING", {"default": ",".join(DEFAULT_PALETTE),
                                       "tooltip": "Comma-separated hex colours (used if no Palette node connected)."}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "mosaic"
    CATEGORY = "LyricSync"

    def mosaic(self, images, timing, frame_rate, cols, font_path, letter_scale,
               scroll_dir, scroll_speed, color_density, flicker_period,
               wordbox_density, wordbox_scale, bg_key, bg_tol, threshold_bias,
               invert_subject, fg_detail, posterize, subject_max, subject_gamma,
               fg_gap, text_color, seed, palette="", palette_in=None):
        if isinstance(timing, str):
            try:
                timing = json.loads(timing)
            except Exception:
                timing = []
        # A connected Palette node wins; otherwise parse the comma-separated text.
        if palette_in:
            pal = [str(c).strip() for c in palette_in if str(c).strip()] or None
        else:
            pal = [c.strip() for c in (palette or "").split(",") if c.strip()] or None

        style = {
            "cols": int(cols), "font_path": font_path, "letter_scale": float(letter_scale),
            "scroll_dir": scroll_dir, "scroll_speed": float(scroll_speed),
            "color_density": float(color_density), "flicker_period": int(flicker_period),
            "wordbox_density": float(wordbox_density), "wordbox_scale": float(wordbox_scale),
            "bg_key": bool(bg_key), "bg_tol": float(bg_tol),
            "threshold_bias": float(threshold_bias), "invert_subject": bool(invert_subject),
            "auto_threshold": True, "auto_contrast": True, "threshold": 0.5,
            "fg_detail": float(fg_detail), "posterize": int(posterize),
            "subject_max": float(subject_max), "subject_gamma": float(subject_gamma),
            "fg_gap": int(fg_gap), "text_color": text_color,
            "subject_color": "#101018", "palette": pal, "seed": int(seed),
        }
        out = render_mosaic_batch(images, timing, float(frame_rate), style)
        return (out,)

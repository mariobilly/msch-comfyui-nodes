"""LyricSyncOverlay node — draw timed lyrics onto an IMAGE batch."""

import json

from .renderer import render_batch


class LyricSyncOverlay:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "timing": ("LYRIC_TIMING",),
                "frame_rate": ("FLOAT", {"default": 30.0, "min": 1.0, "max": 240.0, "step": 0.001}),
                "bilingual": ("BOOLEAN", {"default": True}),
                "position": (["bottom", "center", "top"], {"default": "bottom"}),
                "font_path": ("STRING", {"default": r"C:\Windows\Fonts\segoeui.ttf"}),
                "font_size": ("INT", {"default": 0, "min": 0, "max": 400,
                                       "tooltip": "0 = auto from frame width"}),
                "text_color": ("STRING", {"default": "#FFFFFF"}),
                "box_color": ("STRING", {"default": "#000000"}),
                "box_opacity": ("FLOAT", {"default": 0.6, "min": 0.0, "max": 1.0, "step": 0.05}),
                "corner_radius": ("INT", {"default": 18, "min": 0, "max": 200}),
                "padding": ("INT", {"default": 24, "min": 0, "max": 200}),
                "y_offset": ("INT", {"default": 0, "min": -2000, "max": 2000}),
                "max_width_pct": ("FLOAT", {"default": 0.8, "min": 0.2, "max": 1.0, "step": 0.05}),
                "fade_ms": ("INT", {"default": 150, "min": 0, "max": 2000}),
                "hold_ms": ("INT", {"default": 0, "min": 0, "max": 3000,
                                     "tooltip": "Keep each line on screen this long past its end."}),
                "highlight_words": ("BOOLEAN", {"default": False}),
                "highlight_color": ("STRING", {"default": "#FFDC50"}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("images",)
    FUNCTION = "overlay"
    CATEGORY = "LyricSync"

    def overlay(self, images, timing, frame_rate, bilingual, position, font_path,
                font_size, text_color, box_color, box_opacity, corner_radius,
                padding, y_offset, max_width_pct, fade_ms, hold_ms,
                highlight_words, highlight_color):
        # Accept timing as a list or a JSON string (so it can be wired from a
        # STRING node too).
        if isinstance(timing, str):
            try:
                timing = json.loads(timing)
            except Exception:
                timing = []

        style = {
            "bilingual": bilingual,
            "position": position,
            "font_path": font_path,
            "font_size": int(font_size),
            "text_color": text_color,
            "box_color": box_color,
            "box_opacity": float(box_opacity),
            "corner_radius": int(corner_radius),
            "padding": int(padding),
            "y_offset": int(y_offset),
            "max_width_pct": float(max_width_pct),
            "fade_ms": int(fade_ms),
            "hold": hold_ms / 1000.0,
            "highlight_words": highlight_words,
            "highlight_color": highlight_color,
        }

        out = render_batch(images, timing, float(frame_rate), style)
        return (out,)

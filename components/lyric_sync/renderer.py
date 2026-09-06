"""
Lyric Sync — frame renderer.

Draws timed lyric lines onto a ComfyUI IMAGE batch (torch Tensor [B,H,W,C],
float 0-1). One semi-transparent rounded box per active line, centered text,
optional bilingual stack (original above translation), fade in/out, and optional
karaoke word highlight using per-word timings.

Arabic is shaped (arabic_reshaper) and reordered (python-bidi) before drawing so
glyphs connect and run right-to-left. Both libs are optional — without them, text
still draws (just not correctly shaped for Arabic).
"""

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _HAS_ARABIC = True
except Exception:  # pragma: no cover - optional dependency
    _HAS_ARABIC = False


def _has_arabic(text):
    return any("؀" <= ch <= "ۿ" or "ݐ" <= ch <= "ݿ" for ch in text)


def shape_text(text):
    """Reshape + reorder bidirectional text for correct RTL Arabic rendering."""
    if _HAS_ARABIC and _has_arabic(text):
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            return text
    return text


def _parse_color(c, default=(255, 255, 255)):
    """Accept '#RRGGBB', 'r,g,b', or a tuple. Returns an (r,g,b) tuple."""
    if isinstance(c, (tuple, list)):
        return tuple(int(x) for x in c[:3])
    c = str(c).strip()
    if c.startswith("#") and len(c) >= 7:
        return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
    if "," in c:
        parts = [int(float(p)) for p in c.split(",")[:3]]
        if len(parts) == 3:
            return tuple(parts)
    return default


def _load_font(font_path, size):
    try:
        return ImageFont.truetype(font_path, size)
    except Exception:
        # Try a couple of known Arabic-capable Windows fonts, then PIL default.
        for fallback in (r"C:\Windows\Fonts\segoeui.ttf",
                         r"C:\Windows\Fonts\tahoma.ttf",
                         r"C:\Windows\Fonts\arial.ttf"):
            try:
                return ImageFont.truetype(fallback, size)
            except Exception:
                continue
        return ImageFont.load_default()


def _text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1], bbox[1]  # w, h, top_offset


def _wrap(draw, text, font, max_w):
    """Greedy word-wrap to fit max_w. Returns a list of lines (RTL-safe: we wrap
    the raw text, then shape each resulting line)."""
    words = text.split()
    if not words:
        return [text]
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = cur + " " + w
        tw, _, _ = _text_size(draw, trial, font)
        if tw <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


class LyricRenderer:
    """Holds style + a small overlay cache keyed by active-line index.

    The overlay for a given line (box + text, pre-fade) is identical across every
    frame it spans, so we render it once and just re-alpha-composite per frame.
    """

    def __init__(self, width, height, style):
        self.W = width
        self.H = height
        self.s = style
        self._cache = {}  # key -> (RGBA overlay Image, base_alpha array)

    def _make_overlay(self, line, highlight_word_idx):
        s = self.s
        W, H = self.W, self.H
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        size = s["font_size"] if s["font_size"] > 0 else max(14, int(W * 0.045))
        font = _load_font(s["font_path"], size)

        max_w = int(W * s["max_width_pct"])
        text_color = _parse_color(s["text_color"], (255, 255, 255))
        hi_color = _parse_color(s["highlight_color"], (255, 220, 80))
        box_color = _parse_color(s["box_color"], (0, 0, 0))
        box_a = int(max(0.0, min(1.0, s["box_opacity"])) * 255)
        pad = s["padding"]
        gap = max(2, int(size * 0.2))

        # Build the visual rows: original (always) + translation (if bilingual).
        rows = []  # each: (raw_text, font, color_default, words_for_highlight)
        rows.append((line["text"], font, text_color, line.get("words") or []))
        if s["bilingual"] and line.get("translation"):
            tsize = max(12, int(size * 0.7))
            tfont = _load_font(s["font_path"], tsize)
            rows.append((line["translation"], tfont, text_color, []))

        # Wrap + shape each row into display sublines, measure block size.
        rendered = []  # (subline_text, font, color, width, height, top)
        block_h = 0
        block_w = 0
        for raw, rfont, rcolor, _words in rows:
            for sub in _wrap(draw, raw, rfont, max_w):
                disp = shape_text(sub)
                tw, th, top = _text_size(draw, disp, rfont)
                rendered.append((disp, rfont, rcolor, tw, th, top))
                block_h += th + gap
                block_w = max(block_w, tw)
        block_h -= gap

        # Box geometry.
        box_w = min(W - 2 * pad, block_w + 2 * pad)
        box_h = block_h + 2 * pad
        box_x = (W - box_w) // 2

        pos = s["position"]
        if pos == "top":
            box_y = int(H * 0.07) + s["y_offset"]
        elif pos == "center":
            box_y = (H - box_h) // 2 + s["y_offset"]
        else:  # bottom
            box_y = H - box_h - int(H * 0.07) + s["y_offset"]

        if box_a > 0:
            radius = s["corner_radius"]
            draw.rounded_rectangle(
                [box_x, box_y, box_x + box_w, box_y + box_h],
                radius=radius, fill=(box_color[0], box_color[1], box_color[2], box_a),
            )

        # Draw each subline centered.
        y = box_y + pad
        for disp, rfont, rcolor, tw, th, top in rendered:
            x = (W - tw) // 2
            draw.text((x, y - top), disp, font=rfont, fill=(rcolor[0], rcolor[1], rcolor[2], 255))
            y += th + gap

        # Karaoke highlight: redraw the current word in highlight color over the
        # first row only (original lyric). We draw the whole first subline again
        # split by the active word for a simple, robust sweep.
        if s["highlight_words"] and highlight_word_idx is not None and rendered:
            self._draw_highlight(draw, line, rendered[0], hi_color, highlight_word_idx, W, box_y + pad)

        return overlay

    def _draw_highlight(self, draw, line, first_row, hi_color, word_idx, W, y_top):
        disp, rfont, rcolor, tw, th, top = first_row
        words = line.get("words") or []
        if word_idx >= len(words):
            return
        # Re-render the first subline word-by-word so we can color one word.
        # We rebuild from the original (unwrapped) text words to map indices.
        raw_words = line["text"].split()
        if word_idx >= len(raw_words):
            return
        full = shape_text(line["text"])
        full_w, _, _ = _text_size(draw, full, rfont)
        # If the line wrapped, this simple highlight may be approximate; acceptable.
        x = (W - full_w) // 2
        cursor = x
        for wi, w in enumerate(raw_words):
            piece = shape_text(w + (" " if wi < len(raw_words) - 1 else ""))
            pw, _, ptop = _text_size(draw, piece, rfont)
            if wi == word_idx:
                draw.text((cursor, y_top - top), piece, font=rfont,
                          fill=(hi_color[0], hi_color[1], hi_color[2], 255))
            cursor += pw

    def render_frame(self, frame_np, t):
        """Composite all lines active at time t onto frame_np (H,W,3 float 0-1)."""
        active = [ln for ln in self.lines if ln["start"] <= t <= ln["end"] + self.s["hold"]]
        if not active:
            return frame_np

        base = Image.fromarray((np.clip(frame_np, 0, 1) * 255).astype(np.uint8), "RGB").convert("RGBA")
        for ln in active:
            alpha = self._fade_alpha(ln, t)
            if alpha <= 0:
                continue
            hw = self._active_word(ln, t) if self.s["highlight_words"] else None
            key = (ln["idx"], hw)
            overlay = self._cache.get(key)
            if overlay is None:
                overlay = self._make_overlay(ln, hw)
                self._cache[key] = overlay
            if alpha < 1.0:
                faded = overlay.copy()
                a = faded.getchannel("A").point(lambda p: int(p * alpha))
                faded.putalpha(a)
                base = Image.alpha_composite(base, faded)
            else:
                base = Image.alpha_composite(base, overlay)

        out = np.asarray(base.convert("RGB")).astype(np.float32) / 255.0
        return out

    def _fade_alpha(self, line, t):
        fade = self.s["fade_ms"] / 1000.0
        if fade <= 0:
            return 1.0
        start, end = line["start"], line["end"] + self.s["hold"]
        if t < start or t > end:
            return 0.0
        a_in = (t - start) / fade if t - start < fade else 1.0
        a_out = (end - t) / fade if end - t < fade else 1.0
        return max(0.0, min(1.0, min(a_in, a_out)))

    def _active_word(self, line, t):
        for i, w in enumerate(line.get("words") or []):
            if w["start"] <= t <= w["end"]:
                return i
        return None

    def attach(self, lines):
        self.lines = lines
        return self


def render_batch(images, timing, frame_rate, style):
    """images: torch Tensor [B,H,W,C] float 0-1. Returns a new tensor, same shape."""
    if not timing:
        return images

    arr = images.detach().cpu().numpy()
    B, H, W, C = arr.shape
    renderer = LyricRenderer(W, H, style).attach(timing)

    out = np.empty_like(arr)
    for i in range(B):
        t = i / max(1e-6, frame_rate)
        out[i] = renderer.render_frame(arr[i], t)

    return torch.from_numpy(out).to(images.device).to(images.dtype)

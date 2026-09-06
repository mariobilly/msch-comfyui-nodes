"""
Lyric Sync — TEXT-MOSAIC renderer (the real effect).

Rebuilds each video frame as a grid of colored tiles. Background tiles are filled
with a vibrant palette colour + an Arabic lyric word; the video subject (dark
pixels) is rendered as darker tiles so the figure "emerges" out of a sea of
lyric words. The words shown follow the song's current lyric line (sync).

This matches the reference look: whole-screen word grid, dancer made of tiles.
"""

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _HAS_ARABIC = True
except Exception:  # pragma: no cover
    _HAS_ARABIC = False

import re

# Vibrant Y2K-ish palette sampled from the reference clip.
DEFAULT_PALETTE = [
    "#FFFFFF", "#FFFFFF",            # white (weighted)
    "#7DEFA1", "#5FE39A",           # mint greens
    "#F25CC1", "#FF74B8",           # magenta / pink
    "#63D6F0",                      # cyan
    "#9B5DE5", "#B388F0",           # purple / lavender
    "#F5B8D6",                      # light pink
]

_AR_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _shape(text):
    if _HAS_ARABIC and any("؀" <= ch <= "ۿ" for ch in text):
        try:
            return get_display(arabic_reshaper.reshape(text))
        except Exception:
            return text
    return text


def _hex(c):
    c = c.lstrip("#")
    return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))


def _font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        for fb in (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\tahoma.ttf",
                   r"C:\Windows\Fonts\arial.ttf"):
            try:
                return ImageFont.truetype(fb, size)
            except Exception:
                continue
        return ImageFont.load_default()


def _all_words(timing):
    words = []
    for ln in timing or []:
        words += _AR_WORD.findall(ln.get("text", ""))
        if ln.get("translation"):
            words += _AR_WORD.findall(ln["translation"])
    return words or ["LYRIC"]


def _active_words(timing, t):
    cur = []
    for ln in timing or []:
        if ln["start"] <= t <= ln["end"] + 0.4:
            cur += _AR_WORD.findall(ln.get("text", ""))
            if ln.get("translation"):
                cur += _AR_WORD.findall(ln["translation"])
    return cur


class MosaicRenderer:
    def __init__(self, W, H, style):
        self.W, self.H, self.s = W, H, style
        self.cols = max(6, int(style["cols"]))
        self.cell = W / self.cols
        self.rows = max(1, int(round(H / self.cell)))
        self.palette = [_hex(c) for c in (style.get("palette") or DEFAULT_PALETTE)]
        self.text_color = _hex(style.get("text_color", "#15151E"))
        self.fg_dark = _hex(style.get("subject_color", "#101018"))
        # Pre-pick a stable palette colour per cell (no per-frame flicker).
        self._font_cache = {}
        self._glyphs = {}
        self.letters = list("ابتثجحخدذرزسشصضطظعغفقكلمنهوي")

    def font(self, size):
        size = max(7, int(size))
        if size not in self._font_cache:
            self._font_cache[size] = _font(self.s["font_path"], size)
        return self._font_cache[size]

    def _downsample(self, arr):
        """Block-average colour + luma to rows x cols, with optional auto-contrast."""
        img = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), "RGB")
        small = img.resize((self.cols, self.rows), Image.BILINEAR)
        s = np.asarray(small).astype(np.float32) / 255.0
        luma = 0.299 * s[..., 0] + 0.587 * s[..., 1] + 0.114 * s[..., 2]
        if self.s.get("auto_contrast", True):
            # Stretch the 2nd..98th percentile to [0,1] so any clip separates.
            lo, hi = np.percentile(luma, 2), np.percentile(luma, 98)
            if hi - lo > 1e-3:
                luma = np.clip((luma - lo) / (hi - lo), 0.0, 1.0)
        return s, luma

    @staticmethod
    def _otsu(luma):
        """Otsu threshold on a 0..1 luma grid -> float cutoff."""
        hist, edges = np.histogram(luma.ravel(), bins=64, range=(0.0, 1.0))
        hist = hist.astype(np.float64)
        total = hist.sum()
        if total == 0:
            return 0.5
        p = hist / total
        omega = np.cumsum(p)
        centers = (edges[:-1] + edges[1:]) / 2
        mu = np.cumsum(p * centers)
        mu_t = mu[-1]
        denom = omega * (1 - omega)
        denom[denom == 0] = 1e-12
        sigma_b = (mu_t * omega - mu) ** 2 / denom
        return float(centers[np.argmax(sigma_b)])

    def _foreground_mask(self, arr):
        """Full-res boolean mask of the subject.

        Default: background-colour keying — estimate the backdrop colour from the
        frame border and mark pixels that differ from it as foreground. This keeps
        the WHOLE person (dark clothing AND bright skin) as subject, which a plain
        luma threshold cannot. Falls back to a luma split if bg_key is off.
        """
        H, W, _ = arr.shape
        if self.s.get("bg_key", True):
            b = max(2, H // 36)
            border = np.concatenate([
                arr[:b].reshape(-1, 3), arr[-b:].reshape(-1, 3),
                arr[:, :b].reshape(-1, 3), arr[:, -b:].reshape(-1, 3)])
            bg = np.median(border, axis=0)
            dist = np.sqrt(((arr - bg) ** 2).sum(axis=2))
            d = dist / (dist.max() + 1e-6)
            tol = self.s.get("bg_tol", 0.0)
            if tol <= 0:
                tol = max(0.05, self._otsu(d) + self.s.get("threshold_bias", 0.0))
            fg = d > tol
        else:
            luma = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
            thr = (self._otsu(luma) + self.s.get("threshold_bias", 0.0)
                   if self.s.get("auto_threshold", True) else self.s["threshold"])
            fg = luma < thr
        if self.s["invert_subject"]:
            fg = ~fg
        return fg

    # ---- letters & cheap hashing -------------------------------------------
    @staticmethod
    def _h(*vals):
        """Deterministic pseudo-random float in [0,1) with good avalanche so
        adjacent cells get independent values."""
        h = 0x811C9DC5
        for v in vals:
            h = (h ^ (int(v) & 0xFFFFFFFF)) & 0xFFFFFFFF
            h = (h * 0x01000193) & 0xFFFFFFFF
            h ^= h >> 15
            h = (h * 0x2545F491) & 0xFFFFFFFF
            h ^= h >> 13
        return (h & 0xFFFFFF) / float(0x1000000)

    def set_letters(self, timing):
        """Build the background letter pool from the SONG'S OWN LYRICS.

        Keeps every letter occurrence (so frequent letters appear more often in
        the grid, like the real song's texture). Falls back to a generic Arabic
        alphabet only if there are no lyrics yet.
        """
        base = "ابتثجحخدذرزسشصضطظعغفقكلمنهوي"
        # Use the ORIGINAL sung lyrics only (not the translation) so the grid stays
        # in the song's own language/script, like the reference.
        text = " ".join(ln.get("text", "") for ln in (timing or []))
        chars = [c for c in text if c.isalpha()]   # with repeats -> frequency weighting
        self.letters = chars if len(set(chars)) >= 3 else list(base)

    def _glyph(self, ch, w, h, color):
        key = (ch, w, h, color)
        g = self._glyphs.get(key)
        if g is None:
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            size = max(7, int(min(w, h) * self.s.get("letter_scale", 0.72)))
            f = self.font(size)
            disp = _shape(ch)
            tl = d.textlength(disp, font=f)
            bb = d.textbbox((0, 0), disp, font=f)
            d.text(((w - tl) / 2, (h - (bb[3] - bb[1])) / 2 - bb[1]),
                   disp, font=f, fill=color + (255,))
            g = img
            self._glyphs[key] = g
        return g

    # ---- background: scrolling letter grid + flickering colour cells --------
    def _draw_letter_grid(self, canvas, frame_idx):
        W, H = self.W, self.H
        cw = max(1, int(round(self.cell)))
        ch = max(1, int(round(H / self.rows)))
        n = len(self.letters)

        # scroll offset (px). dir picks the axis/sign; speed is cells/frame.
        spd = self.s.get("scroll_speed", 0.12)
        d = self.s.get("scroll_dir", "down")
        dx = (cw * spd) if d == "right" else (-cw * spd) if d == "left" else 0.0
        dy = (ch * spd) if d == "down" else (-ch * spd) if d == "up" else 0.0
        ox, oy = dx * frame_idx, dy * frame_idx
        shift_c = int(np.floor(ox / cw)); fracx = ox - shift_c * cw
        shift_r = int(np.floor(oy / ch)); fracy = oy - shift_r * ch

        tbucket = frame_idx // max(1, int(self.s.get("flicker_period", 4)))
        dens = self.s.get("color_density", 0.12)
        text_dark = self.text_color
        draw = ImageDraw.Draw(canvas)

        for sr in range(-1, self.rows + 1):
            y0 = int(sr * ch + fracy)
            cr = sr - shift_r
            for sc in range(-1, self.cols + 1):
                x0 = int(sc * cw + fracx)
                cc = sc - shift_c
                # flicker: a fraction of cells light up with a palette colour
                on = self._h(cr, cc, tbucket, 1) < dens
                if on:
                    pcol = self.palette[int(self._h(cr, cc, 5) * len(self.palette)) % len(self.palette)]
                    draw.rectangle([x0, y0, x0 + cw - 1, y0 + ch - 1], fill=pcol)
                    lcol = text_dark
                else:
                    draw.rectangle([x0, y0, x0 + cw - 1, y0 + ch - 1], fill=(255, 255, 255))
                    lcol = text_dark
                ch_letter = self.letters[int(self._h(cr, cc) * n) % n]
                canvas.paste(self._glyph(ch_letter, cw, ch, lcol),
                             (x0, y0), self._glyph(ch_letter, cw, ch, lcol))

    # ---- synced full-word boxes (switch on while the word is sung) ----------
    def _draw_word_boxes(self, canvas, t, timing):
        if not timing:
            return
        W, H = self.W, self.H
        draw = ImageDraw.Draw(canvas)
        ch = max(1, int(round(H / self.rows)))
        bh = int(ch * self.s.get("wordbox_scale", 2.3))
        fsize = int(bh * 0.66)
        font = self.font(fsize)
        pad = int(bh * 0.30)
        for li, ln in enumerate(timing):
            if not (ln["start"] <= t <= ln["end"] + 0.25):
                continue
            words = _AR_WORD.findall(ln.get("text", ""))
            words += _AR_WORD.findall(ln.get("translation", ""))
            for k, w in enumerate(words):
                seed = li * 131 + k
                # only some words show at once -> they pop on/off across the line
                if self._h(seed, int(t * 4)) > self.s.get("wordbox_density", 0.7):
                    continue
                disp = _shape(w)
                tl = draw.textlength(disp, font=font)
                bw = int(tl + 2 * pad)
                x = int(self._h(seed, 7) * max(1, W - bw))
                y = int(self._h(seed, 9) * max(1, H - bh))
                pcol = self.palette[int(self._h(seed, 3) * len(self.palette)) % len(self.palette)]
                draw.rectangle([x, y, x + bw, y + bh], fill=pcol)
                bb = draw.textbbox((0, 0), disp, font=font)
                draw.text((x + pad, y + (bh - (bb[3] - bb[1])) / 2 - bb[1]),
                          disp, font=font, fill=self.text_color)

    def render(self, arr, frame_idx, t, timing):
        W, H = self.W, self.H
        canvas = Image.new("RGB", (W, H), (221, 221, 221))  # light grey -> grid lines
        draw = ImageDraw.Draw(canvas)

        # Layer 1 — background: scrolling letter grid + flickering colour cells.
        self._draw_letter_grid(canvas, frame_idx)
        # Layer 2 — synced full-word boxes (on while their word is sung).
        self._draw_word_boxes(canvas, t, timing)

        # Layer 3 — foreground: the subject as a FINE grayscale mosaic, composited
        # only where the mask says "subject". This is what gives the detailed
        # dancer-made-of-pixels look over the coarser word grid.
        fg = self._foreground_mask(arr)
        detail = max(1.0, self.s.get("fg_detail", 2.6))
        fcols = max(self.cols, int(self.cols * detail))
        frows = max(self.rows, int(self.rows * detail))

        arr8 = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
        small = np.asarray(Image.fromarray(arr8).resize((fcols, frows), Image.BILINEAR)).astype(np.float32) / 255.0
        gray = 0.299 * small[..., 0] + 0.587 * small[..., 1] + 0.114 * small[..., 2]
        # stretch the subject's tones to full range, then posterise for the dither look
        cover = np.asarray(Image.fromarray((fg * 255).astype(np.uint8)).resize((fcols, frows), Image.BILINEAR)).astype(np.float32) / 255.0
        sub = gray[cover > 0.5]
        if sub.size:
            lo, hi = np.percentile(sub, 3), np.percentile(sub, 97)
            if hi - lo > 1e-3:
                gray = np.clip((gray - lo) / (hi - lo), 0.0, 1.0)
        gamma = self.s.get("subject_gamma", 1.0)
        if gamma and gamma != 1.0:
            gray = np.power(np.clip(gray, 0, 1), gamma)
        levels = max(2, int(self.s.get("posterize", 7)))
        gray = np.round(gray * (levels - 1)) / (levels - 1)
        gray = gray * self.s.get("subject_max", 0.9)   # cap brightness if desired

        fcw, fch = W / fcols, H / frows
        fgap = self.s.get("fg_gap", 0)
        fdraw = draw
        for r in range(frows):
            y0 = int(r * fch)
            y1 = int((r + 1) * fch)
            for c in range(fcols):
                if cover[r, c] <= 0.5:
                    continue
                x0 = int(c * fcw)
                x1 = int((c + 1) * fcw)
                v = int(gray[r, c] * 255)
                fdraw.rectangle([x0, y0, x1 - fgap, y1 - fgap], fill=(v, v, v))

        return np.asarray(canvas).astype(np.float32) / 255.0


def render_mosaic_batch(images, timing, frame_rate, style):
    arr = images.detach().cpu().numpy()
    B, H, W, C = arr.shape
    rnd = MosaicRenderer(W, H, style)
    rnd.set_letters(timing)
    out = np.empty_like(arr)
    for i in range(B):
        t = i / max(1e-6, frame_rate)
        out[i] = rnd.render(arr[i], i, t, timing)
    return torch.from_numpy(out).to(images.device).to(images.dtype)

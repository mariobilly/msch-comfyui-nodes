"""Deterministic motion graphics and streaming MP4 export."""

from __future__ import annotations

import bisect
import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

if __package__:
    from .planning import validate_focus, validate_plan
    from .titles import parse_titles, title_bitmap, composite_titles
else:
    from planning import validate_focus, validate_plan
    from titles import parse_titles, title_bitmap, composite_titles


SCENES = ("hero", "split", "stack", "hero", "triptych", "stack", "split", "hero")
TRANSITIONS = ("whip", "zoom", "diagonal", "shutter", "whip", "impact")


def smooth(value):
    value = max(0.0, min(1.0, value))
    return value * value * (3.0 - 2.0 * value)


def ease_out(value):
    return 1.0 - (1.0 - max(0.0, min(1.0, value))) ** 4


def open_photo(source):
    if isinstance(source, (str, Path)):
        with Image.open(source) as image:
            oriented = ImageOps.exif_transpose(image)
            return open_photo(oriented.convert("RGBA") if "transparency" in image.info or "A" in oriented.getbands() else oriented)
    if source.mode == "RGBA":
        base = Image.new("RGBA", source.size, (18, 18, 20, 255))
        base.alpha_composite(source)
        return base.convert("RGB")
    return source.convert("RGB")


def ffmpeg_executable():
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise RuntimeError(
            "Install marioslideshow/requirements.txt with ComfyUI's Python, or install FFmpeg on PATH."
        ) from exc


@dataclass(frozen=True)
class Settings:
    width: int = 1280
    height: int = 720
    fps: int = 30
    bpm: float = 128.0
    beats_per_image: float = 4.0
    seconds_per_image: float = 2.0
    timing: str = "BPM"
    pacing: str = "Dynamic"
    layout: str = "Art directed mix"
    framing: str = "Smart fit"
    transition: str = "Mixed"
    transition_seconds: float = 0.28
    intensity: float = 0.75
    motion_blur: int = 3
    grain: float = 0.08
    accent: str = "#DFFF40"
    graphics: bool = True
    font_path: str = ""
    seed: int = 0
    show_counter: bool = True
    show_progress: bool = True
    show_headlines: bool = True

    def __post_init__(self):
        if not (64 <= self.width <= 4096 and 64 <= self.height <= 4096):
            raise ValueError("Width and height must be between 64 and 4096.")
        if self.width % 2 or self.height % 2:
            raise ValueError("MP4 export requires even width and height.")
        if not 1 <= self.fps <= 60:
            raise ValueError("FPS must be between 1 and 60.")
        if not 20 <= self.bpm <= 300 or not 1 <= self.beats_per_image <= 16:
            raise ValueError("BPM must be 20-300 and beats per image must be 1-16.")
        if not 0.4 <= self.seconds_per_image <= 30:
            raise ValueError("Seconds per image must be between 0.4 and 30.")
        if not 0 <= self.intensity <= 1 or not 0 <= self.grain <= 1:
            raise ValueError("Intensity and grain must be between 0 and 1.")
        if not 0 <= self.transition_seconds <= 1 or self.motion_blur not in (1, 3, 5):
            raise ValueError("Transition duration must be 0-1 seconds; blur samples must be 1, 3 or 5.")
        if self.timing not in ("BPM", "Seconds") or self.pacing not in ("Dynamic", "Even"):
            raise ValueError("Unknown timing or pacing mode.")
        if self.layout not in ("Art directed mix", "Full frame", "Layered", "Split screen"):
            raise ValueError("Unknown layout mode.")
        if self.framing not in ("Smart fit", "Fill", "Contain"):
            raise ValueError("Unknown framing mode.")
        if self.transition not in ("Mixed", "Whip", "Zoom", "Diagonal", "Shutter", "Impact", "Cut"):
            raise ValueError("Unknown transition mode.")
        ImageColor.getrgb(self.accent)
        if self.font_path and not Path(self.font_path).is_file():
            raise ValueError("The specified font file does not exist.")


class PromoRenderer:
    def __init__(self, images, settings=None, headlines=None, plan=None, focus=None, headline_layers=None):
        self.settings = settings or Settings()
        self.images = images
        if not len(images):
            raise ValueError("Load at least one image.")
        if len(images) > 200:
            raise ValueError("Use at most 200 images per render.")
        self.headlines = list(headlines or [])
        self.plan = validate_plan(plan, len(images)) if plan is not None else None
        self.focus = validate_focus(focus, len(images)) if focus is not None else None
        self.headline_layers = parse_titles(headline_layers)
        self.protected_boxes = {}
        self.shot_count = len(self.plan["shots"]) if self.plan is not None else len(images)
        if self.plan is not None:
            self.headlines = [shot["headline"] for shot in self.plan["shots"]]
        self.accent = ImageColor.getrgb(self.settings.accent)
        self.starts = [0]
        s = self.settings
        base = 60.0 / s.bpm * s.beats_per_image if s.timing == "BPM" else s.seconds_per_image
        elapsed = 0.0
        for i in range(self.shot_count):
            factor = (1.0, 0.5, 1.0, 0.5, 1.0, 0.5, 0.5, 1.0)[i % 8]
            if s.pacing == "Even" or len(images) == 1:
                factor = 1.0
            elapsed += self.plan["shots"][i]["duration"] if self.plan is not None else max(0.4, base * factor)
            self.starts.append(max(self.starts[-1] + 1, round(elapsed * s.fps)))
        self.frame_count = self.starts[-1]
        shortest = min(b - a for a, b in zip(self.starts, self.starts[1:]))
        self.transition_frames = min(round(s.transition_seconds * s.fps), shortest // 3)
        if s.transition == "Cut" and self.plan is None:
            self.transition_frames = 0
        self.font_file = self._find_font(s.font_path)
        # These caches belong to one render, not to the node or to the ComfyUI process.
        self._cover_cached = lru_cache(maxsize=12)(self._cover)
        self._text_cached = lru_cache(maxsize=4)(self._text_layer)
        self._title_cached = lru_cache(maxsize=16)(lambda index: title_bitmap(
            self.headline_layers[index], s.width, s.height, self._font))

    @staticmethod
    def _find_font(requested):
        candidates = [requested] if requested else [
            str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "arialbd.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
        return next((p for p in candidates if Path(p).is_file()), None)

    def _font(self, size):
        return ImageFont.truetype(self.font_file, size) if self.font_file else ImageFont.load_default(size=size)

    def _cover(self, index, width, height, blurred=False):
        image = open_photo(self.images[index % len(self.images)])
        if self.focus is not None and not blurred:
            return self._focused_cover(image, index, width, height)
        fitted = ImageOps.fit(image, (width, height), Image.Resampling.LANCZOS)
        if blurred:
            fitted = ImageEnhance.Color(fitted).enhance(0.35)
            fitted = fitted.filter(ImageFilter.GaussianBlur(max(width, height) * 0.018))
            fitted = ImageEnhance.Brightness(fitted).enhance(0.46)
        elif self.settings.framing == "Contain" or (
            self.settings.framing == "Smart fit" and not 0.72 <= (image.width / image.height) / (width / height) <= 1.38
        ):
            fitted = fitted.filter(ImageFilter.GaussianBlur(max(width, height) * 0.025))
            fitted = ImageEnhance.Brightness(fitted).enhance(0.40)
            foreground = ImageOps.contain(image, (max(1, round(width * 0.86)), max(1, round(height * 0.86))), Image.Resampling.LANCZOS)
            fitted.paste(foreground, ((width - foreground.width) // 2, (height - foreground.height) // 2))
        return fitted

    def _focused_cover(self, image, index, width, height):
        item = self.focus["items"][index % len(self.images)]
        iw, ih = image.size
        scale = max(width / iw, height / ih)
        # Division can round a full-axis crop just beyond the source bounds.
        cw, ch = min(iw, width / scale), min(ih, height / scale)
        box = item.get("box")
        roi = [box[0] * iw, box[1] * ih, box[2] * iw, box[3] * ih] if box else None
        fits = roi is None or (roi[2] - roi[0] <= cw and roi[3] - roi[1] <= ch)
        contain = self.settings.framing == "Contain" or (self.settings.framing == "Smart fit" and (
            not fits or (box is None and not 0.72 <= (iw / ih) / (width / height) <= 1.38)))
        if contain:
            background = ImageOps.fit(image, (width, height), Image.Resampling.LANCZOS)
            background = ImageEnhance.Brightness(background.filter(ImageFilter.GaussianBlur(max(width, height) * 0.025))).enhance(0.4)
            foreground = ImageOps.contain(image, (max(1, round(width * 0.86)), max(1, round(height * 0.86))), Image.Resampling.LANCZOS)
            ox, oy = (width - foreground.width) // 2, (height - foreground.height) // 2
            background.paste(foreground, (ox, oy))
            # Contain also protects the whole foreground throughout the camera motion.
            self.protected_boxes[index, width, height] = [ox / width, oy / height,
                (ox + foreground.width) / width, (oy + foreground.height) / height]
            return background
        left = min(max(0, item["x"] * iw - cw / 2), iw - cw)
        top = min(max(0, item["y"] * ih - ch / 2), ih - ch)
        if roi and fits:
            left = min(max(left, max(0, roi[2] - cw)), min(iw - cw, roi[0]))
            top = min(max(top, max(0, roi[3] - ch)), min(ih - ch, roi[1]))
            self.protected_boxes[index, width, height] = [(roi[0] - left) / cw, (roi[1] - top) / ch,
                                                        (roi[2] - left) / cw, (roi[3] - top) / ch]
        return image.resize((width, height), Image.Resampling.LANCZOS,
                            box=(left, top, min(iw, left + cw), min(ih, top + ch)))

    @staticmethod
    def _camera(image, width, height, zoom=1.0, x=0.0, y=0.0):
        # Inverse affine mapping preserves subpixel movement instead of rounding crops.
        scale = max(width / image.width, height / image.height) * zoom
        a = 1.0 / scale
        affine = (a, 0, image.width * (0.5 + x) - a * width / 2,
                  0, a, image.height * (0.5 + y) - a * height / 2)
        return image.transform((width, height), Image.Transform.AFFINE, affine,
                               resample=Image.Resampling.BICUBIC)

    def _moving_photo(self, index, width, height, phase, variant=0, shot=None):
        source = self._cover_cached(index % len(self.images), width, height)
        intensity = self.settings.intensity
        direction = -1 if (index + variant + self.settings.seed) % 2 else 1
        settle = ease_out(phase * 5)
        zoom = 1.10 + intensity * (0.13 * (1 - settle) + 0.065 * phase)
        x = direction * intensity * 0.018 * (2 * phase - 1)
        y = intensity * 0.012 * math.sin(phase * math.pi)
        if shot is not None and "motion" in shot:
            intensity *= shot.get("strength", 1.0)
            motion = shot["motion"]
            travel = smooth(phase)
            zoom, x, y = 1.0, 0.0, 0.0
            if motion == "push":
                zoom = 1 + intensity * (0.025 + 0.22 * travel)
            elif motion == "pull":
                zoom = 1 + intensity * (0.245 - 0.22 * travel)
            elif motion in ("left", "right", "rise"):
                zoom = 1 + intensity * 0.20
                offset = intensity * 0.07 * (2 * travel - 1)
                if motion == "rise":
                    y = -offset
                else:
                    x = offset * (-1 if motion == "left" else 1)
            elif motion == "snap":
                zoom = 1 + intensity * (0.035 + 0.30 * (1 - ease_out(phase * 4)))
            # Keep the inverse camera crop inside the fitted source at every phase.
            padding = (1 - 1 / zoom) * 0.5
            x, y = max(-padding, min(padding, x)), max(-padding, min(padding, y))
        box = self.protected_boxes.get((index % len(self.images), width, height))
        if box is not None:
            zoom = min(zoom, 1 / max(box[2] - box[0], box[3] - box[1], 1e-6))
            half = 0.5 / zoom
            cx = min(max(0.5 + x, half, box[2] - half), 1 - half, box[0] + half)
            cy = min(max(0.5 + y, half, box[3] - half), 1 - half, box[1] + half)
            x, y = cx - 0.5, cy - 0.5
        return self._camera(source, width, height, zoom, x, y)

    def _scene(self, index, frame):
        s = self.settings
        w, h = s.width, s.height
        duration = self.starts[index + 1] - self.starts[index] + self.transition_frames
        phase = max(0.0, min(1.0, (frame - self.starts[index]) / max(1, duration)))
        scene = SCENES[index % len(SCENES)]
        if s.layout != "Art directed mix":
            scene = {"Full frame": "hero", "Layered": "stack", "Split screen": "split"}[s.layout]
        if len(self.images) == 1:
            scene = "stack" if s.layout == "Layered" else "hero"
        photo_index = index
        shot = None
        if self.plan is not None:
            shot = self.plan["shots"][index]
            scene = shot["scene"]
            photo_index = shot["image_index"]
        variant = shot.get("variant", 0) if shot else 0
        if scene == "hero":
            canvas = self._moving_photo(photo_index, w, h, phase, shot=shot)
        elif scene in ("gallery", "window"):
            light = scene == "gallery" and (self.plan or {}).get("preset") != "Cinematic gallery"
            canvas = Image.new("RGB", (w, h), (238, 239, 236) if light else (15, 17, 20))
            if scene == "gallery":
                pw, ph = (round(w * 0.72), round(h * 0.84)) if w >= h else (round(w * 0.84), round(h * 0.72))
            else:
                pw, ph = (w, round(h * 0.76)) if w >= h else (round(w * 0.80), h)
            photo = self._moving_photo(photo_index, pw, ph, phase, shot=shot)
            ox = round((w - pw) * (0.25 if variant % 2 else 0.75)) if scene == "gallery" else (w - pw) // 2
            oy = (h - ph) // 2
            canvas.paste(photo, (ox, oy))
            if s.graphics and scene == "gallery":
                draw = ImageDraw.Draw(canvas)
                draw.line((ox, oy + ph + 3, ox + pw // 4, oy + ph + 3), fill=self.accent, width=2)
        elif scene == "mosaic":
            canvas = Image.new("RGB", (w, h), (16, 16, 18))
            gap = max(2, round(min(w, h) * 0.012))
            if w >= h:
                cut = round(w * (0.60 if variant % 2 else 0.68))
                boxes = [(0, 0, cut - gap, h), (cut, 0, w, h // 2 - gap), (cut, h // 2, w, h)]
            else:
                cut = round(h * (0.60 if variant % 2 else 0.68))
                boxes = [(0, 0, w, cut - gap), (0, cut, w // 2 - gap, h), (w // 2, cut, w, h)]
            for panel, (left, top, right, bottom) in enumerate(boxes):
                if variant >= 4:
                    left, right = w - right, w - left
                photo = self._moving_photo(photo_index + panel, right - left, bottom - top, phase, panel, shot)
                canvas.paste(photo, (left, top))
        elif scene in ("split", "triptych"):
            canvas = Image.new("RGB", (w, h), (16, 16, 18))
            gutter = max(2, round(min(w, h) * 0.008))
            vertical = w >= h
            extent = w if vertical else h
            ratio = (0.38, 0.5, 0.62, 0.72)[variant % 4] if shot and "variant" in shot else 0.62
            cuts = [0, round(extent * ratio), extent] if scene == "split" else [0, extent // 3, extent * 2 // 3, extent]
            for panel, (start, end) in enumerate(zip(cuts, cuts[1:])):
                gap = gutter if panel else 0
                pw, ph = (end - start - gap, h) if vertical else (w, end - start - gap)
                photo = self._moving_photo(photo_index + panel, pw, ph, phase, panel, shot)
                canvas.paste(photo, (start + gap, 0) if vertical else (0, start + gap))
            if s.graphics:
                draw = ImageDraw.Draw(canvas)
                pos = cuts[1]
                if vertical:
                    draw.rectangle((pos - gutter, h * 0.1, pos, h * 0.24), fill=self.accent)
                else:
                    draw.rectangle((w * 0.1, pos - gutter, w * 0.24, pos), fill=self.accent)
        else:
            canvas = self._cover_cached(photo_index, w, h, True).copy()
            pw, ph = (round(w * 0.73), round(h * 0.59)) if h > w else (round(w * 0.64), round(h * 0.76))
            enter = ease_out(phase * 5)
            border = max(2, round(min(w, h) * 0.006))
            for layer in (-1, 0):
                photo = self._moving_photo(photo_index + (1 if layer else 0), pw, ph, phase, layer, shot)
                photo = ImageOps.expand(photo, border=border, fill=(242, 242, 239)).convert("RGBA")
                direction = -1 if (index + variant) % 2 else 1
                rotation = direction * ((-6.0 if layer else 3.2) + (1 - enter) * 6 * s.intensity)
                photo = photo.rotate(rotation, Image.Resampling.BICUBIC, expand=True)
                dx = direction * (w * 0.075 if layer else -w * 0.025)
                dy = h * (0.035 if layer else -0.025) + (1 - enter) * h * 0.10 * s.intensity
                x, y = round((w - photo.width) / 2 + dx), round((h - photo.height) / 2 + dy)
                shadow = Image.new("RGBA", (w, h))
                alpha = Image.new("L", (w, h))
                alpha.paste(photo.getchannel("A"), (x + border * 2, y + border * 3))
                shadow.putalpha(alpha.filter(ImageFilter.GaussianBlur(border * 3)).point(lambda p: int(p * 0.38)))
                canvas = Image.alpha_composite(canvas.convert("RGBA"), shadow)
                canvas.alpha_composite(photo, (x, y))
                canvas = canvas.convert("RGB")
        headline = self.headlines[index] if index < len(self.headlines) else ""
        if headline and s.show_headlines and not self.headline_layers:
            text = self._text_cached(index, headline)
            local = (frame - self.starts[index]) / s.fps
            reveal = ease_out((local - 0.08) / 0.35)
            offset = round(h * 0.065 * (1 - reveal))
            if reveal > 0:
                overlay = text.copy()
                overlay.putalpha(overlay.getchannel("A").point(lambda p: int(p * reveal)))
                canvas = canvas.convert("RGBA")
                canvas.alpha_composite(overlay, (0, offset))
                canvas = canvas.convert("RGB")
        if s.graphics and s.show_counter:
            draw = ImageDraw.Draw(canvas)
            margin = round(min(w, h) * 0.065)
            size = max(8, round(min(w, h) * 0.025))
            label = f"{index + 1:02d} / {self.shot_count:02d}"
            font = self._font(size)
            box = draw.textbbox((margin, margin), label, font=font)
            draw.rectangle((box[0] - 4, box[1] - 3, box[2] + 4, box[3] + 3), fill=(18, 18, 20))
            draw.text((margin, margin), label, font=font, fill=(248, 248, 246))
        if s.graphics and s.show_progress:
            draw = ImageDraw.Draw(canvas)
            line_y = h - max(2, round(h * 0.005))
            draw.rectangle((0, line_y, round(w * (frame + 1) / self.frame_count), h), fill=self.accent)
        return canvas

    def _text_layer(self, index, headline):
        s = self.settings
        w, h = s.width, s.height
        layer = Image.new("RGBA", (w, h))
        draw = ImageDraw.Draw(layer)
        margin = round(min(w, h) * 0.065)
        max_width = w - margin * 2
        target = round(min(w, h) * (0.105 if w >= h else 0.092))
        text = " ".join(headline.split())[:240]
        for size in range(max(10, target), 9, -1):
            font = self._font(size)
            lines = [""]
            for word in text.split():
                candidate = (lines[-1] + " " + word).strip()
                if draw.textlength(candidate, font=font) <= max_width or not lines[-1]:
                    lines[-1] = candidate
                else:
                    lines.append(word)
            if len(lines) <= 3 and all(draw.textlength(line, font=font) <= max_width for line in lines):
                break
        line_height = round(font.size * 1.2)
        tw = max(max(1, math.ceil(draw.textlength(line, font=font))) for line in lines)
        text_image = Image.new("RGBA", (tw + 4, line_height * len(lines) + font.size))
        td = ImageDraw.Draw(text_image)
        for row, line in enumerate(lines):
            td.text((0, row * line_height), line, font=font, fill=(250, 250, 248, 255))
        ratio = min(1, max_width / text_image.width, max(1, round(h * 0.32)) / text_image.height)
        if ratio < 1:
            text_image = text_image.resize((max(1, round(text_image.width * ratio)), max(1, round(text_image.height * ratio))), Image.Resampling.LANCZOS)
        top = h - margin - text_image.height
        fd = ImageDraw.Draw(layer)
        fade_start = max(0, top - margin * 2)
        for y in range(fade_start, h):
            alpha = round(175 * smooth((y - fade_start) / max(1, h - fade_start)))
            fd.line((0, y, w, y), fill=(0, 0, 0, alpha))
        if s.graphics:
            fd.rectangle((margin, top - margin // 3, margin + max(18, w // 12), top - margin // 3 + max(2, h // 180)), fill=self.accent)
        layer.alpha_composite(text_image, (margin, top))
        return layer

    def _transition(self, previous, current, value, index):
        s = self.settings
        w, h = s.width, s.height
        if value <= 0:
            return previous
        if value >= 1:
            return current
        kind = TRANSITIONS[(index - 1 + s.seed) % len(TRANSITIONS)] if s.transition == "Mixed" else s.transition.lower()
        if self.plan is not None:
            kind = self.plan["shots"][index]["transition"]
        q = smooth(value)
        if kind == "dissolve":
            return Image.blend(previous, current, q)
        if kind == "whip":
            canvas = Image.new("RGB", (w, h))
            direction = 1 if index % 2 else -1
            shift = round(w * q)
            canvas.paste(previous, (-direction * shift, 0))
            canvas.paste(current, (direction * (w - shift), 0))
            return canvas
        if kind == "zoom":
            outgoing = self._camera(previous, w, h, 1 + q * 0.65 * s.intensity)
            incoming = self._camera(current, w, h, 1 + (1 - q) * 0.38 * s.intensity)
            return Image.blend(outgoing, incoming, q)
        if kind in ("diagonal", "shutter"):
            mask = Image.new("L", (w, h))
            draw = ImageDraw.Draw(mask)
            if kind == "diagonal":
                edge = (w + h * 0.35) * q
                draw.polygon([(0, 0), (edge, 0), (edge - h * 0.35, h), (0, h)], fill=255)
            else:
                for panel in range(5):
                    left, right = round(w * panel / 5), round(w * (panel + 1) / 5)
                    progress = smooth(value * 1.35 - panel * 0.0875)
                    opening = round(h * progress)
                    if opening:
                        if panel % 2:
                            draw.rectangle((left, h - opening, right, h), fill=255)
                        else:
                            draw.rectangle((left, 0, right, opening - 1), fill=255)
            return Image.composite(current, previous, mask)
        if kind == "impact":
            chosen = previous if value < 0.5 else current
            impact = math.sin(math.pi * value) ** 6 * s.intensity
            chosen = self._camera(chosen, w, h, 1 + impact * 0.10)
            return Image.blend(chosen, Image.new("RGB", (w, h), (244, 246, 239)), impact * 0.20)
        return current

    def _raw_frame(self, frame):
        frame = max(0.0, min(self.frame_count - 1.0, frame))
        index = min(self.shot_count - 1, bisect.bisect_right(self.starts, frame) - 1)
        current = self._scene(index, frame)
        local = frame - self.starts[index]
        cut = self.plan is not None and self.plan["shots"][index]["transition"] == "cut"
        if index > 0 and not cut and self.transition_frames and local < self.transition_frames:
            previous = self._scene(index - 1, frame)
            return self._transition(previous, current, local / self.transition_frames, index)
        return current

    def frame(self, number):
        if not 0 <= number < self.frame_count:
            raise IndexError("Frame index is outside the slideshow.")
        samples = self.settings.motion_blur
        if samples == 1:
            result = self._raw_frame(float(number))
        else:
            result = None
            index = min(self.shot_count - 1, bisect.bisect_right(self.starts, number) - 1)
            hard_cut = self.plan is not None and self.plan["shots"][index]["transition"] == "cut"
            for i, offset in enumerate(np.linspace(-0.35, 0.35, samples)):
                sample_time = number + float(offset)
                if hard_cut:
                    sample_time = max(self.starts[index], sample_time)
                sample = self._raw_frame(sample_time)
                result = sample if result is None else Image.blend(result, sample, 1 / (i + 1))
        if self.settings.show_headlines and self.headline_layers:
            result = composite_titles(result, self.headline_layers, number / self.settings.fps, self._title_cached)
        if self.settings.grain > 0:
            rng = np.random.default_rng((self.settings.seed + number * 997) % (2**63))
            values = np.asarray(result, dtype=np.float32)
            noise = rng.standard_normal((result.height, result.width, 1), dtype=np.float32)
            result = Image.fromarray(np.clip(values + noise * self.settings.grain * 9, 0, 255).astype(np.uint8))
        return result

    def clear_cache(self):
        self._cover_cached.cache_clear()
        self._text_cached.cache_clear()
        self._title_cached.cache_clear()


class VideoWriter:
    """Bounded-memory RGB pipe; stderr goes to disk to prevent pipe deadlocks."""

    def __init__(self, path, settings, quality="High", audio_path=None):
        self.path = Path(path)
        self.settings = settings
        executable = ffmpeg_executable()
        crf = {"Preview": "25", "High": "18", "Master": "14"}[quality]
        command = [executable, "-hide_banner", "-loglevel", "error", "-y",
                   "-f", "rawvideo", "-pix_fmt", "rgb24", "-s:v", f"{settings.width}x{settings.height}",
                   "-r", str(settings.fps), "-i", "pipe:0"]
        if audio_path:
            command.extend(["-i", str(audio_path), "-map", "0:v:0", "-map", "1:a:0",
                            "-af", "apad", "-c:a", "aac", "-b:a", "192k", "-shortest"])
        command.extend(["-c:v", "libx264", "-preset", "veryfast" if quality == "Preview" else "medium",
                        "-crf", crf, "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(self.path)])
        self.error_log = tempfile.TemporaryFile()
        self.process = None
        try:
            self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                            stderr=self.error_log,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except BaseException:
            self.error_log.close()
            raise

    def _error(self):
        self.error_log.seek(0)
        return self.error_log.read().decode("utf-8", errors="replace")[-3000:]

    def write(self, image):
        if image.size != (self.settings.width, self.settings.height):
            raise ValueError("Unexpected video frame size.")
        try:
            self.process.stdin.write(image.convert("RGB").tobytes())
        except (BrokenPipeError, OSError) as exc:
            self.process.wait(timeout=30)
            raise RuntimeError("FFmpeg could not encode the slideshow: " + self._error()) from exc

    def close(self):
        try:
            self.process.stdin.close()
            code = self.process.wait(timeout=180)
            if code:
                raise RuntimeError("FFmpeg export failed: " + self._error())
        except BaseException:
            self.abort()
            raise
        finally:
            self.error_log.close()

    def abort(self):
        if self.process and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=30)
        if self.process and self.process.stdin:
            try:
                self.process.stdin.close()
            except (BrokenPipeError, OSError):
                pass
        self.error_log.close()
        self.path.unlink(missing_ok=True)

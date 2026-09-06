"""Timed, independently positioned headline layers."""

import json
import math

from PIL import Image, ImageColor, ImageDraw


def parse_titles(value):
    layers = (json.loads(value) if value.strip() else []) if isinstance(value, str) else value or []
    if not isinstance(layers, list) or len(layers) > 200:
        raise ValueError("Headline layers must be a JSON array of up to 200 headlines.")
    defaults = dict(text="", start=0, end=2, x=8, y=70, width=84, size=8,
                    color="#FFFFFF", align="left", animation="fade", enabled=True)
    result = []
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict) or set(layer) - set(defaults):
            raise ValueError(f"Headline {index + 1}: unknown fields or invalid object.")
        item = {**defaults, **layer}
        if not isinstance(item["text"], str) or len(item["text"]) > 2000:
            raise ValueError(f"Headline {index + 1}: text must be at most 2000 characters.")
        for key in ("start", "end", "x", "y", "width", "size"):
            if type(item[key]) not in (int, float) or not math.isfinite(item[key]):
                raise ValueError(f"Headline {index + 1}: {key} must be a finite number.")
        if not 0 <= item["start"] < item["end"] <= 24000:
            raise ValueError(f"Headline {index + 1}: use 0 <= start < end <= 24000 seconds.")
        if not 0 <= item["x"] <= 99 or not 0 <= item["y"] <= 99 or not 1 <= item["width"] <= 100 or not 1 <= item["size"] <= 50:
            raise ValueError(f"Headline {index + 1}: invalid position, width or size percentages.")
        if item["align"] not in ("left", "center", "right") or item["animation"] not in ("none", "fade", "slide"):
            raise ValueError(f"Headline {index + 1}: invalid alignment or animation.")
        if type(item["enabled"]) is not bool:
            raise ValueError("Headline enabled must be true or false.")
        ImageColor.getrgb(item["color"])
        result.append(item)
    return result


def title_bitmap(item, width, height, font_loader):
    x, y = round(width * item["x"] / 100), round(height * item["y"] / 100)
    available_w = max(1, min(width - x, round(width * item["width"] / 100)))
    available_h = max(1, height - y)
    size = max(1, round(min(width, height) * item["size"] / 100))
    measure = ImageDraw.Draw(Image.new("L", (1, 1)))
    # Fit the font before allocating, including very long multiline headlines.
    while True:
        font = font_loader(size)
        lines = []
        for paragraph in item["text"].split("\n"):
            line = ""
            for char in paragraph:
                if line and measure.textlength(line + char, font=font) > available_w:
                    space = line.rfind(" ")
                    lines.append(line[:space] if space > 0 else line)
                    line = line[space + 1:] if space > 0 else ""
                line += char
            lines.append(line)
        text = "\n".join(lines)
        spacing = max(1, round(font.size * 0.15))
        box = measure.multiline_textbbox((0, 0), text, font=font, spacing=spacing, align=item["align"], stroke_width=1)
        tw, th = max(1, math.ceil(box[2] - box[0])), max(1, math.ceil(box[3] - box[1]))
        ratio = min(1, available_w / tw, available_h / th)
        if ratio == 1 or size == 1:
            break
        size = max(1, min(size - 1, int(size * ratio)))
    bitmap = Image.new("RGBA", (tw, th))
    ImageDraw.Draw(bitmap).multiline_text((-box[0], -box[1]), text, font=font, spacing=spacing,
        align=item["align"], fill=ImageColor.getrgb(item["color"]), stroke_width=1, stroke_fill=(0, 0, 0, 180))
    ratio = min(1, available_w / tw, available_h / th)
    if ratio < 1:
        bitmap = bitmap.resize((max(1, int(tw * ratio)), max(1, int(th * ratio))), Image.Resampling.LANCZOS)
    x += round((available_w - bitmap.width) * {"left": 0, "center": 0.5, "right": 1}[item["align"]])
    return bitmap, x, y


def composite_titles(canvas, layers, seconds, cached_bitmap):
    result = None
    for index, item in enumerate(layers):
        if not item["enabled"] or not item["text"] or not item["start"] <= seconds < item["end"]:
            continue
        bitmap, x, y = cached_bitmap(index)
        if item["animation"] != "none":
            fade = min(0.25, (item["end"] - item["start"]) / 3)
            amount = max(0, min(1, (seconds - item["start"]) / fade, (item["end"] - seconds) / fade))
            bitmap = bitmap.copy()
            bitmap.putalpha(bitmap.getchannel("A").point(lambda p: round(p * amount)))
            if item["animation"] == "slide":
                y = min(canvas.height - bitmap.height, y + round(canvas.height * 0.04 * (1 - amount)))
        if result is None:
            result = canvas.convert("RGBA")
        result.alpha_composite(bitmap, (x, y))
    return result.convert("RGB") if result is not None else canvas

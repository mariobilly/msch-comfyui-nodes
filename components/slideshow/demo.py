"""Render a sample from local photos without starting ComfyUI."""

import argparse
import json
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine import PromoRenderer, Settings, VideoWriter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", required=True)
    parser.add_argument("--output", default="demo")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--headlines", nargs="*", default=[])
    args = parser.parse_args()
    paths = sorted(p for p in Path(args.images).iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})[:args.count]
    destination = Path(args.output).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    settings = Settings(width=args.width, height=args.height)
    renderer = PromoRenderer(paths, settings, args.headlines)
    writer = VideoWriter(destination / "marioslideshow_demo.mp4", settings)
    started = time.perf_counter()
    sheet = Image.new("RGB", (4 * 320, 2 * 208), (16, 16, 18))
    sample_numbers = [(renderer.starts[i] + renderer.starts[i + 1]) // 2 for i in range(min(8, len(paths)))]
    try:
        for number in range(renderer.frame_count):
            frame = renderer.frame(number)
            writer.write(frame)
            if number in sample_numbers:
                index = sample_numbers.index(number)
                thumb = frame.copy()
                thumb.thumbnail((316, 180))
                x, y = (index % 4) * 320, (index // 4) * 208
                sheet.paste(thumb, (x + (320 - thumb.width) // 2, y))
                ImageDraw.Draw(sheet).text((x + 8, y + 184), f"SHOT {index + 1:02d} / FRAME {number}", fill="white")
            if number % 60 == 0:
                print(f"Rendered {number}/{renderer.frame_count}", flush=True)
        writer.close()
    except BaseException:
        writer.abort()
        raise
    finally:
        renderer.clear_cache()
    sheet.save(destination / "contact_sheet.jpg", quality=94)
    (destination / "render_info.json").write_text(json.dumps({"frames": renderer.frame_count,
        "fps": settings.fps, "duration": renderer.frame_count / settings.fps,
        "render_seconds": round(time.perf_counter() - started, 2)}, indent=2))
    print(destination, flush=True)


if __name__ == "__main__":
    main()

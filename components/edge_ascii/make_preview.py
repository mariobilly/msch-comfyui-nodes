"""Run the real node on a supplied image and save a comparison sheet."""
import argparse
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw

from nodes import EdgeASCII


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--crop", type=int, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    parser.add_argument("--output", type=Path, default=Path("previews"))
    args = parser.parse_args()
    source = Image.open(args.input).convert("RGB")
    if args.crop:
        source = source.crop(tuple(args.crop))
    args.output.mkdir(parents=True, exist_ok=True)
    tensor = torch.from_numpy(np.asarray(source, dtype=np.float32) / 255)[None]
    panels = [("Original", source)]
    for mode in ("edge_only", "mixed", "full_ascii"):
        output, _ = EdgeASCII().apply(tensor, mode=mode, fill_amount=1.0 if mode == "full_ascii" else 0.5)
        preview = Image.fromarray(np.uint8(output[0].numpy().clip(0, 1) * 255))
        preview.save(args.output / (mode + ".png"))
        panels.append((mode.replace("_", " ").title(), preview))
    w, h = source.size
    sheet = Image.new("RGB", (w * 4, h + 40), "#14171D")
    draw = ImageDraw.Draw(sheet)
    for index, (label, picture) in enumerate(panels):
        sheet.paste(picture, (index * w, 40))
        draw.text((index * w + 12, 13), label, fill="white")
    sheet.save(args.output / "comparison.png")
    print(args.output.resolve() / "comparison.png")


if __name__ == "__main__":
    main()

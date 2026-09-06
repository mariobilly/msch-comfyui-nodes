"""Render the supplied screenshot reference through the actual VIDEO node."""
import importlib.util
from pathlib import Path
import sys

import av
import numpy as np
from PIL import Image
import torch
from comfy_api.latest import Types


def main():
    root = Path(__file__).parent
    spec = importlib.util.spec_from_file_location("msch_preview", root / "__init__.py", submodule_search_locations=[str(root)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package
    spec.loader.exec_module(package)
    source = Image.open(sys.argv[1]).convert("RGB")
    if len(sys.argv) == 6:
        source = source.crop(tuple(map(int, sys.argv[2:6])))
    image = torch.from_numpy(np.asarray(source, dtype=np.float32) / 255)[None]
    clip = package.NODE_CLASS_MAPPINGS["MschEdgeASCIIVideo"]().animate(image=image)[0]
    path = root / "previews" / "animated_preview.mp4"
    clip.save_to(str(path), format=Types.VideoContainer.MP4, codec=Types.VideoCodec.H264)
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        print("Encoded:", stream.codec_context.name, "FPS:", stream.average_rate, "Duration:", float(stream.duration * stream.time_base))
        first = later = None
        count = 0
        for frame in container.decode(video=0):
            if count == 0:
                first = frame.to_ndarray(format="rgb24")
            if count == 24:
                later = frame.to_ndarray(format="rgb24")
            count += 1
        assert count == 96 and not np.array_equal(first, later)
        print("Verified", count, "frames and visible frame changes:", path)


if __name__ == "__main__":
    main()

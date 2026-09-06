import json
import threading
import uuid
import sys
from pathlib import Path

import av
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import ROOT
from mariotyport.project import PRESETS, default_project
from mariotyport.render import render

output = ROOT / "artifacts" / ("verification_" + uuid.uuid4().hex[:8])
output.mkdir()
p = default_project("MARIO\nTYPOGRAPHY", duration=1.2)
p["layers"][0].update(enter=.3, exit=.2, shadow_opacity=0)
mov = render(p, output / "alpha_mov", width=640, height=360, fps=12, samples=3)
with av.open(mov["path"]) as video:
    frames = list(video.decode(video=0))
    assert len(frames) == 15
    image = frames[8].to_ndarray(format="rgba")
    assert image[:, :, 3].min() == 0 and image[:, :, 3].max() > 250
    assert ((image[:, :, 3] > 0) & (image[:, :, 3] < 255)).any()
    assert video.streams.video[0].codec_context.name == "prores"

png = render(p, output / "png", width=320, height=180, fps=5, format="PNG sequence", samples=1)
assert len(list((output / "png" / "frames").glob("*.png"))) == 6
with Image.open(output / "png" / "frames" / "000003.png") as image:
    assert image.mode == "RGBA" and image.getchannel("A").getextrema() == (0, 255)

p["layers"][0]["text"] = "\u0645\u0627\u0631\u064a\u0648\n\u062d\u0631\u0643\u0629 \u0648\u0625\u0628\u062f\u0627\u0639"
p["layers"][0]["preset"] = "Word cascade"
arabic = render(p, output / "arabic", width=1920, height=1080, fps=5, format="MP4 composite", samples=1)
with Image.open(arabic["poster"]) as image:
    assert np.asarray(image).std() > 30

# A cancellation must close Chromium/FFmpeg and leave no partial output directory.
cancel = threading.Event()
cancel.set()
try:
    render(p, output / "cancelled", width=320, height=180, cancelled=cancel)
except InterruptedError:
    pass
else:
    raise AssertionError("Cancellation ignored")
assert not (output / "cancelled").exists()

print(json.dumps({"output": str(output), "alpha_mov": mov["path"], "arabic": arabic["path"],
                  "png_alpha": "passed", "cancellation": "passed"}, indent=2))

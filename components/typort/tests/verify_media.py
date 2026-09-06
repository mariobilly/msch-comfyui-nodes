import base64
import io
import json
import subprocess
import sys
import uuid
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import ROOT
from mariotyport.project import FONTS, PRESETS, default_project
from mariotyport.render import ffmpeg, render

output = ROOT / "artifacts" / ("media_" + uuid.uuid4().hex[:8])
output.mkdir()
footage = output / "source.mp4"
subprocess.run([ffmpeg(), "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                "testsrc2=size=640x360:rate=24:duration=4", "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(footage)], check=True)
p = default_project("TYPE\nIN MOTION", duration=1)
p["video_offset"] = 0.5
p["layers"][0].update(size=.3, color="#deff4a", preset="Scale impact", shadow_opacity=.8)
composite = render(p, output / "composite", width=640, height=360, fps=24, format="MP4 composite", samples=5, video=footage)
with av.open(composite["path"]) as video:
    assert len(video.streams.audio) == 1
    assert len(list(video.decode(video=0))) == 24
with av.open(composite["path"]) as video:
    audio = next(video.decode(audio=0)).to_ndarray()
    assert np.abs(audio).max() > .01

p = default_project("MARIO\nTYPOPORT", preset="Static", duration=.1)
master = render(p, output / "4k", width=3840, height=2160, fps=1, format="Transparent MOV", samples=1)
with av.open(master["path"]) as video:
    frame = next(video.decode(video=0))
    assert (frame.width, frame.height) == (3840, 2160)
    alpha = frame.to_ndarray(format="rgba")[:, :, 3]
    assert alpha.min() == 0 and alpha.max() == 255

sheet = Image.new("RGB", (960, 3 * 210), (25, 27, 30))
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content('<canvas id="c" width="640" height="360"></canvas>')
    page.add_script_tag(path=str(ROOT / 'web' / 'engine.js'))
    fonts={n:base64.b64encode((ROOT/'web'/'fonts'/f'Tajawal-{n}.ttf').read_bytes()).decode() for n in FONTS}
    page.evaluate("""async fonts=>{for(const [n,data]of Object.entries(fonts)){const f=new FontFace('MT-'+n,'url(data:font/ttf;base64,'+data+')');document.fonts.add(await f.load());}window.r=MarioType.createRenderer(c);}""",fonts)
    signatures=[]
    for i,preset in enumerate(PRESETS):
        p=default_project("TYPE\nIN MOTION",preset=preset,duration=3)
        data=page.evaluate("""p=>{r.render(p,.22);return c.toDataURL().split(',')[1];}""",p)
        image=Image.open(io.BytesIO(base64.b64decode(data))).convert('RGBA')
        signatures.append(image.tobytes())
        background=Image.new('RGBA',image.size,(25,27,30,255))
        background.alpha_composite(image)
        sheet.paste(background.convert('RGB').resize((320,180)),((i%3)*320,(i//3)*210+20))
        ImageDraw.Draw(sheet).text(((i%3)*320+10,(i//3)*210+4),preset,fill='white')
    assert len(set(signatures)) == len(PRESETS)
    # Shaped Arabic ignores tracking so letter connections cannot be broken by that treatment.
    p=default_project('\u0645\u0627\u0631\u064a\u0648 \u062d\u0631\u0643\u0629',preset='Static')
    before=page.evaluate("p=>{r.render(p,1);return c.toDataURL();}",p)
    p['layers'][0]['tracking']=.08
    after=page.evaluate("p=>{r.render(p,1);return c.toDataURL();}",p)
    assert before==after
    browser.close()
sheet.save(output/'treatments.jpg')
print(json.dumps({'output':str(output),'composite':composite['path'],'4k':master['path'],
                  'audio':'passed','distinct_treatments':len(signatures),'arabic_tracking':'protected'},indent=2))

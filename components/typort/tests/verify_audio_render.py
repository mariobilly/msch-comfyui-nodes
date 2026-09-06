import json
import sys
import uuid
from pathlib import Path

import av
import numpy as np
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import ROOT
from test_audio import make_clicks
from mariotyport.audio_analysis import analyze
from mariotyport.project import default_project, validate_project
from mariotyport.render import render

out = ROOT / 'artifacts' / ('audio_' + uuid.uuid4().hex[:8])
out.mkdir()
audio = ROOT/'artifacts'/'audio_clicks.wav'
make_clicks(audio)
analysis = analyze(audio, 'audio_clicks.wav')
(ROOT/'artifacts'/'audio_analysis.json').write_text(json.dumps(analysis), encoding='utf-8')
p=default_project('FEEL\nTHE BEAT',preset='Static',duration=4)
p['audio'].update(file='audio_clicks.wav',trim_start=0,trim_end=4,start=0,analysis=analysis)
p['layers'][0].update(react_mode='Beats',react_outline=.018,stroke_color='#DEFF4A',react_scale=.1,decay=.09,shadow_opacity=0)
validate_project(p)
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    page=browser.new_page()
    page.add_script_tag(path=str(ROOT/'web'/'engine.js'))
    times=page.evaluate('p=>MarioType.timelineBeats(p)',p)
    beat=next(t for t in times if .5<t<2)
    signals=page.evaluate('({p,beat})=>{const c=new WeakMap();return [beat,beat+.25,beat].map(t=>MarioType.reaction(p,p.layers[0],t,c));}',{'p':p,'beat':beat})
    assert signals[0]>.99 and signals[1]<.1 and signals[0]==signals[2],signals
    p['audio']['trim_start']=.25;p['audio']['trim_end']=3.75;p['audio']['start']=.5
    shifted=page.evaluate('p=>MarioType.timelineBeats(p)',p)
    assert abs(shifted[0]-(next(t for t in times if t>=.25)+.25))<1e-5
    p['audio'].update(trim_start=0,trim_end=4,start=0)
    p['layers'][0].update(beat_every=2)
    pulse=page.evaluate('p=>MarioType.audioBeats(p.audio).slice(0,4).map(t=>MarioType.reaction(p,p.layers[0],t,new WeakMap()))',p)
    assert pulse[0]>.9 and pulse[1]<.1 and pulse[2]>.9,pulse
    p['layers'][0]['beat_every']=1
    browser.close()
result=render(p,out/'transparent',width=640,height=360,fps=30,format='Transparent MOV',samples=3,audio=audio)
with av.open(result['path']) as movie:
    assert len(movie.streams.audio)==1
    frames=list(movie.decode(video=0))
    assert len(frames)==120
    peak=frames[round(beat*30)].to_ndarray(format='rgba')
    trough=frames[round((beat+.25)*30)].to_ndarray(format='rgba')
    assert peak[:,:,3].min()==0 and peak[:,:,3].max()==255
    assert np.count_nonzero(peak[:,:,3])>np.count_nonzero(trough[:,:,3])
with av.open(result['path']) as movie:
    assert max(float(np.abs(frame.to_ndarray()).max()) for frame in movie.decode(audio=0))>.01
print(json.dumps({'output':result,'beat_signals':signals,'beat_times':times[:5]},indent=2))

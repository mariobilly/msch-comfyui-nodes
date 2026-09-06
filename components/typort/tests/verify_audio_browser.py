import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--url',default='http://127.0.0.1:8195')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
with sync_playwright() as pw:
    browser=pw.chromium.launch(headless=True)
    page=browser.new_page(viewport={'width':1600,'height':1050})
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(args.url)
    page.wait_for_function("Boolean(window.app&&window.LiteGraph?.registered_node_types.MarioTyport)",timeout=90000)
    page.evaluate("""()=>{app.graph.clear();window.node=LiteGraph.createNode('MarioTyport');node.pos=[100,80];app.graph.add(node);
        for(const [k,v]of Object.entries({text:'FEEL\\nTHE BEAT',animation:'Static',duration:4,width:640,height:360,fps:24,motion_blur:'Off'}))node.widgets.find(w=>w.name===k).value=v;
        node.widgets.find(w=>w.name==='Open typography studio').callback();}
    """)
    frame=page.frame_locator('iframe[title="mariotyport studio"]')
    frame.locator('#text').wait_for()
    page.wait_for_timeout(900)
    frame.locator('#audioFile').set_input_files(str(root/'artifacts'/'audio_clicks.wav'))
    frame.locator('#audioName').get_by_text('audio_clicks.wav',exact=True).wait_for()
    frame.locator('#analyzeAudio').click()
    frame.locator('#analysisStatus').get_by_text('sources',exact=False).wait_for(timeout=120000)
    assert frame.locator('.mark').count()>5
    pixel_colors=frame.locator('#audioWave').evaluate("c=>new Set(c.getContext('2d').getImageData(0,0,c.width,c.height).data).size")
    assert pixel_colors>20
    clip=frame.locator('#audioClip').bounding_box()
    page.mouse.move(clip['x']+clip['width']*.5,clip['y']+20);page.mouse.down()
    page.mouse.move(clip['x']+clip['width']*.5+60,clip['y']+20,steps=5);page.mouse.up()
    assert float(frame.locator('#audioStart').input_value())>0
    frame.locator('#audioStart').fill('0');frame.locator('#audioStart').dispatch_event('change')
    frame.locator('[data-field="react_mode"]').select_option('Beats')
    frame.locator('[data-field="react_outline"]').fill('1.8')
    frame.locator('[data-field="react_outline"]').dispatch_event('change')
    frame.locator('[data-field="stroke_color"]').fill('#DEFF4A')
    frame.locator('[data-field="stroke_color"]').dispatch_event('change')
    frame.locator('#scrub').fill('0.77');frame.locator('#scrub').dispatch_event('input')
    peak=frame.locator('#canvas').evaluate('c=>c.toDataURL()')
    frame.locator('#scrub').fill('1.01');frame.locator('#scrub').dispatch_event('input')
    trough=frame.locator('#canvas').evaluate('c=>c.toDataURL()')
    if peak==trough:
        frame.locator('#apply').click();page.locator('iframe').wait_for(state='detached')
        saved=json.loads(page.evaluate("node.widgets.find(w=>w.name==='project_json').value"))
        print({k:v for k,v in saved['audio'].items() if k!='analysis'},saved['layers'][0])
        raise AssertionError('Outline did not change')
    frame.locator('#audioStart').fill('0.5');frame.locator('#audioStart').dispatch_event('change')
    frame.locator('#audioIn').fill('0.25');frame.locator('#audioIn').dispatch_event('change')
    frame.locator('#audioBpm').fill('120');frame.locator('#audioBpm').dispatch_event('change')
    frame.locator('#scrub').fill('1.02');frame.locator('#scrub').dispatch_event('input')
    frame.locator('[data-field="react_mode"]').scroll_into_view_if_needed()
    page.screenshot(path=str(root/'artifacts'/'audio_studio_desktop.png'))
    frame.locator('#apply').click();page.locator('iframe').wait_for(state='detached')
    saved=page.evaluate("node.widgets.find(w=>w.name==='project_json').value")
    project=json.loads(saved)
    assert project['audio']['analysis']['bpm']>115
    assert project['audio']['start']==.5 and project['layers'][0]['react_mode']=='Beats'
    graph=page.evaluate('app.graph.serialize()')
    page.evaluate("async g=>{await app.loadGraphData(g);window.node=app.graph._nodes.find(n=>n.type==='MarioTyport');node.widgets.find(w=>w.name==='Open typography studio').callback();}",graph)
    frame.locator('#analysisStatus').get_by_text('sources',exact=False).wait_for()
    assert frame.locator('.mark').count()>5
    page.set_viewport_size({'width':390,'height':844})
    frame.locator('#audioName').scroll_into_view_if_needed()
    page.screenshot(path=str(root/'artifacts'/'audio_studio_mobile.png'))
    frame.locator('#close').click();page.locator('iframe').wait_for(state='detached')
    assert page.evaluate("node.widgets.find(w=>w.name==='project_json').value")==saved
    prompt=page.evaluate('async()=> (await app.graphToPrompt()).output')
    response=page.request.post(args.url+'/prompt',data={'prompt':prompt});assert response.ok,response.text()
    job=response.json()['prompt_id'];deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        history=page.request.get(args.url+'/history/'+job).json()
        if job in history:
            assert history[job]['status']['status_str']=='success',history[job]
            (root/'artifacts'/'audio_comfy_render.json').write_text(json.dumps(history[job],indent=2),encoding='utf-8')
            break
        time.sleep(1)
    else:raise AssertionError('Render timeout')
    assert not errors,errors
    browser.close()
print(json.dumps({'waveform':'passed','analysis':'passed','outline_pixels':'passed','trim_offset_bpm':'passed','reload':'passed','render':job},indent=2))

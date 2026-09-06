import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--url", default="http://127.0.0.1:8194")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
output = root / "artifacts"
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(args.url, wait_until="domcontentloaded")
    page.wait_for_function("Boolean(window.app && window.LiteGraph?.registered_node_types['MarioTyport'])", timeout=90000)
    page.evaluate("""() => {
        app.graph.clear();window.node=LiteGraph.createNode('MarioTyport');node.pos=[150,80];app.graph.add(node);
        for(const [name,value] of Object.entries({width:640,height:360,fps:12,duration:2,motion_blur:'Off'}))node.widgets.find(w=>w.name===name).value=value;
        node.widgets.find(w=>w.name==='Open typography studio').callback();
    }""")
    frame = page.frame_locator('iframe[title="mariotyport studio"]')
    frame.locator('#text').wait_for()
    page.wait_for_timeout(1500)
    frame.locator('#text').fill('MAKE\nIT MATTER')
    frame.locator('#text').blur()
    frame.locator('#scrub').fill('1')
    frame.locator('#scrub').dispatch_event('input')
    page.screenshot(path=str(output / 'studio_desktop.png'))
    frame.locator('#add').click()
    frame.locator('#text').fill('MARIO TYPOGRAPHY')
    frame.locator('#text').blur()
    frame.locator('[data-field="size"]').fill('7')
    frame.locator('[data-field="size"]').dispatch_event('change')
    frame.locator('[data-field="y"]').first.fill('85')
    frame.locator('[data-field="y"]').first.dispatch_event('change')
    frame.locator('[data-field="color"]').fill('#deff4a')
    frame.locator('[data-field="color"]').dispatch_event('change')
    frame.locator('#addKey').click()
    assert frame.locator('#keys option').count() == 1
    frame.locator('#beatGrid').click()
    assert frame.locator('.mark').count() >= 4
    footage = sorted(output.glob('media_*/source.mp4'))[-1]
    frame.locator('#file').set_input_files(str(footage))
    frame.locator('#videoName').get_by_text('source.mp4', exact=True).wait_for()
    page.wait_for_function("() => document.querySelector('iframe').contentDocument.getElementById('footage').readyState >= 2")
    frame.locator('#format').select_option('MP4 composite')
    # Drag a selected text layer and trim a timeline clip.
    stage = frame.locator('#canvas').bounding_box()
    page.mouse.move(stage['x'] + stage['width'] * .5, stage['y'] + stage['height'] * .85)
    page.mouse.down()
    page.mouse.move(stage['x'] + stage['width'] * .56, stage['y'] + stage['height'] * .78, steps=5)
    page.mouse.up()
    clip = frame.locator('.clip').nth(1).bounding_box()
    page.mouse.move(clip['x'] + 3, clip['y'] + 10)
    page.mouse.down()
    page.mouse.move(clip['x'] + 80, clip['y'] + 10, steps=5)
    page.mouse.up()
    frame.locator('#apply').click()
    page.locator('iframe[title="mariotyport studio"]').wait_for(state='detached')
    project = json.loads(page.evaluate("node.widgets.find(w=>w.name==='project_json').value"))
    assert len(project['layers']) == 2
    assert project['layers'][1]['start'] > 0
    assert project['layers'][1]['keyframes'][0]['x'] > .5
    assert page.evaluate("node.widgets.find(w=>w.name==='video_file').value").startswith('mariotyport/')
    # Save/reload a native Comfy workflow, including the studio timeline.
    graph = page.evaluate('app.graph.serialize()')
    (output / 'mariotyport_example.json').write_text(json.dumps(graph, indent=2), encoding='utf-8')
    page.evaluate("async graph=>{await app.loadGraphData(graph);window.node=app.graph._nodes.find(n=>n.type==='MarioTyport');}", graph)
    page.evaluate("node.widgets.find(w=>w.name==='Open typography studio').callback()")
    frame.locator('#text').wait_for()
    page.wait_for_timeout(600)
    assert frame.locator('.layer-row').count() == 2
    frame.locator('#text').fill('CANCELLED CHANGE')
    frame.locator('#text').blur()
    frame.locator('#close').click()
    page.locator('iframe[title="mariotyport studio"]').wait_for(state='detached')
    assert 'CANCELLED CHANGE' not in page.evaluate("node.widgets.find(w=>w.name==='project_json').value")
    page.evaluate("node.widgets.find(w=>w.name==='Open typography studio').callback()")
    page.set_viewport_size({"width":390,"height":844})
    page.wait_for_timeout(600)
    page.screenshot(path=str(output / 'studio_mobile.png'), full_page=True)
    frame.locator('#close').click()
    page.locator('iframe[title="mariotyport studio"]').wait_for(state='detached')
    page.set_viewport_size({"width":1600,"height":1000})
    prompt = page.evaluate("async()=> (await app.graphToPrompt()).output")
    response = page.request.post(args.url + '/prompt', data={"prompt":prompt})
    assert response.ok, response.text()
    prompt_id = response.json()['prompt_id']
    deadline = time.monotonic()+180
    while time.monotonic()<deadline:
        history = page.request.get(args.url+'/history/'+prompt_id).json()
        if prompt_id in history:
            result=history[prompt_id]
            assert result['status']['status_str']=='success',result
            (output/'comfy_render.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            break
        time.sleep(1)
    else:
        raise AssertionError('Comfy render timeout')
    assert not errors, errors
    browser.close()
print(json.dumps({'studio':'passed','keyframes':'passed','trim':'passed','save_reload_cancel':'passed','comfy_render':prompt_id,'errors':errors},indent=2))

import json
import sys
import uuid
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support import ROOT
from mariotyport.project import default_project, layer

project = default_project(duration=6)
project['layers'] = []
for text, preset, start, end, color in [
    ('MAKE\nIT MATTER', 'Line reveal', 0, 2.2, '#FFFFFF'),
    ('MOVE WITH\nPURPOSE', 'Word cascade', 2.0, 4.2, '#DEFF4A'),
    ('MARIOTYPORT', 'Scale impact', 4.0, 6, '#FFFFFF'),
]:
    item = layer(text, 'Black', preset, 6)
    item.update(start=start, end=end, enter=.65, exit=.25, color=color, size=.48,
                width=.90, height=.78, shadow_opacity=.3)
    project['layers'].append(item)
project['background'] = '#14181C'
destination = ROOT / 'examples'
destination.mkdir(exist_ok=True)
(destination / 'promo_project.json').write_text(json.dumps(project, indent=2), encoding='utf-8')
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8194')
    page.wait_for_function("Boolean(window.app && window.LiteGraph?.registered_node_types.MarioTyport)", timeout=60000)
    page.evaluate("""project=>{app.graph.clear();window.node=LiteGraph.createNode('MarioTyport');node.pos=[150,80];app.graph.add(node);
        node.widgets.find(w=>w.name==='project_json').value=JSON.stringify(project);
        node.widgets.find(w=>w.name==='duration').value=6;
    }""", project)
    for name, format in [('01 - Transparent typography.json','Transparent MOV'),('02 - Typography MP4.json','MP4 composite')]:
        page.evaluate("value=>node.widgets.find(w=>w.name==='format').value=value",format)
        graph=page.evaluate('app.graph.serialize()')
        (destination/name).write_text(json.dumps(graph,indent=2),encoding='utf-8')
    browser.close()
print(destination)

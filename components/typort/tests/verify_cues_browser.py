import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1600, 'height': 1050})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))

    def route(request):
        path = root / 'web' / urlparse(request.request.url).path.lstrip('/')
        if path.is_file():
            request.fulfill(path=str(path))
        else:
            request.fulfill(status=404, body='Not found')

    page.route('http://mariotyport.test/**', route)
    page.goto('http://mariotyport.test/editor.html')
    page.evaluate('''()=>{
        window.p=MarioType.makeProject('ORIGINAL','Black','Line reveal',8);
        p.layers[0].start=4;
        p.audio={...MarioType.makeAudio(),trim_end:8,analysis:{duration:8,bpm:120,beats:[.5,1,1.5,2,2.5,3,3.5,4,4.5,5,5.5,6,6.5,7,7.5],
            waveform:[.2,.8,.3,.9],channels:{Mix:{hits:[.25,1.25,2.25,3.25],levels:[]},Drums:{hits:[.75,2.75,4.75,6.75],levels:[]}}}};
        const cues=MarioTextCues.generate(p,{every:4,fps:30});
        if(JSON.stringify(cues)!==JSON.stringify([{start:.5,end:2.5},{start:2.5,end:4.5},{start:4.5,end:6.5},{start:6.5,end:8}]))throw Error('Beat grouping');
        const hits=MarioTextCues.generate(p,{mode:'Hits',source:'Drums',every:1,fps:60});
        if(hits[0].start!==.75||hits[0].end!==2.75)throw Error('Instrument hits');
        const shifted=structuredClone(p);Object.assign(shifted.audio,{trim_start:2,trim_end:6,start:1});
        const shiftedCues=MarioTextCues.generate(shifted,{every:2,fps:30});
        if(shiftedCues[0].start!==1||shiftedCues.at(-1).end!==5)throw Error('Trim mapping');
        const silent=structuredClone(p);silent.audio.analysis.beats=[];
        if(MarioTextCues.generate(silent).length)throw Error('Silence');
        window.addEventListener('message',e=>{if(e.data.type==='mariotyport-apply')window.saved=e.data.project;});
        window.postMessage({type:'mariotyport-init',project:p,options:{width:1280,height:720,fps:30,motion_blur:'Off'}},location.origin);
    }''')
    page.locator('#generateCues').click()
    assert page.locator('#analysisDevice').is_disabled()
    page.locator('#analysisMode').select_option('stems')
    assert page.locator('#analysisDevice').is_enabled()
    page.locator('#analysisDevice').select_option('cuda')
    page.locator('#analysisMode').select_option('mix')
    assert page.locator('#analysisDevice').is_disabled()
    assert page.locator('.text-cue').count() == 4
    page.locator('.text-cue').first.click()
    assert page.locator('#text').input_value() == 'YOUR TEXT'
    page.locator('#text').fill('ON THE BEAT')
    page.locator('#text').dispatch_event('change')
    assert page.locator('.text-cue').count() == 3
    assert page.locator('.layer-row').count() == 2
    page.locator('#showCues').uncheck()
    assert page.locator('.text-cue').count() == 0
    page.locator('#undo').click()
    assert page.locator('.text-cue').count() == 3
    page.locator('#generateCues').scroll_into_view_if_needed()
    page.screenshot(path=str(root / 'artifacts' / 'text_cues_desktop.png'))
    page.locator('#apply').click()
    page.wait_for_function('Boolean(window.saved)')
    saved = page.evaluate('saved')
    assert saved['layers'][0]['text'] == 'ORIGINAL'
    assert saved['layers'][1]['text'] == 'ON THE BEAT'
    assert (saved['layers'][1]['start'], saved['layers'][1]['end']) == (.5, 2.5)
    assert len(saved['text_cues']) == 3
    page.evaluate("p=>window.postMessage({type:'mariotyport-init',project:p,options:{}},location.origin)", saved)
    page.wait_for_timeout(300)
    assert page.locator('.text-cue').count() == 3
    page.locator('#cueAction').select_option('selected')
    page.locator('.text-cue').first.click()
    assert page.locator('.layer-row').count() == 2
    assert page.locator('#text').input_value() == 'ON THE BEAT'
    assert page.locator('[data-field="start"]').input_value() == '2.5'
    page.locator('#undo').click()
    page.locator('#audioStart').fill('1')
    page.locator('#audioStart').dispatch_event('change')
    assert page.locator('.text-cue').count() == 0
    assert page.locator('.layer-row').count() == 2
    page.set_viewport_size({'width':390,'height':844})
    page.locator('#generateCues').scroll_into_view_if_needed()
    page.screenshot(path=str(root / 'artifacts' / 'text_cues_mobile.png'))
    assert not errors, errors
    browser.close()
print(json.dumps({'cue_generation':'passed','instrument_hits':'passed','trim_mapping':'passed',
                  'create_text':'passed','undo_visibility':'passed','save_reload':'passed'}))

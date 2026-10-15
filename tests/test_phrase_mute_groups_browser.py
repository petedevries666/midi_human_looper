#!/usr/bin/env python3
"""Real Chromium phrase options -> guarded native save -> runtime groups."""
import json,os,urllib.request,time
from pathlib import Path
from playwright.sync_api import sync_playwright
from test_phrase_mute_groups import Groups
from test_conductor_persistence import step,block
import conductor
Groups.setUpClass();api=Groups('test_source_groups_roundtrip_and_warning')
try:
    api.setUp()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu'])
        page=browser.new_page(viewport={'width':1366,'height':768})
        page.route('**/conductor.js',lambda route:(time.sleep(.7),route.continue_()))
        page.goto(api.base)
        page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
        assert page.locator('#error').inner_text()=='','delayed editor script must not race initial telemetry'
        page.unroute('**/conductor.js')
        def group(phrase,value):
            page.locator(f'[data-phrase-id="{phrase}"]').get_by_role('button',name='PHRASE OPTIONS',exact=True).click()
            control=page.get_by_role('spinbutton',name=f'MUTE GROUP Phrase {phrase}',exact=True)
            api.wait_for(lambda:not control.is_disabled(),'source metadata loaded')
            control.fill(str(value));page.get_by_role('button',name='SET GROUP',exact=True).click()
            page.get_by_text('GROUP SAVED',exact=True).wait_for()
            page.locator('#editor').get_by_role('button',name='CANCEL',exact=True).click()
        group(1,7);group(2,7)
        page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
        loaded=json.load(urllib.request.urlopen(api.base+'/api/v1/conductor'));model=loaded['model']
        assert model['version']==3 and [s['muteGroup'] for s in model['sources'][:3]]==[7,7,0]
        for phrase in (1,2):
            page.locator(f'[data-phrase-id="{phrase}"] [data-phrase-play]').click()
            api.wait_for(lambda:[v['phraseId'] for v in api.call()['instances']]==[phrase],'browser triggers real native group')
        api.command('panic')
        model['switches']=[dict(switchId=1,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',steps=[step([block(model['sources'][1]['id']),block(model['sources'][0]['id'])])])]
        api.command('conductor_commit',conductor=model)
        page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
        page.locator('[data-switch-id="1"]').get_by_role('button',name='CONDUCTOR',exact=True).click()
        page.get_by_text('GROUP 7 · PHRASE 1 wins',exact=True).wait_for()
        evidence=Path(__file__).resolve().parents[1]/'docs/screenshots/mute-groups';evidence.mkdir(parents=True,exist_ok=True)
        for width,height in ((320,240),(800,480),(1440,900)):
            page.set_viewport_size(dict(width=width,height=height))
            page.get_by_text('GROUP 7 · PHRASE 1 wins',exact=True).scroll_into_view_if_needed()
            page.wait_for_timeout(150)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'horizontal overflow'
            page.screenshot(path=str(evidence/f'step-warning-{width}x{height}.png'))
        page.set_viewport_size(dict(width=1366,height=768))
        page.locator('.conductor-editor').get_by_role('button',name='CANCEL',exact=True).click()
        group(2,0)
        page.locator('[data-switch-id="1"]').get_by_role('button',name='CONDUCTOR',exact=True).click()
        assert page.locator('.conductor-group-warning').count()==0,'warnings must recompute after source edit'
        page.locator('.conductor-editor').get_by_role('button',name='CANCEL',exact=True).click()
        api.patch('save');api.patch('load');page.reload()
        restored=json.load(urllib.request.urlopen(api.base+'/api/v1/conductor'))['model']
        assert [s['muteGroup'] for s in restored['sources'][:2]]==[7,0]
        assert not api.call()['instances']
        browser.close()
    print('PASS actual browser source MUTE GROUP editing, native playback, smallest-ID warning, warning refresh and SAVE/LOAD')
finally:Groups.tearDownClass()

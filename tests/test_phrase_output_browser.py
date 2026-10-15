"""Real Chromium -> API -> native configuration -> SAVE/LOAD + original SMF.
Actual emitted channel data is separately verified by the shared-EEL fixture.
"""
import os
import subprocess
import sys
import base64
import json
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from test_native_free_capture import FreeCapture
from phrase_midi import write_smf
api=FreeCapture('runTest');api.setUpClass()
try:
    api.command('panic')
    assert all(p['outputChannel']==0 for p in api.call()['phrases'])
    raw=write_smf(dict(lengthSeconds=.3,bpm=120,events=[[0,149,60,91],[.15,133,60,19]]))
    state=api.call()
    body=dict(file=base64.b64encode(raw).decode(),phraseId=4,mode='replace',expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'])
    req=urllib.request.Request(api.base+'/api/v1/phrase/midi',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=5) as response:assert response.status==200
    original=api.export(4)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu'])
        page=browser.new_page(viewport={'width':800,'height':480});page.goto(api.base)
        row=page.locator('[data-phrase-id="4"]');row.get_by_role('button',name='PHRASE OPTIONS',exact=True).click()
        output=page.get_by_label('OUTPUT CHANNEL Phrase 4',exact=True)
        assert output.locator('option').all_text_contents()==['ORIGINAL','ALL',*[f'CH{i}' for i in range(1,17)]]
        for value in ('16','0','17','3'):
            output.select_option(value)
            api.wait_for(lambda:api.call()['phrases'][3]['outputChannel']==int(value),'browser channel reaches actual engine')
            expect(output).to_be_enabled()
        assert api.call()['phrases'][4]['outputChannel']==0
        api.patch('save');api.command('phrase_output',phraseId=4,channel=17);api.patch('load')
        assert api.call()['phrases'][3]['outputChannel']==3
        assert api.export(4)==original,'playback routing modified recorded/source SMF'
        page.reload();row=page.locator('[data-phrase-id="4"]');row.get_by_role('button',name='PHRASE OPTIONS',exact=True).click()
        assert page.get_by_label('OUTPUT CHANNEL Phrase 4',exact=True).input_value()=='3'
        dest=Path(os.environ.get('PHRASE_OUTPUT_SCREENSHOT','/tmp/phrase-output-options.png'))
        page.screenshot(path=str(dest));browser.close()
    before=api.call()['revision']
    for channel in (-1,18,True,1.5):api.command('phrase_output',phraseId=4,channel=channel,expected=400)
    assert api.call()['revision']==before
    # A restarted Web worker reloads state from the live engine, not a UI cache.
    api.stop_web();api.start_web()
    assert api.call()['phrases'][3]['outputChannel']==3
    api.stop_web();api.engine.terminate();api.engine.communicate(timeout=5)
    api.engine=subprocess.Popen([os.environ['HEADLESS_BINARY'],str(Path(__file__).resolve().parents[1]/'midi_human_looper.jsfx'),api.sock,'--chain'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    api.wait_for(lambda:Path(api.sock).exists(),'restarted native engine');api.start_web();api.patch('load')
    restored=api.call();assert restored['phrases'][3]['outputChannel']==3 and not restored['instances'] and not restored['chainRunning']
    assert api.export(4)==original
    print('PASS real Chromium selection, native state, independent phrases, SAVE/LOAD, source SMF identity, reload/reconnect/native restart without autoplay and invalid-channel refusal')
finally:
    api.tearDownClass()

#!/usr/bin/env python3
"""Real engine/controller/API and Chromium edges; mock clock, not hardware proof."""
import os,socket,subprocess,tempfile,time
from pathlib import Path
from playwright.sync_api import sync_playwright
from test_headless_mvp import HeadlessTests,BINARY,ROOT
class Held(HeadlessTests):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='mbmf-held-');cls.sock=str(Path(cls.temp.name)/'engine.sock')
        cls.engine=subprocess.Popen([BINARY,str(ROOT/'midi_human_looper.jsfx'),cls.sock,'--demo','--chain','--chain-timing','2'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        cls.wait_for(lambda:Path(cls.sock).exists(),'engine')
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1]
        cls.base='http://127.0.0.1:'+str(cls.port);cls.start_web()
Held.setUpClass();api=Held('test_real_engine_and_fifo')
try:
    api.command('panic');state=api.call()
    assert state['nativePhraseContract']==2 and not state['nativeHeldRelease']
    api.command('parameter_set',targetId=1,kind=20,value=2)
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu'])
        page=browser.new_page(viewport={'width':1366,'height':768});page.goto(api.base)
        page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
        trigger=page.locator('[data-phrase-id="1"] [data-phrase-play]')
        trigger.wait_for();assert not trigger.is_disabled()
        before=api.call()['midiCount'];trigger.click()
        api.wait_for(lambda:api.call()['activeNotes']>0,'pointer PRESS sustained actual notes')
        assert api.call()['midiCount']>before
        page.wait_for_timeout(300);assert api.call()['activeNotes']>0,'pointer RELEASE must not stop HOLD'
        before=api.call()['midiCount'];trigger.click()
        api.wait_for(lambda:api.call()['midiCount']>before,'second PRESS cuts and restarts')
        assert len(api.call()['instances'])==1,'direct HOLD replaces its own occurrence'
        trigger.focus();before=api.call()['midiCount'];page.keyboard.press('Space')
        api.wait_for(lambda:api.call()['midiCount']>before,'keyboard PRESS retrigger')
        assert api.call()['activeNotes']>0,'keyboard RELEASE ignored'
        api.command('phrase_stop',phraseId=1)
        api.wait_for(lambda:api.call()['activeNotes']==0,'explicit source STOP cleanup')
        api.command('phrase_learn',phraseId=1)
        api.command('midi',channel=4,note=99,value=100)
        api.wait_for(lambda:api.call()['controllerLearn']['target']==0,'phrase Learn completion')
        api.command('midi',channel=4,note=99,value=0)
        before=api.call()['midiCount'];api.command('midi',channel=4,note=99,value=100)
        api.wait_for(lambda:api.call()['activeNotes']>0,'learned MIDI PRESS')
        assert api.call()['midiCount']>before
        api.command('midi',channel=4,note=99,value=0)
        assert api.call()['activeNotes']>0,'learned velocity-zero RELEASE ignored'
        before=api.call()['midiCount'];api.command('midi',channel=4,note=99,value=100)
        api.wait_for(lambda:api.call()['midiCount']>before,'learned MIDI retrigger')
        assert len(api.call()['instances'])==1
        api.command('panic');assert api.call()['activeNotes']==0
        browser.close()
    print('PASS M0 latched HOLD: pointer/keyboard retrigger, ignored RELEASE, learned MIDI, source STOP and PANIC')
finally:Held.tearDownClass()

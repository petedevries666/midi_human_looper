#!/usr/bin/env python3
"""Real editor controls and native phrase playback, including release during HTTP PRESS."""
import os,time
from playwright.sync_api import sync_playwright
from test_headless_mvp import HeadlessTests

HeadlessTests.setUpClass()
case=HeadlessTests()
try:
    for instrument in case.call()['instruments']:
        for module in instrument['transformers']:
            case.command('module_structure',instrumentId=instrument['id'],moduleId=module['id'],operation='delete')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
        page=browser.new_page();page.goto(case.base)
        mode=page.get_by_label('Play mode Phrase 1',exact=True);mode.wait_for();mode.select_option('3')
        case.wait_for(lambda:case.call()['phrases'][0]['playbackPolicy']==1,'browser NO RETRIGGER mode')
        trigger=page.locator('[data-phrase-id="1"]').get_by_role('button',name='TRIGGER',exact=True)
        trigger.click();case.wait_for(lambda:case.call()['activeNotes']>0,'first browser PRESS')
        trigger.click();case.wait_for(lambda:case.call()['activeNotes']==0,'second browser PRESS stops')
        mode.select_option('4');case.wait_for(lambda:case.call()['phrases'][0]['playbackPolicy']==2,'browser held mode')
        page.wait_for_timeout(100)
        trigger.focus();page.keyboard.down('Space')
        case.wait_for(lambda:case.call()['activeNotes']>0,'keyboard PRESS starts phrase')
        before=case.call()['midiCount'];page.wait_for_timeout(600)
        assert case.call()['midiCount']>before,'source loops while keyboard trigger is held'
        page.keyboard.up('Space');case.wait_for(lambda:case.call()['activeNotes']==0,'keyboard RELEASE stops')
        box=trigger.bounding_box();page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
        before=case.call()['midiCount'];page.mouse.down();page.mouse.up()
        case.wait_for(lambda:case.call()['midiCount']>=before+2,'short browser tap dispatches both PRESS and RELEASE')
        case.wait_for(lambda:case.call()['activeNotes']==0,'short browser tap never loses release behind pending HTTP')
        browser.close()
    print('PASS Chromium mode selection, toggle STOP, held looping, keyboard release and short pointer tap')
finally:
    case.command('panic');HeadlessTests.tearDownClass()

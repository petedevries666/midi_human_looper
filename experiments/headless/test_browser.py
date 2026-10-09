#!/usr/bin/env python3
"""Optional real browser smoke test; Firefox is the default target."""
import os
import time
from playwright.sync_api import sync_playwright
from test_headless import HeadlessTests

HeadlessTests.setUpClass()
api=HeadlessTests('test_real_engine_and_fifo')
try:
    api.command('panic')
    with sync_playwright() as p:
        engine=os.environ.get('MIDI_BROWSER','firefox')
        if engine=='firefox':
            browser=p.firefox.launch(headless=True)
        elif engine=='chromium':
            browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
        else:
            raise ValueError('MIDI_BROWSER must be firefox or chromium')
        page=browser.new_page(viewport=dict(width=1040,height=1100))
        errors=[]
        page.on('pageerror',lambda error: errors.append(str(error)))
        page.goto(HeadlessTests.base)
        page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
        assert page.locator('.phrase').count()==16
        assert page.locator('.instrument').count()==3
        assert page.locator('.switch').count()==4
        assert page.locator('[data-switch-id="3"] .tests button').first.is_disabled()
        before=api.call()
        page.locator('[data-switch-id="1"]').get_by_role('button',name='TEST TAP',exact=True).click()
        page.wait_for_timeout(600)
        assert api.call()['midiCount']>before['midiCount']
        page.get_by_role('button',name='PANIC',exact=True).click()
        page.wait_for_timeout(100)
        assert api.call()['activeNotes']==0
        page.locator('[data-switch-id="2"]').get_by_role('button',name='SIMULATE FOOTSWITCH',exact=True).click()
        page.wait_for_timeout(80)
        assert api.call()['lastEvent'][2]==64
        page.set_viewport_size(dict(width=420,height=900))
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.locator('.instrument').count()==3
        page.screenshot(path=os.environ.get('BROWSER_SCREENSHOT','/tmp/midi-headless-browser.png'),full_page=True)
        # Browser remains open while the independent web worker disappears/restarts.
        page.get_by_role('button',name='PANIC',exact=True).click()
        page.locator('[data-switch-id="1"]').get_by_role('button',name='TEST TAP',exact=True).click()
        before=api.call()
        HeadlessTests.stop_web()
        page.get_by_text('DISCONNECTED · Engine continues independently',exact=True).wait_for()
        HeadlessTests.start_web()
        page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
        after=api.call()
        assert after['engineSessionId']==before['engineSessionId']
        assert after['sampleClock']>before['sampleClock']
        assert after['midiCount']>before['midiCount']
        browser.close()
        # Closing the real browser also leaves the actual JSFX engine playing.
        before=api.call()
        time.sleep(.6)
        after=api.call()
        assert after['sampleClock']>before['sampleClock']+24000
        assert after['midiCount']>before['midiCount']
        assert not errors,errors
        api.command('panic')
        print(f'PASS: {engine} rendering, TEST, simulated switch, PANIC, responsive layout, reconnect and browser unplug')
finally:
    HeadlessTests.tearDownClass()

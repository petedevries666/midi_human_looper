#!/usr/bin/env python3
"""Real browser local-file preview, CANCEL, replacement and MIDI download."""
import os,sys
from playwright.sync_api import sync_playwright
from test_headless_mvp import HeadlessTests
from test_phrase_midi import fixture
from phrase_midi import read_smf
HeadlessTests.setUpClass();api=HeadlessTests('test_real_engine_and_fifo')
try:
    api.command('panic')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':480,'height':800});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(api.base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
        row=page.locator('[data-phrase-id="4"]');row.get_by_role('button',name='PHRASE OPTIONS',exact=True).click()
        page.get_by_label('MIDI file',exact=True).set_input_files({'name':'reaper-style.mid','mimeType':'audio/midi','buffer':fixture()})
        page.get_by_role('button',name='REPLACE PHRASE',exact=True).wait_for()
        page.get_by_role('button',name='CANCEL',exact=True).click()
        assert api.call()['phrases'][3]['events']==0
        row.get_by_role('button',name='PHRASE OPTIONS',exact=True).click()
        page.get_by_label('MIDI file',exact=True).set_input_files({'name':'reaper-style.mid','mimeType':'audio/midi','buffer':fixture()})
        page.get_by_role('button',name='REPLACE PHRASE',exact=True).click()
        page.locator('#editor').wait_for(state='hidden');assert api.call()['phrases'][3]['events']==6
        row.get_by_role('button',name='PHRASE OPTIONS',exact=True).click()
        with page.expect_download() as downloaded:page.get_by_role('button',name='EXPORT MIDI',exact=True).click()
        result=downloaded.value;assert result.suggested_filename=='mbmf-phrase-04.mid'
        from pathlib import Path
        assert read_smf(Path(result.path()).read_bytes())['noteCount']==3
        page.keyboard.press('Escape');assert not errors,errors
        browser.close();print('PASS browser MIDI preview/CANCEL/replace and actual standard MIDI download')
finally:HeadlessTests.tearDownClass()

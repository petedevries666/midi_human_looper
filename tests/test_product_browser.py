#!/usr/bin/env python3
"""Compact editor workflow against the native engine, including confirmation."""
import os
from playwright.sync_api import sync_playwright
from test_headless_mvp import HeadlessTests
HeadlessTests.setUpClass();api=HeadlessTests('test_real_engine_and_fifo')
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
        page=browser.new_page(viewport={'width':480,'height':800});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(HeadlessTests.base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
        assert page.locator('.phrase').count()==6
        assert not page.locator('#controller-section').evaluate('(e)=>e.open')
        row=page.locator('[data-instrument-id="1"]')
        row.get_by_label('VOLUME',exact=True).fill('68');row.get_by_label('VOLUME',exact=True).press('Tab')
        page.wait_for_function('latest.instruments[0].level===68')
        assert api.call()['instruments'][1]['level']==127
        confirmations=[]
        def reject(dialog):confirmations.append(dialog.message);dialog.dismiss()
        page.on('dialog',reject);row.get_by_role('button',name='×',exact=True).click()
        assert confirmations and len(api.call()['instruments'])==3
        page.remove_listener('dialog',reject);page.on('dialog',lambda dialog:dialog.accept())
        row.get_by_role('button',name='×',exact=True).click();row.wait_for(state='detached')
        assert [i['id'] for i in api.call()['instruments']]==[2,3]
        page.get_by_role('button',name='ADD INSTRUMENT',exact=True).click()
        page.locator('[data-instrument-id="4"]').wait_for()
        phrase=page.locator('[data-phrase-id="2"]')
        phrase.get_by_role('button',name='TRIGGER LEARN',exact=True).click()
        phrase.get_by_role('button',name='CANCEL LEARN',exact=True).wait_for()
        api.command('midi',channel=2,note=94,value=100);api.command('midi',channel=2,note=94,value=0)
        phrase.get_by_role('button',name='LEARN · CH2 N94',exact=True).wait_for()
        assert api.call()['phrases'][1]['triggerNote']==94
        page.get_by_role('button',name='+ CAPTURE SNAPSHOT',exact=True).click()
        page.locator('[data-snapshot-id]').first.wait_for()
        assert not errors,errors
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        browser.close();print('PASS compact editor: six phrases, inline instance isolation, confirmed deletion, stable replacement ID, shared Phrase Learn and Snapshot capture')
finally:HeadlessTests.tearDownClass()

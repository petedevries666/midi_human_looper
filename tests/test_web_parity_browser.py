"""Actual Chromium naming, keyboard editing, persistence and compact controls."""
import os
from playwright.sync_api import sync_playwright
from test_headless_mvp import HeadlessTests
HeadlessTests.setUpClass();api=HeadlessTests('test_real_engine_and_fifo')
try:
    api.command('panic')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
        page=browser.new_page(viewport=dict(width=1366,height=768));errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(api.base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
        page.locator('#app-version').get_by_text('V 1.27.1',exact=True).wait_for()
        assert page.locator('h1').inner_text().replace('\n',' ')=='MIDI BAD MOTHERFUCKER'
        page.get_by_role('button',name='Edit Phrase 1 name',exact=True).click()
        field=page.get_by_role('textbox',name='Phrase 1 name',exact=True)
        field.fill('CANCELLED');field.press('Escape')
        assert api.call()['phrases'][0]['name']==''
        page.get_by_role('button',name='Edit Phrase 1 name',exact=True).click()
        field=page.get_by_role('textbox',name='Phrase 1 name',exact=True)
        field.fill('VERSE');field.press('Enter')
        page.get_by_role('button',name='Edit Phrase 1 name',exact=True).get_by_text('VERSE',exact=True).wait_for()
        assert api.call()['phrases'][0]['name']=='VERSE'
        assert api.call()['phrases'][1]['name']==''
        page.get_by_role('button',name='Edit Instrument 2 name',exact=True).click()
        field=page.get_by_role('textbox',name='Instrument 2 name',exact=True)
        field.fill('PIANO');field.press('Enter')
        page.get_by_role('button',name='Edit Instrument 2 name',exact=True).get_by_text('PIANO',exact=True).wait_for()
        assert api.call()['instruments'][1]['name']=='PIANO'
        page.get_by_label('Play mode Phrase 1',exact=True).select_option('1')
        page.get_by_role('button',name='SAVE PATCH',exact=True).click()
        page.get_by_text('PATCH SAVED',exact=True).wait_for()
        api.command('phrase_rename',phraseId=1,name='OTHER')
        page.get_by_role('button',name='Edit Phrase 1 name',exact=True).get_by_text('OTHER',exact=True).wait_for()
        page.get_by_role('button',name='LOAD PATCH',exact=True).click()
        page.get_by_text('PATCH LOADED',exact=True).wait_for()
        assert api.call()['phrases'][0]['name']=='VERSE'
        page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
        page.get_by_role('button',name='Edit Phrase 1 name',exact=True).get_by_text('VERSE',exact=True).wait_for()
        assert not page.get_by_label('Play mode Phrase 1',exact=True).is_disabled()
        assert page.locator('.phrase').count()==6
        for width in (320,800,1366,1440):
            page.set_viewport_size(dict(width=width,height=768))
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
        assert not errors,errors
        browser.close()
        print('PASS real browser: persistent isolated rename, Enter/Escape, reconnect, mode controls, signature and responsive rows')
finally:HeadlessTests.tearDownClass()

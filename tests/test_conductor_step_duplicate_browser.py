"""Production editor and native commit, without JACK, hardware or screenshots."""
import json
import os
from pathlib import Path
import urllib.request
from playwright.sync_api import sync_playwright, expect
from test_conductor_execution_native import Execution
from test_conductor_editor_browser import save_draft

api=Execution('test_steps_coexist_wrap_capacity_and_persistence')
api.setUpClass()
try:
    api.setUp();api.commit()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu'])
        page=browser.new_page(viewport={'width':1440,'height':900})
        page.goto(api.base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
        tune=page.get_by_label('Tune Phrase 1',exact=True)
        expect(tune).to_be_enabled(timeout=30000)
        assert tune.input_value()=='0' and tune.get_attribute('min')=='-24' and tune.get_attribute('max')=='24'
        tune.fill('12');tune.press('Tab')
        expect(tune).to_have_value('12')
        expect(tune).to_be_enabled(timeout=30000)
        page.locator('[data-switch-id="1"]').get_by_role('button',name='CONDUCTOR',exact=True).click()
        page.locator('.conductor-editor').wait_for()
        first=page.locator('.conductor-step').first
        repeat=page.get_by_label('REPEAT STEP 1',exact=True)
        expect(repeat).to_have_value('1')
        first.get_by_role('button',name='INCREASE REPEAT STEP 1',exact=True).click()
        first.get_by_role('button',name='INCREASE REPEAT STEP 1',exact=True).click()
        expect(repeat).to_have_value('3')
        first.get_by_role('button',name='SUPERCHARGE STEP 1',exact=True).click()
        assert page.get_by_text('SUPERCHARGE · STEP 1',exact=True).is_visible()
        page.get_by_role('button',name='CLOSE PROPERTIES',exact=True).click()
        first.get_by_role('button',name='Add PHRASE STEP 1 LAYER 2',exact=True).click()
        first.get_by_role('button',name=__import__('re').compile('^PHRASE 02 ·')).click()
        first.get_by_role('button',name='EDIT BLOCK',exact=True).first.click()
        assert page.get_by_label('TUNE inheritance',exact=True).input_value()=='INHERIT'
        assert page.get_by_label('TUNE override',exact=True).input_value()=='12'
        page.get_by_label('TUNE inheritance',exact=True).select_option('OVERRIDE')
        page.get_by_label('TUNE override',exact=True).fill('-12')
        page.get_by_label('TUNE override',exact=True).press('Tab')
        page.get_by_label('VEL inheritance',exact=True).select_option('OVERRIDE')
        page.get_by_label('VEL override',exact=True).fill('0.5')
        page.get_by_label('VEL override',exact=True).press('Tab')
        original=first.get_attribute('data-step-id')
        ids=first.locator('[data-layer-id],[data-block-id]').evaluate_all('(els)=>els.flatMap(e=>[e.dataset.layerId,e.dataset.blockId].filter(Boolean))')
        page.keyboard.down('Alt')
        try:first.locator('.conductor-step-header').drag_to(page.locator('.conductor-step').nth(2).locator('.conductor-step-header'))
        finally:page.keyboard.up('Alt')
        copy=page.locator('.conductor-step').nth(2)
        assert copy.get_attribute('data-step-id')!=original
        assert copy.locator('[data-block-id]').count()==2
        copied=copy.locator('[data-layer-id],[data-block-id]').evaluate_all('(els)=>els.flatMap(e=>[e.dataset.layerId,e.dataset.blockId].filter(Boolean))')
        assert not set(ids)&set(copied)
        page.get_by_role('button',name='UNDO',exact=True).click()
        assert page.locator('.conductor-step:not([data-step-position="0"])').count()==4
        page.keyboard.down('Alt')
        try:first.locator('.conductor-step-header').drag_to(page.locator('.conductor-step').last.locator('.conductor-step-header'))
        finally:page.keyboard.up('Alt')
        assert page.locator('.conductor-step[data-step-position="5"]').locator('[data-block-id]').count()==2
        page.get_by_role('button',name='UNDO',exact=True).click()
        first.get_by_role('button',name='DUPLICATE STEP',exact=True).click()
        save_draft(page)
        model=json.load(urllib.request.urlopen(api.base+'/api/v1/conductor'))['model']
        steps=model['switches'][0]['steps']
        assert len(steps)==5
        assert steps[0]['id']!=steps[1]['id']
        assert steps[0]['repeat']==steps[1]['repeat']==3
        for old,new in zip(steps[0]['layers'],steps[1]['layers']):
            assert old['id']!=new['id'] and old['block']['id']!=new['block']['id']
            assert old['block']['sourceId']==new['block']['sourceId']
            assert old['block']['overrides']==new['block']['overrides']
        assert steps[1]['layers'][0]['block']['overrides']['phrase_base_velocity']['value']==.5
        assert model['sources'][0]['tune']==12
        assert steps[1]['layers'][0]['block']['overrides']['phrase_tune']['value']==-12
        assert not api.call()['instances'],'editing must never launch a phrase'
        browser.close()
    print('PASS real editor: ALT step copy, empty-column insertion, touch button, UNDO and native persistence')
finally:
    api.tearDownClass()

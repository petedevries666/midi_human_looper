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
        rate=page.get_by_label('Rate Phrase 1',exact=True)
        expect(rate).to_be_enabled(timeout=30000);expect(rate).to_have_value('1')
        assert rate.get_attribute('min')=='0.1' and rate.get_attribute('max')=='16'
        rate.fill('0.5');rate.press('Tab');expect(rate).to_be_enabled(timeout=30000)
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
        original_step=first.get_attribute('data-step-id')
        first.locator('.conductor-step-header > details > summary').click()
        first.get_by_role('button',name='MOVE STEP RIGHT',exact=True).click()
        assert first.get_attribute('data-step-id')!=original_step
        page.get_by_role('button',name='UNDO',exact=True).click()
        assert first.get_attribute('data-step-id')==original_step
        original_layer=first.locator('[data-layer-id]').first.get_attribute('data-layer-id')
        first.locator('.conductor-layer > details > summary').first.click()
        first.get_by_role('button',name='MOVE LAYER DOWN',exact=True).first.click()
        assert first.locator('[data-layer-id]').first.get_attribute('data-layer-id')!=original_layer
        page.get_by_role('button',name='UNDO',exact=True).click()
        assert first.locator('[data-layer-id]').first.get_attribute('data-layer-id')==original_layer
        first.get_by_role('button',name='EDIT BLOCK',exact=True).first.click()
        assert first.locator('.conductor-layer.is-empty').count()==0
        expect(page.locator('.conductor-editor')).to_have_class(__import__('re').compile('has-inspector'))
        inspector=page.locator('.conductor-properties').bounding_box()
        assert inspector['y']>=0 and inspector['y']<900,'selected block inspector must be visible'
        assert page.locator('.conductor-actions').first.locator('summary').is_visible()
        assert page.get_by_label('TUNE override',exact=True).get_attribute('data-inheritance')=='INHERIT'
        assert page.get_by_label('TUNE override',exact=True).input_value()=='12'
        tune_local=page.get_by_label('TUNE override',exact=True)
        expect(tune_local).to_be_enabled()
        assert page.get_by_label('TUNE inheritance',exact=True).count()==0
        tune_local.fill('12');tune_local.press('Tab')
        expect(tune_local).to_have_attribute('data-inheritance','OVERRIDE')
        tune_local.dblclick()
        expect(tune_local).to_have_attribute('data-inheritance','INHERIT')
        expect(tune_local).to_have_value('12')
        tune_local.fill('-12');tune_local.press('Tab')
        expect(tune_local).to_have_attribute('data-inheritance','OVERRIDE')
        page.get_by_role('button',name='UNDO',exact=True).click()
        first.get_by_role('button',name='EDIT BLOCK',exact=True).first.click()
        expect(tune_local).to_have_attribute('data-inheritance','INHERIT')
        page.get_by_label('TUNE override',exact=True).fill('-12')
        page.get_by_label('TUNE override',exact=True).press('Tab')
        expect(page.get_by_label('RATE override',exact=True)).to_have_attribute('data-inheritance','INHERIT')
        expect(page.get_by_label('RATE override',exact=True)).to_have_value('0.5')
        page.get_by_label('RATE override',exact=True).fill('2')
        page.get_by_label('RATE override',exact=True).press('Tab')
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
        assert model['sources'][0]['rate']==.5
        assert steps[1]['layers'][0]['block']['overrides']['phrase_rate']['value']==2
        assert model['sources'][0]['tune']==12
        assert steps[1]['layers'][0]['block']['overrides']['phrase_tune']['value']==-12
        page.locator('[data-switch-id="1"]').get_by_role('button',name='CONDUCTOR',exact=True).click()
        page.locator('.conductor-step').first.get_by_role('button',name='EDIT BLOCK',exact=True).first.click()
        inherited=page.get_by_label('T.DEC override',exact=True)
        expect(inherited).to_have_attribute('data-inheritance','INHERIT')
        inherited.press('ArrowRight');expect(inherited).to_have_attribute('data-inheritance','OVERRIDE')
        inherited.press('Escape');expect(inherited).to_have_attribute('data-inheritance','INHERIT')
        assert not api.call()['instances'],'editing must never launch a phrase'
        page.get_by_role('button',name='CANCEL',exact=True).click()
        api.command('module_structure',instrumentId=1,operation='add',engineType=3)
        native=api.call()['instruments'][0]
        module=next(m for m in native['transformers'] if m['type']==3)
        card=page.locator(f'.module[data-instrument-id="1"][data-module-id="{module["id"]}"]')
        card.click()
        note_mode=page.get_by_label('NOTE MODE',exact=True)
        expect(note_mode).to_have_value('0')
        note_mode.select_option('1');assert page.evaluate('async()=>await window.mbmfModuleFlush()')
        policy=page.get_by_label('COMPORTEMENT BASS',exact=True)
        expect(policy).to_have_value('0');policy.select_option('2');expect(policy).to_be_enabled(timeout=30000)
        model=json.load(urllib.request.urlopen(api.base+'/api/v1/conductor'))['model']
        assert model['bassPolicies']==[dict(instrumentId=1,moduleId=module['id'],mode=2)]
        assert next(p for p in api.call()['instruments'][0]['transformers'][-1]['parameters'] if p['kind']==11)['value']==1
        page.get_by_role('button',name='CANCEL',exact=True).click()
        expect(page.locator('#editor')).not_to_be_visible()
        assert not json.load(urllib.request.urlopen(api.base+'/api/v1/conductor'))['model'].get('bassPolicies')
        card.click();note_mode.select_option('1');assert page.evaluate('async()=>await window.mbmfModuleFlush()')
        policy.select_option('1');expect(policy).to_be_enabled(timeout=30000)
        page.get_by_role('button',name='DONE',exact=True).click()
        api.patch('save');api.patch('load')
        card.click();expect(policy).to_have_value('1');expect(note_mode).to_have_value('1')
        page.get_by_role('button',name='DONE',exact=True).click()
        assert not api.call()['instances']
        touch=browser.new_context(viewport={'width':360,'height':780},is_mobile=True,has_touch=True)
        mobile=touch.new_page();mobile.goto(api.base)
        mobile.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
        mobile.locator('[data-switch-id="1"]').get_by_role('button',name='CONDUCTOR',exact=True).tap()
        mobile.locator('.conductor-step').first.get_by_role('button',name='EDIT BLOCK',exact=True).first.tap()
        slider=mobile.get_by_label('TUNE override',exact=True);slider.scroll_into_view_if_needed()
        box=slider.bounding_box();x=box['x']+box['width']/2;y=box['y']+box['height']/2
        mobile.touchscreen.tap(x,y);mobile.touchscreen.tap(x,y)
        expect(slider).to_have_attribute('data-inheritance','INHERIT');expect(slider).to_have_value('12')
        assert mobile.evaluate('document.documentElement.scrollWidth<=innerWidth'),'mobile editor must not overflow'
        touch.close()
        # New source modes use actual native metadata and actual keyboard edges.
        mode=page.get_by_label('Play mode Phrase 1',exact=True)
        mode.select_option('3')
        api.wait_for(lambda:api.call()['phrases'][0]['mode']==3,'source GATE committed')
        gate=page.locator('.phrase[data-phrase-id="1"] [data-phrase-play]')
        expect(gate).to_be_enabled();gate.focus();page.keyboard.down('Space')
        api.wait_for(lambda:any(v['phraseId']==1 for v in api.call()['instances']),'real Web GATE press')
        page.keyboard.down('Space')
        assert len([v for v in api.call()['instances'] if v['phraseId']==1])==1,'keyboard repeat cannot stop/retrigger a held GATE'
        page.keyboard.up('Space')
        api.wait_for(lambda:not api.call()['instances'],'real Web GATE release')
        mode.select_option('4');api.wait_for(lambda:api.call()['phrases'][0]['mode']==4,'source RETRIGGER committed')
        expect(gate).to_be_enabled();gate.click();api.wait_for(lambda:bool(api.call()['instances']),'first RETRIGGER')
        first_id=api.call()['instances'][0]['id'];gate.click()
        api.wait_for(lambda:len(api.call()['instances'])==1 and api.call()['instances'][0]['id']!=first_id,'RETRIGGER replaces its previous owner')
        api.command('panic')
        mode.select_option('5');api.wait_for(lambda:api.call()['phrases'][0]['mode']==5,'source TOGGLE committed')
        expect(gate).to_be_enabled();gate.click();api.wait_for(lambda:bool(api.call()['instances']),'TOGGLE start')
        gate.click();api.wait_for(lambda:not api.call()['instances'],'TOGGLE stop')
        api.patch('save');api.patch('load');expect(mode).to_have_value('5')
        stored=json.load(urllib.request.urlopen(api.base+'/api/v1/conductor'))['model']
        assert stored['sources'][0]['playMode']=='TOGGLE'
        browser.close()
    print('PASS real editor: ALT step copy, empty-column insertion, touch button, UNDO and native persistence')
finally:
    api.tearDownClass()

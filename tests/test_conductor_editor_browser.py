#!/usr/bin/env python3
"""Production browser -> guarded C transaction -> actual D native callback."""
import json,os,re,sys
from pathlib import Path
from playwright.sync_api import sync_playwright
from test_conductor_execution_native import Execution

def author_four_steps(page,touch=False):
 page.locator('[data-switch-id="1"]').get_by_role('button',name='CONDUCTOR',exact=True).click()
 page.locator('.conductor-editor').wait_for()
 for i in range(1,5):
  col=page.locator('.conductor-step').nth(i-1)
  getattr(col.get_by_role('button',name=f'Add PHRASE STEP {i} LAYER 1',exact=True),'tap' if touch else 'click')()
  getattr(col.get_by_role('button',name=re.compile(f'^PHRASE {i:02d} ·')),'tap' if touch else 'click')()
 assert page.locator('.conductor-step').count()==5,'next empty STEP must be automatic'

def click_conductor_action(control):
 if not control.is_visible():control.locator('xpath=ancestor::details[1]').locator('summary').click()
 control.click()

def save_draft(page):
 page.locator('#editor').get_by_role('button',name='DONE',exact=True).click()
 page.locator('#editor').wait_for(state='hidden')

if __name__=='__main__':
 api=Execution('test_steps_coexist_wrap_capacity_and_persistence');api.setUpClass()
 try:
  api.setUp()
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu'])
   context=browser.new_context(viewport={'width':1440,'height':900},has_touch=True)
   page=context.new_page();page.goto(api.base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
   page.locator('[data-switch-id="1"]').get_by_role('button',name='CONDUCTOR',exact=True).click();page.locator('.conductor-editor').wait_for();save_draft(page)
   empty_model=json.load(__import__('urllib.request').request.urlopen(api.base+'/api/v1/conductor'))['model']
   assert len(empty_model['switches'][0]['steps'])==1 and not any(l['block'] for l in empty_model['switches'][0]['steps'][0]['layers'])
   assert not api.call()['instances'],'saving EMPTY must not play'
   page.evaluate('()=>{crypto.randomUUID=undefined;}') # LAN HTTP does not provide secure-context randomUUID.
   author_four_steps(page,touch=True)
   # Local override, two populated layers, move/undo and source isolation.
   first=page.locator('.conductor-step').first
   first.get_by_role('button',name='Add PHRASE STEP 1 LAYER 2',exact=True).click()
   first.get_by_role('button',name=re.compile('^PHRASE 02 ·')).click()
   first.get_by_role('button',name='EDIT BLOCK',exact=True).first.click()
   page.get_by_label('VEL override',exact=True).fill('0.5')
   page.get_by_label('VEL override',exact=True).press('ArrowRight')
   assert float(page.get_by_label('VEL override',exact=True).input_value())==.51
   page.get_by_label('VEL override',exact=True).press('ArrowLeft')
   click_conductor_action(first.get_by_role('button',name='MOVE LAYER DOWN',exact=True).first)
   page.get_by_role('button',name='UNDO',exact=True).click()
   click_conductor_action(first.get_by_role('button',name='MOVE STEP RIGHT',exact=True))
   page.get_by_role('button',name='UNDO',exact=True).click()
   click_conductor_action(first.get_by_role('button',name='REMOVE BLOCK',exact=True).nth(1))
   page.get_by_role('button',name='UNDO',exact=True).click()
   # Desktop drag moves the entire STEP; UNDO restores stable IDs and properties.
   original_step=first.get_attribute('data-step-id')
   first.locator('.conductor-step-header').drag_to(page.locator('.conductor-step').nth(2).locator('.conductor-step-header'))
   assert page.locator('.conductor-step').nth(1).get_attribute('data-step-id')==original_step
   page.get_by_role('button',name='UNDO',exact=True).click()
   # Touch/keyboard transfer uses the same block operation, with a new block UUID.
   first.get_by_role('button',name='EDIT BLOCK',exact=True).first.click()
   page.get_by_text('MOVE / REPLACE',exact=True).click()
   target=first.locator('.conductor-layer').nth(1).get_attribute('data-layer-id')
   page.get_by_label('Block destination',exact=True).select_option(target)
   page.get_by_label('Block transfer',exact=True).select_option('DUPLICATE')
   page.get_by_role('button',name='APPLY MOVE',exact=True).click()
   ids=first.locator('[data-block-id]').evaluate_all('(els)=>els.map(e=>e.dataset.blockId)')
   assert len(ids)==2 and ids[0]!=ids[1],'duplicate must reference the source, with a new block identity'
   page.get_by_role('button',name='UNDO',exact=True).click()
   # Preserve four-step-only musical acceptance; extra layer saved later.
   click_conductor_action(first.get_by_role('button',name='REMOVE BLOCK',exact=True).nth(1))
   # Delay the real native commit reply: controls lock, committed data stays exact.
   page.evaluate("""()=>{const original=fetch.bind(window);window.__commitHeld=false;
    window.fetch=async(...args)=>{const body=args[1]?.body?JSON.parse(args[1].body):{};const reply=await original(...args);if(body.action==='conductor_commit'){window.__commitHeld=true;await new Promise(r=>setTimeout(r,500));window.__commitHeld=false;}return reply;};} """)
   page.get_by_role('button',name='DONE',exact=True).click();page.wait_for_function('()=>window.__commitHeld')
   assert page.locator('.conductor-editor button:enabled,.conductor-editor input:enabled,.conductor-editor select:enabled').count()==0
   page.locator('#editor').wait_for(state='hidden')
   model=json.load(__import__('urllib.request').request.urlopen(api.base+'/api/v1/conductor'))['model']
   assert len(model['switches'][0]['steps'])==4
   source_ids=[s['layers'][0]['block']['sourceId'] for s in model['switches'][0]['steps']]
   assert len(set(source_ids))==4 and model['switches'][0]['steps'][0]['layers'][0]['block']['overrides']['phrase_base_velocity']['value']==.5
   assert api.call()['phrases'][0]['baseVelocity']==1
   page.get_by_role('button',name='SAVE PATCH',exact=True).click();page.get_by_text('PATCH SAVED',exact=True).wait_for()
   page.get_by_role('button',name='LOAD PATCH',exact=True).click();page.wait_for_function('()=>!pending')
   assert not api.call()['instances']
   page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
   for i in range(5):
    panel=page.locator('[data-switch-id="1"]');panel.locator('.switch-test').evaluate('e=>e.open=true');panel.get_by_role('button',name='TEST TAP',exact=True).click()
    api.wait_for(lambda:len(api.call()['instances'])==i+1,'actual browser admission')
    assert api.call()['switches'][0]['conductor']['step']==i%4+1
    panel.locator('.switch-test-feedback').filter(has_text=f'STEP {i%4+1} / 4 · ADMITTED 1').wait_for()
   api.command('panic');page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
   # Two independent browser sessions cannot overwrite one another.
   other=context.new_page();other.goto(api.base);other.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
   for p in (page,other):p.locator('[data-switch-id="1"]').get_by_role('button',name='CONDUCTOR',exact=True).click();p.locator('.conductor-editor').wait_for()
   other.locator('.conductor-step').first.get_by_role('button',name='ADD LAYER',exact=True).click();save_draft(other)
   click_conductor_action(page.locator('.conductor-step').first.get_by_role('button',name='DELETE STEP',exact=True))
   page.get_by_role('button',name='DONE',exact=True).click();page.get_by_role('alert').filter(has_text='Configuration changed').wait_for()
   assert page.locator('#editor').is_visible(),'stale draft must stay recoverable'
   page.get_by_role('button',name='CANCEL',exact=True).click()
   # Missing UUID preserved and visible, never rebound to a same slot.
   model=json.load(__import__('urllib.request').request.urlopen(api.base+'/api/v1/conductor'))['model']
   model['sources']=[s for s in model['sources'] if s['id']!=source_ids[0]]
   api.command('conductor_commit',conductor=model)
   page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for();page.locator('[data-switch-id="1"]').get_by_role('button',name='CONDUCTOR',exact=True).click()
   page.locator('.missing-source').wait_for()
   assert page.locator('.missing-source').count()==1
   assert page.locator('.missing-source').inner_text().find(source_ids[0])>=0
   page.keyboard.press('Escape');browser.close()
  print('PASS browser CONDUCTOR: automatic four STEPS, UUID references, layers/move/delete/UNDO, overrides, source isolation, SAVE/LOAD, reconnect, native TEST/wrap, stale-session refusal and missing source preservation')
 finally:api.tearDownClass()

"""Issue #51 hardware workflows through the production HTTP, browser and engine."""
import os,time
from playwright.sync_api import sync_playwright
from test_native_free_capture import FreeCapture
from controller_config import decode
FreeCapture.setUpClass();api=FreeCapture('test_free_capture')
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu'])
  page=browser.new_page(viewport=dict(width=1366,height=768));errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(api.base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  page.locator('#controller-section summary').first.click();page.get_by_role('button',name='ADD CONTROLLER SOURCE',exact=True).click()
  source=decode(api.call()['controllerEngine'])['sources'][0]['id'];card=page.locator(f'[data-source-id="{source}"]')
  card.get_by_role('button',name=f'Edit Controller {source} name',exact=True).click()
  name=card.locator('.name-input');name.fill('');name.press_sequentially('HELIX EXP 1',delay=120)
  assert name.evaluate('(e)=>e===document.activeElement'),'stream refresh must preserve typing focus'
  name.press('Enter');api.wait_for(lambda:decode(api.call()['controllerEngine'])['sources'][0].get('name')=='HELIX EXP 1','source rename')
  card.get_by_role('button',name='EDIT',exact=True).click();page.get_by_label('Controller name',exact=True).fill('PEDAL A');page.get_by_role('button',name='DONE',exact=True).click();page.locator('#editor').wait_for(state='hidden')
  assert decode(api.call()['controllerEngine'])['sources'][0]['name']=='PEDAL A'
  page.once('dialog',lambda d:d.accept());card.get_by_role('button',name='REMOVE',exact=True).click();api.wait_for(lambda:not decode(api.call()['controllerEngine'])['sources'],'targeted source removal')
  # Three real rails aligned horizontally, with one-decimal velocity readout.
  boxes=[page.get_by_role('slider',name=f'{label} Phrase 2',exact=True).bounding_box() for label in ('BASE VEL','VEL DECAY','TIME DECAY')]
  assert max(b['y'] for b in boxes)-min(b['y'] for b in boxes)<2,boxes
  assert [b['x'] for b in boxes]==sorted(b['x'] for b in boxes)
  assert page.locator('[data-phrase-id="2"] .tactile-slider output').first.inner_text()=='×1.0'
  panel=page.locator('[data-instrument-id="1"]')
  for kind in ('1','4'):
   panel.get_by_label('Transformer type for Instrument 1',exact=True).select_option(kind);panel.get_by_role('button',name='ADD TRANSFORMER',exact=True).click()
  panel.locator('.module').first.get_by_role('button',name='EDIT',exact=True).click()
  page.get_by_role('slider',name='SEMITONES',exact=True).fill('12');api.wait_for(lambda:api.call()['instruments'][0]['transformers'][0]['parameters'][0]['value']==12,'immediate module edit')
  rail=page.get_by_role('slider',name='SEMITONES',exact=True);box=rail.bounding_box();page.mouse.move(box['x']+box['width']*.5,box['y']+box['height']/2);page.mouse.down();page.mouse.move(box['x']+box['width']*.75,box['y']+box['height']/2,steps=6)
  value=float(rail.input_value());api.wait_for(lambda:api.call()['instruments'][0]['transformers'][0]['parameters'][0]['value']==value,'MIDI parameter updates while pointer is held')
  assert api.command('midi',channel=1,note=60,value=100)['lastEvent'][2]==60+value;api.command('midi',channel=1,note=60,value=0);page.mouse.up()
  rail.fill('12');api.wait_for(lambda:api.call()['instruments'][0]['transformers'][0]['parameters'][0]['value']==12,'restore transpose')
  panel.locator('.module').nth(1).get_by_role('button',name='EDIT',exact=True).click();page.get_by_role('slider',name='VELOCITY',exact=True).wait_for()
  page.get_by_role('button',name='DONE',exact=True).click();page.locator('#editor').wait_for(state='hidden')
  row=page.locator('[data-phrase-id="1"]');row.get_by_role('button',name='REC / OVERDUB',exact=True).click();api.command('midi',channel=1,note=60,value=100);time.sleep(.15)
  row.get_by_role('button',name='FINISH REC',exact=True).click();page.get_by_role('button',name='PANIC',exact=True).click()
  row.get_by_label('Play mode Phrase 1',exact=True).select_option('0');row.locator('[data-phrase-play]').click();row.get_by_role('button',name='STOP PHRASE',exact=True).wait_for()
  row.get_by_role('button',name='STOP PHRASE',exact=True).click();api.wait_for(lambda:api.call()['activeNotes']==0,'browser STOP owned notes')
  row.get_by_role('button',name='TRIGGER',exact=True).wait_for()
  row.get_by_role('button',name='PHRASE OPTIONS',exact=True).click();page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='CLEAR MIDI',exact=True).click()
  api.wait_for(lambda:api.call()['phrases'][0]['events']==0,'clear inactive source');page.keyboard.press('Escape')
  sw=page.locator('[data-switch-id="1"]');sw.get_by_role('button',name='OPTIONS',exact=True).click()
  page.get_by_label('ENABLED',exact=True).select_option('1');page.get_by_label('TRAVERSAL',exact=True).select_option('2');page.get_by_label('RESET ON RE-ENTRY',exact=True).select_option('1')
  page.get_by_label('Sequence phrase',exact=True).select_option('1');page.get_by_role('button',name='ADD STEP',exact=True).click();page.get_by_label('Sequence phrase',exact=True).select_option('2');page.get_by_role('button',name='ADD STEP',exact=True).click()
  page.get_by_role('button',name='DONE',exact=True).click();page.locator('#editor').wait_for(state='hidden');assert api.call()['switches'][0]['sequence']==[1,2]
  page.get_by_role('button',name='SAVE PATCH',exact=True).click();page.get_by_text('PATCH SAVED',exact=True).wait_for();page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for();assert api.call()['switches'][0]['settings'][9]==2
  page.once('dialog',lambda d:d.dismiss());page.get_by_role('button',name='CLEAR PATCH',exact=True).click();assert api.call()['switches'][0]['sequence']==[1,2]
  page.once('dialog',lambda d:d.accept());page.get_by_role('button',name='CLEAR PATCH',exact=True).click();api.wait_for(lambda:all(not p['events'] for p in api.call()['phrases']),'clear patch')
  assert len(api.call()['instruments'])==3 and not any(i['transformers'] for i in api.call()['instruments'])
  assert not errors,errors;browser.close();print('PASS issue #51: rename focus, EDIT/REMOVE, aligned rails, live module switching, real LOOP STOP/CLEAR, sequencer persistence and confirmed CLEAR PATCH')
finally:FreeCapture.tearDownClass()

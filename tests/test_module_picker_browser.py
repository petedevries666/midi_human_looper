"""Actual native ADD response delayed while the next per-instrument type is chosen."""
import json,os,sys
from playwright.sync_api import sync_playwright
from test_native_free_capture import FreeCapture
FreeCapture.setUpClass();api=FreeCapture('runTest')
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu'])
  page=browser.new_page(viewport=dict(width=1366,height=768));page.goto(api.base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  held=[]
  def delay(route):
   body=route.request.post_data_json
   if body.get('action')=='module_structure' and body.get('engineType')==1 and not held:
    held.append((route,route.fetch())) # real production API/engine, no invented reply
   else:route.continue_()
  page.route('**/api/v1/command',delay)
  panel=page.locator('[data-instrument-id="1"]');picker=panel.get_by_label('Transformer type for Instrument 1',exact=True)
  picker.select_option('1');panel.get_by_role('button',name='ADD TRANSFORMER',exact=True).click()
  for _ in range(100):
   if held:break
   page.wait_for_timeout(10)
  assert held,'actual native ADD response not captured'
  picker.select_option('4');picker.evaluate('e=>e.blur()')
  other=page.get_by_label('Transformer type for Instrument 2',exact=True);other.select_option('6');other.evaluate('e=>e.blur()')
  route,response=held[0];route.fulfill(response=response);page.wait_for_function('()=>!pending')
  # Flush the same real telemetry the response delivers, without a sleep/race.
  page.evaluate('render(latest)')
  selected=picker.input_value();print('PICKER AFTER REAL ACK',json.dumps(dict(selected=selected,other=other.input_value(),nativeTypes=[m['type'] for m in api.call()['instruments'][0]['transformers']])),flush=True)
  assert selected=='4' and other.input_value()=='6','acknowledgement erased an independently selected next type'
  panel.get_by_role('button',name='ADD TRANSFORMER',exact=True).click()
  api.wait_for(lambda:len(api.call()['instruments'][0]['transformers'])==2,'second real module admission')
  assert [m['type'] for m in api.call()['instruments'][0]['transformers']]==[1,4]
  assert not api.call()['instruments'][1]['transformers'],'picker leaked to another instrument'
  page.get_by_role('button',name='SAVE PATCH',exact=True).click();page.get_by_text('PATCH SAVED',exact=True).wait_for()
  page.get_by_role('button',name='LOAD PATCH',exact=True).click();page.wait_for_function('()=>!pending')
  assert [m['type'] for m in api.call()['instruments'][0]['transformers']]==[1,4]
  browser.close();print('PASS actual pending ADD, independent type pickers, correct native module kinds and SAVE/LOAD')
finally:FreeCapture.tearDownClass()

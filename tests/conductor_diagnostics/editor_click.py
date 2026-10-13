"""Real native edit during pointer-down reproduces a lost module click.
Regression: retain the pointer-down target through actual engine telemetry.
"""
import os,sys
from pathlib import Path
if os.environ.get('COMPARE_ROOT'):sys.path.insert(0,str(Path(os.environ['COMPARE_ROOT'])/'tests'))
import json
from playwright.sync_api import sync_playwright
from test_native_free_capture import FreeCapture
api=FreeCapture('runTest');api.setUpClass()
try:
 api.command('panic')
 for kind in (1,4):api.command('module_structure',instrumentId=1,operation='add',engineType=kind)
 module=api.call()['instruments'][0]['transformers'][0]['id']
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-gpu'])
  page=browser.new_page(viewport={'width':1366,'height':768});page.goto(api.base)
  page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  panel=page.locator('[data-instrument-id="1"]')
  panel.locator('.module').first.get_by_role('button',name='EDIT',exact=True).click()
  page.get_by_role('slider',name='SEMITONES',exact=True).wait_for()
  button=panel.locator('.module').nth(1).get_by_role('button',name='EDIT',exact=True)
  button.evaluate('(node)=>window.__pressedEdit=node');box=button.bounding_box()
  page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2);page.mouse.down()
  api.command('parameter_set',targetId=1,moduleId=module,kind=7,value=12)
  page.wait_for_function('()=>latest.instruments[0].transformers[0].parameters[0].value===12')
  assert page.evaluate('window.__pressedEdit.isConnected'),'telemetry detached the pressed target'
  detached=not page.evaluate('window.__pressedEdit.isConnected')
  page.mouse.up()
  # Wait for browser event processing, not for a hoped-for passing condition.
  page.get_by_role('slider',name='VELOCITY',exact=True).wait_for()
  missed=page.get_by_role('slider',name='VELOCITY',exact=True).count()==0
  print('EDITOR CLICK OBSERVATION',json.dumps({'oldButtonDetached':detached,'velocityEditorOpened':not missed,'nativeTranspose':api.call()['instruments'][0]['transformers'][0]['parameters'][0]['value']}),flush=True)
  # Same actual button/action after the observation repaint finishes.
  panel.locator('.module').nth(1).get_by_role('button',name='EDIT',exact=True).click()
  page.get_by_role('slider',name='VELOCITY',exact=True).wait_for()
  print('IDLE EDITOR POSITIVE CONTROL: VELOCITY opened',flush=True)
  browser.close()
 assert not missed,'actual EDIT click was lost'
 print('PASS telemetry preserves pointer target and real EDIT interaction',flush=True)
finally:
 api.tearDownClass()

#!/usr/bin/env python3
"""Real Chromium -> native guarded config -> native runtime, no API mocks."""
import os,sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from test_headless_mvp import HeadlessTests
from playwright.sync_api import sync_playwright
class MovementBrowser(HeadlessTests):
 def test_browser_curve_library_conductor_and_native_execution(self):
  self.command('panic')
  with sync_playwright() as pw:
   browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu'])
   page=browser.new_page(viewport=dict(width=1440,height=900));page.on('pageerror',lambda e:print('PAGEERROR',str(e),flush=True));page.goto(self.base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
   page.locator('#movement-section').evaluate('e=>e.open=true');page.get_by_role('button',name='+ MOVEMENT',exact=True).click();page.locator('.movement-editor').wait_for()
   page.get_by_label('NAME',exact=True).fill('FILTER TEST');page.get_by_label('DURATION s',exact=True).fill('1');page.get_by_label('RETRIGGER',exact=True).select_option('DIRECT');page.get_by_label('CC',exact=True).fill('11')
   page.get_by_role('button',name='ADD POINT',exact=True).click();page.get_by_text('POINTS / PRECISION',exact=True).click();page.get_by_label('Y point 2',exact=True).fill('0.2')
   canvas=page.locator('.movement-editor canvas');box=canvas.bounding_box();page.mouse.move(box['x']+box['width']*.5,box['y']+box['height']*.8);page.mouse.down();page.mouse.move(box['x']+box['width']*.6,box['y']+box['height']*.7);page.mouse.up()
   page.get_by_role('button',name='DONE',exact=True).click();page.locator('#editor').wait_for(state='hidden');assert page.locator('#error').inner_text()=='',page.locator('#error').inner_text()
   model=page.evaluate("fetch('/api/v1/conductor').then(r=>r.json())")['model'];m=model['movements'][0];assert m['name']=='FILTER TEST' and len(m['points'])==3,m
   assert .59<m['points'][1][0]<.61 and .29<m['points'][1][1]<.31,m
   page.locator('#movement-config').evaluate('e=>e.open=true');page.get_by_label('MOVEMENT CC RATE',exact=True).select_option('50');page.wait_for_function("()=>movementModel?.ccRate===50")
   # Preview starts the production runtime; readonly library telemetry must not stop it.
   page.get_by_role('button',name='PREVIEW MOVEMENT FILTER TEST',exact=True).click();page.wait_for_function('()=>latest.movements.active===1');page.evaluate('movementRevision=-1;refreshMovements(latest)');page.wait_for_timeout(250);assert self.call()['movements']['active']==1
   page.get_by_role('button',name='STOP MOVEMENT FILTER TEST',exact=True).click();page.wait_for_function('()=>latest.movements.active===0')
   page.locator('[data-switch-id="1"]').get_by_role('button',name='CONDUCTOR',exact=True).click();page.get_by_role('button',name='Add PHRASE STEP 1 LAYER 2',exact=True).click();page.locator('.conductor-add-menu').get_by_text('MOVEMENTS',exact=True).click();page.get_by_role('button',name='MOVEMENT · FILTER TEST',exact=True).click();page.locator('.conductor-layer').nth(1).get_by_role('button',name='EDIT BLOCK',exact=True).click();page.get_by_label('RETRIGGER inheritance',exact=True).select_option('OVERRIDE');page.get_by_label('RETRIGGER override',exact=True).select_option('DIRECT');page.get_by_role('button',name='DONE',exact=True).click();page.locator('#editor').wait_for(state='hidden')
   page.get_by_role('button',name='SAVE PATCH',exact=True).click();page.get_by_text('PATCH SAVED',exact=True).wait_for();page.get_by_role('button',name='LOAD PATCH',exact=True).click();page.wait_for_function('()=>!pending');page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
   page.locator('[data-switch-id="1"] .switch-test').evaluate('e=>e.open=true');page.locator('[data-switch-id="1"]').get_by_role('button',name='TEST TAP',exact=True).click();page.wait_for_function('()=>latest.movements.active===1');assert self.call()['movements']['rejected']==0
   self.command('panic');page.wait_for_function('()=>latest.movements.active===0');browser.close()
if __name__=='__main__':unittest.main(defaultTest='MovementBrowser.test_browser_curve_library_conductor_and_native_execution')

#!/usr/bin/env python3
"""Existing TEST controls -> real native Conductor callback, no new UI or mocked API."""
import os
from playwright.sync_api import sync_playwright
from test_conductor_execution_native import Execution
api=Execution('test_steps_coexist_wrap_capacity_and_persistence');api.setUpClass()
try:
 api.setUp();api.commit()
 # Manual preview must preserve the existing ability to test without hardware enable.
 sw=api.call()['switches'][0];settings=list(sw['settings']);settings[0]=0;settings[1]=0
 api.command('switch_commit',switchId=1,settings=settings,sequence=[],name='CONDUCTOR')
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu'])
  page=browser.new_page(viewport={'width':1366,'height':768});page.goto(api.base)
  page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  for i in range(4):
   panel=page.locator('[data-switch-id="1"]');panel.locator('.switch-test').evaluate('(e)=>e.open=true')
   panel.get_by_role('button',name='TEST TAP',exact=True).click()
   api.wait_for(lambda:len(api.call()['instances'])==i+1,'manual browser Conductor admission')
   assert api.call()['switches'][0]['conductor']['step']==i+1
  browser.close()
 api.wait_for(lambda:len(api.call()['instances'])==4,'browser disconnect independence')
 api.command('panic');assert not api.call()['instances']
 print('PASS actual Chromium TEST: unassigned/disabled hardware source, four STEPS and concurrent native instances; browser disconnect leaves playback autonomous')
finally:api.tearDownClass()

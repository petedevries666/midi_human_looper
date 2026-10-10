#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
from test_headless_mvp import HeadlessTests
import os,time
HeadlessTests.setUpClass();api=HeadlessTests('test_real_engine_and_fifo')
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1040,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(HeadlessTests.base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  panel=page.locator('[data-instrument-id="1"]');editor=page.locator('#editor');before=api.call()['instruments'][0]['level']
  panel.get_by_role('button',name='EDIT',exact=True).first.click();editor.locator('input[type=number]').last.fill('64');editor.get_by_role('button',name='CANCEL',exact=True).click();assert api.call()['instruments'][0]['level']==before
  panel.get_by_role('button',name='EDIT',exact=True).first.click();page.keyboard.press('Escape');assert not editor.is_visible()
  panel.get_by_role('button',name='EDIT',exact=True).first.click();page.mouse.click(2,2);assert not editor.is_visible()
  panel.get_by_role('button',name='EDIT',exact=True).first.click();editor.locator('input[type=number]').last.fill('64');editor.get_by_role('button',name='DONE',exact=True).click();editor.wait_for(state='hidden');assert api.call()['instruments'][0]['level']==64
  panel.get_by_label('Transformer type for Instrument 1',exact=True).select_option('1');panel.get_by_role('button',name='ADD TRANSFORMER',exact=True).click();panel.locator('.module').wait_for()
  module=panel.locator('.module').first;module.get_by_role('button',name='EDIT',exact=True).click();editor.locator('input[type=number]').fill('12');editor.get_by_role('button',name='DONE',exact=True).click();editor.wait_for(state='hidden')
  assert api.command('midi',channel=1,note=60,value=90)['lastEvent'][2]==72;api.command('midi',channel=1,note=60,value=0)
  module.get_by_role('button',name='EDIT',exact=True).click();editor.locator('input[type=number]').fill('5');api.command('instrument_route',instrumentId=1,field='level',value=70);editor.get_by_role('button',name='DONE',exact=True).click();editor.get_by_text('Configuration changed. CANCEL and reopen this editor.',exact=True).wait_for();editor.get_by_role('button',name='CANCEL',exact=True).click()
  assert api.call()['instruments'][0]['transformers'][0]['parameters'][0]['value']==12
  page.set_viewport_size({'width':420,'height':900});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  assert not errors,errors;browser.close();print('PASS generic browser editor: descriptor rendering, draft DONE/CANCEL/ESC/outside, atomic commit, Transformer output, stale conflict and responsive layout')
finally:HeadlessTests.tearDownClass()

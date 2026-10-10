#!/usr/bin/env python3
import os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from controller_config import decode
from playwright.sync_api import sync_playwright
from test_headless_mvp import HeadlessTests
HeadlessTests.setUpClass();api=HeadlessTests('test_real_engine_and_fifo')
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
  page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(HeadlessTests.base);page.get_by_text('CONTROLLERS / EDITOR / TEST',exact=True).click();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  page.get_by_role('button',name='ADD CONTROLLER SOURCE',exact=True).click()
  page.locator('[data-source-id]').wait_for();source=decode(api.call()['controllerEngine'])['sources'][0]['id']
  page.locator('[data-source-id]').get_by_role('button',name='MIDI LEARN',exact=True).click();page.get_by_text('Waiting for MIDI note or CC…',exact=True).wait_for()
  api.command('midi_cc',channel=2,number=21,value=70);page.get_by_text('CC 21 · CH 2',exact=True).wait_for()
  page.get_by_role('button',name='ADD MAPPING',exact=True).click();editor=page.locator('#editor');editor.wait_for();editor.get_by_role('button',name='ADD POINT',exact=True).click();assert editor.locator('.curve-point').count()==3
  editor.get_by_role('button',name='CANCEL',exact=True).click();assert not decode(api.call()['controllerEngine'])['mappings']
  page.get_by_role('button',name='ADD MAPPING',exact=True).click();editor.get_by_role('button',name='ADD POINT',exact=True).click();editor.get_by_label('Y point 2',exact=True).fill('.8');editor.get_by_label('BEND point 1',exact=True).fill('.2');editor.get_by_role('button',name='DONE',exact=True).click();editor.wait_for(state='hidden')
  mappings=decode(api.call()['controllerEngine'])['mappings'];assert len(mappings)==1 and mappings[0]['points'][1][1]==.8
  api.command('midi_cc',channel=2,number=21,value=64);assert api.call()['instruments'][0]['level']>100
  page.get_by_role('button',name='SAVE PATCH',exact=True).click();page.get_by_text('PATCH SAVED',exact=True).wait_for()
  page.get_by_role('button',name='EXPORT REAPER BASE',exact=True).click();page.get_by_text('EXPORTED patch1-reaper.json',exact=True).wait_for()
  page.get_by_role('button',name='LOAD PATCH',exact=True).click();page.get_by_text('PATCH LOADED',exact=True).wait_for();assert len(decode(api.call()['controllerEngine'])['mappings'])==1
  page.locator('[data-mapping-id]').get_by_role('button',name='EDIT',exact=True).click();page.keyboard.press('Escape');assert not editor.is_visible()
  page.set_viewport_size(dict(width=420,height=900));assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  assert not errors,errors;browser.close();print('PASS Controller browser: Learn, mapping drafts, points/bends, output, persistence, REAPER export, ESC and responsive layout')
finally:HeadlessTests.tearDownClass()

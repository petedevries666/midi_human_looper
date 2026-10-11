"""Real engine/browser direct manipulation and stable parameter isolation."""
import os,time
from playwright.sync_api import sync_playwright
from test_headless_mvp import HeadlessTests
HeadlessTests.setUpClass();api=HeadlessTests('test_real_engine_and_fifo')
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
  page=browser.new_page(viewport=dict(width=1366,height=768));page.goto(api.base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  before=api.call()['instruments'][1]['level']
  slider=page.get_by_role('slider',name='VOLUME Instrument 1',exact=True);slider.scroll_into_view_if_needed();r=slider.bounding_box()
  page.mouse.move(r['x']+r['width']*.5,r['y']+r['height']/2);page.mouse.down();page.mouse.move(r['x']+r['width']*.3,r['y']+r['height']/2,steps=8);page.mouse.up();slider.press('Tab')
  page.wait_for_timeout(400);state=api.call();assert 20<state['instruments'][0]['level']<65,state['instruments'][0]['level'];assert state['instruments'][1]['level']==before
  slider=page.get_by_role('slider',name='VOLUME Instrument 1',exact=True);old=state['instruments'][0]['level'];slider.focus();slider.press('ArrowRight');slider.press('Tab');page.wait_for_timeout(400);assert api.call()['instruments'][0]['level']==old+1
  slider=page.get_by_role('slider',name='VOLUME Instrument 1',exact=True);slider.focus();slider.press('Home');slider.press('Tab');page.wait_for_timeout(300);assert api.call()['instruments'][0]['level']==0
  slider.focus();slider.press('End');slider.press('Tab');page.wait_for_timeout(300);assert api.call()['instruments'][0]['level']==127
  api.command('parameter_set',targetId=1,kind=20,value=1);page.get_by_role('slider',name='TIME DECAY Phrase 1',exact=True).wait_for()
  time_slider=page.get_by_role('slider',name='TIME DECAY Phrase 1',exact=True);time_slider.focus();time_slider.press('End');time_slider.press('Tab');page.wait_for_timeout(300);assert api.call()['phrases'][0]['timeDecay']==2
  time_slider.dblclick();time_slider.press('Tab');page.wait_for_timeout(400);assert api.call()['phrases'][0]['timeDecay']==1
  phrase=page.get_by_role('slider',name='BASE VEL Phrase 1',exact=True);phrase.focus();phrase.press('ArrowRight');phrase.press('Tab');page.wait_for_timeout(400);assert abs(api.call()['phrases'][0]['baseVelocity']-1.01)<.02;assert api.call()['phrases'][1]['baseVelocity']==1
  page.locator('[data-phrase-id="1"]').get_by_role('button',name='MUTE',exact=True).click();page.wait_for_timeout(300);assert api.call()['phrases'][0]['mute']==1;assert api.call()['phrases'][1]['mute']==0
  assert page.locator('[data-phrase-id="1"] .action-icon').count()>4
  page.get_by_role('button',name='SAVE PATCH',exact=True).click();page.get_by_text('PATCH SAVED',exact=True).wait_for();saved=api.call()['instruments'][0]['level'];page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for();assert float(page.get_by_role('slider',name='VOLUME Instrument 1',exact=True).input_value())==saved
  page.locator('[data-instrument-id="1"]').get_by_role('button',name='ADD TRANSFORMER',exact=True).click();page.locator('.transformers .module').first.wait_for();page.locator('.transformers .module').first.get_by_role('button',name='EDIT',exact=True).click();rail=page.locator('#editor input[type=range]').first;old=float(rail.input_value());rail.focus();rail.press('ArrowRight');assert float(rail.input_value())!=old;page.get_by_role('button',name='DONE',exact=True).click();page.locator('#editor').wait_for(state='hidden')
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  browser.close();print('PASS tactile controls: mouse drag, keyboard, phrase isolation, SVG action routing, module draft and refresh persistence')
finally:HeadlessTests.tearDownClass()

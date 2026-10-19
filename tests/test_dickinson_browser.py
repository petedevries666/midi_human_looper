#!/usr/bin/env python3
"""Actual native schema-8 controls via production editor, save/load and Cancel."""
import json,os,sys,pathlib
from playwright.sync_api import sync_playwright,expect
from test_dickinson_native import Dickinson
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from screenshots import AUDIT,verify_png
ROOT=pathlib.Path(__file__).resolve().parents[1]
Dickinson.setUpClass();api=Dickinson('test_arp_controls_snapshots_and_migration')
try:
 api.cmd('module_structure',instrumentId=1,operation='add',engineType=5)
 arp=next(t for t in api.control.request()['instruments'][0]['transformers'] if t['type']==5)
 def values():return {p['kind']:p['value'] for p in next(t for t in api.control.request()['instruments'][0]['transformers'] if t['id']==arp['id'])['parameters']}
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu'])
  page=browser.new_page(viewport=dict(width=1440,height=900));page.goto(api.url);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  card=page.locator(f'.module[data-instrument-id="1"][data-module-id="{arp["id"]}"]');card.click()
  page.get_by_role('button',name='ARP ENABLED',exact=True).click()
  page.get_by_label('MODE',exact=True).select_option(label='RANDOM CLIMB UP')
  page.get_by_role('slider',name='STEP MAX',exact=True).fill('4')
  page.get_by_label('PLAYBACK',exact=True).select_option(label='ONCE')
  page.get_by_role('button',name='DONE',exact=True).click();page.wait_for_function('()=>!document.querySelector("#editor").open')
  assert (values()[27],values()[28])==(4,1)
  page.get_by_role('button',name='SAVE PATCH',exact=True).click();page.get_by_text('PATCH SAVED',exact=True).wait_for()
  api.cmd('parameter_set',targetId=1,moduleId=arp['id'],kind=27,value=1)
  page.get_by_role('button',name='LOAD PATCH',exact=True).click();page.wait_for_function('()=>!pending')
  page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for();card.click()
  expect(page.get_by_role('slider',name='STEP MAX',exact=True)).to_have_value('4')
  expect(page.get_by_label('PLAYBACK',exact=True)).to_have_value('1')
  # Keyboard changes use the same native parameter ownership path.
  page.get_by_role('slider',name='STEP MAX',exact=True).focus();page.keyboard.press('ArrowLeft');page.wait_for_timeout(150)
  assert values()[27]==3
  page.get_by_role('button',name='CANCEL',exact=True).click();page.wait_for_function('()=>!document.querySelector("#editor").open')
  assert values()[27]==4
  card.click()
  out=ROOT/'docs/screenshots/dickinson';out.mkdir(parents=True,exist_ok=True);artifacts=[]
  for width,height in ((320,240),(800,480),(1366,768),(1440,900),(1904,1032)):
   page.set_viewport_size(dict(width=width,height=height));page.wait_for_timeout(200)
   errors=page.evaluate(AUDIT);assert not errors,(width,errors)
   page.get_by_label('PLAYBACK',exact=True).scroll_into_view_if_needed();page.wait_for_timeout(150)
   path=out/f'arp-{width}x{height}.png';page.screenshot(path=str(path));verify_png(path,width,height)
   artifacts.append(dict(file=str(path.relative_to(ROOT)),width=width,height=height,checks=errors))
  (out/'manifest.json').write_text(json.dumps(dict(data='Actual native schema-8 engine / generic ARP editor',interactions='Mouse, keyboard, SAVE/LOAD, refresh, CANCEL; native parameter assertions',artifacts=artifacts),indent=2)+'\n')
  browser.close()
 print('PASS actual native/browser STEP MAX, ONCE, keyboard, SAVE/LOAD and CANCEL; five audited PNGs')
finally:Dickinson.tearDownClass()

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
  page.locator('#editor').get_by_label('MODE',exact=True).select_option(label='RANDOM CLIMB UP')
  page.get_by_role('slider',name='STEP MAX',exact=True).fill('4')
  page.get_by_label('PLAYBACK',exact=True).select_option(label='ONCE')
  page.get_by_role('button',name='DONE',exact=True).click();page.wait_for_function('()=>!document.querySelector("#editor").open')
  assert (values()[4],values()[27],values()[28])==(9,4,1)
  humanizer=page.locator('.expressive-module').filter(has_text='HUMANIZER')
  humanizer.get_by_role('button',name='ENABLE',exact=True).click()
  humanizer.get_by_role('button',name='EDIT',exact=True).click()
  page.get_by_label('TIMING RANGE · ms',exact=True).fill('37')
  page.get_by_role('button',name='APPLY',exact=True).click()
  page.wait_for_function('()=>!document.querySelector("#expressive-editor").open')
  curve=page.locator('.expressive-module').filter(has_text='VELOCITY CURVES')
  curve.get_by_role('button',name='ENABLE',exact=True).click()
  curve.get_by_role('button',name='EDIT',exact=True).click()
  page.get_by_role('button',name='GATE',exact=True).click()
  page.get_by_label('AMOUNT · %',exact=True).fill('75')
  page.get_by_role('button',name='APPLY',exact=True).click()
  page.wait_for_function('()=>!document.querySelector("#expressive-editor").open')
  expressive=api.control.request()['nativeExpressive']['configuration']
  assert expressive[2:4]==[1,1] and expressive[4]==1 and expressive[5]==37 and expressive[15]==75 and expressive[16]==4,('expressive configuration',expressive)
  # Give the live-stream assertion a deterministic, measurable positive delay.
  humanizer.get_by_role('button',name='EDIT',exact=True).click()
  page.get_by_label('TIMING RANGE · ms',exact=True).fill('0')
  page.get_by_label('TIMING BIAS · ms',exact=True).fill('250')
  page.get_by_role('button',name='APPLY',exact=True).click()
  page.wait_for_function('()=>!document.querySelector("#expressive-editor").open')
  page.get_by_role('button',name='SAVE PATCH',exact=True).click();page.get_by_text('PATCH SAVED',exact=True).wait_for()
  saved=json.loads((api.server.patch_dir/'patch1.json').read_text())
  assert (saved['nativeArp']['configuration'][3],saved['nativeArp']['configuration'][4])==(4,1),('saved native ARP',saved.get('nativeArp'))
  assert saved['nativeExpressive']==api.control.request()['nativeExpressive'],('saved expressive modules',saved.get('nativeExpressive'))
  # Verify the actual engine emits the curved velocity through the routed MIDI output.
  api.cmd('parameter_set',targetId=1,moduleId=0,kind=23,value=1)
  state=api.control.request()
  assert state['expressivePending']==0,('no pending expressive event before test',state['expressivePending'])
  reply=api.control.request(op=3,ch=0,note=56,value=56,revision=state['revision'],session=state['engineSessionId'])
  assert reply['status']=='ok',('test MIDI input',reply)
  delayed=api.wait(lambda s:s['expressivePending']>0)
  assert delayed['expressivePending']>0,('HUMANIZER must hold the live attack for its positive bias',delayed)
  emitted=api.wait(lambda s:s['lastEvent'][2]==56 and s['lastEvent'][3]==109)
  assert emitted['lastEvent'][1]&240==144 and emitted['lastEvent'][3]==109,('curved native MIDI',emitted['lastEvent'])
  page.get_by_role('button',name='PANIC',exact=True).click();api.wait(lambda s:s['activeNotes']==0)
  api.cmd('parameter_set',targetId=1,moduleId=arp['id'],kind=27,value=1)
  expected_revision=api.control.request()['revision']
  page.wait_for_function('(expected)=>revision===expected',arg=expected_revision)
  sent=[];original_request=api.server.control.request
  def capture_load(*args,**kwargs):
   if kwargs.get('op')==5:sent.append(kwargs.get('patch'))
   return original_request(*args,**kwargs)
  api.server.control.request=capture_load
  page.get_by_role('button',name='LOAD PATCH',exact=True).click();page.wait_for_function('()=>!pending')
  assert not page.locator('#error').inner_text(),page.locator('#error').inner_text()
  assert sent and sent[-1].get('nativeArp')==saved['nativeArp'],('load carrier',sent[-1].get('nativeArp') if sent else None)
  assert sent[-1].get('nativeExpressive')==saved['nativeExpressive'],('expressive load carrier',sent[-1].get('nativeExpressive') if sent else None)
  api.server.control.request=original_request
  assert (values()[27],values()[28])==(4,1),('native state after LOAD',values())
  page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for();card.click()
  expect(page.get_by_role('slider',name='STEP MAX',exact=True)).to_have_value('4')
  expect(page.get_by_label('PLAYBACK',exact=True)).to_have_value('1')
  # Keyboard changes use the same native parameter ownership path.
  page.get_by_role('slider',name='STEP MAX',exact=True).focus();page.keyboard.press('ArrowLeft');page.wait_for_timeout(150)
  assert values()[27]==3
  page.get_by_role('button',name='CANCEL',exact=True).click();page.wait_for_function('()=>!document.querySelector("#editor").open')
  assert values()[27]==4
  out=ROOT/'docs/screenshots/dickinson';out.mkdir(parents=True,exist_ok=True);artifacts=[]
  sizes=((320,240),(800,480),(1366,768),(1440,900),(1904,1032))
  for view,locator in [('humanizer',humanizer),('velocity',curve)]:
   locator.get_by_role('button',name='EDIT',exact=True).click()
   for width,height in sizes:
    page.set_viewport_size(dict(width=width,height=height));page.wait_for_timeout(200)
    errors=page.evaluate(AUDIT);assert not errors,(view,width,errors)
    page.locator('#expressive-editor').scroll_into_view_if_needed();page.wait_for_timeout(150)
    path=out/(view+'-'+str(width)+'x'+str(height)+'.png');page.screenshot(path=str(path));verify_png(path,width,height)
    artifacts.append(dict(file=str(path.relative_to(ROOT)),width=width,height=height,view=view,checks=errors))
   page.get_by_role('button',name='CANCEL',exact=True).click()
  card.click()
  for width,height in sizes:
   page.set_viewport_size(dict(width=width,height=height));page.wait_for_timeout(200)
   errors=page.evaluate(AUDIT);assert not errors,(width,errors)
   page.get_by_label('PLAYBACK',exact=True).scroll_into_view_if_needed();page.wait_for_timeout(150)
   path=out/f'arp-{width}x{height}.png';page.screenshot(path=str(path));verify_png(path,width,height)
   artifacts.append(dict(file=str(path.relative_to(ROOT)),width=width,height=height,checks=errors))
  (out/'manifest.json').write_text(json.dumps(dict(data='Actual native schema-8 engine / generic ARP editor',interactions='Mouse, keyboard, SAVE/LOAD, refresh, CANCEL; native parameter assertions',artifacts=artifacts),indent=2)+'\n')
  browser.close()
 print('PASS actual native/browser STEP MAX, ONCE, keyboard, SAVE/LOAD and CANCEL; five audited PNGs')
finally:Dickinson.tearDownClass()

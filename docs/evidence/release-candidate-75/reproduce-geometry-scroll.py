"""Issue #51 hardware workflows through the production HTTP, browser and engine."""
import os,time,json
from playwright.sync_api import sync_playwright
import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'tests'))
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
  page.wait_for_function('(id)=>!document.querySelector(`[data-source-id="${id}"]`)',arg=source)
  page.evaluate('window.scrollTo(0,100)')
  snapshots=[]
  for index,label in enumerate(('BASE VEL','VEL DECAY','TIME DECAY')):
   page.evaluate('(i)=>window.scrollTo(0,100+i*64)',index)
   snapshots.append(page.get_by_role('slider',name=f'{label} Phrase 2',exact=True).evaluate('(e)=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,scrollY,documentY:r.y+scrollY}}'))
  atomic=page.locator('[data-phrase-id="2"] input[type=range]').evaluate_all('(es)=>es.map(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,scrollY,documentY:r.y+scrollY}})')
  print(json.dumps(dict(scope='Actual native editor; controlled browser scroll between independent geometry reads only',independent=snapshots,atomic=atomic),indent=2))
  assert len({b['documentY'] for b in snapshots})==1 and len({b['y'] for b in snapshots})>1
  assert len({b['y'] for b in atomic})==1
  browser.close()
finally:FreeCapture.tearDownClass()

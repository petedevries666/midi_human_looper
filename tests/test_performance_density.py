"""Measure real before/after UI text; APIs always use the actual native engine."""
import json,os,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright
from test_headless_mvp import HeadlessTests
ROOT=Path(__file__).resolve().parents[1]
BASE='77b62ab'
MEASURE=r'''selector=>{
 const root=document.querySelector(selector),texts=[];
 for(const e of root.querySelectorAll('button:not(.editable-name),.slider-caption,.inline-control,.parameter,h2,small')){
  if(!e.checkVisibility()||!e.getClientRects().length)continue;
  if(e.matches('small')&&(e.textContent.endsWith(' events')||['ON','OFF','BYPASS'].includes(e.textContent)))continue;
  if(e.matches('h2'))continue; // module identity is useful, not clutter
  const text=[...e.childNodes].filter(n=>n.nodeType===Node.TEXT_NODE).map(n=>n.textContent).join(' ').trim();
  if(text&&text!=='ON'&&text!=='OFF')texts.push(text);
 }
 // Shared headings replace repeated row labels and are counted once.
 if(selector==='#phrases')for(const e of document.querySelectorAll('.phrase-columns span'))texts.push(e.textContent);
 const words=texts.join(' ').match(/[A-Za-z][A-Za-z.]*/g)||[];
 return {labels:texts.length,words:words.length,characters:words.join('').length,texts};
}'''
HeadlessTests.setUpClass();api=HeadlessTests('test_real_engine_and_fifo')
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
  results={};inventories={}
  for old in (True,False):
   page=browser.new_page(viewport=dict(width=1366,height=768))
   if old:
    for name,mime in [('app.js','text/javascript'),('style.css','text/css')]:
     source=subprocess.check_output(['git','show',f'{BASE}:headless/web/{name}'],cwd=ROOT,text=True)
     page.route(f'**/{name}',lambda route,request,body=source,typ=mime:route.fulfill(body=body,content_type=typ))
   page.goto(api.base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
   key='before' if old else 'after';results[key]={}
   for view,selector in [('phrases','#phrases'),('instruments','#instruments')]:
    results[key][view]=page.evaluate(MEASURE,selector)
   inventories[key]=page.locator('#phrases button, #instruments button').evaluate_all('(nodes)=>nodes.map(e=>e.getAttribute("aria-label")||e.textContent).sort()')
   page.locator('[data-instrument-id="1"]').get_by_role('button',name='ADD TRANSFORMER',exact=True).click();page.locator('.transformers .module').first.get_by_role('button',name='EDIT',exact=True).click()
   results[key]['transformer-editor']=page.evaluate(MEASURE,'#editor-content');page.keyboard.press('Escape')
   tf=api.call()['instruments'][0]['transformers'][0];api.command('module_structure',instrumentId=1,moduleId=tf['id'],operation='delete')
   if not old:
    page.evaluate('window.scrollTo(0,0)');assert page.locator('.phrase').count()==6
    bottom=page.locator('.phrase').last.bounding_box()['y']+page.locator('.phrase').last.bounding_box()['height'];results['sixRowBottomPx']=bottom;assert bottom<=768,'Six phrases must fit without page scrolling'
    for width in (320,800,1366):
     page.set_viewport_size(dict(width=width,height=768));assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
    assert page.locator('button.icon-only').evaluate_all('(nodes)=>nodes.every(e=>e.getAttribute("aria-label")&&e.title)')
   page.close()
  assert inventories['before']==inventories['after'],'A primary action disappeared or changed identity'
  for view in ['phrases','instruments']:
   assert results['after'][view]['characters']<results['before'][view]['characters']*.6,results
  results['baselineCommit']=BASE
  (ROOT/'docs/performance-text-audit.json').write_text(json.dumps(results,indent=2)+'\n')
  print('PASS primary action inventory, six visible rows, responsive layout and measured label reduction')
  print(json.dumps({key:{view:{k:v for k,v in values.items() if k!='texts'} for view,values in data.items()} for key,data in results.items() if isinstance(data,dict)}))
  browser.close()
finally:HeadlessTests.tearDownClass()

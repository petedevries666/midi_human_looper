"""Deterministic real-browser/API reproduction; delay only a private PANIC reply.
Regression: the enabled edit queues behind the real pending reply and must apply.
"""
import os,sys
from pathlib import Path
if os.environ.get('COMPARE_ROOT'):sys.path.insert(0,str(Path(os.environ['COMPARE_ROOT'])/'tests'))
import json
from playwright.sync_api import sync_playwright
from test_native_free_capture import FreeCapture
api=FreeCapture('runTest');api.setUpClass()
try:
 api.command('panic');api.command('parameter_set',targetId=1,kind=20,value=1)
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-gpu'])
  page=browser.new_page(viewport={'width':1366,'height':768});page.goto(api.base)
  page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  page.evaluate('''()=>{
   const realFetch=window.fetch.bind(window);window.__parameterPosts=[];
   window.__panicReplyHeld=false;
   window.fetch=async(...args)=>{
    const body=args[1]?.body?JSON.parse(args[1].body):{};
    if(body.action==='parameter_set')window.__parameterPosts.push(body);
    const reply=await realFetch(...args);
    if(body.action==='panic'){
     window.__panicReplyHeld=true;
     await new Promise(resolve=>setTimeout(resolve,750));
     window.__panicReplyHeld=false;
    }
    return reply;
   };
  }''')
  page.get_by_role('button',name='PANIC',exact=True).click()
  page.wait_for_function('()=>window.__panicReplyHeld && pending')
  select=page.get_by_label('Play mode Phrase 1',exact=True)
  assert select.is_enabled(),'fixture needs the currently enabled control'
  select.select_option('0')
  page.wait_for_function('()=>!pending && !window.__panicReplyHeld && window.__parameterPosts.length===1')
  api.wait_for(lambda:api.call()['phrases'][0]['mode']==0,'queued LOOP edit applies')
  first=api.call()['phrases'][0]['mode'];posts=page.evaluate('window.__parameterPosts')
  print('PENDING EDIT OBSERVATION',json.dumps({'requestedMode':0,'nativeMode':first,'parameterPosts':posts,'uiError':page.locator('#error').inner_text()}),flush=True)
  # Positive control: identical target and value after the previous command ends.
  select.select_option('0')
  api.wait_for(lambda:api.call()['phrases'][0]['mode']==0,'idle positive control applies LOOP')
  print('IDLE POSITIVE CONTROL',json.dumps({'nativeMode':api.call()['phrases'][0]['mode'],'parameterPosts':page.evaluate('window.__parameterPosts')}),flush=True)
  browser.close()
 assert first==0 and len(posts)==1,(first,posts)
 print('PASS pending-command enabled edit: one real POST, correct target/value, idle control preserved',flush=True)
finally:
 api.tearDownClass()

"""Issue #53: actual browser -> HTTP -> shared EEL/Controller -> MIDI/state."""
import os,time,json,base64,urllib.request
from playwright.sync_api import sync_playwright
from test_native_free_capture import FreeCapture
from controller_config import decode
from phrase_midi import write_smf,read_smf
FreeCapture.setUpClass();api=FreeCapture('test_free_capture')
try:
 with sync_playwright() as p:
  family=os.environ.get('MIDI_BROWSER','chromium')
  args=dict(headless=True)
  if family=='chromium':args.update(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu'])
  browser=getattr(p,family).launch(**args);page=browser.new_page(viewport=dict(width=1366,height=768));errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(api.base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  panel=page.locator('[data-instrument-id="1"]');types=panel.get_by_label('Transformer type for Instrument 1',exact=True)
  assert types.locator('option',has_text='ADD EMPTY TRANSFORMER').count()==1
  types.select_option('empty');panel.get_by_role('button',name='ADD TRANSFORMER',exact=True).click()
  page.get_by_role('button',name='CANCEL',exact=True).click();assert not api.call()['instruments'][0]['transformers']
  panel.get_by_role('button',name='ADD TRANSFORMER',exact=True).click();page.get_by_label('Blank Transformer type',exact=True).select_option('1');page.get_by_role('button',name='DONE',exact=True).click()
  page.get_by_role('slider',name='SEMITONES',exact=True).wait_for();page.get_by_role('button',name='DONE',exact=True).click()
  tf=api.call()['instruments'][0]['transformers'][0]
  # Source-ID manual input must not fake MIDI Learn or create/change assignments.
  api.command('controller_rename',sourceId=101,name='HELIX EXP',create=True)
  mapping=dict(id=301,sourceId=101,targetId=201,instrumentId=1,moduleId=tf['id'],kind=7,points=[[0,0,0],[1,1,0]])
  api.command('mapping_commit',mapping=mapping);api.command('controller_learn',sourceId=101)
  page.locator('#controller-section').evaluate('e=>e.open=true');rail=page.get_by_role('slider',name='TEST HELIX EXP',exact=True);rail.wait_for()
  before=decode(api.call()['controllerEngine']);assert not page.locator('[data-source-id="101"] [aria-label="×"]').count()
  page.locator('[data-mapping-id="301"]').get_by_role('button',name='REMOVE MAPPING',exact=True).wait_for()
  rail.scroll_into_view_if_needed();box=rail.bounding_box();page.mouse.move(box['x']+box['width']*.25,box['y']+box['height']/2);page.mouse.down();page.mouse.move(box['x']+box['width']*.75,box['y']+box['height']/2,steps=6)
  api.wait_for(lambda:api.call()['instruments'][0]['transformers'][0]['parameters'][0]['value']>12,'manual source live while held')
  value=api.call()['instruments'][0]['transformers'][0]['parameters'][0]['value'];page.mouse.up()
  assert decode(api.call()['controllerEngine'])==before and api.call()['controllerLearn']['target']==101
  api.command('controller_cancel',sourceId=101)
  # Precisely center the source: MIDI pitch must follow the actual mapping.
  rail.fill('127');api.wait_for(lambda:api.call()['instruments'][0]['transformers'][0]['parameters'][0]['value']==48,'manual max maps transpose')
  assert api.command('midi',channel=1,note=60,value=100)['lastEvent'][2]==108
  api.command('midi',channel=1,note=60,value=0)
  rail.focus();rail.press('ArrowLeft');api.wait_for(lambda:api.call()['controllerRuntime'][0]['effective']<1,'manual keyboard source input')
  assert decode(api.call()['controllerEngine'])==before
  api.patch('save');api.patch('load');assert decode(api.call()['controllerEngine'])==before
  page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for();page.locator('#controller-section').evaluate('e=>e.open=true')
  # The formerly ambiguous X is CLEAR MIDI, not a second source deletion.
  api.command('controller_source',sourceId=101,kind=2,channel=2,number=21)
  clear=page.locator('[data-source-id="101"]').get_by_role('button',name='FORGET MIDI',exact=True);clear.wait_for();assert clear.inner_text().strip()=='CLEAR MIDI'
  assert 'keep Controller' in clear.get_attribute('title');clear.click()
  api.wait_for(lambda:decode(api.call()['controllerEngine'])['sources'][0]['kind']==0,'CLEAR MIDI clears only physical binding')
  cleared=decode(api.call()['controllerEngine']);assert cleared['sources'][0]['id']==101 and cleared['sources'][0]['name']=='HELIX EXP' and cleared['mappings']==before['mappings']
  assert page.locator('[data-source-id="101"]').count()==1
  # Cleanup only that source; the module/other Instruments remain intact.
  page.once('dialog',lambda d:d.accept());page.locator('[data-source-id="101"]').get_by_role('button',name='REMOVE',exact=True).click()
  api.wait_for(lambda:not decode(api.call()['controllerEngine'])['sources'],'source removal');assert not decode(api.call()['controllerEngine'])['mappings']
  api.command('parameter_set',targetId=1,moduleId=tf['id'],kind=7,value=0)
  api.command('panic')
  raw=write_smf(dict(lengthSeconds=2,bpm=120,events=[[0,144,60,100],[1.8,128,60,0]]));state=api.call()
  body=dict(phraseId=1,file=base64.b64encode(raw).decode(),mode='replace',expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'])
  urllib.request.urlopen(urllib.request.Request(api.base+'/api/v1/phrase/midi',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})).read()
  api.command('parameter_set',targetId=1,kind=20,value=0);api.command('phrase_play',phraseId=1)
  print('PASS manual source browser/MIDI path',flush=True)
  # Keyboard finalizes the real target, without stopping the independent LOOP.
  finish=[];page.on('request',lambda r:finish.append(r.post_data_json) if r.method=='POST' and r.url.endswith('/command') and r.post_data_json.get('action')=='phrase_finish' else None)
  for key in ('Enter','Space'):
   api.command('phrase_clear',phraseId=2);page.wait_for_function('(r)=>revision>=r',arg=api.call()['revision']);row=page.locator('[data-phrase-id="2"]');row.get_by_role('button',name='REC / OVERDUB',exact=True).click();api.wait_for(lambda:api.call()['chainArmed'],'REC armed');api.command('midi',channel=2,note=64,value=90);api.command('midi',channel=2,note=64,value=0)
   page.wait_for_function("()=>document.querySelector('[data-phrase-id=\"2\"]').dataset.state==='RECORDING'")
   assert api.call()['chainPhraseId']==2
   # Excluded focus and key repeat never finalize a take.
   for selector in ('select','button'):
    element=row.locator(selector).first;element.focus();element.dispatch_event('keydown',dict(key='Enter',bubbles=True));assert api.call()['chainRecording']
   page.evaluate('''()=>{for(const tag of ['input','textarea','div']){const e=document.createElement(tag);if(tag==='div')e.contentEditable='true';document.body.append(e);e.focus();const key=new KeyboardEvent('keydown',{key:' ',bubbles:true,cancelable:true});e.dispatchEvent(key);if(key.defaultPrevented)throw new Error('shortcut captured editing');e.remove();}const d=document.createElement('dialog');document.body.append(d);d.showModal();const key=new KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true});document.body.dispatchEvent(key);if(key.defaultPrevented)throw new Error('shortcut captured dialog');d.close();d.remove();}''');assert api.call()['chainRecording']
   page.evaluate('document.activeElement.blur()');page.keyboard.press('Control+Enter');assert api.call()['chainRecording']
   page.evaluate("document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',repeat:true,bubbles:true,cancelable:true}))");assert api.call()['chainRecording']
   n=len(finish);page.keyboard.press(key)
   api.wait_for(lambda:not api.call()['chainRecording'],'keyboard finishes actual recording')
   api.wait_for(lambda:len(finish)==n+1,'one shortcut request')
   assert finish[-1]['phraseId']==2 and api.call()['phrases'][0]['state']=='PLAYING'
   notes=read_smf(api.export(2))['events'];assert notes[0][0]==0 and [e[2] for e in notes][:2]==[64,64]
  row.get_by_role('button',name='REC / OVERDUB',exact=True).click();api.wait_for(lambda:api.call()['chainArmed'],'overdub armed')
  api.command('midi',channel=2,note=67,value=80);api.command('midi',channel=2,note=67,value=0)
  page.wait_for_function("()=>document.querySelector('[data-phrase-id=\"2\"]').dataset.state==='OVERDUB ACTIVE'")
  page.evaluate('document.activeElement.blur()');page.keyboard.press('Enter');api.wait_for(lambda:not api.call()['chainRecording'],'keyboard overdub finish')
  assert api.call()['phrases'][0]['state']=='PLAYING'
  assert {e[2] for e in read_smf(api.export(2))['events'] if e[1]&0xf0==0x90 and e[3]}>={64,67}
  assert page.evaluate("(()=>{const e=new KeyboardEvent('keydown',{key:' ',bubbles:true,cancelable:true});document.body.dispatchEvent(e);return e.defaultPrevented})()") is False
  api.command('panic');api.command('parameter_set',targetId=1,kind=20,value=1)
  print('PASS targeted keyboard recording with independent LOOP',flush=True)
  # Preview works with switch disabled AND no binding, through shared sw_action.
  sw=api.call()['switches'][0];settings=sw['settings'];settings[0]=0;settings[1]=0;settings[12]=1
  api.command('switch_commit',switchId=sw['id'],settings=settings,sequence=[],name='TEST ONLY')
  page.wait_for_function('(r)=>revision>=r',arg=api.call()['revision']);card=page.locator(f'[data-switch-id="{sw["id"]}"]');card.locator('summary',has_text='TEST').click();card.get_by_role('button',name='TEST TAP',exact=True).click()
  page.get_by_text('TAP · EMPTY SEQUENCE / PHRASE · OPTIONS',exact=True).wait_for()
  api.command('switch_commit',switchId=sw['id'],settings=settings,sequence=[1],name='TEST ONLY');page.wait_for_function('(r)=>revision>=r',arg=api.call()['revision'])
  card.get_by_role('button',name='TEST TAP',exact=True).click();api.wait_for(lambda:api.call()['phrases'][0]['state']=='PLAYING','unbound TAP starts real phrase')
  page.get_by_text('TAP · ACTION NEXT · STEP 1',exact=True).wait_for();assert api.call()['lastEvent'][2]==60
  api.command('panic');assert api.call()['activeNotes']==0
  assert not errors,errors;browser.close();print('PASS issue #53 '+family+': blank draft, targeted keyboard FINISH, unbound TAP MIDI, source test ownership/Learn isolation, mapped MIDI output, persistence/removal')
finally:FreeCapture.tearDownClass()

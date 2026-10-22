#!/usr/bin/env python3
"""Production browser → native MIDI → persistence recovery workflows."""
import os,time,sys,json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
from test_native_free_capture import FreeCapture
FreeCapture.setUpClass();api=FreeCapture('test_free_capture')
try:
 api.command('panic')
 with sync_playwright() as p:
  browser=p.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu'])
  page=browser.new_page(viewport=dict(width=1904 if os.environ.get('SCREENSHOT_RECOVERY_DIR') else 1366,height=1032 if os.environ.get('SCREENSHOT_RECOVERY_DIR') else 768));page.goto(api.base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  evidence=[]
  def screenshot(name,selector=None):
   if not os.environ.get('SCREENSHOT_RECOVERY_DIR'):return
   sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
   from screenshots import AUDIT,verify_png
   # Capture one actually observed frame. Native MIDI continues; only this
   # browser's observation handler is suspended during scroll/paint/capture.
   # This is static evidence, not proof of glitch-free continuous rendering.
   before_capture=api.call()['sampleClock']
   page.evaluate("() => {window.__captureTelemetry={socket:ws,handler:ws?.onmessage};if(ws)ws.onmessage=null;}")
   try:
    if selector:page.locator(selector).first.evaluate("e=>e.scrollIntoView({block:'start'})")
    errors=page.evaluate(AUDIT);assert not errors,errors
    output=Path(os.environ['SCREENSHOT_RECOVERY_DIR']);output.mkdir(parents=True,exist_ok=True)
    path=output/f'{name}-1904x1032.png'
    page.evaluate('() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))')
    page.evaluate('document.fonts.ready');page.screenshot(animations='disabled');page.wait_for_timeout(150)
    page.screenshot(path=str(path),animations='disabled');verify_png(path,1904,1032)
   finally:
    page.evaluate("() => {const saved=window.__captureTelemetry;if(saved.socket)saved.socket.onmessage=saved.handler;delete window.__captureTelemetry;}")
   after_capture=api.call()['sampleClock'];assert after_capture>before_capture,'static capture must not pause native execution'
   evidence.append(dict(view=name,viewport=[1904,1032],file=path.name,checks=[],nativeClockAdvanced=True,capture='Actual observed native state; browser telemetry briefly suspended for static capture, engine continues'))
  panel=page.locator('[data-instrument-id="1"]');panel.get_by_label('Transformer type for Instrument 1',exact=True).select_option('5');panel.get_by_role('button',name='ADD TRANSFORMER',exact=True).click()
  panel.locator('.module').last.click()
  page.get_by_role('button',name='ARP ENABLED',exact=True).click()
  page.locator('#editor').get_by_label('MODE',exact=True).select_option(label='DOWN')
  page.get_by_role('slider',name='RATE',exact=True).fill('16')
  page.get_by_role('slider',name='GATE',exact=True).fill('0.5')
  screenshot('recovery-arp-editor')
  page.get_by_role('button',name='DONE',exact=True).click();page.locator('#editor').wait_for(state='hidden')
  module_id=int(panel.locator('.module').last.get_attribute('data-module-id'));module=next(t for t in api.call()['instruments'][0]['transformers'] if t['id']==module_id);values={v['kind']:v['value'] for v in module['parameters']}
  assert values[3]==1 and values[4]==2 and values[5]==16 and values[6]==.5,values
  # Every catalog ARP mode must round-trip through the browser and native EEL
  # scaling; legacy bounds at 2 used to turn DOWN into RANDOM and clamp newer modes.
  page.locator(f'[data-instrument-id="1"] [data-module-id="{module_id}"]').click()
  mode=page.locator('#editor').get_by_label('MODE',exact=True)
  mode.select_option(label='RANDOM CLIMB DOWN')
  page.get_by_role('button',name='DONE',exact=True).click();page.locator('#editor').wait_for(state='hidden')
  assert next(v['value'] for t in api.call()['instruments'][0]['transformers'] if t['id']==module['id'] for v in t['parameters'] if v['kind']==4)==10
  page.locator(f'[data-instrument-id="1"] [data-module-id="{module_id}"]').click()
  page.locator('#editor').get_by_label('MODE',exact=True).select_option(label='DOWN')
  page.get_by_role('button',name='DONE',exact=True).click();page.locator('#editor').wait_for(state='hidden')
  assert next(v['value'] for t in api.call()['instruments'][0]['transformers'] if t['id']==module['id'] for v in t['parameters'] if v['kind']==4)==2
  # Native commit completion precedes the asynchronous browser repaint. Require
  # the actual module text within Playwright's unchanged default timeout; do not
  # read the old DOM once and confuse that observation with a lost native edit.
  expect(panel.locator('.module')).to_contain_text('DOWN')
  for note in (60,64,67):api.command('midi',channel=1,note=note,value=100)
  before=api.call()['midiCount'];time.sleep(.25);assert api.call()['midiCount']>=before+10,'enabled ARP must generate repeated MIDI'
  for note in (60,64,67):api.command('midi',channel=1,note=note,value=0)
  api.command('panic');assert api.call()['activeNotes']==0
  page.get_by_role('button',name='SAVE PATCH',exact=True).click();page.get_by_text('PATCH SAVED',exact=True).wait_for()
  api.command('module_commit',instrumentId=1,moduleId=module['id'],parameters=[dict(kind=3,value=0)])
  api.patch('load');assert next(v for t in api.call()['instruments'][0]['transformers'] if t['id']==module['id'] for v in t['parameters'] if v['kind']==3)['value']==1
  page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for();expect(page.locator('[data-instrument-id="1"] .module')).to_contain_text('DOWN')
  # Named source and contextual assignment use the real native ownership engine.
  api.command('controller_source',sourceId=101,kind=2,channel=2,number=21)
  api.command('controller_rename',sourceId=101,name='EXP 1 CODIE')
  # A mapped enum edited by hand must commit through the same owner policy;
  # it cannot silently lose a user's selection as an untouched draft field.
  api.command('mapping_commit',mapping=dict(id=2,targetId=2,sourceId=101,instrumentId=1,moduleId=module['id'],kind=4,enabled=1,points=[[0,0,0],[1,1,0]]))
  page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  page.locator(f'[data-instrument-id="1"] [data-module-id="{module["id"]}"]').click()
  page.locator('#editor').get_by_label('MODE',exact=True).select_option(label='UP')
  page.get_by_role('button',name='DONE',exact=True).click();page.locator('#editor').wait_for(state='hidden')
  assert next(v['value'] for t in api.call()['instruments'][0]['transformers'] if t['id']==module['id'] for v in t['parameters'] if v['kind']==4)==1
  api.command('mapping_delete',mappingId=2)
  api.command('module_commit',instrumentId=1,moduleId=module['id'],parameters=[dict(kind=4,value=2)])
  page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  rail=page.get_by_role('slider',name='VOLUME Instrument 1',exact=True);rail.click(button='right')
  screenshot('recovery-modulator-menu')
  page.get_by_role('menuitem',name='EXP 1 CODIE',exact=True).click()
  page.get_by_label('Controller source',exact=True).wait_for()
  page.get_by_role('button',name='ADD POINT',exact=True).click()
  page.locator('.curve-precision summary').click()
  page.get_by_label('Y point 2',exact=True).fill('0.25')
  page.get_by_label('BEND point 1',exact=True).fill('0.6')
  page.get_by_role('button',name='STORE CUSTOM 1',exact=True).click();page.wait_for_timeout(200)
  screenshot('recovery-curve-editor')
  api.command('midi_cc',channel=2,number=21,value=64)
  assert api.call()['instruments'][0]['level']==64,'physical-equivalent CC must control actual volume'
  page.get_by_role('button',name='DONE',exact=True).click();page.locator('#editor').wait_for(state='hidden')
  page.get_by_role('slider',name='VOLUME Instrument 1',exact=True).focus()
  api.command('midi_cc',channel=2,number=21,value=32)
  assert api.call()['instruments'][0]['level']==2,'bend and multipoint curve must change native scaling'
  page.wait_for_function("""() => document.querySelector('[data-instrument-id="1"] input[aria-label="VOLUME Instrument 1"]').value==='2'""")
  emitted=api.call()['lastEvent'];assert emitted[1:]==[176,7,2],f'named controller curve must emit actual instrument CC7 volume: {emitted}'
  # Reopening a mapped slider and changing its base value must leave its
  # controller curve editable and committed. The cyan marker follows the live
  # effective output while the slider thumb continues to represent the base.
  live=page.locator('[data-instrument-id="1"] [data-modulation-live]')
  page.wait_for_function("""() => {const m=document.querySelector('[data-instrument-id="1"] [data-modulation-live]');return m&&!m.hidden&&m.style.left!==''}""")
  before_live=float(live.evaluate("(e)=>parseFloat(e.style.left)"))
  api.command('midi_cc',channel=2,number=21,value=96)
  page.wait_for_function("""before => {const m=document.querySelector('[data-instrument-id="1"] [data-modulation-live]');return m&&!m.hidden&&Math.abs(parseFloat(m.style.left)-before)>1}""",arg=before_live)
  rail=page.get_by_role('slider',name='VOLUME Instrument 1',exact=True)
  rail.click()
  page.get_by_label('Controller source',exact=True).wait_for()
  page.evaluate("""() => {const e=document.querySelector('[data-instrument-id="1"] input[aria-label="VOLUME Instrument 1"]');e.value='80';e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));}""")
  page.wait_for_function("""() => document.querySelector('[data-instrument-id="1"] input[aria-label="VOLUME Instrument 1"]').value==='80'""")
  page.get_by_role('button',name='DONE',exact=True).click()
  page.locator('#mapping-editor').wait_for(state='hidden')
  from controller_config import decode
  after_base_edit=decode(api.call()['controllerEngine'])
  assert len(after_base_edit['mappings'])==1,'editing the base slider must preserve its controller assignment'
  assert after_base_edit['mappings'][0]['points'][1][1]==.25,'editing the base slider must preserve the response curve'
  api.command('panic');api.patch('save');api.patch('load')
  from controller_config import decode
  api.command('panic');api.patch('save');api.patch('load')
  from controller_config import decode
  config=decode(api.call()['controllerEngine']);assert config['sources'][0]['name']=='EXP 1 CODIE'
  assert config['mappings'][0]['points'][1][1]==.25 and config['presets'][0][1][1]==.25
  page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  rail=page.get_by_role('slider',name='VOLUME Instrument 1',exact=True);rail.click(button='right')
  page.get_by_role('menuitem',name='NONE',exact=True).click();page.wait_for_timeout(200)
  assert not decode(api.call()['controllerEngine'])['mappings']
  # REC visuals are observations, not browser-predicted state flags.
  phrase=page.locator('[data-phrase-id="2"]');phrase.get_by_role('button',name='REC / OVERDUB',exact=True).click()
  page.wait_for_function("""() => document.querySelector('[data-phrase-id="2"]').dataset.state==="ARMED" """)
  assert api.call()['phrases'][1]['state']=='ARMED'
  screenshot('recovery-record-armed','#phrase-pagination')
  api.command('midi',channel=3,note=69,value=91)
  page.wait_for_function("""() => document.querySelector('[data-phrase-id="2"]').dataset.state==="RECORDING" """)
  assert api.call()['phrases'][1]['state']=='RECORDING'
  screenshot('recovery-recording','#phrase-pagination')
  api.command('midi',channel=3,note=69,value=0)
  phrase.get_by_role('button',name='FINISH REC',exact=True).click()
  page.wait_for_function("""() => document.querySelector('[data-phrase-id="2"]').dataset.state==="FINISHED" """)
  page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
  assert page.locator('[data-phrase-id="2"]').get_attribute('data-state')=='FINISHED'
  if os.environ.get('SCREENSHOT_RECOVERY_DIR'):
   # Reproduce the reference's musical chain arrangement with real persisted
   # instances. This changes this private fixture only, never a user's patch.
   api.command('panic')
   for instrument in api.call()['instruments']:
    for module in instrument['transformers']:api.command('module_structure',instrumentId=instrument['id'],moduleId=module['id'],operation='delete')
   configured={}
   for instrument,types in ((1,(4,)),(2,(6,1,3,2)),(3,(1,5))):
    api.command('instrument_route',instrumentId=instrument,field='enabled',value=1)
    api.command('instrument_route',instrumentId=instrument,field='output',value=instrument)
    api.command('instrument_route',instrumentId=instrument,field='level',value={1:114,2:77,3:14}[instrument])
    for type_ in types:
     api.command('module_structure',instrumentId=instrument,operation='add',engineType=type_)
     configured[instrument,type_]=api.call()['instruments'][instrument-1]['transformers'][-1]['id']
   for instrument,type_,parameters in ((2,1,[(7,12)]),(3,1,[(7,24)]),(2,3,[(11,1)]),(2,2,[(8,2)]),(2,6,[(2,58),(13,14)]),(3,5,[(3,1),(4,0),(5,4)])):
    api.command('module_commit',instrumentId=instrument,moduleId=configured[instrument,type_],parameters=[dict(kind=k,value=v) for k,v in parameters])
   api.command('mapping_commit',mapping=dict(id=1,targetId=1,sourceId=101,instrumentId=3,moduleId=0,kind=1,enabled=1,points=[[0,.1,0],[.5,.25,0],[1,1,0]]))
   page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
   screenshot('recovery-performance','header')
   screenshot('recovery-instrument-chains','#instruments')
   page.locator(f'[data-instrument-id="2"] [data-module-id="{configured[2,6]}"]').click()
   screenshot('recovery-transformer-editor')
   page.keyboard.press('Escape')
  else:screenshot('recovery-performance','header')
  if evidence:(Path(os.environ['SCREENSHOT_RECOVERY_DIR'])/'recovery-manifest.json').write_text(json.dumps(dict(runtimeBuildRevision=api.call()['buildRevision'],data='Actual native --chain; real CC mapping and recording actions',artifacts=evidence),indent=2)+'\n')
  browser.close()
 print('PASS contextual named modulation, multipoint/bend/presets/persistence, real recording states and browser ARP enable, named DOWN, RATE/GATE, actual generated native MIDI, PANIC and save/load')
finally:FreeCapture.tearDownClass()

#!/usr/bin/env python3
"""Actual production host + private JACK, source CCs are captured at the port."""
import os,sys,json,time,tempfile,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'headless'),str(ROOT/'tests')]
from server import Control
from test_conductor_persistence import step,block
from test_movement_persistence import movement
import conductor
with tempfile.TemporaryDirectory(prefix='mbmf-movement-jack-') as tmp:
 env=dict(os.environ,JACK_DEFAULT_SERVER='mbmf-movement-f')
 server=subprocess.Popen([env['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime','-d','dummy','-r','48000','-p','8192'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 engine=probe=web=browser=None
 try:
  time.sleep(1);assert server.poll() is None
  sock=str(Path(tmp)/'engine.sock');engine=subprocess.Popen([env['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),sock,'--chain','--jack','--client','mbmf_d'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  deadline=time.monotonic()+15
  while not Path(sock).exists() and time.monotonic()<deadline:assert engine.poll() is None;time.sleep(.05)
  c=Control(sock)
  def command(**args):
   state=c.request();result=c.request(revision=state['revision'],session=state['engineSessionId'],**args);assert result.get('status')=='ok',result;return result
  command(op=2)
  for i in (2,3):command(op=32,target=i,arg=21,macro=[0,0])
  settings=c.request()['switches'][0]['settings'];settings[:4]=[1,1,0,110];settings[11]=0;command(op=41,target=1,settings=settings+[0]*64+[0]*16)
  probe=subprocess.Popen([env['MOVEMENT_JACK_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);assert probe.stdout.readline().strip()=='READY'
  def event(st,n,v):probe.stdin.write(f'{st} {n} {v} 16\n');probe.stdin.flush();time.sleep(.2)
  def install(rate,items,steps=None):
   command(op=2);state=c.request();patch=c.request(op=4,arg=1,revision=state['revision'],session=state['engineSessionId']);model=conductor.migrate(patch);model.update(version=2,movements=items,ccRate=rate)
   model['switches']=[dict(switchId=1,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',steps=steps or [step([None,block(items[0]['id'],'MOVEMENT')])])]
   patch['conductor']=conductor.encode(model);command(op=5,target=7,arg=1,patch=patch);assert c.request()['movements']['active']==0
  for rate,cc in [(10,10),(25,11),(50,12),(100,13)]:
   m=movement();m.update(retrigger='DIRECT',duration=1,points=[[0,0],[1,1]]);m['target']['number']=cc;install(rate,[m]);event(144,110,127);event(128,110,0);time.sleep(1.2);assert c.request()['movements']['active']==0,c.request()
  # Physical takeover: passthrough unchanged and no stale CC after it.
  m=movement();m.update(retrigger='DIRECT',duration=5);m['target']['number']=14;install(25,[m]);event(144,110,127);event(128,110,0);event(176,14,77);time.sleep(.5);assert c.request()['movements']['active']==0
  # A later physical CC in the *same* real JACK block wins the deferred PRESS.
  m=movement();m.update(duration=5,retrigger='DIRECT');m['target']['number']=18;install(100,[m]);probe.stdin.write('144 110 127 16\n176 18 77 220\n');probe.stdin.flush();time.sleep(.5);assert not c.request()['movements']['active'];event(128,110,0)
  # Replacement is last admitted source on target; older source never returns.
  a=movement();a.update(duration=5,retrigger='DIRECT',points=[[0,.2],[1,.2]]);a['target']['number']=15
  b=movement();b.update(duration=.5,retrigger='DIRECT',points=[[0,.8],[1,.8]]);b['target']['number']=15
  install(25,[a,b],[step([None,block(a['id'],'MOVEMENT')]),step([None,block(b['id'],'MOVEMENT')])]);event(144,110,127);event(128,110,0);event(144,110,127);event(128,110,0);time.sleep(.8);assert not c.request()['movements']['active']
  # PHRASE + MOVEMENT and STOP PHRASES leaves automation running.
  command(op=35,target=0,arg=1,phrase=dict(lengthSeconds=2,events=[[0,144,60,100],[1.8,128,60,0]]))
  m=movement();m.update(duration=4,retrigger='DIRECT');m['target']['number']=16
  state=c.request();patch=c.request(op=4,revision=state['revision'],session=state['engineSessionId']);model=conductor.migrate(patch);src=model['sources'][0]['id']
  install(25,[m],[step([block(src),block(m['id'],'MOVEMENT')])]);event(144,110,127);event(128,110,0);assert c.request()['instances'] and c.request()['movements']['active']==1,c.request()
  sw=c.request()['switches'][1]['settings'];sw[0]=1;sw[12]=2;command(op=41,target=2,settings=sw+[0]*64+[0]*16);command(op=1,target=2);time.sleep(.3);assert not c.request()['instances'];assert c.request()['movements']['active']==1,c.request()
  command(op=2);time.sleep(.3);assert c.request()['movements']['active']==0;assert c.request()['outputOverflow']==0
  # Two destinations continue independently across a STEP change; HOLD points
  # are sampled at cadence, not mistaken for prerecorded phrase CC events.
  a=movement();a.update(duration=3,retrigger='DIRECT',points=[[0,0],[1,1]]);a['target']['number']=21
  b=movement();b.update(duration=1,retrigger='DIRECT',interpolation='HOLD',points=[[0,0],[.25,.2],[.5,.9],[1,.1]]);b['target'].update(channel=2,number=22)
  install(25,[a,b],[step([None,block(a['id'],'MOVEMENT')]),step([None,block(b['id'],'MOVEMENT')])]);event(144,110,127);event(128,110,0);event(144,110,127);event(128,110,0);time.sleep(1.2);assert c.request()['movements']['active']==1,c.request();time.sleep(1.4);assert not c.request()['movements']['active']
  short=movement();short.update(duration=.01,retrigger='DIRECT',points=[[0,0],[1,1]]);short['target']['number']=23;install(100,[short]);event(144,110,127);event(128,110,0);assert not c.request()['movements']['active']
  soft=movement();soft.update(duration=1,points=[[0,0],[1,1]]);soft['target']['number']=24;install(25,[soft]);event(176,24,100);event(144,110,127);event(128,110,0);time.sleep(1.1);assert not c.request()['movements']['active']
  install(25,[m],[step([block(src),block(m['id'],'MOVEMENT')])])
  if os.environ.get('MOVEMENT_BROWSER_AUTHOR')=='1':
   import socket,urllib.request
   from playwright.sync_api import sync_playwright
   with socket.socket() as ps:ps.bind(('127.0.0.1',0));port=ps.getsockname()[1]
   url=f'http://127.0.0.1:{port}';web=subprocess.Popen([sys.executable,str(ROOT/'headless/server.py'),'--socket',sock,'--port',str(port),'--patch-dir',str(Path(tmp)/'patches')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
   deadline=time.monotonic()+10
   while time.monotonic()<deadline:
    try:urllib.request.urlopen(url+'/api/v1/state').close();break
    except OSError:time.sleep(.05)
   pw=sync_playwright().start();browser=pw.chromium.launch(headless=True,executable_path=env.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu']);page=browser.new_page(viewport={'width':1440,'height':900});page.goto(url);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
   page.locator('#movement-section').evaluate('e=>e.open=true');page.get_by_role('button',name='+ MOVEMENT',exact=True).click();page.locator('.movement-editor').wait_for();page.get_by_label('NAME',exact=True).fill('JACK BROWSER');page.get_by_label('CC',exact=True).fill('17');page.get_by_label('DURATION s',exact=True).fill('1');page.get_by_label('RETRIGGER',exact=True).select_option('DIRECT');page.get_by_role('button',name='DONE',exact=True).click();page.locator('#editor').wait_for(state='hidden')
   page.locator('[data-switch-id="1"]').get_by_role('button',name='CONDUCTOR',exact=True).click()
   # Replace current PHRASE master and CC16 reference with masterless CC17.
   page.locator('.conductor-layer').nth(0).get_by_role('button',name='REMOVE BLOCK',exact=True).click();page.locator('.conductor-layer').nth(1).get_by_role('button',name='REMOVE BLOCK',exact=True).click();page.get_by_role('button',name='Add PHRASE STEP 1 LAYER 2',exact=True).click();page.locator('.conductor-add-menu').get_by_text('MOVEMENTS',exact=True).click();page.get_by_role('button',name='MOVEMENT · JACK BROWSER',exact=True).click();page.get_by_role('button',name='DONE',exact=True).click();page.locator('#editor').wait_for(state='hidden')
   page.get_by_role('button',name='SAVE PATCH',exact=True).click();page.get_by_text('PATCH SAVED',exact=True).wait_for();page.get_by_role('button',name='LOAD PATCH',exact=True).click();page.wait_for_function('()=>!pending');page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for();assert not c.request()['movements']['active']
   page.locator('[data-switch-id="1"] .switch-test').evaluate('e=>e.open=true');page.locator('[data-switch-id="1"]').get_by_role('button',name='TEST TAP',exact=True).click();page.wait_for_function('()=>latest.movements.active===1');time.sleep(1.3);assert not c.request()['movements']['active']
  probe.stdin.close();lines=probe.stdout.read().splitlines();assert probe.wait(timeout=5)==0;probe=None
  trace=[list(map(int,line.split())) for line in lines];assert all(a[0]+a[1]<=b[0]+b[1] for a,b in zip(trace,trace[1:])),trace
  for rate,cc in [(10,10),(25,11),(50,12),(100,13)]:
   events=[e for e in trace if e[2]==176 and e[3]==cc];origin=events[0][0]+events[0][1]
   assert len(events)==rate+1,(rate,events)
   assert [e[0]+e[1]-origin for e in events]==[i*48000//rate for i in range(rate+1)],(rate,events)
   assert [e[4] for e in events]==[int(i*127/rate+.5) for i in range(rate+1)],(rate,events)
  events=[e for e in trace if e[2]==176 and e[3]==14];assert events[-1][4]==77 and sum(e[4]==77 for e in events)==1,events
  assert [e[4] for e in trace if e[2]==176 and e[3]==15]==[25,102]
  same=[e for e in trace if e[2]==176 and e[3]==18];assert len(same)==2 and same[0][0]==same[1][0] and [e[1] for e in same]==[16,220] and [e[4] for e in same]==[0,77],same
  soft_events=[e for e in trace if e[2]==176 and e[3]==24];assert soft_events[0][4]==100,soft_events
  expected=[int(((100/127)*(1-min(1,(i/25)/.2))+(i/25)*min(1,(i/25)/.2))*127+.5) for i in range(26)]
  assert [e[4] for e in soft_events[1:]]==expected,soft_events
  independent=[e for e in trace if e[2]==176 and e[3]==21];assert len(independent)==76 and independent[0][4]==0 and independent[-1][4]==127,independent
  stepped=[e for e in trace if e[2]==177 and e[3]==22];origin=stepped[0][0]+stepped[0][1];assert [e[4] for e in stepped]==[0,25,114,13],stepped;assert [e[0]+e[1]-origin for e in stepped]==[0,13440,24960,48000],stepped
  short_events=[e for e in trace if e[2]==176 and e[3]==23];assert len(short_events)==2 and [e[4] for e in short_events]==[0,127] and short_events[1][0]+short_events[1][1]-short_events[0][0]-short_events[0][1]==480,short_events
  if os.environ.get('MOVEMENT_BROWSER_AUTHOR')=='1':
   web_events=[e for e in trace if e[2]==176 and e[3]==17];assert len(web_events)==26 and web_events[0][4]==0 and web_events[-1][4]==127,web_events
  assert any(e[2]==144 and e[3]==60 for e in trace),trace
  report=dict(backend='actual private JACK',physicalHardware=False,sampleRate=48000,blockSize=8192,events=trace,rates=[10,25,50,100],state=c.request())
  if os.environ.get('MOVEMENT_TRACE'):Path(os.environ['MOVEMENT_TRACE']).write_text(json.dumps(report,indent=2)+'\n')
  print('PASS actual JACK MOVEMENT initial/final values, exact 10/25/50/100 Hz timestamps, replacement, intact physical CC takeover, PHRASE coexistence, STOP PHRASES independence, PANIC and stable MIDI ordering')
 finally:
  if browser is not None:browser.close();pw.stop()
  if web is not None:web.terminate();web.communicate(timeout=5)
  if probe is not None:probe.terminate();probe.communicate(timeout=5)
  if engine is not None:engine.terminate();engine.communicate(timeout=10)
  server.terminate();server.communicate(timeout=5)

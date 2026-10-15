#!/usr/bin/env python3
"""Actual JACK -> native PHRASE/Controller runtime -> captured MIDI CC7 + notes."""
import json,os,subprocess,sys,tempfile,time,socket,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'headless'),str(ROOT/'tests')]
from server import Control
import conductor
from test_conductor_persistence import step,block
from test_movement_persistence import movement
with tempfile.TemporaryDirectory(prefix='mbmf-reveal-jack-') as tmp:
 env=dict(os.environ,JACK_DEFAULT_SERVER='mbmf-reveal')
 processes=[];probe=None;browser=None;pw=None
 logs={name:open(Path(tmp)/(name+'.log'),'w+') for name in ('jack','engine')}
 try:
  jack=subprocess.Popen([env['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime','-d','dummy','-r','48000','-p','8192'],env=env,stdout=logs['jack'],stderr=subprocess.STDOUT);processes.append(jack)
  time.sleep(1);assert jack.poll() is None
  sock=str(Path(tmp)/'engine.sock')
  engine=subprocess.Popen([env['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),sock,'--chain','--chain-timing','2','--jack','--client','mbmf_d'],env=env,stdout=logs['engine'],stderr=subprocess.STDOUT);processes.append(engine)
  def wait(fn,label):
   end=time.monotonic()+10
   while time.monotonic()<end:
    assert all(p.poll() is None for p in processes),label
    if fn():return
    time.sleep(.03)
   raise AssertionError(label)
  wait(lambda:Path(sock).exists(),'native socket');c=Control(sock)
  def cmd(**args):
   s=c.request();r=c.request(revision=s['revision'],session=s['engineSessionId'],**args);assert r.get('status')=='ok',r;return r
  cmd(op=2)
  for i in (2,3):cmd(op=32,target=i,arg=21,macro=[0,0])
  cmd(op=9,target=1,arg=1,value=0) # Physical CC stays on its original channel.
  for p,ch,pitch,length in ((0,0,48,30),(1,1,72,30)):
   cmd(op=32,target=p+1,arg=20,macro=[0,1]);cmd(op=32,target=p+1,arg=15,macro=[0,1])
   events=[[0,144|ch,pitch,100],[length-.5,128|ch,pitch,0]]
   if p==1:events=[[0,145,72,100],[.75,145,76,90],[10,129,72,0],[20,129,76,0]]
   cmd(op=35,target=p,arg=1,phrase=dict(lengthSeconds=length,events=events))
  # The source owns sustain as well as notes. Use the validated legacy patch
  # carrier because SMF import intentionally accepts notes only.
  state=c.request();source_patch=c.request(op=4,revision=state['revision'],session=state['engineSessionId'])
  source_events=[[0,177,64,127],[0,145,72,100],[.75,145,76,90],[10,129,72,0],[20,129,76,0],[29,177,64,0]]
  for j,(seconds,st,n,value) in enumerate(source_events):
   at=2048*5+j*5;source_patch['memory'][at:at+5]=[seconds*48000,st,n,value,0]
  source_patch['memory'][16*2048*5+1]=len(source_events)
  cmd(op=5,target=7,patch=source_patch)
  sw=c.request()['switches'][0]['settings'];sw[:4]=[1,1,0,110];sw[8]=250;cmd(op=41,target=1,settings=sw+[0]*64+[0]*16)
  s=c.request();p=c.request(op=4,revision=s['revision'],session=s['engineSessionId']);model=conductor.migrate(p)
  master=block(model['sources'][0]['id']);pad=block(model['sources'][1]['id']);pad['overrides'].update(trigger=dict(mode='OVERRIDE',value='HOLD'),entry=dict(mode='OVERRIDE',value='REVEAL'))
  m=movement();m.update(duration=3,target=dict(type='CC',channel=2,number=7),retrigger='DIRECT',points=[[0,.8],[1,.2]]);model.update(version=2,ccRate=25,movements=[m])
  model['switches']=[dict(switchId=1,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',steps=[step([master,pad])])]
  def install():
   cmd(op=2);s=c.request();p=c.request(op=4,arg=1,revision=s['revision'],session=s['engineSessionId']);p['conductor']=conductor.encode(model);cmd(op=5,target=7,arg=1,patch=p)
  # Author REVEAL through the real editor, using the already-proven source picker.
  pad['overrides'].pop('entry')
  install()
  if env.get('REVEAL_BROWSER_TEST'):
   from playwright.sync_api import sync_playwright
   from test_conductor_editor_browser import save_draft
   with socket.socket() as port_socket:port_socket.bind(('127.0.0.1',0));port=port_socket.getsockname()[1]
   base=f'http://127.0.0.1:{port}'
   web=subprocess.Popen([sys.executable,str(ROOT/'headless/server.py'),'--socket',sock,'--port',str(port),'--patch-dir',str(Path(tmp)/'patches')],env=env,stdout=subprocess.DEVNULL,stderr=logs['engine']);processes.append(web)
   def ready():
    try:return urllib.request.urlopen(base+'/api/v1/state',timeout=1).status==200
    except OSError:return False
   wait(ready,'real HTTP editor')
   pw=sync_playwright().start();browser=pw.chromium.launch(headless=True,executable_path=env.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox','--disable-gpu']);page=browser.new_page(viewport=dict(width=1440,height=900));page.goto(base);page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
   def properties():
    page.locator('[data-switch-id="1"]').get_by_role('button',name='CONDUCTOR',exact=True).click();page.locator('.conductor-step').first.get_by_role('button',name='EDIT BLOCK',exact=True).nth(1).click()
   properties();page.get_by_label('ENTRY inheritance',exact=True).select_option('OVERRIDE');page.get_by_label('ENTRY override',exact=True).select_option('REVEAL');page.get_by_text('CC7 CHANNEL-WIDE',exact=True).first.wait_for();save_draft(page)
   page.get_by_role('button',name='SAVE PATCH',exact=True).click();page.get_by_text('PATCH SAVED',exact=True).wait_for();page.get_by_role('button',name='LOAD PATCH',exact=True).click();page.wait_for_function('()=>!pending');page.reload();page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
   assert not c.request()['instances'],'browser SAVE/LOAD cannot start hidden notes'
   model=json.load(urllib.request.urlopen(base+'/api/v1/conductor'))['model'];pad=model['switches'][0]['steps'][0]['layers'][1]['block'];assert pad['overrides']['entry']['value']=='REVEAL'
  else:pad['overrides']['entry']=dict(mode='OVERRIDE',value='REVEAL');install()
  probe=subprocess.Popen([env['CONDUCTOR_JACK_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);assert probe.stdout.readline().strip()=='READY'
  def event(st,n=110,v=None,offset=16):
   if v is None:v=127 if st&240==144 else 0
   probe.stdin.write(f'{st} {n} {v} {offset}\n');probe.stdin.flush()
  event(144);event(128,offset=64);wait(lambda:len(c.request()['instances'])==1,'short tap bass only');time.sleep(.4);assert len(c.request()['instances'])==1
  cmd(op=2);time.sleep(.2)
  event(144);wait(lambda:len(c.request()['instances'])==2,'PRESS starts real hidden pad')
  time.sleep(.4);event(128);time.sleep(1.8);assert [v['phraseId'] for v in c.request()['instances']]==[1,2],'LATCH retains both occurrences after RELEASE'
  cmd(op=2)
  if browser:
   properties();page.get_by_label('REL inheritance',exact=True).select_option('OVERRIDE');page.get_by_label('REL override',exact=True).select_option('GATE');save_draft(page)
   model=json.load(urllib.request.urlopen(base+'/api/v1/conductor'))['model'];pad=model['switches'][0]['steps'][0]['layers'][1]['block'];assert pad['overrides']['release']['value']=='GATE'
  else:pad['overrides']['release']=dict(mode='OVERRIDE',value='GATE');install()
  event(144);wait(lambda:len(c.request()['instances'])==2,'GATE hidden instance');print('GATE PRESS',{k:v for k,v in c.request().items() if k in ('reveals','lastEvent','sampleClock')},flush=True);time.sleep(.4);print('GATE HOLD',{k:v for k,v in c.request().items() if k in ('reveals','lastEvent','sampleClock')},flush=True);event(128);time.sleep(.7)
  assert len(c.request()['instances'])==2,'GATE remask retains same running timeline'
  # Source STOP releases only pad; bass remains. No deferred CC7 after cleanup.
  cmd(op=40,target=1,arg=6);wait(lambda:len(c.request()['instances'])==1,'targeted pad STOP');time.sleep(.3)
  cmd(op=2);time.sleep(.2)
  # A real CC7 MOVEMENT loses its token to the newly hidden PHRASE. Its
  # subsequent cleanup must not delete the winning REVEAL target.
  cmd(op=46,target=0);time.sleep(.25);event(144);wait(lambda:len(c.request()['instances'])==2,'REVEAL replaces CC7 MOVEMENT');time.sleep(.4)
  assert c.request()['movements']['active']==0,'losing CC7 MOVEMENT cannot keep writing'
  event(128);time.sleep(1.8);cmd(op=2);time.sleep(.2)
  # PRESS and PANIC in one actual source callback: releases must not be stamped
  # before their attacks and no private START may survive the later PANIC.
  panic=c.request()['switches'][1]['settings'];panic[:4]=[1,1,0,111];panic[6]=0;panic[12]=6;cmd(op=41,target=2,settings=panic+[0]*64+[0]*16)
  event(144);event(144,111,127,64);wait(lambda:c.request()['switches'][1]['lastAction']==6,'actual hardware PANIC gesture');time.sleep(.3)
  assert not c.request()['instances'];event(128);event(128,111);time.sleep(.2)
  event(144);wait(lambda:len(c.request()['instances'])==2,'physical takeover scenario');time.sleep(.4)
  event(177,7,85);time.sleep(.2);event(128);time.sleep(1);cmd(op=40,target=1,arg=6);time.sleep(.3)
  cmd(op=2);time.sleep(.3);assert not c.request()['instances'];assert c.request()['outputOverflow']==0
  probe.stdin.close();trace=[list(map(int,line.split())) for line in probe.stdout.read().splitlines()];assert probe.wait(timeout=5)==0;probe=None
  if env.get('REVEAL_EVIDENCE_DIR'):
   dest=Path(env['REVEAL_EVIDENCE_DIR']);dest.mkdir(parents=True,exist_ok=True);(dest/'observed-trace.json').write_text(json.dumps(dict(events=trace,state=c.request()),indent=2)+'\n')
  assert all(a[0]+a[1]<=b[0]+b[1] for a,b in zip(trace,trace[1:])),trace
  notes=[e for e in trace if e[2]&240==144 and e[4]>0]
  assert [e[3] for e in notes]==[48,72,48,72,76,48,72,76,48,72,76,48,72,48,72,76],notes
  pads=[e for e in notes if e[3]==72];cc=[e for e in trace if e[2]==177 and e[3]==7]
  for index,on in enumerate(pads):
   pos=trace.index(on);assert any(e[2:]==[177,7,0] and e[0]+e[1]==on[0]+on[1] for e in trace[:pos]),('CC7 mute must precede real pad attack',on,trace)
   if index not in (0,4): # Early RELEASE and PANIC precede HOLD.
    hide=max(i for i,e in enumerate(trace[:pos]) if e[2:]==[177,7,0] and e[0]+e[1]==on[0]+on[1])
    baseline=next((e[4] for e in reversed(trace[:hide]) if e[2]==177 and e[3]==7),127)
    assert any(e[4]==baseline and e[0]+e[1]-on[0]-on[1]==12000 for e in cc),('HOLD must restore actual prior audible value at exact threshold',on,baseline,cc)
    if index==3:assert 0<baseline<127,'MOVEMENT effective value must replace default 127'
   elif index==4:
    for pitch in (48,72):assert any(e[2]&240==128 and e[3]==pitch and e[0]==on[0] and e[1]==64 for e in trace),('PANIC release must follow same-cycle attacks',on,trace)
   else:
    assert any(e[2:4]==[129,72] and e[0]==on[0] and e[1]==64 for e in trace),'short tap releases real hidden attack at RELEASE'
    assert not any(e[2]&240==128 and e[3]==48 and e[0]==on[0] and e[1]==64 for e in trace),'short RELEASE must leave bass playing'
    release_cc=next(i for i,e in enumerate(trace) if e[2:]==[177,64,0] and e[0]==on[0] and e[1]==64)
    restore_cc=next(i for i,e in enumerate(trace) if e[2:]==[177,7,127] and e[0]==on[0] and e[1]==64)
    assert release_cc<restore_cc,'source-owned sustain must release before hidden volume is restored'

  # Gate second note remains at original 0.75 s after PRESS despite remasking.
  gate_pad=pads[2];gate_note=[e for e in notes if e[3]==76][1]
  assert gate_note[0]+gate_note[1]-gate_pad[0]-gate_pad[1]==36000,(gate_pad,gate_note)
  physical=next(i for i,e in enumerate(trace) if e[2:]==[177,7,85])
  assert not any(e[2]==177 and e[3]==7 for e in trace[physical+1:]),'old reveal must not remask/restore over physical owner'
  report=dict(events=trace,attacks=[e[3] for e in notes],cc7=[e for e in cc],backend='actual private acyclic JACK',sampleRate=48000,blockFrames=8192,physicalHardware=False)
  if env.get('REVEAL_EVIDENCE_DIR'):
   dest=Path(env['REVEAL_EVIDENCE_DIR']);dest.mkdir(parents=True,exist_ok=True);(dest/'jack-trace.json').write_text(json.dumps(report,indent=2)+'\n')
  print('PASS real JACK REVEAL mute-before-On, 250ms reveal, no reattack, GATE timeline, targeted STOP, physical takeover, PANIC; attacks',report['attacks'],'CC7',cc)
 finally:
  if browser is not None:browser.close();pw.stop()
  if probe is not None:probe.terminate();probe.communicate(timeout=5)
  for process in reversed(processes):
   process.terminate()
   try:process.wait(timeout=10)
   except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5);raise
  for name,log in logs.items():
   log.flush();log.seek(0)
   if env.get('REVEAL_EVIDENCE_DIR'):
    dest=Path(env['REVEAL_EVIDENCE_DIR']);dest.mkdir(parents=True,exist_ok=True);(dest/(name+'.log')).write_text(log.read())
   log.close()

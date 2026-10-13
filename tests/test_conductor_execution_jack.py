#!/usr/bin/env python3
"""Private JACK source -> actual engine -> captured port MIDI, never an API echo."""
import os,sys,json,time,tempfile,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'headless'),str(ROOT/'tests')]
from server import Control
import conductor
from test_conductor_persistence import step,block,uid
with tempfile.TemporaryDirectory(prefix='mbmf-conductor-jack-') as tmp:
 env=dict(os.environ,JACK_DEFAULT_SERVER='mbmf-conductor-d')
 server=subprocess.Popen([env['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime','-d','dummy','-r','48000','-p','8192'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 engine=probe=None
 try:
  time.sleep(1);assert server.poll() is None
  sock=str(Path(tmp)/'engine.sock')
  engine=subprocess.Popen([env['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),sock,'--chain','--jack','--client','mbmf_d'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  deadline=time.monotonic()+15
  while not Path(sock).exists() and time.monotonic()<deadline:
   assert engine.poll() is None;time.sleep(.05)
  c=Control(sock)
  def command(**args):
   state=c.request();result=c.request(revision=state['revision'],session=state['engineSessionId'],**args);assert result.get('status')=='ok',result;return result
  def wait(fn,label):
   until=time.monotonic()+8
   while time.monotonic()<until:
    if fn():return
    time.sleep(.03)
   raise AssertionError(label+': '+json.dumps(c.request()))
  command(op=2)
  for i in (2,3):command(op=32,target=i,arg=21,macro=[0,0])
  settings=c.request()['switches'][0]['settings'];settings[:4]=[1,1,0,110];settings[11]=0
  command(op=41,target=1,settings=settings+[0]*64+[0]*16)
  for p,pitch in enumerate((60,62,64,65)):
   command(op=32,target=p+1,arg=20,macro=[0,1])
   command(op=32,target=p+1,arg=15,macro=[0,1])
   command(op=35,target=p,arg=1,phrase=dict(lengthSeconds=60,events=[[0,144,pitch,100],[59,128,pitch,0]]))
  state=c.request();patch=c.request(op=4,revision=state['revision'],session=state['engineSessionId'])
  model=conductor.migrate(patch);sources=model['sources']
  model['switches']=[dict(switchId=1,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',steps=[step([block(sources[i]['id'])]) for i in range(4)])]
  def install(m):
   command(op=2);state=c.request();p=c.request(op=4,arg=1,revision=state['revision'],session=state['engineSessionId']);p['conductor']=conductor.encode(m);command(op=5,target=7,arg=1,patch=p)
  install(model)
  probe=subprocess.Popen([env['CONDUCTOR_JACK_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
  assert probe.stdout.readline().strip()=='READY'
  def event(st,n,v):probe.stdin.write(f'{st} {n} {v}\n');probe.stdin.flush();time.sleep(.2)
  for i in range(5):
   event(144,110,127);wait(lambda:len(c.request()['instances'])==i+1,'four distinct STEPS and wrap');event(128,110,0)
   assert c.request()['switches'][0]['conductor']['step']==i%4+1
  a=c.request()['instances'][0];command(op=44,instance=(a['id'],a['generation']));time.sleep(.3)
  assert len(c.request()['instances'])==4
  command(op=2);time.sleep(.3);assert not c.request()['instances']
  model['switches'][0]['steps']=[step([block(uid())])];install(model)
  event(144,110,127);event(128,110,0);assert not c.request()['instances'];assert c.request()['switches'][0]['conductor']['missing']==1
  model['switches'][0]['steps']=[step([block(sources[0]['id']),block(sources[1]['id'])])];install(model)
  event(144,110,127);wait(lambda:len(c.request()['instances'])==2,'simultaneous layers');event(128,110,0)
  owners=c.request()['instances'];command(op=44,instance=(owners[0]['id'],owners[0]['generation']));time.sleep(.2);assert len(c.request()['instances'])==1
  # STOP is the real existing action dispatcher on another legacy switch.
  sw=c.request()['switches'][1]['settings'];sw[0]=1;sw[12]=2
  command(op=41,target=2,settings=sw+[0]*64+[0]*16);command(op=1,target=2);time.sleep(.3);assert not c.request()['instances']
  command(op=2);time.sleep(.3)
  state=c.request();saved=c.request(op=4,revision=state['revision'],session=state['engineSessionId']);command(op=5,target=7,patch=saved);time.sleep(.3)
  assert not c.request()['instances'] and c.request()['switches'][0]['conductor']['step']==0
  assert c.request()['outputOverflow']==0
  probe.stdin.close();lines=probe.stdout.read().splitlines();assert probe.wait(timeout=5)==0;probe=None
  trace=[list(map(int,line.split())) for line in lines];ons=[e for e in trace if e[2]&240==144 and e[4]>0]
  assert [e[3] for e in ons]==[60,62,64,65,60,60,62],trace
  assert all(a[0]+a[1]<=b[0]+b[1] for a,b in zip(trace,trace[1:])),trace
  assert all(e[3]!=110 for e in trace),'footswitch commands leaked into musical output'
  # Last-owner MIDI semantics: first targeted same-pitch owner STOP emits no Off.
  assert [e[3] for e in trace if e[2]&240==128]==[60,62],trace
  assert any(e[2]==176 and e[3] in (120,123) for e in trace),'PANIC did not emit receiver cleanup'
  sounding=set()
  for e in trace:
   ch=e[2]&15;kind=e[2]&240;key=(ch,e[3])
   if kind==144 and e[4]>0:sounding.add(key)
   elif kind==128 or (kind==144 and e[4]==0):sounding.discard(key)
   elif kind==176 and e[3] in (120,123):sounding={k for k in sounding if k[0]!=ch}
  assert not sounding,('receiver still sounding',sounding,trace)
  report=dict(events=trace,attacks=[e[3] for e in ons],backend='actual private JACK',sampleRate=48000,blockSize=8192,physicalHardware=False)
  if os.environ.get('CONDUCTOR_TRACE'):Path(os.environ['CONDUCTOR_TRACE']).write_text(json.dumps(report,indent=2)+'\n')
  print('PASS actual JACK CONDUCTOR: hardware-like PRESS input, four STEPS/wrap, independent layers, missing reference silence, selective STOP, PANIC, silent LOAD and timestamp ordering',json.dumps({'notes':[e for e in trace if e[2]&240 in (128,144)],'cleanupMessages':sum(e[2]&240==176 for e in trace),'attacks':report['attacks']}))
 finally:
  if probe is not None:probe.terminate();probe.communicate(timeout=5)
  if engine is not None:engine.terminate();engine.communicate(timeout=10)
  server.terminate();server.communicate(timeout=5)

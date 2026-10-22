#!/usr/bin/env python3
"""Actual private JACK MIDI input/output; no hardware or Oram route activation."""
import json,os,pathlib,subprocess,sys,tempfile,time,types
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'headless')]
from server import Control
from native_capacity import build_source
from patch_recall import RecallService
with tempfile.TemporaryDirectory(prefix='mbmf-dickinson-jack-') as tmp:
 folder=pathlib.Path(tmp);env=dict(os.environ,JACK_DEFAULT_SERVER='mbmf-dickinson-'+str(os.getpid()))
 log=(folder/'run.log').open('w+');engine=probe=None
 jack=subprocess.Popen([env['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime','-d','dummy','-r','48000','-p','1024'],env=env,stdout=log,stderr=log)
 try:
  time.sleep(1);assert jack.poll() is None
  source=folder/'native.jsfx';source.write_text(build_source((ROOT/'midi_human_looper.jsfx').read_text()));sock=folder/'engine.sock'
  engine=subprocess.Popen([env['HEADLESS_BINARY'],str(source),str(sock),'--chain','--chain-timing','2','--jack','--client','mbmf_d'],env=env,stdout=log,stderr=log)
  until=time.monotonic()+15
  while not sock.exists():assert engine.poll() is None and time.monotonic()<until;time.sleep(.02)
  c=Control(str(sock))
  def command(op,**kw):
   s=c.request();r=c.request(op=op,revision=s['revision'],session=s['engineSessionId'],**kw);assert r.get('status')=='ok',r;return r
  command(2)
  for i in (2,3):command(32,target=i,arg=21,macro=[0,0])
  command(13,target=1,arg=1,note=5)
  tf=next(t for t in c.request()['instruments'][0]['transformers'] if t['type']==5)
  command(12,target=1,module=tf['id'],parameters=[dict(kind=k,value=v) for k,v in [(3,1),(4,1),(5,16),(6,.5),(12,0),(27,4),(28,1)]])
  s=c.request();saved=c.request(op=4,revision=s['revision'],session=s['engineSessionId']);command(5,target=8,patch=saved,loaded_slot=7)
  probe=subprocess.Popen([env['CONDUCTOR_JACK_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True)
  assert probe.stdout.readline().strip()=='READY'
  def send(st,n,v):probe.stdin.write(f'{st} {n} {v} 16\n');probe.stdin.flush()
  for n in (60,64,67):send(144,n,100)
  time.sleep(.7)
  # Runtime no-op while actual MIDI-generated ARP ownership has been exercised.
  with patch('patch_recall.threading.Thread'):
   service=RecallService(types.SimpleNamespace(snapshot_dir=str(folder)),folder,folder/'library',{1:dict(control=c)})
  service.settings.update(enabled=True,channel=15)
  before=c.request()
  for _ in range(8):
   assert service.midi_event(1,bytes([0xce,7]));job=service.pending;service.pending=None;service.recall(job[1],midi=True)
  after=c.request();assert after['revision']==before['revision'] and after['engineSessionId']==before['engineSessionId']
  for n in (60,64,67):send(128,n,0)
  time.sleep(.15)
  # A second genuine gate plays the same complete traversal exactly once.
  for n in (60,64,67):send(144,n,100)
  time.sleep(.7)
  command(2);time.sleep(.3)
  probe.stdin.close();lines=probe.stdout.read().splitlines();assert probe.wait(timeout=5)==0;probe=None
  events=[list(map(int,line.split())) for line in lines];notes=[v[3] for v in events if v[2]&240==144 and v[4]]
  assert notes==[60,64,67,60,64,67],notes
  owned={}
  for frame,off,st,n,v in events:
   if st&240==144 and v:owned[(st&15,n)]=owned.get((st&15,n),0)+1
   elif st&240==128 or (st&240==144 and not v):
    # PANIC's safety sweep intentionally includes unmatched releases.
    owned[(st&15,n)]=max(0,owned.get((st&15,n),0)-1)
   elif st&240==176 and n in (120,123):owned={k:0 if k[0]==st&15 else count for k,count in owned.items()}
  assert not any(owned.values()),owned
  assert all(a[0]+a[1]<=b[0]+b[1] for a,b in zip(events,events[1:])),events
  state=c.request();assert state['outputOverflow']==0 and not state['activeNotes']
  result=dict(backend='private non-RT dummy JACK',sampleRate=48000,frames=1024,notes=notes,events=events,counters={k:state.get(k) for k in ('xrunCount','outputOverflow','midiReceived','midiWritten')},samePatchPCs=8,sessionUnchanged=True)
  print('PASS DICKINSON real JACK',json.dumps({k:v for k,v in result.items() if k!='events'}))
  if os.environ.get('DICKINSON_MIDI_EVIDENCE'):pathlib.Path(os.environ['DICKINSON_MIDI_EVIDENCE']).write_text(json.dumps(result,indent=2)+'\n')
 finally:
  if probe is not None:probe.terminate();probe.communicate(timeout=5)
  for worker in (engine,jack):
   if worker is not None:worker.terminate();worker.wait(timeout=10)
  log.flush();log.seek(0)
  if sys.exc_info()[0]:print(log.read()[-5000:])
  log.close()

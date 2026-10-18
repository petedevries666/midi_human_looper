#!/usr/bin/env python3
"""Real private dummy-JACK qualification, never run on a live Zynthian server."""
import argparse,csv,gzip,hashlib,json,os,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'headless'),str(ROOT/'tests')]
from server import Control
from test_conductor_persistence import step,block
from test_movement_persistence import movement
import conductor
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--buffers',default='8192,1024,512,256,128');p.add_argument('--seconds',type=float,default=3);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
results=[]
for frames in map(int,a.buffers.split(',')):
 d=a.output/str(frames);d.mkdir(exist_ok=True);env=dict(os.environ,JACK_DEFAULT_SERVER=f'mbmf-rt-{frames}');handles=[];server=engine=probe=None;phases=[];report=dict(frames=frames,sampleRate=48000,deadlineUs=frames/48000*1e6,physicalHardware=False,errors=[])
 def phase(name,action=None,seconds=None):
  start=time.monotonic_ns()
  if action:action()
  time.sleep(a.seconds if seconds is None else seconds)
  phases.append(dict(name=name,start=start,end=time.monotonic_ns()))
 try:
  for name in ('jack','engine'):handles.append(open(d/(name+'.log'),'w'))
  server=subprocess.Popen([env['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime','-d','dummy','-r','48000','-p',str(frames)],env=env,stdout=handles[0],stderr=subprocess.STDOUT);time.sleep(1);assert server.poll() is None
  sock=str(d.resolve()/'engine.sock');engine=subprocess.Popen([env['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),sock,'--chain','--jack','--client','mbmf_d','--rt-trace',str(d/'callback.csv')],env=env,stdout=handles[1],stderr=subprocess.STDOUT)
  deadline=time.monotonic()+15
  while not Path(sock).exists() and time.monotonic()<deadline:assert engine.poll() is None;time.sleep(.05)
  c=Control(sock)
  def command(**args):
   state=c.request();r=c.request(revision=state['revision'],session=state['engineSessionId'],**args);assert r.get('status')=='ok' or (args.get('op')==4 and r.get('format')=='MIDI_HUMAN_LOOPER_PATCH'),str(r)[:1500];return r
  command(op=2)
  for i in (2,3):command(op=32,target=i,arg=21,macro=[0,0])
  settings=c.request()['switches'][0]['settings'];settings[:4]=[1,1,0,110];settings[11]=0;command(op=41,target=1,settings=settings+[0]*64+[0]*16)
  command(op=35,target=0,arg=1,phrase=dict(lengthSeconds=60,events=[[0,144,60,100],[59,128,60,0]]))
  patch=command(op=4,arg=1);model=conductor.migrate(patch);src=model['sources'][0]['id']
  items=[]
  for cc in (10,11,12,13):
   m=movement();m.update(retrigger='DIRECT',duration=60,points=[[0,0],[1,1]]);m['target']['number']=cc;items.append(m)
  replacement=movement();replacement.update(retrigger='DIRECT',duration=60,points=[[0,.8],[1,.8]]);replacement['target']['number']=10;items.append(replacement)
  model.update(version=2,movements=items,ccRate=100);model['switches']=[dict(switchId=1,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',steps=[step([block(src),block(items[0]['id'],'MOVEMENT')]),step([None,block(items[1]['id'],'MOVEMENT')])])];patch['conductor']=conductor.encode(model);command(op=5,target=7,arg=1,patch=patch)
  probe=subprocess.Popen([env['MOVEMENT_JACK_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);assert probe.stdout.readline().strip()=='READY'
  def event(st,n,v):probe.stdin.write(f'{st} {n} {v} 16\n');probe.stdin.flush()
  def start(*ids):
   for i in ids:command(op=46,target=i)
  phase('idle')
  phase('phrase',lambda:command(op=1,target=1)) # real existing Smart Switch TEST -> CONDUCTOR
  command(op=2)
  phase('movement',lambda:start(0))
  command(op=2)
  phase('independent',lambda:start(0,1,2)) # 8192/100 Hz bound admits exactly three
  command(op=2)
  phase('combined',lambda:(command(op=1,target=1),start(1,2)))
  phase('replacement',lambda:start(4))
  phase('physical_takeover',lambda:event(176,10,77))
  def burst():
   for repeat in range(8):
    for n in range(32):event(144,n+64,100)
    time.sleep(max(.04,frames/48000+.02))
    for n in range(32):event(128,n+64,0)
    time.sleep(max(.04,frames/48000+.02))
  phase('note_bursts',burst)
  def polling():
   until=time.monotonic()+a.seconds
   while time.monotonic()<until:c.request();time.sleep(.02)
  phase('telemetry',polling,seconds=0)
  phase('step_change',lambda:command(op=1,target=1))
  # Existing STOP PHRASES switch action must leave automation running.
  sw=c.request()['switches'][1]['settings'];sw[0]=1;sw[12]=2;command(op=41,target=2,settings=sw+[0]*64+[0]*16)
  phase('stop_phrases',lambda:command(op=1,target=2));state=c.request();assert not state['instances'] and state['movements']['active']>0,state
  phase('panic',lambda:command(op=2));state=c.request();assert not state['movements']['active'] and not state['instances'],state
  report['state']=state
 except Exception as e:
  report['errors'].append(str(e));(d/'failure.txt').write_text(traceback.format_exc())
 finally:
  if probe:
   try:
    probe.stdin.close();lines=probe.stdout.read().splitlines();report['probeExit']=probe.wait(timeout=5);events=[list(map(int,l.split())) for l in lines];(d/'midi.json').write_text(json.dumps(events));report['midiEvents']=len(events)
    if report['probeExit']!=0:report['errors'].append('probe exit '+str(report['probeExit']))
    if not all(x[0]+x[1]<=y[0]+y[1] for x,y in zip(events,events[1:])):report['errors'].append('MIDI timestamp order')
    if not any(e[2]==144 and e[3]==60 for e in events):report['errors'].append('missing real PHRASE Note On')
    if not any(e[2]==176 and e[3]==10 and e[4]==77 for e in events):report['errors'].append('missing intact physical takeover')
   except Exception as e:report['errors'].append('probe '+str(e));probe.kill()
  if engine:
   engine.terminate()
   try:report['engineExit']=engine.wait(timeout=30)
   except subprocess.TimeoutExpired:engine.kill();report['errors'].append('engine shutdown timeout')
  if server:server.terminate();server.wait(timeout=10)
  for h in handles:h.close()
  (d/'phases.json').write_text(json.dumps(phases,indent=2))
  if (d/'callback.csv').exists():
   lines=(d/'callback.csv').read_text().splitlines();report['traceFooter']=lines[-1];rows=list(csv.DictReader(l for l in lines if not l.startswith('#')))
   def stats(values):
    values=sorted(values);return dict(count=len(values),p95Us=values[int((len(values)-1)*.95)]/1000,p99Us=values[int((len(values)-1)*.99)]/1000,maxUs=values[-1]/1000) if values else {}
   report['phases']=[]
   for ph in phases:
    rr=[{k:int(v) for k,v in r.items()} for r in rows if ph['start']<=int(r['entry_ns'])<=ph['end']]
    summary=dict(name=ph['name'],wall=stats([r['wall_ns'] for r in rr]),cpu=stats([r['cpu_ns'] for r in rr]),offCpu=stats([max(0,r['wall_ns']-r['cpu_ns']) for r in rr]),entryGap=stats([r['entry_gap_ns'] for r in rr]),deadlineOverruns=sum(r['wall_ns']>frames/48000*1e9 for r in rr))
    for key in ('xruns','rejected','overflow'):summary[key]=max((r[key] for r in rr),default=0)-min((r[key] for r in rr),default=0)
    summary['stages']={k:stats([r[k] for r in rr]) for k in (rows[0].keys() if rows else []) if k.endswith('_cpu_ns') and k!='cpu_ns'}
    report['phases'].append(summary)
   top=sorted(rows,key=lambda r:int(r['wall_ns']),reverse=True)[:20];report['slowest']=top
   with gzip.open(d/'callback.csv.gz','wt') as f:f.write('\n'.join(lines)+'\n')
   (d/'callback.csv').unlink()
  (d/'summary.json').write_text(json.dumps(report,indent=2));results.append(report);print(frames,'errors',report['errors'],flush=True)
meta=dict(binarySha256=hashlib.sha256(Path(os.environ['HEADLESS_BINARY']).read_bytes()).hexdigest(),sourceSha256=hashlib.sha256((ROOT/'headless/engine.cpp').read_bytes()).hexdigest(),host=os.uname()._asdict() if hasattr(os.uname(),'_asdict') else list(os.uname()),results=results)
(a.output/'summary.json').write_text(json.dumps(meta,indent=2));sys.exit(bool(any(r['errors'] for r in results)))

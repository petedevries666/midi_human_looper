#!/usr/bin/env python3
"""Prepared concert profiles: no HTTP/browser, no editing inside measured window.
Real MIDI PRESS/RELEASE, STEP and pedal input via JACK. No PREVIEW.
"""
import argparse,csv,gzip,hashlib,json,os,subprocess,sys,time,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'headless'),str(ROOT/'tests')]
from server import Control
from test_conductor_persistence import step,block
from test_movement_persistence import movement
import conductor
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--buffers',default='512,256');p.add_argument('--profiles',default='LIVE_LIGHT,LIVE_NORMAL,STRESS');p.add_argument('--no-trace',action='store_true');p.add_argument('--seconds',type=float,default=12);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
reports=[]
for frames in map(int,a.buffers.split(',')):
 for profile in a.profiles.split(','):
  d=a.output/f'{frames}-{profile}';d.mkdir(exist_ok=True);env=dict(os.environ,JACK_DEFAULT_SERVER=f'mbmf-live-{frames}');logs=[];server=engine=probe=None;report=dict(profile=profile,frames=frames,sampleRate=48000,physicalHardware=False,browser=False,errors=[],actions=[])
  try:
   for name in ('jack','engine'):logs.append(open(d/(name+'.log'),'w'))
   server=subprocess.Popen([env['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime','-d','dummy','-r','48000','-p',str(frames)],env=env,stdout=logs[0],stderr=subprocess.STDOUT);time.sleep(1);assert server.poll() is None
   sock=str(d.resolve()/'engine.sock');engine=subprocess.Popen([env['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),sock,'--chain','--jack','--client','mbmf_d',]+([] if a.no_trace else ['--rt-trace',str(d/'callback.csv')]),env=env,stdout=logs[1],stderr=subprocess.STDOUT)
   until=time.monotonic()+15
   while not Path(sock).exists() and time.monotonic()<until:assert engine.poll() is None;time.sleep(.05)
   c=Control(sock)
   def command(**args):
    s=c.request();r=c.request(revision=s['revision'],session=s['engineSessionId'],**args);assert r.get('status')=='ok' or (args.get('op')==4 and r.get('format')=='MIDI_HUMAN_LOOPER_PATCH'),str(r)[:1000];return r
   command(op=2)
   for i in (2,3):command(op=32,target=i,arg=21,macro=[0,0])
   settings=c.request()['switches'][0]['settings'];settings[:4]=[1,1,0,110];settings[11]=0;command(op=41,target=1,settings=settings+[0]*64+[0]*16)
   number=1 if profile=='LIVE_LIGHT' else 3 if profile=='LIVE_NORMAL' else 12
   rate=25 if profile!='STRESS' else 100
   movCount=1 if profile=='LIVE_LIGHT' else 2 if profile=='LIVE_NORMAL' else 8
   for i in range(number):
    duration=2 if profile=='LIVE_LIGHT' else 20
    density=2 if profile!='STRESS' else 8
    events=[]
    for j in range(duration*density):
     for k in range(1 if profile!='STRESS' else 4):
      note=36+i*2+k;events.extend([[j/density,144,note,100],[j/density+.08,128,note,0]])
    events.sort(key=lambda e:e[0]);command(op=35,target=i,arg=1,phrase=dict(lengthSeconds=duration,events=events))
   patch=command(op=4,arg=1);model=conductor.migrate(patch);sources=[s['id'] for s in model['sources'][:number]];items=[]
   for i in range(movCount):
    m=movement();duration=4 if profile=='LIVE_LIGHT' else 20
    # Normal: slow triangles; stress: steep triangles keep integer CC output busy.
    segments=1 if profile=='LIVE_LIGHT' else 20 if profile=='LIVE_NORMAL' else 80
    m.update(retrigger='SOFT_RESTART',duration=duration,points=[[j/segments,j%2] for j in range(segments+1)])
    m['target'].update(channel=1,number=20+i);items.append(m)
   master=[block(s) for s in sources]+[block(m['id'],'MOVEMENT') for m in items]
   steps=[step(master)]
   if profile=='LIVE_NORMAL':steps+=[step([None]+[block(m['id'],'MOVEMENT') for m in items]),step([None]+[block(m['id'],'MOVEMENT') for m in items])]
   if profile=='STRESS':steps+=[step([None]+[block(m['id'],'MOVEMENT') for m in items])]
   model.update(version=2,movements=items,ccRate=rate);model['switches']=[dict(switchId=1,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',steps=steps)];patch['conductor']=conductor.encode(model);command(op=5,target=7,arg=1,patch=patch)
   # Drain preparatory PANIC messages and let initial page/cache activity settle.
   until=time.monotonic()+10
   while c.request()['pendingOutput'] and time.monotonic()<until:time.sleep(.03)
   time.sleep(1)
   probe=subprocess.Popen([env['MOVEMENT_JACK_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);assert probe.stdout.readline().strip()=='READY';time.sleep(.2)
   report['before']=c.request();report.update(configuredPhraseSources=number,configuredMovements=movCount,ccRate=rate,phraseLength=2 if profile=='LIVE_LIGHT' else 20,phraseAttacksPerSecond=2 if profile!='STRESS' else 32,curvePoints=[m['points'] for m in items],sourceIds=sources,movementIds=[m['id'] for m in items])
   def midi(st,n,v,label):
    report['actions'].append(dict(timeNs=time.monotonic_ns(),status=st,number=n,value=v,label=label));probe.stdin.write(f'{st} {n} {v} 16\n');probe.stdin.flush()
   def press():midi(144,110,127,'PRESS');time.sleep(.025);midi(128,110,0,'RELEASE')
   start=time.monotonic_ns();report['startNs']=start;press();sent={0};lastBurst=lastPedal=-1
   while (time.monotonic_ns()-start)/1e9<a.seconds:
    t=(time.monotonic_ns()-start)/1e9
    for at in (4,8):
     if t>=at and at not in sent:press();sent.add(at)
    if profile!='LIVE_LIGHT' and 5<=t<6 and int((t-5)*25)!=lastPedal:
     lastPedal=int((t-5)*25);midi(176,20,min(127,lastPedal*5),'expression takeover')
    if profile=='STRESS' and int(t*4)!=lastBurst:
     lastBurst=int(t*4)
     for n in range(16):midi(145,80+n,100,'burst on')
     time.sleep(.02)
     for n in range(16):midi(129,80+n,0,'burst off')
    time.sleep(.005)
   report['endNs']=time.monotonic_ns();report['after']=c.request()
   command(op=2);time.sleep(.4);report['panicAfter']=c.request();assert not report['panicAfter']['instances'] and not report['panicAfter']['movements']['active']
  except Exception as e:report['errors'].append(str(e)[:2000]);(d/'failure.txt').write_text(traceback.format_exc()[:10000])
  finally:
   if probe:
    try:
     probe.stdin.close();lines=probe.stdout.read().splitlines();report['probeExit']=probe.wait(timeout=5);events=[list(map(int,l.split())) for l in lines];(d/'midi.json').write_text(json.dumps(events));assert report['probeExit']==0, 'capture exit '+str(report['probeExit']);bad=[(i,x,y) for i,(x,y) in enumerate(zip(events,events[1:])) if x[0]+x[1]>y[0]+y[1]];assert not bad, 'MIDI timestamp regression '+str(bad[:3])
    except Exception as e:report['errors'].append('probe '+str(e));probe.kill()
   if engine:
    engine.terminate()
    try:report['engineExit']=engine.wait(timeout=15)
    except subprocess.TimeoutExpired:engine.kill();report['errors'].append('engine shutdown timeout')
   if server:server.terminate();server.wait(timeout=10)
   for f in logs:f.close()
   if (d/'callback.csv').exists():
    lines=(d/'callback.csv').read_text().splitlines();rows=[{k:int(v) for k,v in r.items()} for r in csv.DictReader(l for l in lines if not l.startswith('#'))];rr=[r for r in rows if report.get('startNs',0)<=r['entry_ns']<=report.get('endNs',0)]
    def stats(v):
     v=sorted(v);return dict(p95Us=v[int((len(v)-1)*.95)]/1000,p99Us=v[int((len(v)-1)*.99)]/1000,maxUs=v[-1]/1000) if v else {}
    if rr:
     seconds=(report['endNs']-report['startNs'])/1e9
     report['measured']=dict(seconds=seconds,callbacks=len(rr),wall=stats([r['wall_ns'] for r in rr]),cpu=stats([r['cpu_ns'] for r in rr]),offCpu=stats([max(0,r['wall_ns']-r['cpu_ns']) for r in rr]),entryGap=stats([r['entry_gap_ns'] for r in rr]),wallOverruns=sum(r['wall_ns']>frames/48000*1e9 for r in rr),cpuOverruns=sum(r['cpu_ns']>frames/48000*1e9 for r in rr),xruns=max(r['xruns'] for r in rr)-min(r['xruns'] for r in rr),movementMin=min(r['active'] for r in rr),movementMax=max(r['active'] for r in rr),phraseInstancesMax=max(r['phrase_instances'] for r in rr),phraseSourcesMax=max(r['phrase_sources_mask'].bit_count() for r in rr),notes=sum(r['note_events'] for r in rr),cc=sum(r['cc_events'] for r in rr),noteOns=sum(r['note_ons'] for r in rr),rejected=max(r['rejected'] for r in rr)-min(r['rejected'] for r in rr),overflow=max(r['overflow'] for r in rr)-min(r['overflow'] for r in rr),instanceRejected=max(r['instance_rejected'] for r in rr)-min(r['instance_rejected'] for r in rr),stages={k:stats([r[k] for r in rr]) for k in rr[0] if k.endswith('_cpu_ns') and k!='cpu_ns'})
     for k in ('notes','cc','noteOns'):report['measured'][k+'PerSecond']=report['measured'][k]/seconds
     report['measured'].update(orderErrors=sum(r.get('order_errors',0) for r in rr),minorFaults=sum(r.get('minor_faults',0) for r in rr),majorFaults=sum(r.get('major_faults',0) for r in rr),userUs=sum(r.get('user_us',0) for r in rr),systemUs=sum(r.get('system_us',0) for r in rr),involuntarySwitches=sum(r.get('involuntary_switches',0) for r in rr),clockReads=stats([r.get('clock_read_wall_ns',0) for r in rr]),resourceReads=stats([r.get('resource_read_wall_ns',0) for r in rr]),cpuAboveWall=sum(r['cpu_ns']>r['wall_ns']+2000 for r in rr))
     report['slowest']=sorted(rr,key=lambda r:r['wall_ns'],reverse=True)[:15]
    with gzip.open(d/'callback.csv.gz','wt') as f:f.write('\n'.join(lines)+'\n')
    (d/'callback.csv').unlink()
   (d/'summary.json').write_text(json.dumps(report,indent=2)+'\n');reports.append(report);print(frames,profile,'errors',report['errors'],flush=True)
(a.output/'summary.json').write_text(json.dumps(dict(binarySha256=hashlib.sha256(Path(os.environ['HEADLESS_BINARY']).read_bytes()).hexdigest(),results=reports),indent=2)+'\n')
raise SystemExit(bool(any(r['errors'] for r in reports)))

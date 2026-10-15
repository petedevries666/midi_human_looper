#!/usr/bin/env python3
"""Real acyclic JACK safety gates; untouched production JSFX, no browser."""
import json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'headless'),str(ROOT/'tests')]
from server import Control
from test_conductor_persistence import step,block
import conductor
from collections import Counter

def run(burst=False,source_sustain=False,takeover=False):
 with tempfile.TemporaryDirectory(prefix='mbmf-reveal-safety-') as tmp:
  env=dict(os.environ,JACK_DEFAULT_SERVER='mbmf-reveal-safety');processes=[];probe=None
  log=open(Path(tmp)/'runtime.log','w+')
  try:
   jack=subprocess.Popen([env['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime','-d','dummy','-r','48000','-p','8192'],env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(jack);time.sleep(1)
   sock=str(Path(tmp)/'engine.sock')
   engine=subprocess.Popen([env['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),sock,'--chain','--jack','--client','mbmf_d'],env=env,stdout=log,stderr=subprocess.STDOUT);processes.append(engine)
   def wait(fn,label):
    end=time.monotonic()+12
    while time.monotonic()<end:
     assert all(p.poll() is None for p in processes),label
     if fn():return
     time.sleep(.025)
    raise AssertionError(label)
   wait(lambda:Path(sock).exists(),'socket');c=Control(sock)
   def cmd(**args):
    s=c.request();r=c.request(revision=s['revision'],session=s['engineSessionId'],**args);assert r['status']=='ok',r;return r
   cmd(op=2)
   for i in (2,3):cmd(op=32,target=i,arg=21,macro=[0,0])
   cmd(op=9,target=1,arg=1,value=0)
   for p,ch,n in ((0,0,48),(1,1,72)):
    cmd(op=32,target=p+1,arg=20,macro=[0,1]);cmd(op=32,target=p+1,arg=15,macro=[0,1])
    events=[[0,144|ch,n,100],[29,128|ch,n,0]]
    if burst and p==1:events=[[0,145,72,90] for _ in range(1024)]+[[29,129,72,0] for _ in range(1024)]
    cmd(op=35,target=p,arg=1,phrase=dict(lengthSeconds=30,events=events))
   if source_sustain:
    state=c.request();carrier=c.request(op=4,revision=state['revision'],session=state['engineSessionId'])
    entries=[[0,177,64,127,0],[0,145,72,100,0],[29*48000,129,72,0,0],[29*48000,177,64,0,0]]
    carrier['memory'][10240:10260]=[x for row in entries for x in row];carrier['memory'][163841]=4
    cmd(op=5,target=7,patch=carrier)
   original=cmd(op=35,target=1,arg=0)['phraseData']
   sw=c.request()['switches'][0]['settings'];sw[:4]=[1,1,0,110];sw[8]=250;cmd(op=41,target=1,settings=sw+[0]*80)
   s=c.request();patch=c.request(op=4,revision=s['revision'],session=s['engineSessionId']);model=conductor.migrate(patch)
   def pad():
    b=block(model['sources'][1]['id']);b['overrides'].update(trigger=dict(mode='OVERRIDE',value='HOLD'),entry=dict(mode='OVERRIDE',value='REVEAL'));return b
   model['switches']=[dict(switchId=1,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',steps=[step([block(model['sources'][0]['id'])]+[pad() for _ in range(5 if burst else 1)])])]
   patch['conductor']=conductor.encode(model);cmd(op=5,target=7,patch=patch)
   probe=subprocess.Popen([env['CONDUCTOR_JACK_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True);assert probe.stdout.readline().strip()=='READY'
   def send(*messages):
    probe.stdin.write(''.join(' '.join(map(str,m))+'\n' for m in messages));probe.stdin.flush()
   def cycles(n=3):
    s=c.request()['sampleClock'];wait(lambda:c.request()['sampleClock']>=s+n*8192,'callback progress')
   if burst:
    send((144,110,127,16));wait(lambda:c.request()['outputOverflow']>0,'shared output saturation')
    wait(lambda:not c.request()['instances'] and not c.request()['pendingOutput'] and not c.request()['activeNotes'],'bounded emergency cleanup');cycles()
    assert not c.request()['reveals'];assert cmd(op=35,target=1,arg=0)['phraseData']==original
   else:
    send((177,64,127,0),(145,55,100,8));cycles()
    send((144,110,127,16),(128,110,0,64));wait(lambda:len(c.request()['instances'])==1,'hidden owner stopped');cycles()
    if takeover:send((177,7,85,96));cycles()
    send((177,64,0,128));cycles()
    send((129,55,0,256));cycles();cmd(op=2);cycles()
   state=c.request();probe.stdin.close();events=[list(map(int,x.split())) for x in probe.stdout.read().splitlines()];assert probe.wait(timeout=5)==0;probe=None
   out=Path(env.get('REVEAL_SAFETY_EVIDENCE','/tmp/mbmf-reveal-safety-evidence'));out.mkdir(parents=True,exist_ok=True)
   (out/('burst.json' if burst else ('deferred-physical-takeover.json' if takeover else ('shared-source-sustain.json' if source_sustain else 'sustain.json')))).write_text(json.dumps(dict(events=events,state=state,physicalHardware=False,sampleRate=48000,blockFrames=8192),separators=(',',':'))+'\n')
   assert all(a[0]+a[1]<=b[0]+b[1] for a,b in zip(events,events[1:])),events
   if not burst:
    mute=next(i for i,e in enumerate(events) if e[2:]==[177,7,0]);pedal=next(i for i,e in enumerate(events) if e[2:]==[177,64,0]);restore=next(i for i,e in enumerate(events) if e[2:]==[177,7,85 if takeover else 127])
    if takeover:
     assert mute<restore<pedal
     assert not any(e[2:4]==[177,7] for e in events[restore+1:]),'physical volume must supersede deferred restore'
    else:assert mute<pedal<restore,'CC7 must remain hidden until external sustain is released'
    live_on=next(i for i,e in enumerate(events) if e[2:]==[145,55,100]);live_off=next(i for i,e in enumerate(events) if e[2:]==[129,55,0]);assert live_on<restore<live_off,'unrelated live owner must survive early RELEASE'
    assert sum(e[2:]==[129,55,0] for e in events)==1
    assert sum(e[2:]==[177,64,127] for e in events)==(2 if source_sustain else 1),'physical pedal passes once; optional source contributes its own recorded pedal'
    assert not state['outputOverflow']
   else:
    ons=[e for e in events if e[2]&240==144 and e[4]];assert ons,'burst must actually emit MIDI, not just refuse before output'
    first=next(i for i,e in enumerate(events) if e[2]&240==176 and e[3] in (120,123))
    assert not any(e[2]&240==144 and e[4] for e in events[first+1:]),'no queued attack after emergency'
    held=Counter()
    for e in events:
     ch=e[2]&15;kind=e[2]&240
     if kind==144 and e[4]:held[(ch,e[3])]+=1
     elif kind==128 or (kind==144 and not e[4]):held[(ch,e[3])]=max(0,held[(ch,e[3])]-1)
     elif kind==176 and e[3] in (120,123):held=Counter({k:v for k,v in held.items() if k[0]!=ch})
    assert not any(held.values()),'actual receiver must have no sounding stacked notes after emergency'
    cc7=[e[4] for e in events if e[2:4]==[177,7]];assert not cc7 or cc7[-1]==127,cc7
   assert not state['instances'] and not state['activeNotes'] and not state['pendingOutput']
   print('PASS actual JACK', 'REVEAL full-buffer burst' if burst else 'REVEAL external/shared sustain', 'events',len(events),'overflow',state['outputOverflow'])
  finally:
   if probe is not None:probe.terminate();probe.communicate(timeout=5)
   for p in reversed(processes):p.terminate();p.wait(timeout=10)
   log.close()
if __name__=='__main__':run('--burst' in sys.argv,'--source-sustain' in sys.argv,'--takeover' in sys.argv)

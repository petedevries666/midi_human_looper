#!/usr/bin/env python3
"""Actual private JACK -> native ChainMode -> captured MIDI; no echo/model."""
import json,os,subprocess,sys,tempfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'headless'))
from server import Control
with tempfile.TemporaryDirectory(prefix='mbmf-m0-jack-') as tmp:
    env=dict(os.environ,JACK_DEFAULT_SERVER='mbmf-m0')
    engine=probe=None
    logs={n:open(Path(tmp)/(n+'.log'),'w+') for n in ('jack','engine')}
    jack=subprocess.Popen([env['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime','-d','dummy','-r','48000','-p','8192'],env=env,stdout=logs['jack'],stderr=subprocess.STDOUT)
    try:
        time.sleep(1);assert jack.poll() is None
        sock=str(Path(tmp)/'engine.sock')
        engine=subprocess.Popen([env['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),sock,'--chain','--chain-timing','2','--jack','--client','mbmf_d'],env=env,stdout=logs['engine'],stderr=subprocess.STDOUT)
        def wait(fn,label):
            end=time.monotonic()+10
            while time.monotonic()<end:
                if fn():return
                time.sleep(.05)
            raise AssertionError(label)
        wait(lambda:Path(sock).exists(),'engine socket')
        c=Control(sock)
        def cmd(**args):
            s=c.request();r=c.request(revision=s['revision'],session=s['engineSessionId'],**args);assert r.get('status')=='ok',r;return r
        cmd(op=2)
        for i in (2,3):cmd(op=32,target=i,arg=21,macro=[0,0])
        for p,pitch,mode in ((0,60,1),(1,62,1),(2,64,2),(3,65,0)):
            cmd(op=32,target=p+1,arg=20,macro=[0,mode]);cmd(op=32,target=p+1,arg=15,macro=[0,1])
            # Long ONCE sources coexist; short HOLD retains past source Note Off.
            length=30 if mode==1 else 2
            cmd(op=35,target=p,arg=1,phrase=dict(lengthSeconds=length,events=[[0,144,pitch,100],[length-.5,128,pitch,0]]))
        probe=subprocess.Popen([env['CONDUCTOR_JACK_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        assert probe.stdout.readline().strip()=='READY'
        cmd(op=6,target=0);time.sleep(.4)
        cmd(op=6,target=1);time.sleep(.4)
        assert len(c.request()['instances'])==2,'ONCE sources must coexist'
        cmd(op=6,target=2);time.sleep(2.5)
        assert len(c.request()['instances'])==3,'HOLD retained after source end'
        cmd(op=6,target=2);time.sleep(.4)
        assert len(c.request()['instances'])==3,'HOLD retrigger replaces its own occurrence'
        print('M0 before LOOP',json.dumps(c.request()['phrases'][3]),flush=True)
        cmd(op=6,target=3);time.sleep(.4)
        print('M0 first LOOP',json.dumps(c.request()['phrases'][3]),flush=True)
        cmd(op=6,target=3);time.sleep(.4)
        print('M0 second LOOP',json.dumps(c.request()['phrases'][3]),flush=True)
        assert not c.request()['phrases'][3]['state']=='PLAYING','LOOP second PRESS stops'
        cmd(op=2);time.sleep(.4)
        assert not c.request()['instances'];assert c.request()['outputOverflow']==0
        probe.stdin.close();trace=[list(map(int,line.split())) for line in probe.stdout.read().splitlines()]
        assert probe.wait(timeout=5)==0;probe=None
        musical=[e[2:] for e in trace if e[2]&240 in (128,144)]
        print('M0 JACK actual note trace:',json.dumps(musical),flush=True)
        assert [e[1] for e in musical if e[0]&240==144 and e[2]>0]==[60,62,64,64,65],musical
        hold=[e for e in musical if e[1]==64]
        assert hold[:3]==[[144,64,100],[128,64,0],[144,64,100]],hold
        loop=[e for e in musical if e[1]==65]
        assert loop==[[144,65,100],[128,65,0]],loop
        assert any(e[2]&240==176 and e[3] in (120,123) for e in trace),'PANIC must emit receiver cleanup'
        # Chronology checked as observed; never sorted or filtered into order.
        assert all(a[0]+a[1]<=b[0]+b[1] for a,b in zip(trace,trace[1:])),trace
        print('PASS M0 actual JACK: ONCE overlap, latched HOLD/retrigger, LOOP toggle, PANIC; 48k/8192 Cloud dummy backend')
    finally:
        if probe is not None:probe.terminate();probe.communicate(timeout=5)
        for process in (engine,jack):
            if process is not None:process.terminate();process.wait(timeout=10)
        for name,log in logs.items():
            log.flush();log.seek(0);data=log.read()
            if 'xrun' in data.lower():print(name+' JACK diagnostic:',data[-5000:])
            log.close()

#!/usr/bin/env python3
"""Production FREE TIME recording with actual stopped/start/seek/stop JACK clock."""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'headless'))
from server import Control
from phrase_midi import write_smf,read_smf
with tempfile.TemporaryDirectory(prefix='mbmf-m4-clock-') as tmp:
    env=dict(os.environ,JACK_DEFAULT_SERVER='mbmf-m4-clock');processes=[];probe=transport=None
    log=open(Path(tmp)/'runtime.log','w+')
    try:
        processes.append(subprocess.Popen([env['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime',
                         '-d','dummy','-r','48000','-p','8192'],env=env,stdout=log,stderr=log))
        time.sleep(1);assert processes[0].poll() is None
        sock=str(Path(tmp)/'engine.sock')
        processes.append(subprocess.Popen([env['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),sock,
                         '--chain','--chain-timing','2','--jack','--client','mbmf_d'],env=env,stdout=log,stderr=log))
        def wait(fn,label):
            end=time.monotonic()+12
            while time.monotonic()<end:
                if fn():return
                time.sleep(.05)
            raise AssertionError(label)
        wait(lambda:Path(sock).exists(),'engine socket');c=Control(sock)
        def cmd(**args):
            s=c.request();r=c.request(revision=s['revision'],session=s['engineSessionId'],**args)
            assert r['status']=='ok',(args,r['status'])
            return r
        cmd(op=2)
        for i in (2,3):cmd(op=32,target=i,arg=21,macro=[0,0])
        cmd(op=9,target=1,arg=1,value=3)
        transport=subprocess.Popen([env['M4_TRANSPORT_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        assert transport.stdout.readline().strip()=='READY'
        def control(command):
            transport.stdin.write(command+'\n');transport.stdin.flush()
            return list(map(int,transport.stdout.readline().split()))
        assert control('state')[0]==0,'private JACK starts stopped'
        probe=subprocess.Popen([env['CONDUCTOR_JACK_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        assert probe.stdout.readline().strip()=='READY'
        cmd(op=40,arg=2,target=0)
        time.sleep(.4)
        assert control('state')[0]==0,'FREE TIME REC must not start the global JACK transport'
        probe.stdin.write('146 65 97 17\n');probe.stdin.flush()
        wait(lambda:c.request()['chainRecording'],'first JACK Note On begins recording while stopped')
        states=[]
        for action in ('start','locate 1234567','stop'):
            control(action);time.sleep(.4);s=c.request();states.append(dict(command=action,transport=control('state'),recording=s['chainRecording'],error=s['chainErrorReason'],frameGap=s['chainFrameGap'],audioGap=s['chainClockGap'],xruns=s['lateBlocks'],samples=s['sampleClock'],maxCallbackUs=s['maxCallbackUs']))
            if os.environ.get('M4_CLOCK_PROGRESS'):Path(os.environ['M4_CLOCK_PROGRESS']).write_text(json.dumps(states,indent=2)+'\n')
            assert s['chainRecording'] and not s['chainError'],states
        probe.stdin.write('130 65 31 64\n');probe.stdin.flush()
        wait(lambda:c.request()['phrases'][0]['events']==2,'paired source capture')
        cmd(op=40,arg=3,target=0)
        source=cmd(op=35,target=0,arg=0)['phraseData']
        assert [e[1:] for e in source['events']]==[[146,65,97],[130,65,31]],source
        assert source['events'][0][0]==0 and source['events'][1][0]>.5,source
        exported=read_smf(write_smf(source))
        assert exported['events'][0]==[0,146,65,97],exported
        assert exported['events'][1][1:]==[130,65,31],exported
        assert abs(exported['events'][1][0]-source['events'][1][0])<.002,exported
        assert control('state')[0]==0
        cmd(op=40,arg=1,target=0)
        assert control('state')[0]==0,'FREE TIME PLAY does not start global transport either'
        time.sleep(.4);cmd(op=2);time.sleep(.4)
        state=c.request()
        assert state['instruments'][0]['output']==3,state['instruments'][0]
        assert not state['instances'] and not state['chainRecording'] and state['activeNotes']==0,state
        assert state['chainErrorReason']=='none' and state['captureRejected']==0,state
        probe.stdin.close();events=[list(map(int,l.split())) for l in probe.stdout.read().splitlines()]
        assert probe.wait(timeout=5)==0;probe=None
        assert any(e[2:]==[146,65,97] for e in events),events
        assert any(e[2]&240==128 and e[3]==65 for e in events),events
        assert all(a[0]+a[1]<=b[0]+b[1] for a,b in zip(events,events[1:])),events
        result=dict(clock='actual private JACK audio clock; transport stopped/start/seek/stop',
                    states=states,source=source,smf=exported,events=events,
                    diagnostics={k:state[k] for k in ('chainErrorReason','captureRejected','captureOverflows','outputOverflow','lateBlocks')})
        if os.environ.get('M4_CLOCK_EVIDENCE'):Path(os.environ['M4_CLOCK_EVIDENCE']).write_text(json.dumps(result,indent=2)+'\n')
        print('PASS actual JACK FREE TIME capture and source SMF:',json.dumps(result),flush=True)
    finally:
        for p in (probe,transport):
            if p is not None:p.terminate();p.communicate(timeout=5)
        for p in reversed(processes):p.terminate();p.wait(timeout=10)
        log.flush();log.seek(0)
        if sys.exc_info()[0]:print(log.read()[-6000:])
        log.close()

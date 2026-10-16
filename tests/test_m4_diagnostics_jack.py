#!/usr/bin/env python3
"""Actual JACK ingress/egress counter boundaries. No router/hardware activation."""
import json, os, subprocess, sys, tempfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'headless'))
from server import Control
with tempfile.TemporaryDirectory(prefix='mbmf-m4-midi-') as tmp:
    env=dict(os.environ,JACK_DEFAULT_SERVER='mbmf-m4-counters')
    engine=probe=None
    log=open(Path(tmp)/'jack.log','w+')
    jack=subprocess.Popen([env['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime',
                           '-d','dummy','-r','48000','-p','8192'],env=env,stdout=log,stderr=log)
    try:
        time.sleep(1);assert jack.poll() is None
        sock=str(Path(tmp)/'engine.sock')
        engine=subprocess.Popen([env['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),sock,
                                  '--chain','--jack','--client','mbmf_d'],env=env,stdout=log,stderr=log)
        def wait(fn,label):
            end=time.monotonic()+10
            while time.monotonic()<end:
                if fn():return
                time.sleep(.05)
            raise AssertionError(label)
        wait(lambda:Path(sock).exists(),'native engine')
        c=Control(sock)
        def command(**args):
            state=c.request();reply=c.request(revision=state['revision'],session=state['engineSessionId'],**args)
            assert reply['status']=='ok',reply
            return reply
        command(op=2)
        for i in (2,3):command(op=32,target=i,arg=21,macro=[0,0])
        probe=subprocess.Popen([env['CONDUCTOR_JACK_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        assert probe.stdout.readline().strip()=='READY'
        time.sleep(.4)
        before=c.request()
        probe.stdin.write('177 1 83 16\n145 60 90 32\n129 60 32 64\n');probe.stdin.flush()
        wait(lambda:c.request()['midiWritten']-before['midiWritten']>=3,'three actual JACK writes')
        time.sleep(.4)
        after=c.request()
        keys=('midiReceived','midiInputAccepted','midiGenerated','midiQueued','midiWritten',
              'midiDropped','midiWriteFailures','midiRecoveries','outputOverflow','midiCount')
        delta={k:after[k]-before[k] for k in keys}
        assert delta==dict(midiReceived=3,midiInputAccepted=3,midiGenerated=3,midiQueued=3,
                           midiWritten=3,midiDropped=0,midiWriteFailures=0,midiRecoveries=0,
                           outputOverflow=0,midiCount=3),delta
        probe.stdin.close();actual=[list(map(int,line.split())) for line in probe.stdout.read().splitlines()]
        assert probe.wait(timeout=5)==0;probe=None
        assert len(actual)==delta['midiWritten'],actual
        assert [v[2]&240 for v in actual]==[176,144,128],actual
        assert all(a[0]+a[1]<=b[0]+b[1] for a,b in zip(actual,actual[1:])),actual
        result=dict(backend='actual private dummy JACK',rate=48000,frames=8192,delta=delta,events=actual)
        print('PASS M4 real JACK boundaries',json.dumps(result),flush=True)
        if os.environ.get('M4_MIDI_EVIDENCE'):Path(os.environ['M4_MIDI_EVIDENCE']).write_text(json.dumps(result,indent=2)+'\n')
    finally:
        if probe is not None:probe.terminate();probe.communicate(timeout=5)
        for p in (engine,jack):
            if p is not None:p.terminate();p.wait(timeout=10)
        log.flush();log.seek(0)
        if sys.exc_info()[0]:print(log.read()[-5000:])
        log.close()

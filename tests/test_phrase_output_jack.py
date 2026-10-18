"""Real production native renderer -> JACK port, with source SMF unchanged.
The probe records wire events; it does not implement any channel remapping.
"""
import os,sys,json,time,tempfile,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'headless'))
from server import Control
with tempfile.TemporaryDirectory(prefix='mbmf-phrase-output-') as tmp:
    env=dict(os.environ,JACK_DEFAULT_SERVER='mbmf-phrase-output')
    log=open(Path(tmp)/'jack.log','wb')
    server=subprocess.Popen([env['JACKD'],'--name',env['JACK_DEFAULT_SERVER'],'--no-realtime','-d','dummy','-r','48000','-p','8192'],env=env,stdout=log,stderr=log)
    engine=probe=None;traces=[]
    try:
        time.sleep(1);assert server.poll() is None
        sock=str(Path(tmp)/'engine.sock')
        engine=subprocess.Popen([env['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),sock,'--chain','--jack','--client','mbmf_d'],env=env,stdout=log,stderr=log)
        def wait(predicate,label):
            until=time.monotonic()+12
            while time.monotonic()<until:
                if predicate():return
                time.sleep(.04)
            raise AssertionError(label)
        wait(lambda:Path(sock).exists(),'native engine socket');control=Control(sock)
        def command(**args):
            state=control.request();r=control.request(revision=state['revision'],session=state['engineSessionId'],**args)
            assert (r.get('format')=='MIDI_HUMAN_LOOPER_PATCH' if args['op']==4 else r.get('status')=='ok'),str(r.get('status',r.get('format')))
            return r
        command(op=2)
        for i in (2,3):command(op=32,target=i,arg=21,macro=[0,0])
        command(op=32,target=1,arg=23,macro=[0,6])
        command(op=32,target=1,arg=20,macro=[0,1]);command(op=32,target=1,arg=15,macro=[0,1])
        source=dict(lengthSeconds=1.2,events=[[0,149,60,100],[.1,181,64,127],[.2,184,42,87],[.4,226,0,64],[.6,201,12,0],[.7,167,60,33],[.8,133,60,23],[.9,181,64,0]])
        # SMF importer is deliberately note-only today. Seed compatible CC/bend
        # source events via the actual schema-7 patch transaction, not a fake
        # output renderer or a test-only engine mutation endpoint.
        command(op=35,target=0,arg=1,phrase=dict(lengthSeconds=1.2,events=[source['events'][0],source['events'][6]]))
        patch=command(op=4)
        patch['memory'][16*2048*5]=len(source['events'])
        for index,event in enumerate(source['events']):
            patch['memory'][index*5:index*5+5]=[round(event[0]*48000),*event[1:],0]
        command(op=5,target=7,patch=patch)
        original=command(op=35,target=0,arg=0)['phraseData']
        for policy in (0,2,16,17):
            command(op=49,target=0,value=policy)
            probe=subprocess.Popen([env['PHRASE_OUTPUT_PROBE']],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=log,text=True)
            assert probe.stdout.readline().strip()=='READY'
            command(op=6,target=0)
            time.sleep(.3)
            if policy==17:command(op=49,target=0,value=3) # Existing instance keeps ALL.
            time.sleep(1.4)
            text=probe.communicate('',timeout=8)[0];assert probe.returncode==0
            events=[list(map(int,line.split())) for line in text.splitlines()]
            probe=None
            assert events and all(b[0]+b[1]>=a[0]+a[1] for a,b in zip(events,events[1:])),events
            checks=[(144,60,100,5),(128,60,0,5),(176,42,87,8),(224,0,64,2),(192,12,0,9),(160,60,33,7),(176,64,127,5),(176,64,0,5)]
            for status,number,value,original_channel in checks:
                actual=[e for e in events if e[2]&240==status and e[3:]==[number,value]]
                channels=sorted(e[2]&15 for e in actual)
                expected=list(range(16)) if policy==17 else [policy-1 if policy else original_channel]
                assert channels==expected,(policy,status,channels,expected,events)
            assert control.request()['activeNotes']==0
            assert command(op=35,target=0,arg=0)['phraseData']==original
            traces.append(dict(policy=policy,events=events))
        destination=Path(os.environ.get('PHRASE_OUTPUT_TRACE','/tmp/phrase-output-jack.json'))
        destination.write_text(json.dumps(traces,indent=2)+'\n')
        print('PASS actual JACK ORIGINAL/CH2/CH16/ALL: channel-voice events, exact emitted destinations, sustain cleanup, frozen active policy, source MIDI unchanged and chronological output')
    finally:
        if probe and probe.poll() is None:probe.terminate();probe.communicate(timeout=5)
        if engine:engine.terminate();engine.wait(timeout=8)
        server.terminate();server.wait(timeout=5);log.close()

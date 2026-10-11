#!/usr/bin/env python3
"""One actual native MBMF VM, three channel-aware virtual receivers, real dummy JACK.

The probe models Oram's native fanout (not channel filtering). Receiver filtering is
explicit in the assertions. No physical synth or Oram routing daemon is simulated
as validated hardware. The Oram resolver itself is covered by test_zynthian_routing.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
ROOT=Path(__file__).resolve().parents[1]
BLOCK=int(os.environ.get('CHAIN_JACK_BLOCK','2048'))
sys.path.insert(0,str(ROOT/'headless'))
class Base:
    my_data_dir=''
    def __init__(self,*args):self.options={};self.processors=[]
base=types.ModuleType('zyngine.zynthian_engine');base.zynthian_engine=Base
sys.modules['zyngine']=types.ModuleType('zyngine');sys.modules['zyngine.zynthian_engine']=base
spec=importlib.util.spec_from_file_location('mbh_dedicated',ROOT/'zynthian/zynthian_engine_mbh.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
server=engine=probe=None
with tempfile.TemporaryDirectory(prefix='mbh-dedicated-') as temp:
    directory=Path(temp);Base.my_data_dir=temp
    config=directory/'install.json'
    config.write_text(json.dumps(dict(version=1,chain_timing_version=2,repository=str(ROOT),
        binary=os.environ.get('HEADLESS_BINARY',str(ROOT/'.build/midi-headless-engine')),
        web_port_base=21000,web_bind='127.0.0.1')))
    os.environ['MBH_CONFIG']=str(config);os.environ['JACK_DEFAULT_SERVER']='mbh-dedicated-test'
    processor=types.SimpleNamespace(id=1,refresh_controllers=lambda:None)
    log=(directory/'jack.log').open('wb')
    def wait(predicate,label,timeout=14):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if predicate():return
            time.sleep(.04)
        raise AssertionError(label)
    try:
        server=subprocess.Popen([os.environ.get('JACKD','jackd'),'--name','mbh-dedicated-test',
            '--no-realtime','-d','dummy','-r','48000','-p',str(BLOCK)],stdout=log,stderr=log)
        time.sleep(1)
        if server.poll() is not None:raise RuntimeError((directory/'jack.log').read_text())
        engine=adapter.zynthian_engine_mbh(None);engine.add_processor(processor)
        assert len(engine.instances)==1
        control=engine.instances[1]['control']
        def command(action):
            state=control.request()
            response=control.request(op=40,target=0,arg=action,revision=state['revision'],session=state['engineSessionId'])
            assert response['status']=='ok',response
        def mode(value):
            state=control.request()
            response=control.request(op=32,target=1,arg=20,macro=[0,value],revision=state['revision'],session=state['engineSessionId'])
            assert response['status']=='ok',response
            wait(lambda:control.request()['phrases'][0]['mode']==value,'mode update was not applied')
        probe=subprocess.Popen([os.environ.get('CHAIN_JACK_PROBE','/tmp/mbh-chain-probe')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env={**os.environ,'CHAIN_FANOUT':'1'})
        assert probe.stdout.readline().strip()=='READY','fanout probe failed to connect'
        def send(value):probe.stdin.write(str(value)+'\n');probe.stdin.flush()
        assert control.request()['chainCaptureMode']=='free-time'
        mode(0);send(7);command(2)
        wait(lambda:control.request()['chainRecording']==1,'shared recording did not start')
        # The source releases at 512 ms; FINISH is an explicit performance edge,
        # never automatic expiration of the former two-bar recording window.
        time.sleep(1);command(3)
        wait(lambda:control.request()['chainRecording']==0,'manual free recording did not finish')
        send(0)
        state=control.request()
        assert state['chainError']==0,state
        assert state['phrases'][0]['events']==6,state['phrases'][0]
        # Existing source-phrase export API, not transformed MIDI output.
        notes=control.request(op=35,target=0,arg=0,revision=state['revision'],session=state['engineSessionId'])['phraseData']
        assert {event[1]&15 for event in notes['events']}=={0,1,2},notes
        assert notes['events'][0][0]==0 and notes['lengthSeconds']<2,notes
        command(1)
        time.sleep(4.2) # One full recorded playback cycle without physical input.
        command(0) # Bounded chain STOP cleanup to every connected receiver.
        mode(1)
        before=control.request()['midiCount'];command(1);time.sleep(4.4)
        once=control.request()
        assert once['midiCount']>before and once['activeNotes']==0,once
        time.sleep(.5)
        assert control.request()['midiCount']==once['midiCount'],'ONCE repeated on shared transport'
        command(1);time.sleep(.4)
        assert control.request()['midiCount']>once['midiCount'],'ONCE could not retrigger'
        command(0)
        mode(2)
        state=control.request()
        assert state['nativeHeldRelease']
        before=state['midiCount'];command(1);time.sleep(4.4)
        held=control.request();assert held['midiCount']>before and held['chainRunning'],held
        command(4);time.sleep(.4)
        released=control.request();assert released['activeNotes']==0,released
        time.sleep(.4)
        assert control.request()['midiCount']==released['midiCount'],'HOLD emitted notes after release'
        # A very short tap queues both edges without losing the release.
        command(1);command(4);time.sleep(.4)
        assert control.request()['activeNotes']==0
        command(0)
        mode(0)
        send(8);time.sleep(.4)
        assert not control.request()['chainRunning']
        send(9);command(1);time.sleep(4.2)
        # Remove the single processor while its recorded phrase remains enabled.
        engine.remove_processor(processor)
        assert not engine.instances and processor.jackname is None
        time.sleep(.4)
        probe.stdin.close();probe.stdin=None
        text=probe.communicate(timeout=10)[0]
        assert probe.returncode==0
        records=[tuple(map(int,line.split())) for line in text.splitlines() if line.strip()]
        assert records,'no captured MIDI'
        streams=[[r[1:] for r in records if r[0]==destination] for destination in range(3)]
        assert streams[0]==streams[1]==streams[2],'native fanout duplicated/lost events on a destination'
        accepted=[0,0,0]
        for destination,stream in enumerate(streams):
            active=set();previous=-1
            for frame,offset,status,note,value in stream:
                assert frame+offset>=previous,'JACK timestamp order regressed'
                previous=frame+offset
                if status&15!=destination:continue # A genuinely channel-aware synth.
                kind=status&240
                if kind==144 and value:active.add(note);accepted[destination]+=1
                elif kind==128 or (kind==144 and not value):active.discard(note)
                elif kind==176 and note in (120,123):active.clear()
            assert not active,(destination,active)
            assert accepted[destination]>=2,(destination,accepted)
            # Each wire carries all channels: channel selection alone in Oram
            # does not protect an omni synth. This is an intentional guardrail.
            assert {status&15 for _,_,status,_,value in stream if status&240==144 and value}=={0,1,2}
        print('PASS one actual MBMF instance: 3-channel source capture/playback, native-style fanout, '
              'identical ordered output streams, explicit receiver channel isolation, LOOP/ONCE/retrigger/HOLD/release/short-tap, STOP/transport/restart/removal cleanup')
    finally:
        if probe and probe.poll() is None:
            probe.terminate();probe.communicate(timeout=5)
        if engine:engine.stop()
        if server:
            server.terminate()
            try:server.wait(timeout=5)
            except subprocess.TimeoutExpired:server.kill();server.wait()
        log.close()

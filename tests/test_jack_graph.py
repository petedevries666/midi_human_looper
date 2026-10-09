#!/usr/bin/env python3
"""Explicit desktop dummy JACK server test; never start a second server on Zynthian."""
import os,socket,subprocess,tempfile,time,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
binary=os.environ.get('HEADLESS_BINARY',str(ROOT/'.build/midi-headless-engine'))
jackd=os.environ.get('JACKD','jackd')
probe=os.environ.get('JACK_TEST_BINARY','/tmp/midi-jack-smoke')
with tempfile.TemporaryDirectory(prefix='midi-jack-') as temp:
    env=dict(os.environ,JACK_DEFAULT_SERVER='midi-first-test')
    server=subprocess.Popen([jackd,'--name','midi-first-test','--no-realtime','-d','dummy','-r','48000','-p','512'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    engine=None
    try:
        time.sleep(1)
        if server.poll() is not None:raise RuntimeError(server.stderr.read().decode())
        path=str(Path(temp)/'engine.sock')
        engine=subprocess.Popen([binary,str(ROOT/'midi_human_looper.jsfx'),path,'--jack','--demo'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        deadline=time.monotonic()+15
        while not Path(path).exists() and time.monotonic()<deadline:
            if engine.poll() is not None:raise RuntimeError(engine.stderr.read().decode())
            time.sleep(.05)
        if not Path(path).exists():raise RuntimeError('engine startup timeout')
        def command(op,target,arg,value,rev):
            with socket.socket(socket.AF_UNIX) as c:
                c.settimeout(5);c.connect(path);c.sendall(f'1 {op} {target} {arg} {rev} 0 0 {value}\n'.encode());f=c.makefile('rb');s=json.loads(f.readline());f.close();assert s['status']=='ok',s;return s
        rev=1
        for op,arg,value in [(9,0,2),(9,1,2),(10,0,1)]:rev=command(op,2,arg,value,rev)['revision']
        deadline=time.monotonic()+5
        state=command(0,0,0,0,rev)
        while state['pendingOutput'] and time.monotonic()<deadline:time.sleep(.02);state=command(0,0,0,0,rev)
        assert state['pendingOutput']==0,state
        observer=subprocess.Popen([probe],env=env)
        time.sleep(.8)
        state=command(2,0,0,0,rev)
        print('PANIC diagnostic', {k:state[k] for k in ('blocks','midiCount','activeNotes','outputOverflow','lateBlocks','maxCallbackUs','lastEvent')}, flush=True)
        assert observer.wait(timeout=10)==0
        assert state['activeNotes']==0 and state['outputOverflow']==0,state
        print('PASS actual JACK graph: two Instruments, phrase switch, Note On/Off and PANIC')
        deadline=time.monotonic()+5
        while command(0,0,0,0,rev)['pendingOutput'] and time.monotonic()<deadline:time.sleep(.02)
        flood=subprocess.Popen([probe,'--flood'],env=env)
        time.sleep(2.6)
        before=command(0,0,0,0,rev)
        print('Flood diagnostic', {k:before[k] for k in ('midiCount','outputOverflow','pendingOutput','lateBlocks')},flush=True)
        state=command(2,0,0,0,rev)
        assert flood.wait(timeout=10)==0
        assert before['outputOverflow']>0,before
        assert state['activeNotes']==0,state
        print('PASS actual JACK FIFO overflow: emergency channel releases, bounded recovery and final PANIC')

    finally:
        if engine is not None:engine.terminate();engine.communicate(timeout=10)
        server.terminate();server.communicate(timeout=5)

"""Native adapter + three actual existing JSFX engines on an isolated dummy JACK graph."""
import importlib.util,json,os,subprocess,sys,tempfile,time,types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BLOCK=int(os.environ.get('CHAIN_JACK_BLOCK','2048'))
if BLOCK not in (2048,4096,8192):raise ValueError('CHAIN_JACK_BLOCK must be 2048, 4096 or 8192')
PERIOD=int(192000/BLOCK+.5)*BLOCK
# UI prerequisites are hardware-specific. Only base/UI controls are stubbed; adapter,
# IPC, engine, persistence, transport and MIDI routing are real.
class Base:
    my_data_dir=''
    def __init__(self,state):self.processors=[];self.options={}
sys.modules['zyngine']=types.ModuleType('zyngine')
base=types.ModuleType('zyngine.zynthian_engine');base.zynthian_engine=Base;sys.modules[base.__name__]=base
spec=importlib.util.spec_from_file_location('mbh',ROOT/'zynthian/zynthian_engine_mbh.py');adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
class Processor:
    def __init__(self,id):self.id=id;self.jackname=None
    def refresh_controllers(self):pass
with tempfile.TemporaryDirectory(prefix='mbh-chains-') as temp:
    directory=Path(temp);Base.my_data_dir=temp
    config=directory/'config.json';config.write_text(json.dumps(dict(version=1,repository=str(ROOT),binary=os.environ['HEADLESS_BINARY'])))
    os.environ['MBH_CONFIG']=str(config);os.environ['JACK_DEFAULT_SERVER']='mbh-chains-test'
    server_log_path=directory/'jack.log'
    # Never leave an unread logging pipe behind a real-time server.
    with server_log_path.open('wb') as server_output:
        server=subprocess.Popen([os.environ.get('JACKD','jackd'),'--name','mbh-chains-test','--no-realtime','-d','dummy','-r','48000','-p',str(BLOCK)],stdout=subprocess.DEVNULL,stderr=server_output)
    processors=[Processor(i) for i in range(1,4)];engines=[];probe=None;browser=None;playwright=None
    try:
        time.sleep(1)
        if server.poll() is not None:raise RuntimeError(server_log_path.read_text(errors='replace'))
        engines=[adapter.zynthian_engine_mbh(None) for _ in processors]
        for engine,p in zip(engines,processors):engine.add_processor(p)
        assert [p.jackname for p in processors]==['^mbh_1:','^mbh_2:','^mbh_3:']
        import re
        assert re.search(engines[0].jackname,'mbh_1:midi_in') and not re.search(engines[0].jackname,'mbh_10:midi_in')
        from controller_config import binding_wire,decode
        c=engines[0].instances[1]['control'];now=c.request()
        assert c.request(op=14,target=101,arg=2,ch=0,note=21,revision=now['revision'],session=now['engineSessionId'])['status']=='ok'
        now=c.request();wire=binding_wire(dict(id=201,sourceId=101,targetId=301,instrumentId=1,moduleId=0,kind=1,base=1,takeover=2,returnMode=1))
        assert c.request(op=16,target=201,binding=wire,revision=now['revision'],session=now['engineSessionId'])['status']=='ok'
        # Native chain actions use opcode 40; snapshots keep opcode 20. Both
        # must coexist and persist without sharing state across processors.
        def guarded(control, **args):
            current=control.request()
            result=control.request(revision=current['revision'], session=current['engineSessionId'], **args)
            assert result.get('status')=='ok',result
            return result
        guarded(c,op=20)
        captured=c.request()['snapshots'][0]['id']
        guarded(c,op=32,target=1,arg=1,macro=[0,64])
        guarded(c,op=20)
        guarded(c,op=26,target=captured)
        assert c.request()['instruments'][0]['level']==127
        assert len(c.request()['snapshots'])==2
        assert not engines[1].instances[2]['control'].request()['snapshots']
        probe=subprocess.Popen([os.environ.get('CHAIN_JACK_PROBE','/tmp/mbh-chain-probe')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        assert probe.stdout.readline().strip()=='READY'
        def source(mask):probe.stdin.write(str(mask)+'\n');probe.stdin.flush()
        def state(i):return engines[i-1].instances[i]['control'].request()
        def action(i,name):engines[i-1].send_controller_value(types.SimpleNamespace(processor=processors[i-1],graph_path=name,value=1))
        def wait(i,key,value,timeout=12):
            deadline=time.monotonic()+timeout
            while time.monotonic()<deadline:
                s=state(i)
                assert not s['chainError'],s
                if bool(s[key])==value:return s
                time.sleep(.02)
            raise AssertionError((key,value,state(i)))
        for i in range(1,4):
            source(1<<(i-1));action(i,'record')
            wait(i,'chainRecording',True);wait(i,'chainRecording',False)
            source(0)
            s=state(i);assert s['phrases'][0]['events']>=2,s
            assert s['chainLength']==PERIOD and s['chainRunning'],s
            for previous in range(1,i):assert state(previous)['chainRunning']
        # Actual overdub while Bass and Synth remain playing independently.
        previous_events=state(1)['phrases'][0]['events']
        source(1);action(1,'record')
        wait(1,'chainRecording',True);wait(1,'chainRecording',False);source(0)
        assert state(1)['phrases'][0]['events']>=previous_events+2
        assert state(2)['chainRunning'] and state(3)['chainRunning']
        if os.environ.get('RUN_CHAIN_BROWSER')=='1':
            from playwright.sync_api import sync_playwright
            playwright=sync_playwright().start();browser=playwright.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),args=['--no-sandbox'])
            pages=[]
            for i in range(1,4):
                page=browser.new_page();page.goto('http://127.0.0.1:'+str(8765+i))
                page.get_by_text('CONNECTED · Engine running',exact=True).wait_for()
                page.locator('details').filter(has=page.locator('#metrics')).locator('summary').click()
                page.get_by_text('Zynthian · two bars',exact=False).wait_for()
                pages.append(page)
            assert pages[0].locator('[data-source-id]').count()==1
            assert pages[1].locator('[data-source-id]').count()==0
            assert pages[2].locator('[data-source-id]').count()==0
            browser.close();browser=None;playwright.stop();playwright=None
            print('PASS three native-chain Chromium editors: independent sources and chain telemetry')
        # No live input now. Actual capture must show all three independent recorded loops.
        silence_frame=state(1)['chainFrame'];time.sleep(4.5)
        action(2,'stop');assert not state(2)['chainRunning'] and state(1)['chainRunning'] and state(3)['chainRunning']
        action(2,'save');action(2,'load');assert not state(2)['chainRunning'];action(2,'play')
        time.sleep(.15)
        for i in range(1,4):action(i,'stop')
        time.sleep(.5)
        assert all(state(i)['activeNotes']==0 and state(i)['outputOverflow']==0 for i in range(1,4))
        snapshot=engines[0].get_extended_config()
        assert len(snapshot['processors'])==3
        for i in range(1,4):
            action(i,'save');assert (directory/f'midi-human-looper/processor-{i}/patch1.json').exists()
        future_path=directory/'midi-human-looper/processor-2/patch1.json'
        original=future_path.read_bytes();future=json.loads(original)
        future['unknownModuleExtension']={'version':99,'preserve':True}
        unsupported=json.dumps(future).encode();future_path.write_bytes(unsupported)
        try:
            action(2,'save');raise AssertionError('unknown extension overwritten')
        except ValueError:pass
        assert future_path.read_bytes()==unsupported
        future_path.write_bytes(original)
        # Recorded source MIDI round trip through real native worker; other
        # chain and phrase data remain unchanged. Parsing stays outside JACK.
        from phrase_midi import write_smf,read_smf
        recorded=guarded(c,op=35,target=0,arg=0)['phraseData']
        original_other=engines[1].instances[2]['control'].request(op=35,target=0,arg=0,revision=-1)['phraseData']
        exported=write_smf(recorded); imported=read_smf(exported)
        canonical=[]
        for event in sorted(recorded['events'],key=lambda e:e[0]):
            t,st,n,v=event
            canonical.append([t,(128|(st&15)) if st&240==144 and not v else st,n,v])
        assert [e[1:] for e in imported['events']]==[e[1:] for e in canonical]
        assert all(abs(a[0]-b[0])<=1/48000 for a,b in zip(imported['events'],canonical))
        guarded(c,op=35,target=1,arg=1,phrase=imported)
        copied=guarded(c,op=35,target=1,arg=0)['phraseData']
        assert [e[1:] for e in copied['events']]==[e[1:] for e in imported['events']],(copied,imported)
        assert all(abs(a[0]-b[0])<=1/48000 for a,b in zip(copied['events'],imported['events']))
        assert engines[1].instances[2]['control'].request(op=35,target=0,arg=0,revision=-1)['phraseData']==original_other
        too_long={**imported,'lengthSeconds':recorded['lengthSeconds']*2}
        now=c.request();assert c.request(op=35,target=1,arg=1,revision=now['revision'],session=now['engineSessionId'],phrase=too_long)['status']=='invalid'
        assert guarded(c,op=35,target=1,arg=0)['phraseData']==copied
        assert state(1)['phrases'][1]['mode']==0
        guarded(c,op=32,target=1,arg=18,macro=[0,1]) # Mute the original; imported copy must be the source.
        imported_frame=state(1)['chainFrame']
        guarded(c,op=40,target=1,arg=1);time.sleep(4.5);action(1,'stop')
        assert not state(2)['chainRunning'] and not state(3)['chainRunning']
        time.sleep(.3);assert state(1)['activeNotes']==0
        action(1,'save');snapshot=engines[0].get_extended_config()
        probe.stdin.close();lines=probe.stdout.read().splitlines();assert probe.wait(timeout=5)==0;probe=None
        events=[list(map(int,line.split())) for line in lines]
        assert any(e[0]==0 and e[1]>imported_frame and e[3]&240==144 and e[5]>0 for e in events), 'imported phrase never played on JACK'
        for i in range(3):
            own=[e for e in events if e[0]==i]
            from collections import Counter
            held_notes=Counter();last_time=-1
            for event in own:
                _,frame,offset,status,note,value=event
                assert frame+offset>=last_time,('nonmonotonic JACK output',event,last_time)
                last_time=frame+offset
                key=(status&15,note)
                if status&240==144 and value:held_notes[key]+=1
                elif status&240==128 or (status&240==144 and not value):held_notes[key]=max(0,held_notes[key]-1)
                elif status&240==176 and note in (120,123):held_notes=Counter({k:v for k,v in held_notes.items() if k[0]!=(status&15)})
            assert not any(held_notes.values()),('unreleased actual MIDI output',i,held_notes)
            assert own and all(e[4]==60+i and e[3]&15==i for e in own if e[3]&240==144 and e[5]>0),own
            playback=[e for e in own if e[1]>silence_frame and e[3]&240==144 and e[5]>0]
            assert playback,('missing recorded playback',i,own)
            assert all((e[1]+e[2])%PERIOD==0 for e in playback),playback
            assert any(e[1]>silence_frame and e[4]==60+i and (e[3]&240==128 or (e[3]&240==144 and e[5]==0)) for e in own),own
        for engine in engines:engine.stop()
        engines=[]
        # Recreate with same stable IDs; Zynthian snapshot restores assignments/events, never playing state.
        engines=[adapter.zynthian_engine_mbh(None) for _ in processors]
        for engine,p in zip(engines,processors):engine.set_extended_config(snapshot);engine.add_processor(p)
        for i in range(1,4):assert state(i)['phrases'][0]['events']>=2 and not state(i)['chainRunning']
        assert all(engine.get_extended_config()['processors']==snapshot['processors'] for engine in engines)
        assert state(1)['phrases'][1]['events']==len(recorded['events'])
        assert len(state(1)['snapshots'])==2 and not state(2)['snapshots'] and not state(3)['snapshots']
        assert decode(state(1)['controllerEngine'])['mappings'][0]['id']==201
        assert not decode(state(2)['controllerEngine'])['mappings']
        print('PASS native Zynthian adapter: three isolated chains, sequential recording during playback, shared phase, Note Offs, per-chain STOP/SAVE/LOAD and snapshot recreation')
    finally:
        if sys.exc_info()[0]:
            for engine in engines:
                for pid,entry in engine.instances.items():
                    log=entry['data']/'engine.log'
                    print('CHAIN FAILURE',pid,'process exit',entry['engine'].poll(),flush=True)
                    if log.exists():print(log.read_text(errors='replace')[-4096:],flush=True)
        if browser:browser.close()
        if playwright:playwright.stop()
        if probe:
            if probe.stdin and not probe.stdin.closed:probe.stdin.close()
            try:probe.wait(timeout=5)
            except subprocess.TimeoutExpired:probe.kill();probe.wait()
        for engine in engines:engine.stop()
        failed=sys.exc_info()[0] is not None
        server.terminate();server.communicate(timeout=5)
        if failed:print('JACK FAILURE LOG',server_log_path.read_text(errors='replace')[-4096:],flush=True)

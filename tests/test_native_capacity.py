"""Real native schema-8 audit. Private worker, no JACK, no live mutation."""
import copy,json,os,pathlib,subprocess,sys,tempfile,threading,time,unittest,urllib.request,uuid
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'headless'))
from server import Control,make_server
from native_capacity import migrate,layout,address
from switch_presets import switches,apply_config
from portable_project import validate_patch,capture,materialize
import conductor

class Capacity(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(prefix='mbmf-native-capacity-');cls.dir=pathlib.Path(cls.tmp.name);cls.sock=cls.dir/'engine.sock'
  cls.log=(cls.dir/'engine.log').open('w')
  os.environ.setdefault('HEADLESS_BINARY',str(ROOT/'.build/midi-headless-engine'))
  if not pathlib.Path(os.environ['HEADLESS_BINARY']).exists():raise unittest.SkipTest('Build the actual native engine first')
  from native_capacity import build_source
  cls.source=cls.dir/'native-expanded.jsfx';cls.source.write_text(build_source((ROOT/'midi_human_looper.jsfx').read_text(encoding='utf-8')),encoding='utf-8')
  legacy_sock=cls.dir/'legacy.sock'
  worker=subprocess.Popen([os.environ['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),str(legacy_sock),'--demo'],stdout=cls.log,stderr=cls.log)
  try:
   for _ in range(200):
    if worker.poll() is not None:raise RuntimeError('Legacy fixture failed')
    if legacy_sock.exists():break
    time.sleep(.05)
   legacy=Control(str(legacy_sock));state=legacy.request();cls.legacy=legacy.request(op=4,revision=state['revision'],session=state['engineSessionId'])
  finally:
   worker.terminate();worker.wait(timeout=10)
  cls.proc=subprocess.Popen([os.environ['HEADLESS_BINARY'],str(cls.source),str(cls.sock),'--chain','--chain-timing','2'],stdout=cls.log,stderr=cls.log)
  for _ in range(200):
   if cls.proc.poll() is not None:raise RuntimeError((cls.dir/'engine.log').read_text())
   if cls.sock.exists():break
   time.sleep(.05)
  cls.control=Control(str(cls.sock));cls.factory=cls.export()
  cls.server=make_server('127.0.0.1',0,str(cls.sock),patch_dir=cls.dir/'patches');threading.Thread(target=cls.server.serve_forever,daemon=True).start()
  cls.url='http://127.0.0.1:'+str(cls.server.server_port)
 @classmethod
 def tearDownClass(cls):
  cls.server.shutdown();cls.server.server_close();cls.proc.terminate()
  try:cls.proc.wait(timeout=10)
  except subprocess.TimeoutExpired:cls.proc.kill();cls.proc.wait()
  cls.log.close();cls.tmp.cleanup()
 @classmethod
 def export(cls):
  s=cls.control.request();return cls.control.request(op=4,revision=s['revision'],session=s['engineSessionId'])
 def setUp(self):
  s=self.control.request();self.control.request(op=2,revision=s['revision'],session=s['engineSessionId']);self.load(self.factory)
 def load(self,p):
  s=self.control.request();r=self.control.request(op=5,target=p['schema'],patch=p,revision=s['revision'],session=s['engineSessionId']);self.assertEqual(r.get('status'),'ok',r)
 def cmd(self,action,**kw):
  s=self.control.request();body=dict(protocolVersion=1,expectedRevision=s['revision'],expectedEngineSessionId=s['engineSessionId'],action=action,**kw)
  req=urllib.request.Request(self.url+'/api/v1/command',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
  try:r=json.load(urllib.request.urlopen(req,timeout=30))
  except urllib.error.HTTPError as e:raise AssertionError((action,e.code,e.read().decode()))
  self.assertEqual(r.get('status'),'ok',r);return r
 def wait(self,predicate,timeout=3):
  end=time.monotonic()+timeout
  while time.monotonic()<end:
   s=self.control.request()
   if predicate(s):return s
   time.sleep(.01)
  self.fail('Native state predicate timed out: '+json.dumps({k:s.get(k) for k in ('chainRunning','activeNotes','midiCount','instanceError','instanceRejected')}|{'switch':s['switches'][-1]}))
 def add_all(self):
  for _ in range(60):self.cmd('switch_add')
  self.assertEqual(len(self.control.request()['switches']),64)
 def phrase128(self,mode=1):
  p=self.export();p['globals'][0]=9600;cfg=layout(p);m=p['memory'];base=127*10240
  m[base:base+10]=[0,144,67,90,0,4800,128,67,0,0]
  m[cfg['COUNT_BASE']+127]=2;m[cfg['LEN_BASE']+127]=9600;m[cfg['MODE_BASE']+127]=mode
  self.load(p)
 def configure(self,ident=64,policy=1):
  s=next(v for v in self.control.request()['switches'] if v['id']==ident)
  settings=list(s['settings']);settings[:11]=[1,1,15,119,127,0,policy,80,100,0,0]
  settings[12:]=[1,3,4,63,63,63]
  return self.cmd('switch_commit',switchId=ident,settings=settings,sequence=[128],name='CAPACITY TEST',longHold={'milliseconds':250,'action':6,'target':0})
 def test_01_dimensions_and_factory(self):
  s=self.control.request();self.assertEqual((s['schemaVersion'],s['phraseCapacity'],s['switchCapacity']),(8,128,64));self.assertEqual(len(s['phrases']),128)
  p=self.export();self.assertEqual(len(p['memory']),layout(p)['PATCH_PAYLOAD_SIZE']);validate_patch(p)
 def test_02_legacy_source_data_preserved(self):
  old=copy.deepcopy(self.legacy)
  self.assertEqual(old['schema'],7);before=copy.deepcopy(old);new=migrate(old);self.assertEqual(old,before)
  for i,value in enumerate(old['memory']):self.assertEqual(new['memory'][address(new,i)],value,('legacy cell',i))
  self.assertEqual(new['globals'],old['globals']);validate_patch(new);self.load(new)
  got=self.export();self.assertEqual(got['memory'],new['memory'])
  self.assertEqual(got.get('conductor'),new.get('conductor'))
 def test_03_switch64_and_capacity_guard(self):
  self.add_all();self.configure();s=self.control.request();v=s['switches'][-1];self.assertEqual(v['id'],64);self.assertEqual(v['sequence'],[128])
  r=self.control.request(op=51,revision=s['revision'],session=s['engineSessionId']);self.assertNotEqual(r['status'],'ok');self.assertEqual(len(self.control.request()['switches']),64)
 def test_04_phrase128_on_play_and_stop(self):
  self.phrase128();before=self.control.request()['midiCount'];self.cmd('phrase_play_independent',phraseId=128)
  self.wait(lambda s:s['midiCount']>=before+2 and s['activeNotes']==0)
  self.phrase128(mode=2);self.cmd('phrase_play',phraseId=128);self.wait(lambda s:s['activeNotes']>0);self.cmd('phrase_stop',phraseId=128);self.wait(lambda s:s['activeNotes']==0)
 def test_05_phrase128_loop_stop_flag(self):
  self.phrase128(mode=0);self.cmd('phrase_play',phraseId=128);self.wait(lambda s:s['chainRunning'])
  self.cmd('phrase_stop',phraseId=128);self.wait(lambda s:not s['chainRunning'] and s['activeNotes']==0)
 def test_06_gestures_real_edges_switch64(self):
  self.add_all();self.phrase128();self.configure();self.cmd('switch_test_edge',switchId=64,edge='press');time.sleep(.02);self.cmd('switch_test_edge',switchId=64,edge='release')
  self.wait(lambda s:s['switches'][-1]['lastAction']==1)
  time.sleep(.12)
  for _ in range(2):self.cmd('switch_test_edge',switchId=64,edge='press');self.cmd('switch_test_edge',switchId=64,edge='release');time.sleep(.015)
  self.wait(lambda s:s['switches'][-1]['lastAction']==3)
  self.cmd('switch_test_edge',switchId=64,edge='press');self.wait(lambda s:s['switches'][-1]['lastAction']==4);self.wait(lambda s:s['switches'][-1]['lastAction']==6);self.cmd('switch_test_edge',switchId=64,edge='release')
  self.wait(lambda s:s['activeNotes']==0)
 def test_07_switch64_conductor_phrase128(self):
  self.add_all();self.phrase128();self.configure(policy=0);p=self.export();model=conductor.with_mute_groups(conductor.migrate(p));source=next(v['id'] for v in model['sources'] if v['slot']==128)
  model['switches']=[dict(switchId=64,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',steps=[dict(id=str(uuid.uuid4()),transition='INHERIT',layers=[dict(id=str(uuid.uuid4()),block=dict(id=str(uuid.uuid4()),type='PHRASE',sourceId=source,overrides={}))])])]
  p['conductor']=conductor.encode(model);self.load(p);before=self.control.request()['midiCount'];self.cmd('switch_test_edge',switchId=64,edge='press')
  # An empty HOLD/LONG phase legitimately resets the per-phase admitted count.
  # Assert the source's actual MIDI and cursor rather than sampling that pulse.
  self.cmd('switch_test_edge',switchId=64,edge='release')
  s=self.wait(lambda s:s['switches'][-1]['conductor']['step']==1 and s['midiCount']>=before+2 and not s['activeNotes'])
  self.assertEqual((s['lastEvent'][1]&240,s['lastEvent'][2]),(128,67))
 def test_08_preset_and_roundtrip_high_slots(self):
  self.add_all();self.phrase128();self.configure();p=self.export();cfg=switches(p)[64]['config'];q,resolved,w,e=apply_config(p,63,cfg,{'double':{'type':'switch','id':'SELF'}})
  self.assertIn('MIDI source already used by SWITCH 64',e)
  cfg['settings'][1]=0;q,resolved,w,e=apply_config(p,63,cfg,{'double':{'type':'switch','id':'SELF'}})
  self.assertFalse(e);self.assertEqual(resolved['settings'][16],62);self.load(q);got=self.export();self.assertEqual(switches(got)[63]['config']['sequence'],[128]);validate_patch(got)
  project=capture(got,48000);roundtrip=materialize(project,48000);self.assertEqual(roundtrip['memory'][127*10240:128*10240],got['memory'][127*10240:128*10240]);self.load(roundtrip)
 def test_09_phrase128_parameters_and_midi_file(self):
  self.cmd('phrase_rename',phraseId=128,name='LAST PHRASE');self.cmd('parameter_set',targetId=128,moduleId=0,kind=17,value=1.5)
  self.assertEqual(self.control.request()['phrases'][-1]['name'],'LAST PHRASE')
 def test_10_record_and_export_phrase128(self):
  from phrase_midi import read_smf
  self.cmd('phrase_record',phraseId=128);self.wait(lambda s:s['phrases'][-1]['state']=='ARMED')
  self.cmd('midi',channel=1,note=69,value=100);self.wait(lambda s:s['phrases'][-1]['state']=='RECORDING');time.sleep(.08)
  self.cmd('midi',channel=1,note=69,value=0);self.cmd('phrase_finish',phraseId=128)
  self.wait(lambda s:s['phrases'][-1]['events']>=2 and not s['chainRecording'])
  raw=urllib.request.urlopen(self.url+'/api/v1/phrase/128/midi',timeout=30).read();parsed=read_smf(raw);self.assertGreaterEqual(len(parsed['events']),2)
 def test_11_snapshot_contains_phrase128(self):
  self.cmd('snapshot_capture');s=self.control.request();ident=s['snapshots'][-1]['id'];detail=self.control.request(op=29,target=ident,revision=-1)['snapshotDetail']
  self.assertTrue(any(v['instrumentId']==128 and v['kind']==17 for v in detail['parameters']))
  self.assertGreater(detail['parameterCount'],512);self.load(self.export())
 def test_12_schema6_migration_keeps_source_notes(self):
  from native_capacity import layouts
  old=copy.deepcopy(self.legacy)
  p=copy.deepcopy(old);p['schema']=6;p['memory']=p['memory'][:layouts()[0]['I_LEGACY_PAYLOAD']];p['work_mem_size']=len(p['memory']);p.pop('conductor',None);p.pop('controllerEngine',None);p.pop('globalSnapshots',None)
  converted=migrate(p);self.load(converted);self.assertEqual(converted['memory'][:163840],old['memory'][:163840])
 def test_13_invalid_high_slot_data_is_rejected(self):
  p=self.export();p['memory'][layout(p)['COUNT_BASE']+127]=2049;s=self.control.request()
  r=self.control.request(op=5,target=8,patch=p,revision=s['revision'],session=s['engineSessionId']);self.assertNotEqual(r['status'],'ok')
  self.assertEqual(self.control.request()['phrases'][-1]['events'],0)
  r=self.control.request(op=35,target=128,arg=0,revision=-1);self.assertNotEqual(r['status'],'ok')
 def test_14_reusing_legacy_switch_keeps_phrase_metadata(self):
  p=self.export();b=layout(p)['SW_LEGACY_PAYLOAD']+1;m=p['memory'];m[b+20]=0;m[b+21]=0
  for offset,value in {24:9,25:2,27:6,112:1.5,116:5}.items():m[b+offset]=value
  self.load(p);self.cmd('switch_add');got=self.export()['memory']
  for offset,value in {24:9,25:2,27:6,112:1.5,116:5}.items():self.assertEqual(got[b+offset],value)
 def test_15_snapshot_action_on_switch64_restores_phrase128(self):
  self.add_all();self.configure(policy=0);self.cmd('snapshot_capture');ident=self.control.request()['snapshots'][-1]['id']
  self.cmd('parameter_set',targetId=128,moduleId=0,kind=17,value=1.5)
  self.cmd('parameter_set',targetId=128,moduleId=0,kind=18,value=1)
  self.cmd('snapshot_switch',switchId=64,gesture=0,snapshotAction=3,snapshotId=ident)
  self.cmd('switch_test_edge',switchId=64,edge='press');self.cmd('switch_test_edge',switchId=64,edge='release')
  self.wait(lambda s:abs(s['phrases'][-1]['baseVelocity']-1)<.001 and not s['phrases'][-1]['mute'])
 def test_16_supercharge_release_on_switch64(self):
  self.add_all();self.configure(policy=0);p=self.export();model=conductor.with_mute_groups(conductor.migrate(p));uid=lambda:str(uuid.uuid4())
  move=dict(id=uid(),name='HIGH SLOT CHARGE',target=dict(type='CC',channel=16,number=119),points=[[0,0],[1,1]],duration=1,interpolation='LINEAR',retrigger='DIRECT',glideSeconds=.1)
  item=dict(id=uid(),type='MOVEMENT',sourceId=move['id'],overrides={'trigger':dict(mode='OVERRIDE',value='SUPERCHARGE_RELEASE')})
  model.update(movements=[move],ccRate=25,supercharge=dict(thresholdMs=50,fullMs=100))
  model['switches']=[dict(switchId=64,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',advance='RELEASE',steps=[dict(id=uid(),transition='INHERIT',layers=[dict(id=uid(),block=None),dict(id=uid(),block=item)])])]
  p['conductor']=conductor.encode(model);self.load(p);self.cmd('switch_test_edge',switchId=64,edge='press');time.sleep(.15)
  self.cmd('switch_test_edge',switchId=64,edge='release');self.wait(lambda s:s['movements']['active']==1)
  self.assertEqual(self.control.request()['movements']['running'][0]['id'],move['id'])

 def test_17_clear_expanded_patch_discards_last_slot_state(self):
  self.add_all();self.phrase128();self.configure();self.cmd('snapshot_capture')
  self.cmd('patch_clear',confirm=True);state=self.control.request()
  self.assertEqual(state['phraseCapacity'],128)
  self.assertTrue(all(p['events']==0 and p['mode']==1 for p in state['phrases']))
  self.assertFalse(state['snapshots']);self.assertEqual(len(state['switches']),4)
  self.assertFalse(state['activeNotes']);self.assertFalse(state['chainRunning'])

if __name__=='__main__':unittest.main(verbosity=2)

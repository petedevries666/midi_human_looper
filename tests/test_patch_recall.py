"""Host orchestration fixtures; real engine/physical qualification is separate."""
import copy,json,pathlib,sys,tempfile,time,types,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'headless'))
from patch_recall import RecallService,slot_number,checked_patch
from project_sync import atomic_json
from patch_names import rename,read

def musical(value):return dict(format='MIDI_HUMAN_LOOPER_PATCH',schema=1,work_mem_size=1,memory=[value],globals=[0]*9)
class Control:
 def __init__(self,session=1):self.session=session;self.revision=1;self.patch=musical(9);self.reservation=0;self.calls=[]
 def request(self,op=0,**kw):
  self.calls.append((op,kw))
  if op==4:return copy.deepcopy(self.patch)
  if op==5:
   assert kw['session']==self.session;self.patch=copy.deepcopy(kw['patch'])
  if op==53:self.reservation=kw['value']
  if op:self.revision+=1
  return dict(status='ok',revision=self.revision,engineSessionId=self.session,activeNotes=0,instances=0,chainRunning=False,chainRecording=False,chainArmed=False)
class Links:
 def __init__(self):self.bindings={'1':'chain-a'}
 def snapshot(self):return dict(self.bindings)
 def restore(self,s):self.bindings=dict(s)
 def synchronize(self):pass
 def status(self):return {'bindings':{k:{'destination':v} for k,v in self.bindings.items()}}
class RecallTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name);self.library=self.root/'library';self.library.mkdir();self.snapshots=self.root/'snapshots';self.snapshots.mkdir()
  self.control=Control();self.entries={4:dict(control=self.control,host_chains=types.SimpleNamespace(links=Links()))}
  self.loads=[];self.fail_load=False
  self.manager=types.SimpleNamespace(snapshot_dir=str(self.snapshots),last_snapshot_fpath='before',ctrldev_manager=types.SimpleNamespace(midi_event=lambda d,e:False),save_snapshot=self.save,load_snapshot=self.load)
  # Unit tests call operations deterministically, without a background worker.
  with patch('patch_recall.threading.Thread'):
   self.service=RecallService(self.manager,self.root,self.library,self.entries)
  for slot in (1,2,127):atomic_json(self.library/f'patch{slot}.json',musical(slot))
 def save(self,path):atomic_json(path,dict(chains={'1':{'slots':[{'4':'MB'}]}},engine_config={'MB/3':{'processors':{'4':{'patch':self.entries[4]['control'].patch}}}}));self.manager.last_snapshot_fpath=path;return True
 def load(self,path):
  self.loads.append(path)
  if self.fail_load and len(self.loads)==1:return False
  self.entries[4]=dict(control=Control(self.entries[4]['control'].session+1),host_chains=types.SimpleNamespace(links=Links()));return True
 def associate(self,slot=1):
  path=self.snapshots/'000'/'001-test.zss';path.parent.mkdir(exist_ok=True);self.save(path)
  self.service.request(dict(operation='link',slot=slot,snapshot='000/001-test.zss'))
 def test_raw_program_zero_channels_and_consumption(self):
  self.service.settings.update(enabled=True,channel=3)
  self.assertFalse(self.service.midi_event(1,bytes([0xc1,1])))
  self.assertTrue(self.service.midi_event(1,bytes([0xc2,0])));self.assertIsNone(self.service.pending)
  for n in (1,4,127):self.assertTrue(self.service.midi_event(1,bytes([0xc2,n])));self.assertEqual(self.service.pending,('recall',n))
  self.assertTrue(self.service.midi_event(1,bytes([0xc2,2,0])));self.assertEqual(self.service.pending,('recall',2))
  self.service.settings['enabled']=False;self.assertFalse(self.service.midi_event(1,bytes([0xc2,1])))
 def test_all_channels_and_hook_prevents_second_dispatch(self):
  called=[];self.manager.ctrldev_manager.midi_event=lambda d,e:called.append(e) or False;self.service.install_midi_hook()
  self.service.settings['enabled']=True
  for channel in range(1,17):
   self.service.settings['channel']=channel;self.assertTrue(self.manager.ctrldev_manager.midi_event(2,bytes([0xc0+channel-1,1])))
  self.assertEqual(called,[])
 def test_patch_only_and_boundary_127(self):
  self.service.settings.update(withSnapshot=False,enabled=True,channel=7);original=(self.library/'patch2.json').read_bytes()
  self.service.recall(127);self.assertEqual(self.control.patch['memory'],[127]);self.assertEqual(self.control.reservation,7);self.assertEqual(self.service.selected,127);self.assertEqual(self.loads,[]);self.assertEqual((self.library/'patch2.json').read_bytes(),original)
 def test_missing_and_corrupt_do_not_stop_current(self):
  for slot in (3,4):
   if slot==4:(self.library/'patch4.json').write_text('{')
   with self.assertRaises((ValueError,OSError)):self.service.recall(slot)
  self.assertFalse(any(op==2 for op,_ in self.control.calls));self.assertEqual(self.control.patch['memory'],[9])
 def test_snapshot_recreates_engine_and_latest_patch_wins(self):
  self.associate();old=self.control;self.service.recall(1);new=self.entries[4]['control']
  self.assertIsNot(old,new);self.assertEqual(new.patch['memory'],[1]);self.assertEqual(self.service.selected,1);self.assertEqual(len(self.loads),1)
  self.assertTrue(any(op==5 and kw['session']==2 for op,kw in new.calls))
 def test_failed_snapshot_recovers_previous_patch(self):
  self.associate();self.fail_load=True
  with self.assertRaisesRegex(ValueError,'previous patch restored'):self.service.recall(1)
  self.assertEqual(self.entries[4]['control'].patch['memory'],[9]);self.assertEqual(len(self.loads),2)
 def test_missing_link_no_stop_and_path_escape_refused(self):
  with self.assertRaises(ValueError):self.service.recall(1)
  with self.assertRaises(ValueError):self.service.snapshot_path('../../elsewhere.zss')
  self.assertFalse(any(op==2 for op,_ in self.control.calls))
 def test_save_pair_and_rename_preserves_link(self):
  rename(self.library,127,'MONZTER','');self.service.save_pair(127)
  link=self.service.settings['links']['127'];self.assertEqual(link['snapshot'],'001-MBMF/127-MONZTER.zss');self.assertEqual(checked_patch(self.library/'patch127.json')['memory'],[9]);self.assertTrue(self.service.snapshot_path(link['snapshot']).is_file())
  rename(self.library,127,'MONZTER NEW','MONZTER');self.assertEqual(self.service.settings['links']['127'],link);self.assertEqual(read(self.library)['127'],'MONZTER NEW')
 def test_save_pair_failure_preserves_previous_files(self):
  before=(self.library/'patch2.json').read_bytes();self.manager.save_snapshot=lambda p:False
  with self.assertRaises(ValueError):self.service.save_pair(2)
  self.assertEqual((self.library/'patch2.json').read_bytes(),before);self.assertNotIn('2',self.service.settings['links'])
 def test_new_bank_visible_and_legacy_snapshot_preserved(self):
  legacy=self.snapshots/'MBMF'/'002-old.zss';legacy.parent.mkdir();self.save(legacy)
  original=legacy.read_bytes();self.service.request(dict(operation='link',slot=2,snapshot='MBMF/002-old.zss'))
  self.service.recall(2);self.assertEqual(self.loads[-1],str(legacy))
  self.service.save_pair(2);relative=self.service.settings['links']['2']['snapshot']
  self.assertTrue(relative.startswith('001-MBMF/002-'))
  self.assertEqual(legacy.read_bytes(),original)
  self.assertIn(relative,[row['path'] for row in self.service.status()['snapshots']])
 def test_new_bank_collision_preserves_unassociated_snapshot(self):
  target=self.snapshots/'001-MBMF'/'002-PATCH 02.zss';target.parent.mkdir();target.write_text('unrelated')
  before=(self.library/'patch2.json').read_bytes()
  with self.assertRaisesRegex(ValueError,'already exists'):self.service.save_pair(2)
  self.assertEqual(target.read_text(),'unrelated');self.assertEqual((self.library/'patch2.json').read_bytes(),before)
 def test_legacy_journal_recovery_remains_supported(self):
  stage=self.root/'patch-pair-stage';stage.mkdir()
  legacy=self.snapshots/'MBMF'/'002-old.zss';legacy.parent.mkdir();legacy.write_text('partial')
  (stage/'snapshot.old').write_text('original')
  (stage/'patch.old').write_bytes((self.library/'patch2.json').read_bytes())
  atomic_json(self.root/'patch-pair-journal.json',dict(slot=2,snapshot='MBMF/002-old.zss',existed=['patch','snapshot']))
  self.service.recover_save();self.assertEqual(legacy.read_text(),'original')
  self.assertFalse((self.root/'patch-pair-journal.json').exists())
 def test_interrupted_pair_save_rolls_back(self):
  self.service.save_pair(2);before=(self.library/'patch2.json').read_bytes();link=copy.deepcopy(self.service.settings['links']['2'])
  original=__import__('patch_recall').atomic_json
  def fail_registry(path,data):
   if pathlib.Path(path)==self.service.path:raise OSError('fixture failed registry publication')
   return original(path,data)
  self.control.patch=musical(55)
  with patch('patch_recall.atomic_json',side_effect=fail_registry):
   with self.assertRaises(OSError):self.service.save_pair(2)
  self.assertEqual((self.library/'patch2.json').read_bytes(),before);self.assertEqual(self.service.settings['links']['2'],link)
 def test_active_worker_is_never_reported_ready(self):
  self.service.active=('recall',1)
  self.service.phase='ready'
  self.assertEqual(self.service.status()['phase'],'preflight')

 def test_slot_bounds(self):
  self.assertNotIn('error',self.service.status()) # Transport errors reserve this key.
  for n in (0,128,True,'1'):
   with self.assertRaises(ValueError):slot_number(n)
 def test_latest_external_request_survives_snapshot_loading(self):
  self.service.settings.update(enabled=True,channel=15);self.service.phase='snapshot';self.service.active=('recall',1)
  self.service.midi_event(0,bytes([0xce,2,0]));self.assertEqual(self.service.pending,('recall',2))
  self.service.midi_event(255,bytes([0xce,3,0]));self.assertEqual(self.service.pending,('recall',2))
  self.service.midi_event(0,bytes([0xce,1,0]));self.assertIsNone(self.service.pending)
 def test_completed_midi_recall_is_idempotent_but_manual_reload_is_explicit(self):
  self.service.settings.update(enabled=True,channel=3,withSnapshot=False)
  self.service.recall(2);self.service.phase='ready'
  count=len(self.control.calls)
  self.assertTrue(self.service.midi_event(1,bytes([0xc2,2])))
  self.assertIsNone(self.service.pending);self.assertEqual(len(self.control.calls),count)
  self.service.request(dict(operation='recall',slot=2));self.assertEqual(self.service.pending,('recall',2))
 def test_failed_or_changed_selection_does_not_suppress_midi_retry(self):
  self.service.settings.update(enabled=True,channel=3,withSnapshot=False)
  self.service.recall(2);self.service.phase='failed'
  self.service.midi_event(1,bytes([0xc2,2]));self.assertEqual(self.service.pending,('recall',2))
  self.service.pending=None;self.service.phase='ready';self.service.selected=1
  self.service.midi_event(1,bytes([0xc2,2]));self.assertEqual(self.service.pending,('recall',2))

if __name__=='__main__':unittest.main()

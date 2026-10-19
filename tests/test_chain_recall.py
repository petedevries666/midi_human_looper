"""Real snapshot splice / service, with fake host engines (no live MIDI)."""
import copy,json,pathlib,sys,types,unittest,uuid
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'headless'));sys.path.insert(0,str(ROOT/'tests'))
from chain_recall import scoped_update,snapshot_chain,fingerprint,validate_assets
import test_patch_recall as recall_fixture
from project_sync import atomic_json

class Engine:
 def __init__(self,root):self.my_data_dir=str(root);self.processors=[];self.calls=0;self.opaque='GUI-only edited sound'
 def get_extended_config(self):return None
 def save_preset(self,bank,name):
  self.calls+=1;path=pathlib.Path(self.my_data_dir)/'presets/lv2/managed.presets.lv2'/(name+'.ttl');path.parent.mkdir(parents=True,exist_ok=True);path.write_text('captured '+self.opaque);return path.as_uri()
class Processor:
 def __init__(self,id,code,engine):self.id=id;self.eng_code=code;self.engine=engine;engine.processors.append(self);self.preset_info=['file:///original-'+str(id),None,'Original '+str(id),None];self.value=12
 def get_state(self):return dict(preset_info=copy.deepcopy(self.preset_info),bank_info=None,controllers={'cutoff':{'value':self.value}})
class Chain:
 def __init__(self,identity,procs):self.chain_id=1;self._mbmf_instrument_identity=identity;self.midi_slots=[];self.synth_slots=[[procs[0]]];self.audio_slots=[[p] for p in procs[1:]];self.mixer_chan=0
 def get_state(self):return dict(midi_chan=0,mixer_chan=0,slots=[{str(p.id):p.eng_code} for slot in self.synth_slots+self.audio_slots for p in slot],fader_pos=1)

class ChainRecallTests(unittest.TestCase):
 def setUp(self):
  self.base=recall_fixture.RecallTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
  self.service=self.base.service;self.identity=str(uuid.uuid4());self.root=self.base.root
  self.synth=Processor(5,'JV/Surge XT',Engine(self.root));self.fx=Processor(8,'JV/Delay',Engine(self.root));self.chain=Chain(self.identity,[self.synth,self.fx])
  manager=types.SimpleNamespace(chains={1:self.chain},zyngines={'surge':self.synth.engine,'delay':self.fx.engine})
  self.service.manager.chain_manager=manager;self.service.manager.zynmixer=types.SimpleNamespace(get_state=lambda:{'chan_00':{'level':.5},'chan_01':{'level':.9}})
  self.links=self.base.entries[4]['host_chains'].links;self.links.manager=manager;self.links.chain_volume=lambda d:.5;self.links.chain_pan=lambda d:0
  self.links.destinations=lambda:[dict(chainId=1,identity=self.identity,channel=1)]
  self.service.selected=1
  self.path=self.base.snapshots/'000/001-test.zss';self.path.parent.mkdir()
  self.document=dict(chains={'1':dict(midi_chan=0,mixer_chan=0,slots=[{'5':'JV/Surge XT'},{'7':'JV/OldFX'}],fader_pos=1),'2':dict(midi_chan=1,mixer_chan=1,slots=[{'6':'JV/Other'}])},zs3={'zs3-0':{'processors':{'4':{'MB':'unchanged'},'5':{'preset_info':['old',None,'old',None]},'7':{'old':True},'6':{'other':'untouched'}},'mixer':{'chan_00':{'level':.1},'chan_01':{'level':.3}},'chains':{'1':{'midi_in':['a']},'2':{'midi_in':['b']}}},'different-zs3':{'processors':{'6':{'keep':True}}}},engine_config={'MB/1':{'processors':{'4':{'patch':{'memory':[987]}}},'hostChainIdentities':{'1':{'identity':self.identity,'signature':[[5,'JV/Surge XT']]}}},'other':{'untouched':True}},midi_profile_state={'keep':'same'},zynseq_riff_b64='keep')
  atomic_json(self.path,self.document);self.service.settings['links']['1']=dict(snapshot='000/001-test.zss',bindings={})
 def request(self):return dict(action='patch_recall',operation='save_chain',slot=1,chainId=1,identity=self.identity,fingerprint=fingerprint(self.chain,self.links),expectedEngineSessionId=1)
 def save(self):self.service.chain_saves.save(self.request());return json.loads(self.path.read_text())
 def test_only_selected_chain_changes_and_actual_lv2_state_is_captured(self):
  files={p:p.read_bytes() for p in self.base.library.glob('patch*.json')};result=self.save()
  self.assertEqual(result['chains']['2'],self.document['chains']['2']);self.assertEqual(result['engine_config'],self.document['engine_config']);self.assertEqual(result['midi_profile_state'],self.document['midi_profile_state'])
  self.assertEqual(result['zs3']['different-zs3'],self.document['zs3']['different-zs3']);self.assertEqual(result['zs3']['zs3-0']['processors']['6'],{'other':'untouched'});self.assertEqual(result['zs3']['zs3-0']['processors']['4'],{'MB':'unchanged'})
  self.assertEqual(result['zs3']['zs3-0']['mixer']['chan_01'],{'level':.3});self.assertEqual(result['zs3']['zs3-0']['mixer']['chan_00'],{'level':.5});self.assertNotIn('7',result['zs3']['zs3-0']['processors']);self.assertIn('8',result['zs3']['zs3-0']['processors'])
  for p,data in files.items():self.assertEqual(p.read_bytes(),data)
  self.assertEqual(self.synth.preset_info[0],'file:///original-5','SAVE must not select a preset in the live synth')
  self.assertEqual(self.synth.engine.calls,1);self.assertEqual(self.fx.engine.calls,1)
  validate_assets(result,self.root/'presets/lv2');self.assertIn('GUI-only edited sound',next((self.root/'presets/lv2').rglob('*.ttl')).read_text())
  backups=list((self.service.directory/'chain-save-backups').glob('*.zss'));self.assertEqual(len(backups),1);self.assertEqual(json.loads(backups[0].read_text()),self.document)
 def test_stale_session_identity_and_fingerprint_fail_before_export(self):
  for key,value in [('expectedEngineSessionId',999),('identity',str(uuid.uuid4())),('fingerprint','0'*64)]:
   request=self.request();request[key]=value
   with self.assertRaises(ValueError):self.service.chain_saves.save(request)
  self.assertEqual(self.synth.engine.calls,0);self.assertEqual(json.loads(self.path.read_text()),self.document)
 def test_refuses_to_replace_another_chains_processor(self):
  self.document['chains']['2']['slots'].append({'8':'JV/OtherFX'});atomic_json(self.path,self.document)
  with self.assertRaisesRegex(ValueError,'conflit'):self.save()
  self.assertEqual(json.loads(self.path.read_text()),self.document)
 def test_missing_association_or_identity_does_not_change_snapshot(self):
  self.service.settings['links'].clear()
  with self.assertRaises(ValueError):self.save()
  self.assertEqual(self.synth.engine.calls,0)
  with self.assertRaises(ValueError):snapshot_chain(self.document,str(uuid.uuid4()))
 def test_atomic_publish_failure_keeps_original(self):
  before=self.path.read_bytes()
  with patch('project_sync.atomic_json',side_effect=OSError('disk full')):
   with self.assertRaises(OSError):self.save()
  self.assertEqual(self.path.read_bytes(),before)
 def test_damaged_captured_preset_blocks_validation(self):
  result=self.save();next((self.root/'presets/lv2').rglob('*.ttl')).write_text('changed')
  with self.assertRaisesRegex(ValueError,'changé'):self.service.validate_snapshot(self.path)
 def test_modification_state_and_recall_aliases(self):
  result=self.save();row=self.service.chain_saves.inventory()[0];self.assertEqual(row['state'],'saved')
  uri=result['zs3']['zs3-0']['processors']['5']['preset_info'][0];self.synth.preset_info[0]=uri
  self.assertEqual(self.service.chain_saves.inventory()[0]['state'],'saved')
  self.synth.value=90;self.assertEqual(self.service.chain_saves.inventory()[0]['state'],'modified')
 def test_request_validates_and_queues_without_exporting(self):
  self.service.request(self.request());self.assertEqual(self.service.pending[0],'save_chain');self.assertEqual(self.synth.engine.calls,0)
  with self.assertRaisesRegex(ValueError,'progress'):self.service.request(self.request())
 def test_shared_lv2_engine_is_refused(self):
  self.synth.engine.processors.append(types.SimpleNamespace(id=99))
  with self.assertRaisesRegex(ValueError,'indépendante'):self.save()
  self.assertEqual(self.synth.engine.calls,0)
 def test_active_music_is_not_stopped_by_save(self):
  original=self.base.control.request
  def active(**kw):return {**original(**kw),'chainRunning':True}
  self.base.control.request=active
  with self.assertRaisesRegex(ValueError,'Arrêter'):self.save()
  self.assertEqual(self.synth.engine.calls,0);self.assertFalse(any(op==2 for op,_ in self.base.control.calls))
 def test_concurrent_snapshot_edit_is_preserved(self):
  original=self.fx.engine.save_preset
  def change(bank,name):
   uri=original(bank,name);d=copy.deepcopy(self.document);d['externalEdit']=True;atomic_json(self.path,d);return uri
  self.fx.engine.save_preset=change
  with self.assertRaisesRegex(ValueError,'Snapshot modifié'):self.save()
  self.assertTrue(json.loads(self.path.read_text())['externalEdit'])
 def test_mixer_change_marks_the_chain_modified(self):
  self.save();self.links.chain_pan=lambda d:.5
  self.assertEqual(self.service.chain_saves.inventory()[0]['state'],'modified')

if __name__=='__main__':unittest.main()

"""Actual ChainLinks and scoped relay with mock Oram control objects, no live MIDI."""
import sys,pathlib,types,copy,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'headless'))
import test_zynthian_learned_cc as relay_fixture
from zynthian_chains import ChainLinks

class Teach(unittest.TestCase):
 def setUp(self):
  self.fixture=relay_fixture.Relay();self.fixture.setUp();self.fixture.arm()
  manager=self.fixture.manager;manager.state_manager=self.fixture.context.state_manager
  self.state={'revision':7,'engineSessionId':9,'instruments':[{'id':4,'enabled':1,'transformers':[{'id':18,'type':6,'enabled':1,'parameters':[{'kind':13,'value':6},{'kind':2,'value':0}]}]}]}
  self.links=ChainLinks(manager,99,types.SimpleNamespace(request=lambda:self.state))
  self.status={'engineRevision':7,'engineSessionId':9,'inventoryRevision':'inventory','bindings':{'4':{'identity':'identity','status':'synchronized','destination':{'chainId':2,'channel':1}}}}
  self.links.status=lambda:self.status
  self.request={'action':'teach_cc','instrumentId':4,'moduleId':18,'identity':'identity','inventoryRevision':'inventory','expectedRevision':7,'expectedEngineSessionId':9}
  self.modules=patch.dict(sys.modules,{'zyngine.zynthian_engine_mbh_router':relay_fixture.router});self.modules.start();self.addCleanup(self.modules.stop)
 def test_explicit_teach_uses_actual_module_output_and_applies_current_value(self):
  result=self.links.teach_cc(self.request);self.assertEqual(result,dict(status='taught',channel=1,cc=6,value=0));self.assertEqual(self.fixture.values,[0]);self.assertEqual(len(self.fixture.learns),1)
 def test_stale_session_revision_identity_inventory_module_refused(self):
  for key,value in [('expectedRevision',6),('expectedEngineSessionId',8),('identity','old'),('inventoryRevision','old'),('moduleId',19),('instrumentId',True)]:
   with self.subTest(key=key),self.assertRaises(ValueError):self.links.teach_cc({**self.request,key:value})
  self.assertFalse(self.fixture.learns)
 def movement_request(self):
  return {k:v for k,v in self.request.items() if k!='moduleId'}|dict(action='teach_movement',channel=1,cc=11,value=82)
 def test_movement_teach_uses_selected_channel_including_channel_two(self):
  self.fixture.chain.midi_chan=1
  self.status['bindings']['4']['destination']['channel']=2
  result=self.links.teach_movement(self.movement_request()|dict(channel=2))
  self.assertEqual(result,dict(status='taught',channel=2,cc=11,value=82))
  self.assertEqual(self.fixture.learns[0][:2],(1,11));self.assertEqual(self.fixture.values,[82])
 def test_movement_wrong_destination_reserved_cc_and_stale_context_refused(self):
  for change in ({'channel':2},{'cc':0},{'cc':32},{'cc':64},{'cc':120},{'value':128},{'channel':True},{'identity':'old'},{'inventoryRevision':'old'},{'expectedEngineSessionId':8},{'expectedRevision':6}):
   with self.subTest(change=change),self.assertRaises(ValueError):self.links.teach_movement(self.movement_request()|change)
  self.assertFalse(self.fixture.learns)
 def test_bypass_disabled_instrument_wrong_module_and_reserved_cc_refused(self):
  original=copy.deepcopy(self.state)
  for change in ('bypass','instrument','type','cc'):
   self.state=copy.deepcopy(original);instrument=self.state['instruments'][0];module=instrument['transformers'][0]
   if change=='bypass':module['enabled']=0
   elif change=='instrument':instrument['enabled']=0
   elif change=='type':module['type']=5
   else:module['parameters'][0]['value']=120
   with self.subTest(change=change),self.assertRaises(ValueError):self.links.teach_cc(self.request)
  self.assertFalse(self.fixture.learns)
if __name__=='__main__':unittest.main()

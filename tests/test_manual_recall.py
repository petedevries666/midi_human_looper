"""Exercise production HTTP LOAD dispatch without a live engine or Zynthian."""
import io,json,pathlib,sys,tempfile,types,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'headless'))
from server import Handler

class ManualRecallTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=pathlib.Path(self.tmp.name);(self.root/'patch2.json').write_text('{}')
  self.ops=[];self.calls=[];self.result=None
  def control(**kw):
   self.ops.append(kw.get('op',0));return dict(status='ok',revision=4,engineSessionId=7)
  self.handler=object.__new__(Handler)
  self.handler.server=types.SimpleNamespace(patch_dir=self.root,host_chain_socket='fixture',control=types.SimpleNamespace(request=control),switch_presets=types.SimpleNamespace(on_patch=lambda n:None))
  self.handler.path='/api/v1/patch/load'
  self.handler.respond=lambda status,value:setattr(self,'result',(status,value))
 def run_load(self,slot=2,revision=4,reply=None):
  body=json.dumps(dict(slot=slot,expectedRevision=revision,expectedEngineSessionId=7)).encode()
  self.handler.headers={'Content-Length':str(len(body))};self.handler.rfile=io.BytesIO(body)
  def bridge(path,data):self.calls.append(data);return reply or dict(phase='queued')
  with patch('zynthian_chains.bridge_request',side_effect=bridge):self.handler._patch_command_locked()
 def test_saved_load_uses_host_queue_without_import(self):
  self.run_load();self.assertEqual(self.result[0],202);self.assertEqual(self.calls,[dict(action='patch_recall',operation='recall',slot=2)])
  self.assertNotIn(5,self.ops)
 def test_stale_request_does_not_enqueue(self):
  self.run_load(revision=3);self.assertEqual(self.result[0],409);self.assertEqual(self.calls,[])
 def test_empty_slot_stays_new_patch(self):
  self.run_load(slot=3);self.assertEqual(self.result[0],200);self.assertTrue(self.result[1]['emptySlot']);self.assertIn(42,self.ops);self.assertEqual(self.calls,[])
 def test_host_refusal_does_not_fallback_to_patch_only(self):
  self.run_load(reply={'error':'busy'});self.assertEqual(self.result[0],409);self.assertNotIn(5,self.ops)

if __name__=='__main__':unittest.main()

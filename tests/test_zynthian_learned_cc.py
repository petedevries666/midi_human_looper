"""Native device-consumer gate: scoped learned CC, never global UI/PANIC."""
import importlib.util,pathlib,types,unittest
r=pathlib.Path(__file__).resolve().parents[1];spec=importlib.util.spec_from_file_location('router',r/'zynthian/zynthian_engine_mbh_router.py');router=importlib.util.module_from_spec(spec);spec.loader.exec_module(router)
class Relay(unittest.TestCase):
 def setUp(self):
  self.values=[];self.other=[];self.chain=types.SimpleNamespace(chain_id=2,midi_chan=0,zmop_index=1)
  ctrl=types.SimpleNamespace(processor=types.SimpleNamespace(chain_id=2),midi_control_change=self.values.append)
  other=types.SimpleNamespace(processor=types.SimpleNamespace(chain_id=3),midi_control_change=self.other.append)
  self.manager=types.SimpleNamespace(chains={2:self.chain},chain_midi_cc_binding={(2<<16)|5:[ctrl,ctrl,other]},absolute_midi_cc_binding={},active_chain_id=3)
  self.route=1;self.flags=1
  self.context=types.SimpleNamespace(chain_manager=self.manager,devices_in=[types.SimpleNamespace(name='mbh_1:midi_out')],lib_zyncore=types.SimpleNamespace(zmop_get_route_from=lambda o,i:self.route,zmip_get_flags=lambda i:self.flags,zmip_set_flags=self.set_flags),state_manager=types.SimpleNamespace(ctrldev_manager=types.SimpleNamespace(drivers={})))
  self.relay=router._learned_cc_relay(self.context,0,'mbh_1:midi_out');self.relay.allowed=(self.chain,)
 def set_flags(self,i,v):self.flags=v;return 1
 def test_cc5_targets_learned_chain_not_active_chain_and_deduplicates(self):
  self.assertTrue(self.relay.midi_event(bytes([176,5,91])));self.assertEqual(self.values,[91]);self.assertFalse(self.other)
 def test_panic_bank_program_note_and_clock_are_consumed_without_actions(self):
  for event in ([176,120,0],[176,123,0],[176,121,0],[176,0,10],[176,32,10],[144,60,100],[192,2],[248]):self.assertTrue(self.relay.midi_event(bytes(event)))
  self.assertFalse(self.values)
 def test_wrong_channel_unlearned_and_unrouted_cc_are_ignored(self):
  self.relay.midi_event(bytes([177,5,91]));self.relay.midi_event(bytes([176,8,91]));self.route=0;self.relay.midi_event(bytes([176,5,91]));self.assertFalse(self.values)
 def test_recycled_chain_is_not_touched(self):
  self.manager.chains[2]=types.SimpleNamespace(chain_id=2);self.relay.midi_event(bytes([176,5,91]));self.assertFalse(self.values)
 def test_recycled_device_is_not_consumed(self):
  self.context.devices_in[0].name='keyboard:out';self.assertFalse(self.relay.midi_event(bytes([176,5,91])))
 def test_shutdown_closes_capture_and_existing_driver_is_preserved(self):
  self.relay.end();self.assertEqual(self.flags&1,0);self.assertFalse(self.relay.allowed)
  self.context.state_manager.ctrldev_manager.drivers[0]=object()
  with self.assertRaises(RuntimeError):router._learned_cc_relay(self.context,0,'mbh_1:midi_out')
if __name__=='__main__':unittest.main()

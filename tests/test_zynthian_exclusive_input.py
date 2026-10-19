"""Opt-in exclusive keyboard -> MBMF -> virtual ZynMidiRouter source."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'mb_router', Path(__file__).resolve().parents[1] / 'zynthian/zynthian_engine_mbh_router.py')
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)


class NativeAPI:
    def __init__(self):
        self.cc_routes = {}
        self.flags = {}
        self.routes = {}
        self.modes = {}
        self.bad_readback = None
        self.calls = []

    def zmop_get_cc_route(self, index, buffer):
        for i, value in enumerate(self.cc_routes.get(index, [0]*128)): buffer[i] = value
        return 1

    def zmop_set_cc_route(self, index, buffer):
        self.cc_routes[index] = list(buffer)
        return 1

    def zmip_get_flags(self, index):
        return self.flags.get(index, 0xff)

    def zmip_set_flags(self, index, flags):
        self.flags[index] = flags
        self.calls.append(('flags', index, flags))
        return 1

    def zmop_get_route_from(self, zmop, dev):
        if zmop >= 43: return -1
        if self.bad_readback == (zmop, dev):
            return 1
        return self.routes.get((zmop, dev), 1)

    def zmop_set_route_from(self, zmop, dev, enabled):
        self.calls.append(('route', zmop, dev, enabled))
        self.routes[(zmop, dev)] = enabled
        return 1

    def zmip_get_flag_active_chain(self, dev):
        return self.modes.get(dev, 1)

    def zmip_set_flag_active_chain(self, dev, value):
        self.calls.append(('mode', dev, value))
        self.modes[dev] = value
        return 1


class ExclusiveInput(unittest.TestCase):
    def setUp(self):
        proc = lambda code: types.SimpleNamespace(
            eng_code=code, engine=types.SimpleNamespace(get_jackname=lambda: 'mbh_1:'))
        chain = lambda cid, zmop, slots, synth=False: types.SimpleNamespace(
            chain_id=cid, zmop_index=zmop, midi_slots=slots,
            synth_slots=[[proc('SYN')]] if synth else [], midi_out=[])
        self.mb = chain(1, 0, [[proc('MB')]])
        self.synth = chain(2, 1, [], synth=True)
        self.other = chain(3, 2, [[proc('OTHER')]])
        self.chains = {1: self.mb, 2: self.synth, 3: self.other}
        self.api = NativeAPI()
        self.keyboard = types.SimpleNamespace(name='system:midi_capture_1')
        self.ttymidi = types.SimpleNamespace(name='ttymidi:MIDI_in')
        self.virtual = types.SimpleNamespace(name='mbh_1:midi_out')
        self.ctx = types.SimpleNamespace(
            max_num_devs=24,
            devices_in=[self.keyboard, self.ttymidi, self.virtual] + [None] * 24,
            devices_in_mode=[1] * 27,
            hw_midi_src_ports=[],
            chain_manager=types.SimpleNamespace(chains=self.chains),
            state_manager=types.SimpleNamespace(
                get_max_num_zmops=lambda: 16,
                get_zmip_seq_index=lambda: 24,
                get_zmip_step_index=lambda: 25,
                get_zmip_int_index=lambda: 26),
            lib_zyncore=self.api,
            jclient=types.SimpleNamespace(get_ports=lambda *args, **kwargs: [self.virtual]))
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'install.json'
        self.patch_path = patch.object(router, 'CONFIG_PATH', self.path)
        self.patch_path.start()
        self.addCleanup(self.patch_path.stop)
        self.set_ports(['system:midi_capture_1'])

    def tearDown(self):
        if os.environ.get('M4_ROUTING_TRACE'):
            with open(os.environ['M4_ROUTING_TRACE'], 'a') as out:
                out.write(json.dumps(dict(test=self.id(), calls=self.api.calls))+'\n')

    def set_ports(self, ports):
        self.path.write_text(json.dumps({'exclusive_midi_input_ports': ports}))

    def route(self, zmop, dev):
        return self.api.routes.get((zmop, dev), 1)

    def configure(self):
        graph = {'mbh_1:midi_in': {'ZynMidiRouter:ch0_out'},
                 'synthv1-01:in': {'ZynMidiRouter:ch1_out'}}
        router.configure(self.ctx, graph)
        return graph

    def assert_virtual_never_enabled(self):
        self.assertFalse([c for c in self.api.calls
                          if c[0] == 'route' and c[2] == 2 and c[3] == 1],
                         'unsafe virtual routes must never be enabled, even transiently')

    def test_no_transient_admission_without_opt_in(self):
        self.set_ports([])
        self.configure()
        self.assert_virtual_never_enabled()

    def test_no_transient_admission_on_missing_keyboard(self):
        self.set_ports(['missing:out'])
        self.configure()
        self.assert_virtual_never_enabled()

    def test_disconnected_keyboard_does_not_mute_present_selected_helix(self):
        self.set_ports([self.keyboard.name,self.ttymidi.name])
        self.ctx.devices_in[0]=None
        graph=self.configure()
        self.assertEqual(graph['ZynMidiRouter:dev2_in'],{'mbh_1:midi_out'})
        self.assertEqual(self.route(0,1),1)
        self.assertEqual(self.route(1,1),0)
        self.assertEqual(self.route(2,1),0)
        self.assertFalse([c for c in self.api.calls if c[0]=='mode' and c[1]==0])
        self.assertEqual(json.loads(self.path.read_text())['exclusive_midi_input_ports'],[self.keyboard.name,self.ttymidi.name])

    def test_reconnected_selected_keyboard_rejoins_without_direct_synth_bypass(self):
        self.set_ports([self.keyboard.name,self.ttymidi.name])
        self.ctx.devices_in[0]=None;self.configure()
        self.ctx.devices_in[0]=self.keyboard;graph=self.configure()
        self.assertEqual(graph['ZynMidiRouter:dev2_in'],{'mbh_1:midi_out'})
        for device in (0,1):
            self.assertEqual(self.route(0,device),1)
            self.assertEqual(self.route(1,device),0)
            self.assertEqual(self.route(2,device),0)

    def test_unselected_present_device_never_substitutes_missing_selected_one(self):
        self.ctx.devices_in[0]=None
        self.set_ports([self.keyboard.name]);self.configure()
        self.assert_virtual_never_enabled()
        self.assertEqual(self.route(1,1),1)
        self.assertFalse([c for c in self.api.calls if c[0]=='mode' and c[1]==1])

    def test_no_transient_admission_on_invalid_config(self):
        self.path.write_text('{invalid')
        self.configure()
        self.assert_virtual_never_enabled()

    def test_no_transient_admission_on_physical_isolation_failure(self):
        self.api.bad_readback = (1, 0)
        self.configure()
        self.assert_virtual_never_enabled()

    def test_no_transient_admission_on_virtual_quarantine_failure(self):
        self.api.bad_readback = (0, 2)
        self.configure()
        self.assert_virtual_never_enabled()

    def test_refresh_quarantines_before_any_keyboard_change(self):
        self.configure()
        self.api.calls.clear()
        self.configure()
        close = next(i for i,c in enumerate(self.api.calls) if c == ('route', 1, 2, 0))
        physical = next(i for i,c in enumerate(self.api.calls) if c == ('mode', 0, 0))
        enable = next(i for i,c in enumerate(self.api.calls) if c == ('route', 1, 2, 1))
        self.assertLess(close, physical)
        self.assertLess(physical, enable)

    def test_late_enable_failure_quarantines_before_physical_restore(self):
        original = self.api.zmop_set_route_from
        def failing(zmop, dev, enabled):
            result = original(zmop, dev, enabled)
            return 0 if (zmop, dev, enabled) == (1, 2, 1) else result
        self.api.zmop_set_route_from = failing
        graph = self.configure()
        self.assertFalse(graph['ZynMidiRouter:dev2_in'])
        enable = self.api.calls.index(('route', 1, 2, 1))
        after = self.api.calls[enable+1:]
        self.assertLess(after.index(('route', 1, 2, 0)), after.index(('route', 1, 0, 1)))
        self.assertFalse([c for c in after if c[0]=='route' and c[2]==2 and c[3]==1])
        self.assertEqual(self.route(1, 2), 0)

    def test_quarantine_exception_never_admits_virtual_source(self):
        original = self.api.zmop_set_route_from
        def failing(zmop, dev, enabled):
            result = original(zmop, dev, enabled)
            if (zmop, dev) == (0, 2):
                raise RuntimeError('injected native quarantine failure')
            return result
        self.api.zmop_set_route_from = failing
        self.assertFalse(self.configure()['ZynMidiRouter:dev2_in'])
        self.assert_virtual_never_enabled()
        self.assertIn(('route', 1, 2, 0), self.api.calls,
                      'failure closing one route must not skip other closures')

    def test_removed_mb_never_resurrects_its_virtual_input(self):
        self.configure();self.api.calls.clear();del self.chains[1]
        router.discover(self.ctx)
        self.assert_virtual_never_enabled()
        self.assertEqual(self.route(1,2),0)
        self.assertEqual(self.route(1,0),1,'physical keyboard restored after quarantine')

    def test_removed_mb_failed_quarantine_keeps_keyboard_isolated(self):
        self.configure();self.api.calls.clear();del self.chains[1]
        self.api.bad_readback=(1,2)
        router.discover(self.ctx)
        self.assertEqual(self.route(1,0),0)
        self.assertIsNotNone(self.ctx._mbmf_exclusive)
        self.assert_virtual_never_enabled()

    def test_failed_physical_restore_retains_ownership_for_retry(self):
        self.configure();self.set_ports([])
        original=self.api.zmop_set_route_from
        def failing(zmop,dev,enabled):
            if (zmop,dev,enabled)==(1,0,1):
                self.api.calls.append(('route',zmop,dev,enabled));return 0
            return original(zmop,dev,enabled)
        self.api.zmop_set_route_from=failing
        self.configure()
        self.assertIsNotNone(self.ctx._mbmf_exclusive,'failed restore cannot discard its ownership journal')
        self.assertEqual(self.route(1,0),0)
        self.api.zmop_set_route_from=original
        self.configure()
        self.assertIsNone(self.ctx._mbmf_exclusive)
        self.assertEqual(self.route(1,0),1)

    def test_retired_output_is_removed_from_desired_jack_graph(self):
        self.configure();self.api.calls.clear();del self.chains[1]
        graph={'synth:in': {'mbh_1:midi_out','other:out'},
               'ZynMidiRouter:dev2_in': {'mbh_1:midi_out'}}
        router.configure(self.ctx,graph)
        self.assertEqual(graph['synth:in'],{'other:out'})
        self.assertEqual(graph['ZynMidiRouter:dev2_in'],set())
        self.assert_virtual_never_enabled()

    def test_recycled_device_slot_is_not_overwritten_during_retirement(self):
        self.configure();self.api.calls.clear();del self.chains[1]
        self.ctx.devices_in[2]=types.SimpleNamespace(name='unrelated:new_input')
        router.discover(self.ctx)
        self.assertFalse([c for c in self.api.calls
                          if (c[0]=='route' and c[2]==2) or (c[0]=='mode' and c[1]==2)])
        self.assertEqual(self.route(1,0),0,'unverified recycled graph keeps physical bypass isolated')
        self.assertIsNotNone(self.ctx._mbmf_exclusive)

    def test_failed_physical_mode_restore_can_retry(self):
        self.configure();self.set_ports([])
        original=self.api.zmip_set_flag_active_chain
        def failing(dev,mode):
            if (dev,mode)==(0,1):
                self.api.calls.append(('mode',dev,mode));return 0
            return original(dev,mode)
        self.api.zmip_set_flag_active_chain=failing
        self.configure()
        self.assertIsNotNone(self.ctx._mbmf_exclusive)
        self.api.zmip_set_flag_active_chain=original
        self.configure()
        self.assertIsNone(self.ctx._mbmf_exclusive)
        self.assertEqual(self.api.modes[0],1)

    def test_keyboard_only_through_mb_and_virtual_to_synth(self):
        graph = self.configure()
        self.assertEqual(graph['ZynMidiRouter:dev2_in'], {'mbh_1:midi_out'})
        self.assertEqual(self.route(0, 0), 1)
        self.assertEqual(self.route(1, 0), 0)
        self.assertEqual(self.route(2, 0), 0)
        self.assertEqual(self.route(0, 2), 0)
        self.assertEqual(self.route(1, 2), 1)
        self.assertEqual(self.api.modes[0], 0)
        self.assertEqual(self.api.modes[2], 0)

    def test_sequencer_return_blocked_unrelated_ttymidi_preserved(self):
        self.configure()
        for dev in (24, 25, 26):
            self.assertEqual(self.route(0, dev), 0)
        self.assertEqual(self.route(1, 24), 1)
        self.assertEqual(self.route(0, 1), 1)
        self.assertEqual(self.route(1, 1), 1)

    def test_default_no_opt_in_preserves_existing_routes(self):
        self.set_ports([])
        self.configure()
        self.assertEqual(self.route(1, 0), 1)
        self.assertEqual(self.route(0, 24), 1)
        self.assertEqual(self.api.modes.get(0, 1), 1)
        self.assertEqual(self.configure()['ZynMidiRouter:dev2_in'], set())

    def test_missing_keyboard_fails_closed(self):
        self.set_ports(['missing:out'])
        graph = self.configure()
        self.assertEqual(graph['ZynMidiRouter:dev2_in'], set())
        self.assertEqual(self.route(1, 0), 1)

    def test_invalid_json_fails_closed(self):
        self.path.write_text('{invalid')
        self.assertEqual(self.configure()['ZynMidiRouter:dev2_in'], set())

    def test_readback_failure_restores_keyboard(self):
        self.api.bad_readback = (1, 0)
        graph = self.configure()
        self.assertEqual(graph['ZynMidiRouter:dev2_in'], set())
        self.assertEqual(self.route(1, 0), 1)
        self.assertEqual(self.route(0, 24), 1)
        self.assertEqual(self.api.modes[0], 1)

    def test_disable_policy_restores_original_routes(self):
        self.configure()
        self.set_ports([])
        self.configure()
        self.assertEqual(self.route(1, 0), 1)
        self.assertEqual(self.route(0, 24), 1)
        self.assertEqual(self.api.modes[0], 1)

    def test_removing_mb_restores_before_slot_reuse(self):
        self.configure()
        del self.chains[1]
        router.discover(self.ctx)
        self.assertEqual(self.route(1, 0), 1)
        self.assertEqual(self.api.modes[0], 1)
        self.assertIsNone(self.ctx._mbmf_exclusive)

    def test_new_synth_after_snapshot_stays_isolated(self):
        self.configure()
        self.chains[4] = types.SimpleNamespace(
            chain_id=4, zmop_index=4, midi_slots=[], synth_slots=[['synth']], midi_out=[])
        self.configure()
        self.assertEqual(self.route(4, 0), 0)
        self.assertEqual(self.route(4, 2), 1)

    def test_repeated_refresh_is_idempotent(self):
        self.configure()
        before = (dict(self.api.routes), dict(self.api.modes))
        self.configure()
        self.assertEqual((self.api.routes, self.api.modes), before)


    def test_quarantine_precedes_keyboard_bypass_restore(self):
        self.configure()
        self.api.calls.clear()
        self.set_ports([])
        graph = self.configure()
        self.assertEqual(graph['ZynMidiRouter:dev2_in'], set())
        virtual_close = next(i for i, c in enumerate(self.api.calls)
                             if c == ('route', 1, 2, 0))
        keyboard_restore = next(i for i, c in enumerate(self.api.calls)
                                if c == ('route', 1, 0, 1))
        self.assertLess(virtual_close, keyboard_restore)

    def test_failed_virtual_quarantine_never_restores_keyboard_bypass(self):
        self.configure()
        self.api.bad_readback = (1, 2)
        self.set_ports([])
        graph = self.configure()
        self.assertEqual(graph['ZynMidiRouter:dev2_in'], set())
        self.assertEqual(self.route(1, 0), 0)
        self.assertEqual(self.api.modes[0], 0)



    def test_native_matrix_note_and_transport_paths_do_not_double_or_loop(self):
        """Model the topology ZynMidiRouter applies, not audio/DSP timing.

        dev0 -> MB ch0 -> dev2 -> synth ch1. A synth-side SMF tap may
        re-enter through internal seq input, which must not reach MB.
        """
        self.configure()
        def destinations(device, channel):
            # Channel filter is native; only synth ch1 accepts channel 2
            return [chain for chain in (self.mb, self.synth, self.other)
                    if self.route(chain.zmop_index, device)
                    and (chain is self.mb or
                         (chain is self.synth and channel == 2))]
        # Keyboard feeds MB only, even when the played note is on ch2.
        self.assertEqual(destinations(0, 2), [self.mb])
        # A forwarded MB event can reach the requested synth, not MB.
        self.assertEqual(destinations(2, 2), [self.synth])
        self.assertEqual(destinations(2, 3), [])
        # Even an SMF side-tap of synth output can't reach MB again.
        self.assertNotIn(self.mb, destinations(24, 2))
        # Two note events (on/off) remain two events at each stage.
        notes = [('on', 41, 100), ('off', 41, 0)]
        observed = [(state, key, velocity, target.chain_id)
                    for state, key, velocity in notes
                    for target in destinations(2, 2)]
        self.assertEqual(observed, [
            ('on', 41, 100, 2), ('off', 41, 0, 2)
        ])

    def test_keyboard_selection_change_is_rejected_without_new_permission(self):
        self.configure()
        self.set_ports(['ttymidi:MIDI_in'])
        graph = self.configure()
        # Missing or changed input selection may not silently admit
        # existing virtual MB output in an unreviewed hardware graph.
        self.assertEqual(graph['ZynMidiRouter:dev2_in'],
                         {'mbh_1:midi_out'})
        self.assertEqual(self.route(1, 1), 0)
        self.assertEqual(self.route(1, 0), 1)



if __name__ == '__main__':
    unittest.main()

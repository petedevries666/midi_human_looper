"""Opt-in exclusive keyboard -> MBMF -> virtual ZynMidiRouter source."""
import importlib.util
import json
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
        self.routes = {}
        self.modes = {}
        self.bad_readback = None

    def zmop_get_route_from(self, zmop, dev):
        if self.bad_readback == (zmop, dev):
            return 1
        return self.routes.get((zmop, dev), 1)

    def zmop_set_route_from(self, zmop, dev, enabled):
        self.routes[(zmop, dev)] = enabled
        return 1

    def zmip_get_flag_active_chain(self, dev):
        return self.modes.get(dev, 1)

    def zmip_set_flag_active_chain(self, dev, value):
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

    def set_ports(self, ports):
        self.path.write_text(json.dumps({'exclusive_midi_input_ports': ports}))

    def route(self, zmop, dev):
        return self.api.routes.get((zmop, dev), 1)

    def configure(self):
        graph = {'mbh_1:midi_in': {'ZynMidiRouter:ch0_out'},
                 'synthv1-01:in': {'ZynMidiRouter:ch1_out'}}
        router.configure(self.ctx, graph)
        return graph

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


if __name__ == '__main__':
    unittest.main()

"""Regression tests for MBMF's native MIDI feedback firewall."""
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('mb_router', Path(__file__).resolve().parents[1] / 'zynthian/zynthian_engine_mbh_router.py')
router = importlib.util.module_from_spec(spec)
spec.loader.exec_module(router)


class NativeAPI:
    def __init__(self):
        self.routes = {}
        self.modes = {}
        self.calls = []
        self.bad_readback = None
        self.bad_mode = False

    def zmip_get_flag_active_chain(self, index):
        return 1 if self.bad_mode else self.modes.get(index, 1)

    def zmip_set_flag_active_chain(self, index, value):
        self.calls.append(('mode', index, value))
        self.modes[index] = value
        return 1

    def zmop_get_route_from(self, zmop, index):
        if self.bad_readback == zmop:
            return 1
        return self.routes.get((zmop, index), 1)

    def zmop_set_route_from(self, zmop, index, value):
        self.calls.append(('route', zmop, index, value))
        self.routes[(zmop, index)] = value
        return 1


class FeedbackGuard(unittest.TestCase):
    def setUp(self):
        # This suite isolates the native virtual-source firewall. Physical
        # input isolation and the explicit opt-in gate are separately tested
        # in test_zynthian_exclusive_input.py.
        self._policy = patch.object(router, '_read_exclusive_ports', return_value=['keyboard:out'])
        self._apply = patch.object(router, '_apply_exclusive', return_value=True)
        self._policy.start()
        self._apply.start()
        self.addCleanup(self._apply.stop)
        self.addCleanup(self._policy.stop)
        def proc(code):
            return types.SimpleNamespace(eng_code=code, engine=types.SimpleNamespace(get_jackname=lambda: 'mbh_1:'))

        def chain(cid, zmop, slots, synth=False):
            return types.SimpleNamespace(chain_id=cid, zmop_index=zmop, midi_slots=slots,
                                         synth_slots=[[proc('SYN')]] if synth else [], midi_out=[])

        self.chains = {
            1: chain(1, 4, [[proc('MB')]]),
            2: chain(2, 7, [], synth=True),
            3: chain(3, 9, [], synth=True),
            4: chain(4, 11, [], synth=True),
            5: chain(5, 13, [[proc('OTHER')]]),
        }
        self.api = NativeAPI()
        self.port = types.SimpleNamespace(name='mbh_1:midi_out')
        self.ctx = types.SimpleNamespace(
            chain_manager=types.SimpleNamespace(chains=self.chains),
            jclient=types.SimpleNamespace(get_ports=lambda *args, **kw: [self.port]),
            hw_midi_src_ports=[], devices_in=[None, None, self.port],
            devices_in_mode=[1, 1, 1], lib_zyncore=self.api)

    def test_synth_only_no_feedback_and_no_direct_jack_shortcuts(self):
        routes = {'mbh_1:midi_in': {'ZynMidiRouter:ch4_out'},
                  'synthv1:in': {'mbh_1:midi_out', 'ZynMidiRouter:ch7_out'}}
        router.discover(self.ctx)
        router.configure(self.ctx, routes)
        self.assertEqual(routes['ZynMidiRouter:dev2_in'], {'mbh_1:midi_out'})
        self.assertEqual(routes['synthv1:in'], {'ZynMidiRouter:ch7_out'})
        for zmop in (7, 9, 11):
            self.assertEqual(self.api.routes[(zmop, 2)], 1)
        for zmop in (4, 13):
            self.assertEqual(self.api.routes[(zmop, 2)], 0)
        self.assertEqual(self.api.modes[2], 0)
        router.configure(self.ctx, routes)
        self.assertEqual(routes['ZynMidiRouter:dev2_in'], {'mbh_1:midi_out'})

    def test_synth_return_chain_is_excluded(self):
        self.chains[2].midi_out = [5]
        self.chains[5].midi_out = [1]
        routes = {}
        router.configure(self.ctx, routes)
        self.assertEqual(self.api.routes[(7, 2)], 0)
        self.assertEqual(self.api.routes[(9, 2)], 1)

    def test_jack_graph_return_to_mb_is_excluded(self):
        routes = {'mbh_1:midi_in': {'loopback:out'},
                  'loopback:out': {'ZynMidiRouter:ch9_out'}}
        router.configure(self.ctx, routes)
        self.assertEqual(self.api.routes[(9, 2)], 0)
        self.assertEqual(self.api.routes[(7, 2)], 1)

    def test_native_readback_failure_disables_entire_source(self):
        self.api.bad_readback = 4
        routes = {'synthv1:in': {'mbh_1:midi_out'}}
        router.configure(self.ctx, routes)
        self.assertEqual(routes['ZynMidiRouter:dev2_in'], set())
        self.assertEqual(routes['synthv1:in'], set())
        for zmop in (4, 7, 9, 11, 13):
            self.assertEqual(self.api.routes[(zmop, 2)], 0)

    def test_native_mode_readback_failure_disables_source(self):
        self.api.bad_mode = True
        routes = {}
        router.configure(self.ctx, routes)
        self.assertEqual(routes['ZynMidiRouter:dev2_in'], set())
        for zmop in (4, 7, 9, 11, 13):
            self.assertEqual(self.api.routes[(zmop, 2)], 0)

    def test_removal_restores_previous_mode_and_routes(self):
        router.configure(self.ctx, {})
        del self.chains[1]
        router.discover(self.ctx)
        self.assertEqual(self.api.modes[2], 1)
        self.assertEqual(self.api.routes[(7, 2)], 1)
        self.assertEqual(self.ctx._mbmf_source_inputs, {})

    def test_unrelated_jack_routes_untouched(self):
        routes = {'synthv1:in': {'keyboard:out', 'other:out'}}
        router.configure(self.ctx, routes)
        self.assertEqual(routes['synthv1:in'], {'keyboard:out', 'other:out'})


if __name__ == '__main__':
    unittest.main()

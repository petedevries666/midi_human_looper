"""The installed production helper calls Oram's real zmip/zmop APIs.
Hardware lib_zyncore itself is unavailable in Cloud; calls are captured explicitly.
"""
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mb_router',ROOT/'zynthian/zynthian_engine_mbh_router.py')
router=importlib.util.module_from_spec(spec);spec.loader.exec_module(router)
class NativeSource(unittest.TestCase):
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
        proc=lambda code:types.SimpleNamespace(eng_code=code,engine=types.SimpleNamespace(get_jackname=lambda:'mbh_1:'))
        chain=lambda ident,slots,synth=False:types.SimpleNamespace(chain_id=ident,zmop_index=ident,midi_slots=slots,synth_slots=[[proc('SYN')]] if synth else [],midi_out=[])
        self.chains={1:chain(1,[[proc('MB')]]),**{i:chain(i,[],True) for i in (2,3,4)}}
        self.cc_routes={};self.flags={};self.calls=[];self.routes={};self.modes={};self.port=types.SimpleNamespace(name='mbh_1:midi_out')
        def get_mode(index):
            return self.modes.get(index,1)
        def set_mode(index,value):
            self.modes[index]=value
            self.calls.append(('mode',index,value))
            return 1
        def get_route(zmop,index):
            if zmop >= 43: return -1
            return self.routes.get((zmop,index),1)
        def set_route(zmop,index,enabled):
            self.routes[(zmop,index)]=enabled
            self.calls.append(('route',zmop,index,enabled))
            return 1
        def get_cc(index, buffer):
            for i,value in enumerate(self.cc_routes.get(index,[0]*128)):buffer[i]=value
            return 1
        def set_cc(index, buffer):
            self.cc_routes[index]=list(buffer)
            return 1
        def set_flags(index, flags):
            self.flags[index]=flags
            return 1
        self.ctx=types.SimpleNamespace(state_manager=types.SimpleNamespace(get_max_num_zmops=lambda:16),chain_manager=types.SimpleNamespace(chains=self.chains),
            jclient=types.SimpleNamespace(get_ports=lambda *a,**kw:[self.port]),hw_midi_src_ports=[],
            devices_in=[None,self.port],devices_in_mode=[1,1],lib_zyncore=types.SimpleNamespace(
                zmop_get_cc_route=get_cc,zmop_set_cc_route=set_cc,
                zmip_get_flags=lambda index:self.flags.get(index,255),zmip_set_flags=set_flags,
                zmip_get_flag_active_chain=get_mode,zmop_get_route_from=get_route,
                zmip_set_flag_active_chain=set_mode,
                zmop_set_route_from=set_route))
    def test_three_filtered_receivers_no_direct_shortcuts_or_focus_dependency(self):
        router.discover(self.ctx);router.discover(self.ctx)
        self.assertEqual(self.ctx.hw_midi_src_ports,[self.port])
        self.chains[1].midi_out=[2,3,4] # Old #64 snapshot: don't reinterpret or erase it.
        routes={f'synth_{i}:in':{'mbh_1:midi_out',f'ZynMidiRouter:ch{i}_out'} for i in (2,3,4)}
        routes['mbh_1:midi_in']={'ZynMidiRouter:ch1_out'}
        router.configure(self.ctx,routes)
        self.assertEqual(routes['ZynMidiRouter:dev1_in'],{'mbh_1:midi_out'})
        for i in (2,3,4):
            self.assertEqual(routes[f'synth_{i}:in'],{f'ZynMidiRouter:ch{i}_out'})
            self.assertIn(('route',i,1,1),self.calls)
        self.assertIn(('route',1,1,0),self.calls)
        self.assertIn(('mode',1,0),self.calls)
        self.assertEqual(self.chains[1].midi_out,[2,3,4])
        router.configure(self.ctx,routes) # Refresh / snapshot restore.
        self.assertEqual(routes['ZynMidiRouter:dev1_in'],{'mbh_1:midi_out'})
        del self.chains[3];router.configure(self.ctx,routes)
    def test_return_chain_is_excluded_and_insertion_mode_unaffected(self):
        self.chains[2].midi_out=[1];router.configure(self.ctx,{})
        self.assertIn(('route',2,1,0),self.calls)
        self.chains[1].synth_slots=[['synth']]
        self.assertEqual(router.sources(self.ctx),{})
    def test_removal_restores_native_input_slot_before_reuse(self):
        router.configure(self.ctx,{})
        self.chains.clear();router.discover(self.ctx)
        self.assertIn(1,self.ctx._mbmf_source_inputs,'still-live orphan must remain quarantined')
        self.assertEqual(self.modes[1],0)
        self.ctx.devices_in[1]=None
        router.discover(self.ctx)
        self.assertEqual(self.ctx._mbmf_source_inputs,{})
        self.assertIn(('mode',1,1),self.calls)

    def test_other_devices_and_routes_retained(self):
        other=types.SimpleNamespace(name='keyboard:out');self.ctx.hw_midi_src_ports=[other]
        routes={'synth:in':{'keyboard:out','other:out'}}
        router.discover(self.ctx);router.configure(self.ctx,routes)
        self.assertEqual(self.ctx.hw_midi_src_ports,[other,self.port])
        self.assertEqual(routes['synth:in'],{'keyboard:out','other:out'})
    def test_scoped_learn_installed_before_capture_and_keeps_native_firewall(self):
        self.ctx.state_manager.ctrldev_manager=types.SimpleNamespace(drivers={})
        values=[];control=types.SimpleNamespace(processor=types.SimpleNamespace(chain_id=2),midi_control_change=values.append)
        self.ctx.chain_manager.chain_midi_cc_binding={(2<<16)|5:[control]}
        self.ctx.chain_manager.absolute_midi_cc_binding={}
        for chain in self.chains.values():chain.midi_chan=0
        router.configure(self.ctx,{})
        relay=self.ctx.state_manager.ctrldev_manager.drivers[1]
        self.assertEqual(self.flags[1]&1,1)
        relay.midi_event(bytes([176,5,80]));self.assertEqual(values,[80])
        relay.midi_event(bytes([176,123,0]));self.assertEqual(values,[80])
        self.assertEqual(self.routes[(0,1)],0)
        self.assertEqual(self.routes[(1,1)],0)
        self.assertEqual(self.routes[(42,1)],0)

if __name__=='__main__':unittest.main()

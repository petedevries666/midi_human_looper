"""The installed production helper calls Oram's real zmip/zmop APIs.
Hardware lib_zyncore itself is unavailable in Cloud; calls are captured explicitly.
"""
import importlib.util
from pathlib import Path
import types
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mb_router',ROOT/'zynthian/zynthian_engine_mbh_router.py')
router=importlib.util.module_from_spec(spec);spec.loader.exec_module(router)
class NativeSource(unittest.TestCase):
    def setUp(self):
        proc=lambda code:types.SimpleNamespace(eng_code=code,engine=types.SimpleNamespace(get_jackname=lambda:'mbh_1:'))
        chain=lambda ident,slots,synth=False:types.SimpleNamespace(chain_id=ident,zmop_index=ident,midi_slots=slots,synth_slots=[[proc('SYN')]] if synth else [],midi_out=[])
        self.chains={1:chain(1,[[proc('MB')]]),**{i:chain(i,[],True) for i in (2,3,4)}}
        self.calls=[];self.port=types.SimpleNamespace(name='mbh_1:midi_out')
        self.ctx=types.SimpleNamespace(chain_manager=types.SimpleNamespace(chains=self.chains),
            jclient=types.SimpleNamespace(get_ports=lambda *a,**kw:[self.port]),hw_midi_src_ports=[],
            devices_in=[None,self.port],devices_in_mode=[1,1],lib_zyncore=types.SimpleNamespace(
                zmip_get_flag_active_chain=lambda index:1,zmop_get_route_from=lambda *a:1,
                zmip_set_flag_active_chain=lambda *a:self.calls.append(('mode',*a)),
                zmop_set_route_from=lambda *a:self.calls.append(('route',*a))))
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
        self.assertEqual(self.ctx._mbmf_source_inputs,{})
        self.assertIn(('mode',1,1),self.calls)

    def test_other_devices_and_routes_retained(self):
        other=types.SimpleNamespace(name='keyboard:out');self.ctx.hw_midi_src_ports=[other]
        routes={'synth:in':{'keyboard:out','other:out'}}
        router.discover(self.ctx);router.configure(self.ctx,routes)
        self.assertEqual(self.ctx.hw_midi_src_ports,[other,self.port])
        self.assertEqual(routes['synth:in'],{'keyboard:out','other:out'})
if __name__=='__main__':unittest.main()

"""Exercise actual Oram chain/route resolver excerpts, not a invented channel router."""
import importlib.util
from pathlib import Path
import re
import types
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('oram_routes',ROOT/'tests/fixtures/oram/routing.py')
oram=importlib.util.module_from_spec(spec);spec.loader.exec_module(oram)

class Routing(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        oram.zynautoconnect=types.SimpleNamespace(acquire_lock=lambda:True,release_lock=lambda:None,
            request_midi_connect=lambda force:self.calls.append(force))
        def proc(name):
            engine=types.SimpleNamespace(get_jackname=lambda:name,jackname=name)
            return types.SimpleNamespace(engine=engine,type='MIDI Tool' if name.startswith('mbh') else 'MIDI Synth',eng_code='MB' if name.startswith('mbh') else 'SYN',
                                         get_jackname=lambda *args:name)
        self.mb=oram.NativeChain(1,midi_slots=[[proc('mbh_1')]],midi_chan=0xffff)
        self.destinations=[oram.NativeChain(i,synth_slots=[[proc(f'synth_{i}')]],midi_chan=i-2) for i in (2,3,4)]
        self.chains={c.chain_id:c for c in [self.mb,*self.destinations]}
        self.manager=oram.ChainManager(self.chains)
        ports=[types.SimpleNamespace(name=f'synth_{i}:midi_in',input=True) for i in (2,3,4)]
        ports += [types.SimpleNamespace(name='mbh_1:midi_in',input=True),
                  types.SimpleNamespace(name='mbh_1:midi_out',input=False)]
        ports += [types.SimpleNamespace(name=f'ZynMidiRouter:ch{i}_out',input=False) for i in range(1,5)]
        class Jack:
            def get_ports(self,pattern=None,is_input=False,is_output=False,is_midi=True):
                return [p for p in ports if (not pattern or re.search(pattern,p.name)) and
                        (not is_input or p.input) and (not is_output or not p.input)]
        self.jack=Jack()

    def test_one_dedicated_processor_three_native_chain_destinations_and_no_duplicate_connections(self):
        self.assertEqual(self.mb.get_type(),'MIDI Tool')
        for c in self.destinations:self.mb.toggle_midi_out(c.chain_id)
        self.assertEqual(self.mb.midi_out,[2,3,4])
        self.assertEqual(self.calls,[True,True,True])
        routes=oram.resolve_routes(self.manager,self.jack)
        for c in self.destinations:
            sources=routes[f'synth_{c.chain_id}:midi_in']
            self.assertEqual(sources,{'mbh_1:midi_out',f'ZynMidiRouter:ch{c.chain_id}_out'})
            # Two Oram routing paths coalesce into a set, never two identical connections.
            self.assertEqual(list(sources).count('mbh_1:midi_out'),1)
        self.assertEqual(routes['mbh_1:midi_in'],{'ZynMidiRouter:ch1_out'})
        # The test deliberately does NOT pretend native fanout filters MIDI channels.
        # Synth input also has a router path: disable hardware input on destination
        # chains through their UI to prevent double keyboard delivery.

    def test_channel_selection_does_not_filter_or_remap_direct_fanout(self):
        self.mb.toggle_midi_out(2)
        before=oram.resolve_routes(self.manager,self.jack)
        self.destinations[0].midi_chan=8
        self.assertEqual(oram.resolve_routes(self.manager,self.jack),before)

    def test_chain_removal_and_disconnection_drop_only_that_destination(self):
        for c in self.destinations:self.mb.toggle_midi_out(c.chain_id)
        del self.chains[3]
        routes=oram.resolve_routes(self.manager,self.jack)
        self.assertNotIn('mbh_1:midi_out',routes['synth_3:midi_in'])
        self.assertIn('mbh_1:midi_out',routes['synth_2:midi_in'])
        self.mb.toggle_midi_out(4)
        self.assertNotIn('mbh_1:midi_out',oram.resolve_routes(self.manager,self.jack)['synth_4:midi_in'])

    def test_native_feedback_detection_flags_return_routes(self):
        self.mb.toggle_midi_out(2)
        self.assertFalse(self.manager.will_midi_howl(1,2))
        self.destinations[0].toggle_midi_out(1)
        self.assertTrue(self.manager.will_midi_howl(1,2))
        self.assertTrue(self.manager.will_midi_howl(1,1))

if __name__=='__main__':unittest.main()

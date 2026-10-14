"""Production adapter control path + pinned Oram chain/graph API, no hardware claim."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
ROOT = Path(__file__).resolve().parents[1]

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module
oram = load('oram_destinations', ROOT/'tests/fixtures/oram/routing.py')
class Base:
    def get_controllers_dict(self, processor):
        # Oram's static-controller builder is host UI code. Routing is real below.
        return {symbol: types.SimpleNamespace(processor=processor, **options)
                for symbol, options in self._ctrls}
package = types.ModuleType('zyngine')
base = types.ModuleType('zyngine.zynthian_engine'); base.zynthian_engine = Base
sys.modules['zyngine'] = package; sys.modules[base.__name__] = base
adapter = load('mbmf_destinations', ROOT/'zynthian/zynthian_engine_mbh.py')

class Destinations(unittest.TestCase):
    def setUp(self):
        self.refreshes = []
        oram.zynautoconnect = types.SimpleNamespace(acquire_lock=lambda: True, release_lock=lambda: None,
            request_midi_connect=lambda force: self.refreshes.append(force))
        def proc(name):
            return types.SimpleNamespace(engine=types.SimpleNamespace(get_jackname=lambda: name),
                get_jackname=lambda *args: name)
        self.source = oram.NativeChain(1, midi_slots=[[proc('mbh_1:')]])
        self.source.midi_thru=False # Oram's default: internal output routes still work.
        self.destinations = [oram.NativeChain(n, synth_slots=[[proc('receiver%s:'%n)]], midi_chan=n-1)
                             for n in (2, 3, 4)]
        for c in self.destinations: c.get_title=lambda c=c: 'Instrument %s'%c.chain_id
        self.manager = oram.ChainManager({c.chain_id:c for c in [self.source, *self.destinations]})
        self.engine = object.__new__(adapter.zynthian_engine_mbh)
        self.engine.state_manager = types.SimpleNamespace(chain_manager=self.manager)
        self.processor = types.SimpleNamespace(id=1, chain_id=1)
        self.commands = []; self.status='ok'; self.active={}
        def request(**args):
            self.commands.append(args)
            return dict(status=self.status, revision=7, engineSessionId=99, **self.active)
        self.engine.instances={1:dict(control=types.SimpleNamespace(request=request))}
    def control(self, n):
        return self.engine.get_controllers_dict(self.processor)['destination_%s'%n]
    def set_route(self, control, enabled):
        control.value=enabled; self.engine.send_controller_value(control)
    def test_explicit_three_destinations_idempotence_and_native_snapshot_state(self):
        self.assertEqual(self.source.midi_out, [])  # Reproduces absent auto connection.
        for n in (2,3,4): self.set_route(self.control(n), True)
        self.assertEqual(self.source.midi_out,[2,3,4]); self.assertEqual(len(self.refreshes),3)
        self.assertFalse(any(x.get('op')==2 for x in self.commands))
        self.set_route(self.control(2),True)
        self.assertEqual(len(self.refreshes),3)
        # Route truth remains Oram's chain state, not an extra MBMF project field.
        saved=list(self.source.midi_out); self.source.midi_out=list(saved); self.source.rebuild_midi_graph()
        for n in (2,3,4): self.assertEqual(self.control(n).value,1)
        self.set_route(self.control(3),False)
        self.assertEqual(self.source.midi_out,[2,4])
    def test_deleted_destination_and_reused_chain_id_cannot_receive_stale_control(self):
        stale=self.control(2); del self.manager.chains[2]
        with self.assertRaises(ValueError): self.set_route(stale,True)
        self.manager.chains[2]=oram.NativeChain(2,synth_slots=self.destinations[0].synth_slots)
        with self.assertRaises(ValueError): self.set_route(stale,True)
        self.assertIs(stale.graph_path[2],self.destinations[0]) # strong reference prevents Python id reuse
        self.assertEqual(self.commands,[])
    def test_feedback_rejected_even_if_route_changed_after_editor_open(self):
        stale=self.control(2); self.destinations[0].midi_out=[1]
        self.assertNotIn('destination_2', self.engine.get_controllers_dict(self.processor))
        with self.assertRaises(ValueError): self.set_route(stale,True)
        self.assertEqual(self.source.midi_out,[])
    def test_unavailable_state_retains_old_graph(self):
        self.status='rejected'
        with self.assertRaises(RuntimeError): self.set_route(self.control(2),True)
        self.assertEqual(self.source.midi_out,[]); self.assertEqual(self.refreshes,[])
    def test_active_performance_or_held_notes_refuse_route_edit_without_panic(self):
        for active in ({'activeNotes':1}, {'instances':[1]}, {'movements':{'active':1}},
                       {'chainRunning':True}, {'chainRecording':1}):
            self.active=active
            control=self.control(2)
            with self.assertRaises(RuntimeError): self.set_route(control,True)
            self.assertEqual(control.value,0)
            self.assertEqual(self.source.midi_out,[])
        self.assertFalse(any(x.get('op')==2 for x in self.commands))

    def test_instrument_insertion_never_fanouts_implicitly(self):
        self.source.synth_slots=self.destinations[0].synth_slots
        self.assertFalse(any(x.startswith('destination_') for x in self.engine.get_controllers_dict(self.processor)))
    def test_refresh_observes_new_chain_and_native_changes_without_duplication(self):
        self.source.midi_out=[2]; self.assertEqual(self.control(2).value,1)
        del self.manager.chains[3]
        self.assertNotIn('destination_3',self.engine.get_controllers_dict(self.processor))
        self.assertEqual(self.source.midi_out,[2])

if __name__=='__main__': unittest.main()

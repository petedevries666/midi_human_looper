"""Native selector built before destination restore must update in place."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'headless'))
from zynthian_chains import ChainLinks
from test_zynthian_instrument_links import Control, chain
sys.modules['zyngine']=types.ModuleType('zyngine')
base=types.ModuleType('zyngine.zynthian_engine');base.zynthian_engine=object
sys.modules[base.__name__]=base
spec=importlib.util.spec_from_file_location('selector_adapter',ROOT/'zynthian/zynthian_engine_mbh.py')
adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)

class Selector(unittest.TestCase):
    def test_late_restoration_renames_and_removal_update_existing_controller(self):
        destination=chain(2,name='Calf Monosynth')
        manager=types.SimpleNamespace(chains={2:destination},will_midi_howl=lambda a,b:False)
        control=Control();links=ChainLinks(manager,1,control)
        identity=links.status()['chains'][0]['identity'];links.restore({'1':identity})
        manager.chains.clear()
        controller=types.SimpleNamespace(labels=['UNLINKED','DESTINATION MISSING'],value=1,
            graph_path=('host_chain',1,[None,identity],'old'),is_dirty=False)
        def set_options(options):controller.__dict__.update(options)
        controller.set_options=set_options
        processor=types.SimpleNamespace(id=1,controllers_dict={'host_chain_1':controller})
        engine=object.__new__(adapter.zynthian_engine_mbh)
        engine.instances={1:{'host_chains':types.SimpleNamespace(links=links)}}
        manager.chains[2]=destination
        engine._refresh_host_chain_selectors(processor)
        self.assertIs(processor.controllers_dict['host_chain_1'],controller)
        self.assertEqual(controller.labels[controller.value],'C2 Calf Monosynth CH1')
        self.assertTrue(controller.is_dirty)
        self.assertFalse(controller.is_trigger)
        self.assertEqual(links.status()['nativeSelectors']['1'],'C2 Calf Monosynth CH1')
        destination.midi_chan=3;destination.get_title=lambda:'Bass'
        engine._refresh_host_chain_selectors(processor)
        self.assertEqual(controller.labels[controller.value],'C2 Bass CH4')
        manager.chains.clear();engine._refresh_host_chain_selectors(processor)
        self.assertEqual(controller.labels[controller.value],'DESTINATION MISSING')
        manager.chains[2]=chain(2,name='Replacement')
        engine._refresh_host_chain_selectors(processor)
        self.assertEqual(controller.labels[controller.value],'DESTINATION MISSING')
        self.assertEqual(links.snapshot(),{'1':identity})
        self.assertEqual(control.commands,[])

if __name__=='__main__':unittest.main()

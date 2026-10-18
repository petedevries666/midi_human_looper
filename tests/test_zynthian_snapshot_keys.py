"""Real Oram MB/N snapshot key mismatch, multi-processor isolation and owned hooks."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.modules['zyngine']=types.ModuleType('zyngine')
base=types.ModuleType('zyngine.zynthian_engine');base.zynthian_engine=object
sys.modules[base.__name__]=base
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
adapter=load('mbh_snapshot_adapter',ROOT/'zynthian/zynthian_engine_mbh.py')
installer=load('mbh_snapshot_installer',ROOT/'zynthian/install.py')

class SnapshotKeys(unittest.TestCase):
    def test_exact_processor_selects_correct_multi_engine_snapshot(self):
        first={'version':1,'processors':{'1':{'hostChainBindings':{'1':'saved'}}}}
        second={'version':1,'processors':{'9':{}}}
        config={'MB/1':first,'MB/7':second,'JV/2':{'processors':{'1':{}}}}
        self.assertIs(adapter.mbh_snapshot_config(config,1),first)
        self.assertIs(adapter.mbh_snapshot_config(config,'9'),second)
        self.assertIsNone(adapter.mbh_snapshot_config(config,2))
    def test_ambiguous_and_legacy_keys_are_never_guessed(self):
        with self.assertRaises(ValueError):adapter.mbh_snapshot_config({'MB/1':{'processors':{'1':{'patch':1}}},'MB/2':{'processors':{'1':{'patch':2}}}},1)
        for config in (None,{}, {'MB/1':None},{'MB/1':{'processors':[]}}):
            self.assertIsNone(adapter.mbh_snapshot_config(config,1))
    def test_legacy_aggregated_snapshots_agree_for_selected_processor(self):
        one={'processors':{'1':{'patch':1},'2':{'patch':2}}}
        two={'processors':{'1':{'patch':1},'2':{'patch':3}}}
        self.assertIs(adapter.mbh_snapshot_config({'MB/1':one,'MB/2':two},1),one)
        with self.assertRaises(ValueError):adapter.mbh_snapshot_config({'MB/1':one,'MB/2':two},2)
    def fixture(self):
        source=(ROOT/'tests/fixtures/oram/manager.py').read_text()
        # Real set_state anchor is nested inside five loops/branches.
        return source+'\ndef restore_fixture():\n'+''.join('    '*n+'if True:\n' for n in range(1,6))+installer.SNAPSHOT_ANCHOR+'                        pass\n'
    def test_snapshot_hook_is_idempotent_and_owned_rollback_is_exact(self):
        source=self.fixture()
        installed=installer.registration(source,host_chain_links=True)
        self.assertIn('mbh_snapshot_config(engine_config, proc_id)',installed)
        self.assertEqual(installer.registration(installed),installed)
        self.assertEqual(installer.registration(installed,remove=True),source)
    def test_unknown_or_modified_snapshot_hook_refused(self):
        source=(ROOT/'tests/fixtures/oram/manager.py').read_text()
        with self.assertRaises(ValueError):installer.registration(source,host_chain_links=True)
        changed=installer.registration(self.fixture(),host_chain_links=True).replace('eng_config is None','not eng_config')
        with self.assertRaises(ValueError):installer.registration(changed)

if __name__=='__main__':unittest.main()

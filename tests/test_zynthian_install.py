"""Oram catalog/selector and installer lifecycle without touching a real Zynthian."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/oram'
spec = importlib.util.spec_from_file_location('installer', ROOT/'zynthian/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class Installation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.ui = self.path/'ui'
        self.package = self.ui/'zyngine'
        self.package.mkdir(parents=True)
        self.manager = self.package/'zynthian_chain_manager.py'
        self.catalog = self.package/'zynthian_lv2.py'
        self.adapter = self.package/'zynthian_engine_mbh.py'
        self.helper = self.package/'zynthian_engine_mbh_catalog.py'
        self.original = (FIXTURES/'manager.py').read_text()
        self.catalog_original = (FIXTURES/'catalog.py').read_text()
        self.manager.write_text(self.original)
        self.catalog.write_text(self.catalog_original)
        self.manager.chmod(0o644)
        self.catalog.chmod(0o640)
        self.data = self.path/'data/midi-human-looper'
        self.manifest = self.data/'installation.json'
        self.args = ['--ui-dir',str(self.ui),'--data-dir',str(self.path/'data'),'--binary',sys.executable]
        self.command = [sys.executable,str(ROOT/'zynthian/install.py'),*self.args]

    def run_install(self, *args, success=True):
        result = subprocess.run([*self.command,*args],capture_output=True,text=True)
        self.assertEqual(result.returncode==0,success,result.stderr)
        return result

    def legacy(self):
        # Recreate the exact old issue-26 installer format, including an older adapter.
        text = self.original.replace('from zyngine import *\n','from zyngine import *\n'+installer.IMPORT)
        text = text.replace('engine2class = {\n','engine2class = {\n'+installer.CLASS)
        text = text.replace('        cls.engine_info = eng_info\n','        cls.engine_info = eng_info\n'+installer.INFO)
        text = text.replace(installer.ORIGINAL_MULTI,installer.MULTI)
        self.manager.write_text(text)
        self.adapter.write_text('# previously deployed adapter; keep its runtime ABI\n')
        self.data.mkdir(parents=True)
        (self.data/'zynthian_chain_manager.py.original').write_text(self.original)
        self.manifest.write_text(json.dumps(dict(version=1,original_sha256=installer.digest(self.original.encode()),
            adapter_sha256=installer.digest(self.adapter.read_bytes()))))
        (self.data/'install.json').write_text('{"version":1,"repository":"/old/live/repo","binary":"/old/live/engine","chain_timing_version":1,"web_bind":"0.0.0.0","web_port_base":9100,"token_file":"private"}')
        (self.data/'editor.token').write_text('private test token\n')
        (self.data/'editor.token').chmod(0o600)
        (self.data/'processor-1').mkdir()
        (self.data/'processor-1/patch1.json').write_text('{"preserve":"phrases and unknown data"}')
        return text

    def snapshot_files(self):
        return {str(p.relative_to(self.path)):(p.read_bytes(),p.stat().st_mode & 0o777)
                for p in self.path.rglob('*') if p.is_file()}

    def exercise_selector(self):
        # Import the actually installed catalog and manager; only hardware imports are stubbed.
        package = types.ModuleType('zyngine');package.__path__=[str(self.package)]
        engine = types.ModuleType('zyngine.zynthian_engine_mbh')
        engine.zynthian_engine_mbh = type('zynthian_engine_mbh',(),{})
        with patch.dict(sys.modules, {'zyngine':package,'zyngine.zynthian_engine_mbh':engine}):
            spec = importlib.util.spec_from_file_location('zyngine.zynthian_lv2', self.catalog)
            catalog = importlib.util.module_from_spec(spec);sys.modules[spec.name]=catalog
            self.addCleanup(sys.modules.pop,spec.name,None)
            self.addCleanup(sys.modules.pop,'zyngine.zynthian_engine_mbh_catalog',None)
            spec.loader.exec_module(catalog)
            package.zynthian_lv2 = catalog
            disk = self.path/'engines.json'
            original_engines={
                'MC':dict(NAME='MIDI Control',TYPE='MIDI Tool',CAT='Other',ENABLED=True,custom={'keep':1}),
                'SF':dict(NAME='Sfizz',TYPE='MIDI Synth',CAT='Sampler',ENABLED=True),
                'LV2/unrelated':dict(NAME='Unrelated',TYPE='Audio Effect',CAT='Delay',ENABLED=False,custom='unchanged'),
            }
            disk.write_text(json.dumps(original_engines))
            catalog.ENGINE_CONFIG_FILE = catalog.JALV_LV2_CONFIG_FILE = str(disk)
            scope={};exec(compile(self.manager.read_text(),str(self.manager),'exec'),scope)
            chain=scope['Chain']();chain.get_engine_info()
            selected=chain.filtered_engines_by_cat('MIDI Tool')
            self.assertIn('MB', selected['Other'])
            self.assertIs(chain.engine_info['MB']['ENGINE'],engine.zynthian_engine_mbh)
            self.assertIs(catalog.engines_by_type['MIDI Tool']['MB'],chain.engine_info['MB'])
            self.assertEqual(chain.start_engine('MB'),'multiple')
            self.assertEqual(catalog.engines['LV2/unrelated'],original_engines['LV2/unrelated']|{'ENGINE':None})
            self.assertEqual(json.loads(disk.read_text()),original_engines) # No catalog JSON writes on load.
            catalog.engines['MB']['TITLE']='Custom MB title'
            catalog.engines['MB']['QUALITY']=4
            catalog.get_engines_by_type()
            self.assertEqual(catalog.engines['MB']['TITLE'],'Custom MB title')
            self.assertEqual(catalog.engines['MB']['QUALITY'],4)
            catalog.engines['MB']['ENABLED']=False;catalog.get_engines_by_type()
            self.assertNotIn('MB',chain.filtered_engines_by_cat('MIDI Tool')['Other'])
            self.assertIn('MB',chain.filtered_engines_by_cat('MIDI Tool',all=True)['Other'])
            # Reload an old disk catalog lacking MB, then resolve the engine again.
            catalog.load_engines();chain.get_engine_info()
            self.assertIn('MB',chain.filtered_engines_by_cat('MIDI Tool')['Other'])
            # Full regeneration includes the standalone registration, even before reload.
            catalog.generate_engines_config_file();catalog.get_engines_by_type();chain.get_engine_info()
            self.assertIn('MB',chain.filtered_engines_by_cat('MIDI Tool')['Other'])
            self.assertIn('MB',json.loads(disk.read_text()))
            # Simulate a new UI session loading the rebuilt disk catalog.
            catalog.engines={};catalog.engines_by_type=None;catalog.engines_mtime=None
            chain.__class__.engine_info=None;chain.get_engine_info()
            self.assertIn('MB',chain.filtered_engines_by_cat('MIDI Tool')['Other'])

    def test_fresh_install_selector_refresh_restart_and_rollback(self):
        before=self.snapshot_files()
        result=self.run_install('--check')
        self.assertTrue(json.loads(result.stdout)['catalogCompatible'])
        self.assertEqual(self.snapshot_files(),before)
        self.run_install('--lan')
        self.assertEqual(json.loads(self.manifest.read_text())['version'],2)
        self.assertEqual(json.loads((self.data/'install.json').read_text())['chain_timing_version'],2)
        self.assertEqual((self.data/'editor.token').stat().st_mode & 0o777,0o600)
        self.exercise_selector()
        self.run_install('--rollback')
        self.assertEqual(self.manager.read_text(),self.original)
        self.assertEqual(self.catalog.read_text(),self.catalog_original)
        self.assertEqual(self.catalog.stat().st_mode & 0o777,0o640)
        self.assertFalse(self.adapter.exists());self.assertFalse(self.helper.exists())
        self.assertTrue((self.data/'editor.token').exists())
        self.assertTrue((self.data/'install.json').exists())

    def test_rollback_cached_catalog_entry_is_disabled_then_regenerated(self):
        self.run_install()
        self.exercise_selector() # Native regeneration has persisted MB in engines.json.
        disk=self.path/'engines.json'
        cached=json.loads(disk.read_text())
        cached['AE']['ID']='aeolus' # Current-format catalog: avoid legacy regeneration on load.
        disk.write_text(json.dumps(cached))
        self.run_install('--rollback')
        package=types.ModuleType('zyngine');package.__path__=[str(self.package)]
        with patch.dict(sys.modules, {'zyngine':package}):
            spec=importlib.util.spec_from_file_location('rollback_catalog',self.catalog)
            catalog=importlib.util.module_from_spec(spec);spec.loader.exec_module(catalog)
            catalog.ENGINE_CONFIG_FILE=catalog.JALV_LV2_CONFIG_FILE=str(self.path/'engines.json')
            package.zynthian_lv2=catalog
            scope={};exec(compile(self.manager.read_text(),str(self.manager),'exec'),scope)
            chain=scope['Chain']();chain.get_engine_info()
            self.assertNotIn('MB',chain.filtered_engines_by_cat('MIDI Tool')['Other'])
            self.assertFalse(catalog.engines['MB']['ENABLED'])
            self.assertIn('MC',chain.filtered_engines_by_cat('MIDI Tool')['Other'])
            catalog.generate_engines_config_file();catalog.get_engines_by_type()
            self.assertNotIn('MB',catalog.engines)

    def test_legacy_upgrade_preserves_live_adapter_configuration_patches_and_backups(self):
        old=self.legacy();saved=self.snapshot_files()
        result=self.run_install('--check')
        check=json.loads(result.stdout)
        self.assertTrue(check['managedUpgrade']);self.assertFalse(check['upgradeRequiresRollback'])
        self.assertEqual(self.snapshot_files(),saved)
        self.run_install()
        for name in ('editor.token','install.json','processor-1/patch1.json','zynthian_chain_manager.py.original'):
            self.assertEqual((self.data/name).read_bytes(),saved['data/midi-human-looper/'+name][0])
        self.assertEqual(self.adapter.read_bytes(),saved['ui/zyngine/zynthian_engine_mbh.py'][0])
        self.assertEqual((self.data/'pre-oram-upgrade/zynthian_chain_manager.py').read_text(),old)
        self.assertEqual((self.data/'pre-oram-upgrade/installation.json').read_bytes(),saved['data/midi-human-looper/installation.json'][0])
        self.assertNotIn(installer.INFO,self.manager.read_text())
        # Selector uses a stubbed class, so old adapter source stays untouched.
        self.exercise_selector()
        self.run_install('--rollback')
        self.assertEqual(self.manager.read_text(),self.original)
        self.assertEqual(self.catalog.read_text(),self.catalog_original)
        self.assertTrue((self.data/'processor-1/patch1.json').exists())

    def test_explicit_adapter_upgrade_and_adapter_only_rollback_preserve_runtime_and_routes(self):
        self.legacy(); self.run_install()
        before=self.snapshot_files(); old=self.adapter.read_bytes()
        check=self.run_install('--check','--upgrade-adapter')
        self.assertFalse(json.loads(check.stdout)['adapterPreserved'])
        self.assertEqual(self.snapshot_files(),before)
        self.run_install('--upgrade-adapter')
        self.assertEqual(self.adapter.read_bytes(),(ROOT/'zynthian/zynthian_engine_mbh.py').read_bytes())
        for name in ('editor.token','install.json','processor-1/patch1.json'):
            self.assertEqual((self.data/name).read_bytes(),before['data/midi-human-looper/'+name][0])
        upgraded=self.snapshot_files();self.run_install('--upgrade-adapter')
        self.assertEqual(self.snapshot_files(),upgraded)
        self.run_install('--rollback-adapter')
        self.assertEqual(self.adapter.read_bytes(),old)
        self.assertTrue(self.helper.exists());self.exercise_selector()
        self.assertFalse('adapter_previous' in json.loads(self.manifest.read_text()))
        self.run_install('--rollback-adapter',success=False)

    def test_adapter_update_failure_restores_old_bytes_and_manifest(self):
        self.legacy(); self.run_install(); before=self.snapshot_files(); real=installer.atomic
        def fail_once(path,data):
            if path==self.manifest:raise OSError('injected adapter manifest failure')
            return real(path,data)
        with patch.object(installer,'atomic',side_effect=fail_once):
            with self.assertRaises(OSError):installer.main([*self.args,'--upgrade-adapter'])
        self.assertEqual(self.snapshot_files(),before)

    def test_adapter_backup_symlink_rejected_by_check_and_upgrade(self):
        self.legacy();self.run_install()
        (self.data/'adapter-upgrades').symlink_to(self.path/'external',target_is_directory=True)
        before=self.snapshot_files()
        self.run_install('--check','--upgrade-adapter',success=False)
        self.run_install('--upgrade-adapter',success=False)
        self.assertEqual(self.snapshot_files(),before)

    def test_modified_adapter_backup_rejects_rollback_without_mutation(self):
        self.legacy();self.run_install('--upgrade-adapter')
        previous=json.loads(self.manifest.read_text())['adapter_previous']
        backup=self.data/'adapter-upgrades'/(previous['sha256']+'.py')
        backup.write_text('# unexpected modification\n');before=self.snapshot_files()
        self.run_install('--rollback-adapter',success=False)
        self.assertEqual(self.snapshot_files(),before)

    def test_repeated_install_is_byte_and_mode_idempotent(self):
        self.run_install('--lan');before=self.snapshot_files()
        self.run_install('--lan');self.assertEqual(self.snapshot_files(),before)
        self.run_install('--check');self.assertEqual(self.snapshot_files(),before)

    def test_legacy_rollback_still_works(self):
        self.legacy();self.run_install('--rollback')
        self.assertEqual(self.manager.read_text(),self.original)
        self.assertEqual(self.catalog.read_text(),self.catalog_original)
        self.assertFalse(self.adapter.exists())

    def test_unknown_catalog_and_invalid_category_rejected_without_mutation(self):
        for text in ('standalone_engine_info={}\n',self.catalog_original.replace('"Other"','"Unknown"')):
            self.catalog.write_text(text);before=self.snapshot_files()
            self.run_install(success=False);self.assertEqual(self.snapshot_files(),before)

    def test_modified_owned_files_or_backups_rejected_before_upgrade_or_rollback(self):
        self.run_install()
        for target in (self.manager,self.catalog,self.adapter,self.helper,self.data/'zynthian_lv2.py.original'):
            original=target.read_text();target.write_text(original+'# unrelated edit\n')
            before=self.snapshot_files()
            self.run_install(success=False);self.run_install('--rollback',success=False)
            self.assertEqual(self.snapshot_files(),before);target.write_text(original)

    def test_failed_activation_restores_entire_pre_upgrade_state(self):
        self.legacy();before=self.snapshot_files();real=installer.atomic
        def fail_once(path,data):
            if path==self.catalog:
                raise OSError('injected activation failure')
            return real(path,data)
        with patch.object(installer,'atomic',side_effect=fail_once):
            with self.assertRaises(OSError):installer.main(self.args)
        self.assertEqual(self.snapshot_files(),before)

    def test_registration_functions_are_reversible_and_idempotent(self):
        for original,register in ((self.original,installer.registration),(self.catalog_original,installer.catalog_registration)):
            after=register(original)
            self.assertEqual(register(after),after)
            self.assertEqual(register(after,True),original)
        self.assertIn('Other',ast.literal_eval(next(n.value for n in ast.parse(self.catalog_original).body
            if isinstance(n,ast.Assign) and n.targets[0].id=='engine_categories'))['MIDI Tool'])

class NativeChannelInstallation(Installation):
    def setUp(self):
        super().setUp()
        self.autoconnect=self.ui/'zynautoconnect/__init__.py'
        self.autoconnect.parent.mkdir()
        self.autoconnect_original="""def enumerate_ports():
    update = False
    host_usb_connected = is_host_usb_connected()
    return update

def midi_autoconnect():
    required_routes={}
    # Connect and disconnect routes
    for dst, sources in required_routes.items():
        pass

def audio_autoconnect():
    required_routes={}
    # Connect and disconnect routes
    for dst, sources in required_routes.items():
        pass
"""
        self.autoconnect.write_text(self.autoconnect_original)

    def test_native_upgrade_repeat_and_rollback(self):
        self.run_install() # Existing #47/#64 installation.
        retained={p:p.read_bytes() for p in (self.data/'install.json',)}
        self.run_install('--check','--native-channel-routing','--upgrade-adapter')
        self.assertEqual(self.autoconnect.read_text(),self.autoconnect_original)
        self.run_install('--native-channel-routing','--upgrade-adapter')
        first=self.snapshot_files()
        self.run_install('--native-channel-routing','--upgrade-adapter')
        self.assertEqual(self.snapshot_files(),first)
        for path,data in retained.items():self.assertEqual(path.read_bytes(),data)
        self.assertIn(installer.ROUTER_CONFIGURE,self.autoconnect.read_text())
        self.assertEqual(self.autoconnect.read_text().split('def audio_autoconnect():')[1],self.autoconnect_original.split('def audio_autoconnect():')[1])
        self.run_install('--rollback')
        self.assertEqual(self.autoconnect.read_text(),self.autoconnect_original)
        self.assertFalse((self.package/'zynthian_engine_mbh_router.py').exists())

    def test_native_activation_failure_rolls_back_every_owned_file(self):
        self.run_install()
        before=self.snapshot_files();atomic=installer.atomic;failed=False
        def injected(path,data):
            nonlocal failed
            atomic(path,data)
            if path==self.autoconnect and not failed:
                failed=True
                raise OSError('injected native source activation failure')
        with patch.object(installer,'atomic',injected):
            with self.assertRaises(OSError):installer.main([*self.args,'--native-channel-routing','--upgrade-adapter'])
        self.assertTrue(failed)
        self.assertEqual(self.snapshot_files(),before)

    def test_channel_only_rollback_retains_registration_and_runtime(self):
        self.run_install('--native-channel-routing','--upgrade-adapter')
        retained={path:path.read_bytes() for path in (self.manager,self.catalog,self.adapter,self.data/'install.json')}
        self.run_install('--rollback-channel-routing')
        for path,data in retained.items():self.assertEqual(path.read_bytes(),data)
        self.assertEqual(self.autoconnect.read_text(),self.autoconnect_original)
        self.assertFalse((self.package/'zynthian_engine_mbh_router.py').exists())
        self.run_install('--native-channel-routing')
        self.run_install('--check')

    def test_native_fresh_and_unsupported_source_no_partial_activation(self):
        self.run_install('--native-channel-routing')
        self.run_install('--rollback')
        self.autoconnect.write_text('unsupported = True\n')
        before=self.snapshot_files()
        self.run_install('--native-channel-routing',success=False)
        self.assertEqual(self.snapshot_files(),before)

if __name__=='__main__':unittest.main()

import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('installer',ROOT/'zynthian/install.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class Installation(unittest.TestCase):
    def test_registration_idempotence_and_rollback(self):
        original='from zyngine import *\nengine2class = {\n}\nclass Chain:\n    def config(self, eng_info):\n        cls.engine_info = eng_info\n        if True: pass\n        elif eng_code in ("SF", "PD"):\n            pass\n'
        installed=module.registration(original)
        self.assertEqual(module.registration(installed),installed)
        self.assertEqual(module.registration(installed,True),original)
        self.assertIn('"TYPE":"MIDI Tool"',installed)
    def test_unknown_ui_rejected_without_mutation(self):
        for text in ('engine2class={}\n','from zyngine import *\nfrom zyngine import *\n'):
            with self.assertRaises(ValueError):module.registration(text)
    def test_actual_install_repeat_and_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);ui=path/'ui';(ui/'zyngine').mkdir(parents=True)
            manager=ui/'zyngine/zynthian_chain_manager.py'
            original='from zyngine import *\nengine2class = {\n}\nclass Chain:\n    def config(self, eng_info):\n        cls.engine_info = eng_info\n        if True: pass\n        elif eng_code in ("SF", "PD"):\n            pass\n'
            manager.write_text(original)
            command=[sys.executable,str(ROOT/'zynthian/install.py'),'--ui-dir',str(ui),'--data-dir',str(path/'data'),'--binary',sys.executable]
            subprocess.run(command+['--lan'],check=True,capture_output=True)
            config=path/'data/midi-human-looper/install.json';saved=config.read_text()
            token=path/'data/midi-human-looper/editor.token'
            self.assertEqual(token.stat().st_mode&0o777,0o600)
            subprocess.run(command,check=True,capture_output=True);self.assertEqual(config.read_text(),saved)
            manager.write_text(manager.read_text()+'# unrelated change\n')
            self.assertNotEqual(subprocess.run(command+['--rollback'],capture_output=True).returncode,0)
            manager.write_text(manager.read_text().replace('# unrelated change\n',''))
            subprocess.run(command+['--rollback'],check=True,capture_output=True)
            self.assertEqual(manager.read_text(),original)
            self.assertFalse((ui/'zyngine/zynthian_engine_mbh.py').exists());self.assertTrue(token.exists())
if __name__=='__main__':unittest.main()

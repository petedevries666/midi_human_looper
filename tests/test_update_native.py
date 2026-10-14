"""Production adapter actions with pinned Oram confirm/info surface; no device."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'zynthian/update'))
import backend
package=types.ModuleType('zyngine');base=types.ModuleType('zyngine.zynthian_engine');base.zynthian_engine=object
sys.modules['zyngine']=package;sys.modules[base.__name__]=base
spec=importlib.util.spec_from_file_location('mbmf_update_adapter',ROOT/'zynthian/zynthian_engine_mbh.py');adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
class NativeUpdate(unittest.TestCase):
    def setUp(self):
        self.engine=object.__new__(adapter.zynthian_engine_mbh);self.engine.root=ROOT
        self.messages=[];self.confirmations=[]
        gui=types.SimpleNamespace(show_info=lambda message:self.messages.append(message),show_confirm=lambda text,callback:self.confirmations.append((text,callback)))
        zyngui=types.ModuleType('zyngui');zyngui.zynthian_gui_config=types.SimpleNamespace(zyngui=gui)
        self.modules=patch.dict(sys.modules,{'zyngui':zyngui});self.modules.start();self.addCleanup(self.modules.stop)
        self.calls=[];self.status=dict(installed='b'*40,available=dict(name='reviewed',revision='a'*40,changes='changes'),progress=dict(phase='ready',message='checked'),rollbackAvailable=True)
        def client(action,**fields):self.calls.append((action,fields));return self.status if action=='status' else dict(accepted=True)
        self.client=patch.object(backend,'client',side_effect=client);self.client.start();self.addCleanup(self.client.stop)
    def test_native_check_status_and_explicit_install_confirmation(self):
        self.engine.update_control('check');self.assertEqual(self.calls[-1],('check',{'native':True}))
        self.engine.update_control('status');self.assertIn('AVAILABLE reviewed',self.messages[-1]);self.assertIn('changes',self.messages[-1])
        self.engine.update_control('install');self.assertEqual(self.calls[-1][0],'status');self.assertEqual(len(self.confirmations),1)
        self.confirmations[0][1]();self.assertEqual(self.calls[-1],('install',dict(native=True,confirm=True,revision='a'*40)))
    def test_rollback_confirmation_and_no_candidate_refusal(self):
        self.engine.update_control('rollback');self.assertEqual(self.calls[-1][0],'status')
        self.confirmations[0][1]();self.assertEqual(self.calls[-1][0],'rollback')
        self.status['available']=None;self.engine.update_control('install');self.assertIn('CHECK UPDATE first',self.messages[-1])
    def test_trigger_reset_no_restore_side_effect_and_no_engine_command(self):
        control=types.SimpleNamespace(value=1,graph_path='update_status')
        self.engine.send_controller_value(control);self.assertEqual(control.value,0)
        count=len(self.calls);self.engine.send_controller_value(control);self.assertEqual(len(self.calls),count)
        for name,options in self.engine._ctrls:
            if name.startswith('update_'):self.assertFalse(options['midi_autolearn']);self.assertTrue(options['is_trigger'])
if __name__=='__main__':unittest.main()

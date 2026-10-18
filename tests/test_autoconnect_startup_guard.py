"""The native host must release its graph mutex while engines start or fail."""
import ast,importlib.util,pathlib,types,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('mbmf_install',ROOT/'zynthian/install.py')
install=importlib.util.module_from_spec(spec);spec.loader.exec_module(install)
SOURCE="""def midi_autoconnect():
    if not acquire_lock():
        return
    global deferred_midi_connect
    deferred_midi_connect = False
    jclient.get_ports()
    release_lock()
"""
class StartupGuard(unittest.TestCase):
 def test_deferred_start_and_exception_release(self):
  events=[]
  class Jack:
   def get_ports(self):raise RuntimeError('injected graph failure')
  scope=dict(acquire_lock=lambda:True,release_lock=lambda:events.append('release'),chain_manager=types.SimpleNamespace(processors={1:types.SimpleNamespace(engine=None)}),jclient=Jack())
  guarded=install.autoconnect_startup_guard(SOURCE);self.assertEqual(install.autoconnect_startup_guard(guarded),guarded)
  self.assertEqual(ast.dump(ast.parse(install.autoconnect_startup_guard(guarded,True))),ast.dump(ast.parse(SOURCE)))
  exec(guarded,scope);scope['midi_autoconnect']();self.assertEqual(events,['release']);self.assertTrue(scope['deferred_midi_connect'])
  events.clear();scope['chain_manager'].processors[1].engine=object()
  with self.assertRaises(RuntimeError):scope['midi_autoconnect']()
  self.assertEqual(events,['release'])
if __name__=='__main__':unittest.main()

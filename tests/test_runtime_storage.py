import json,os,pathlib,socket,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'headless'))
from runtime_storage import patch_library,recover_socket
from switch_presets import Store,default_library

class Storage(unittest.TestCase):
 def test_selected_road_slot_survives_server_restart(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=default_library();data['activeSlot']=2
   (pathlib.Path(tmp)/'smart-switch-presets.json').write_text(json.dumps(data))
   store=Store(tmp,None);store.recover();self.assertEqual(store.active_slot,2)
 def test_processor_recreation_preserves_patch_one_and_road(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);old=root/'processor-4';old.mkdir()
   for name,body in {'patch1.json':'fear','patch2.json':'road','patch-names.json':'{"1":"FEAR","2":"road"}','smart-switch-presets.json':'{}'}.items():(old/name).write_text(body)
   (old/'editor.token').write_text('private');(old/'engine.log').write_text('runtime')
   library=patch_library(old);self.assertEqual((library/'patch2.json').read_text(),'road')
   self.assertFalse((library/'editor.token').exists());self.assertFalse((library/'engine.log').exists())
   newer=root/'processor-9';newer.mkdir();(newer/'patch2.json').write_text('empty replacement')
   self.assertEqual(patch_library(newer),library);self.assertEqual((library/'patch1.json').read_text(),'fear');self.assertEqual((library/'patch2.json').read_text(),'road')
   self.assertEqual((old/'patch2.json').read_text(),'road')
 def test_failed_migration_leaves_originals_and_no_partial_library(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=pathlib.Path(tmp)/'processor-2';data.mkdir();(data/'patch2.json').write_text('road');(data/'smart-switch-preset-transaction.json').write_text('{}')
   with self.assertRaises(RuntimeError):patch_library(data)
   self.assertFalse((data.parent/'patch-library').exists());self.assertEqual((data/'patch2.json').read_text(),'road')
 def test_existing_library_can_be_pinned_without_copying_live_files(self):
  with tempfile.TemporaryDirectory() as tmp:
   old=pathlib.Path(tmp)/'processor-4';old.mkdir();(old/'patch2.json').write_text('road')
   self.assertEqual(patch_library(old,str(old)),old)
   self.assertEqual(patch_library(old.parent/'processor-9',str(old)),old)
   self.assertEqual((old/'patch2.json').read_text(),'road')
 @unittest.skipUnless(pathlib.Path('/proc/net/unix').is_file(),'Linux kernel UNIX socket inventory required')
 def test_abandoned_socket_recovered_but_bound_owner_never_removed(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'control.sock'
   with socket.socket(socket.AF_UNIX) as owner:
    owner.bind(str(path))
    with self.assertRaises(RuntimeError):recover_socket(path)
    self.assertTrue(path.is_socket())
    owner.listen()
    with self.assertRaises(RuntimeError):recover_socket(path)
   self.assertTrue(path.exists());recover_socket(path);self.assertFalse(path.exists());recover_socket(path)
 def test_file_and_symlink_are_never_removed(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'control.sock';path.write_text('keep')
   with self.assertRaises(RuntimeError):recover_socket(path)
   self.assertEqual(path.read_text(),'keep')
   if os.name!='nt':
    link=path.parent/'host.sock';link.symlink_to(path)
    with self.assertRaises(RuntimeError):recover_socket(link)
    self.assertTrue(link.is_symlink())

if __name__=='__main__':unittest.main(verbosity=2)

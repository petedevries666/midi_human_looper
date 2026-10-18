import pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'headless'))
import patch_names

class Names(unittest.TestCase):
 def test_persistence_conflicts_and_bad_input_preserve_existing_label(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp)
   self.assertEqual(patch_names.rename(root,1,'REFRAIN été',''),'REFRAIN été')
   for slot,name,expected in [(1,'Lost','old'),(True,'bad',''),(1,'x'*49,'REFRAIN été'),(1,'line\nbreak','REFRAIN été')]:
    with self.assertRaises(ValueError):patch_names.rename(root,slot,name,expected)
   self.assertEqual(patch_names.read(root),{'1':'REFRAIN été'})
   self.assertFalse((root/'patch1.json').exists())
   patch_names.rename(root,1,'Couplet','REFRAIN été')
   self.assertEqual(patch_names.read(root)['1'],'Couplet')

if __name__=='__main__':unittest.main()

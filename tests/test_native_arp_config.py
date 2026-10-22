import copy,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'headless'))
from native_arp_config import decode
from server import validate_patch_extensions
class Codec(unittest.TestCase):
 def test_exact_version_and_identity_validation(self):
  good={'version':1,'configuration':[1,2,7,4,1,99,2,0]}
  self.assertEqual(decode(good),[(7,4,1),(99,2,0)])
  for index,value in ((0,True),(1,9),(2,0),(3,0),(3,5),(4,2),(5,7),(6,1.5)):
   bad=copy.deepcopy(good);bad['configuration'][index]=value
   with self.assertRaises(ValueError):decode(bad)
  for version in (True,2):
   with self.assertRaises(ValueError):decode(dict(good,version=version))
  with self.assertRaises(ValueError):decode(dict(good,extra=1))
 def test_legacy_rejects_extension_without_discarding_it(self):
  p=dict(format='MIDI_HUMAN_LOOPER_PATCH',schema=7,nativeArp={'version':1,'configuration':[1,0]})
  before=copy.deepcopy(p)
  with self.assertRaises(ValueError):validate_patch_extensions(p)
  self.assertEqual(p,before)

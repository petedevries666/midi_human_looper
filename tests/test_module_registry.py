import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from registry import Registry,REGISTRY
class RegistryTests(unittest.TestCase):
 def test_normalized_ranges_and_roundtrip(self):
  for id,p in REGISTRY.parameters.items():
   for v in (p['min'],p['default'],p['max']):self.assertAlmostEqual(REGISTRY.scale(id,REGISTRY.normalize(id,v)),v)
  self.assertEqual(REGISTRY.scale('range_mode',.5),2)
  self.assertEqual(REGISTRY.scale('transpose',.5),0)
 def test_extension_registration_without_page(self):
  registry=Registry(REGISTRY.document());module=dict(registry.modules['velocity'],typeId='example_velocity',engineType=99,label='EXAMPLE VELOCITY')
  registry.register(module);self.assertEqual(registry.engine_types[99],'example_velocity');self.assertEqual(registry.modules['example_velocity']['parameters'],['velocity'])
  with self.assertRaises(ValueError):registry.register(module)
 def test_reject_unknown_parameter_and_invalid_metadata(self):
  registry=Registry(REGISTRY.document())
  with self.assertRaises(ValueError):registry.register(dict(registry.modules['velocity'],typeId='bad',engineType=98,parameters=['missing']))
  with self.assertRaises(ValueError):Registry(dict(REGISTRY.document(),contractVersion=99))
if __name__=='__main__':unittest.main()

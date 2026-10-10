import sys,json,unittest,tempfile,subprocess,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from registry import Registry,REGISTRY
class RegistryTests(unittest.TestCase):
 def test_normalized_ranges_and_roundtrip(self):
  for id,p in REGISTRY.parameters.items():
   for v in (p['min'],p['default'],p['max']):self.assertAlmostEqual(REGISTRY.scale(id,REGISTRY.normalize(id,v)),v)
  self.assertEqual(REGISTRY.scale('range_mode',.5),2)
  self.assertEqual(REGISTRY.scale('transpose',.5),0)
 def test_native_identity_registry_matches_descriptors(self):
  root=Path(__file__).resolve().parents[1]
  statements=[]
  for module in REGISTRY.modules.values():
   type_=module['engineType']
   if not 1<=type_<=6:continue
   statements.append(f'static_assert(performance::parameterCount({type_})=={len(module["parameters"])},"parameter count");')
   for row,id in enumerate(module['parameters']):
    p=REGISTRY.parameters[id]
    statements.append(f'static_assert(performance::parameterKind({type_},{row})=={p["engineKind"]},"stable identity");')
    discrete=p['valueType'] in ('enum','toggle') or p['engineKind']==13
    statements.append(f'static_assert(performance::discrete({p["engineKind"]})=={str(discrete).lower()},"switch policy");')
  with tempfile.TemporaryDirectory() as directory:
   source=Path(directory)/'registry.cpp';source.write_text('#include "headless/parameter_registry.hpp"\n'+'\n'.join(statements)+'\nint main(){}\n')
   subprocess.run([os.environ.get('CXX','c++'),'-std=c++11','-I',str(root),str(source),'-o',str(Path(directory)/'registry')],check=True,capture_output=True)
 def test_extension_registration_without_page(self):
  registry=Registry(REGISTRY.document());module=dict(registry.modules['velocity'],typeId='example_velocity',engineType=99,label='EXAMPLE VELOCITY')
  registry.register(module);self.assertEqual(registry.engine_types[99],'example_velocity');self.assertEqual(registry.modules['example_velocity']['parameters'],['velocity'])
  with self.assertRaises(ValueError):registry.register(module)
 def test_reject_unknown_parameter_and_invalid_metadata(self):
  registry=Registry(REGISTRY.document())
  with self.assertRaises(ValueError):registry.register(dict(registry.modules['velocity'],typeId='bad',engineType=98,parameters=['missing']))
  with self.assertRaises(ValueError):Registry(dict(REGISTRY.document(),contractVersion=99))
if __name__=='__main__':unittest.main()

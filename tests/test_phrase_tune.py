"""TUNE compatibility, bounds and lossless configuration persistence."""
import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
import conductor

class PhraseTune(unittest.TestCase):
    def model(self):
        m=conductor.migrate({'schema':8})
        source=m['sources'][0]
        uid=lambda n:f'11111111-1111-1111-1111-{n:012d}'
        b=dict(id=uid(3),type='PHRASE',sourceId=source['id'],overrides={})
        m['switches']=[dict(switchId=1,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',steps=[dict(id=uid(1),transition='INHERIT',layers=[dict(id=uid(2),block=b)])])]
        return m,b
    def test_old_documents_remain_unchanged(self):
        m,_=self.model();before=copy.deepcopy(m)
        self.assertEqual(conductor.decode(conductor.encode(m)),before)
    def test_source_and_independent_local_override_roundtrip(self):
        for value in (-24,0,24):
            m,b=self.model();m['sources'][0]['tune']=value
            b['overrides']['phrase_tune']=dict(mode='OVERRIDE',value=-value)
            self.assertEqual(conductor.decode(conductor.encode(m)),m)
            b['overrides']['phrase_tune']=dict(mode='INHERIT')
            self.assertEqual(conductor.decode(conductor.encode(m)),m)
    def test_reject_invalid_or_fractional_semitones(self):
        for value in (-25,25,.5,True,'12'):
            for local in (False,True):
                m,b=self.model()
                if local:b['overrides']['phrase_tune']=dict(mode='OVERRIDE',value=value)
                else:m['sources'][0]['tune']=value
                with self.assertRaises(ValueError):conductor.validate(m)

if __name__=='__main__':unittest.main()

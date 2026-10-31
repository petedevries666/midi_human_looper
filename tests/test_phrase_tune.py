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
    def test_bass_policies_identity_and_bounds(self):
        for mode in (0,1,2):
            m,_=self.model();m['bassPolicies']=[dict(instrumentId=16777215,moduleId=9,mode=mode)]
            self.assertEqual(conductor.decode(conductor.encode(m)),m)
        invalid=[None,{},[dict(instrumentId=1,moduleId=2,mode=3)],[dict(instrumentId=0,moduleId=2,mode=1)],[dict(instrumentId=1,moduleId=2,mode=True)],[dict(instrumentId=1,moduleId=2,mode=1,extra=0)],[dict(instrumentId=1,moduleId=2,mode=1)]*2]
        for policies in invalid:
            m,_=self.model();m['bassPolicies']=policies
            with self.assertRaises(ValueError):conductor.validate(m)
    def test_gesture_phrase_modes_roundtrip(self):
        for mode in ('GATE','RETRIGGER','TOGGLE'):
            m,b=self.model();m['sources'][0]['playMode']=mode;b['overrides']['playMode']=dict(mode='OVERRIDE',value=mode)
            self.assertEqual(conductor.decode(conductor.encode(m)),m)
        for invalid in ('ONCE','OTHER',True,None,3):
            m,_=self.model();m['sources'][0]['playMode']=invalid
            with self.assertRaises(ValueError):conductor.validate(m)
    def test_phrase_direction_roundtrip(self):
        for direction in ('FORWARD','REVERSE','PING_PONG'):
            m,b=self.model();m['sources'][0]['direction']=direction;b['overrides']['direction']=dict(mode='OVERRIDE',value=direction)
            self.assertEqual(conductor.decode(conductor.encode(m)),m)
        for invalid in ('BACKWARDS',2,None,True):
            m,b=self.model();m['sources'][0]['direction']=invalid
            with self.assertRaises(ValueError):conductor.validate(m)
    def test_phrase_randomization_roundtrip_and_bounds(self):
        jitter=dict(amount=75,mode='FREE',redraw='CYCLE');pitch=dict(enabled=1,low=-12,high=12,notes=145)
        m,b=self.model();m['sources'][0].update(startJitter=jitter,randomPitch=pitch)
        b['overrides'].update(startJitter=dict(mode='OVERRIDE',value=jitter),randomPitch=dict(mode='OVERRIDE',value=pitch))
        step=m['switches'][0]['steps'][0];step['layerSelection']='RANDOM_NO_REPEAT';step['layers'][0]['selectionRole']='FIXED'
        self.assertEqual(conductor.decode(conductor.encode(m)),m)
        for key,value in [('amount',101),('amount',-1),('amount',True),('mode','UNKNOWN'),('redraw','ALWAYS')]:
            bad=copy.deepcopy(m);bad['sources'][0]['startJitter'][key]=value
            with self.assertRaises(ValueError):conductor.validate(bad)
        for key,value in [('low',-25),('low',13),('high',25),('notes',4096),('notes',-1),('enabled',True)]:
            bad=copy.deepcopy(m);bad['sources'][0]['randomPitch'][key]=value
            with self.assertRaises(ValueError):conductor.validate(bad)
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
    def test_repeat_default_bounds_and_roundtrip(self):
        for value in (1,3,999):
            m,_=self.model();m['switches'][0]['steps'][0]['repeat']=value
            self.assertEqual(conductor.decode(conductor.encode(m)),m)
        for value in (0,-1,1000,1.5,True,'3'):
            m,_=self.model();m['switches'][0]['steps'][0]['repeat']=value
            with self.assertRaises(ValueError):conductor.validate(m)

    def test_rate_source_and_override_range_roundtrip(self):
        for value in (.1,.5,1,1.25,16):
            m,b=self.model();m['sources'][0]['rate']=value;b['overrides']['phrase_rate']=dict(mode='OVERRIDE',value=value)
            self.assertEqual(conductor.decode(conductor.encode(m)),m)
            b['overrides']['phrase_rate']=dict(mode='INHERIT')
            self.assertEqual(conductor.decode(conductor.encode(m)),m)
        for value in (0,.09,16.01,float('nan'),float('inf'),True,'2'):
            for local in (False,True):
                m,b=self.model()
                if local:b['overrides']['phrase_rate']=dict(mode='OVERRIDE',value=value)
                else:m['sources'][0]['rate']=value
                with self.assertRaises(ValueError):conductor.validate(m)

    def test_reject_invalid_or_fractional_semitones(self):
        for value in (-25,25,.5,True,'12'):
            for local in (False,True):
                m,b=self.model()
                if local:b['overrides']['phrase_tune']=dict(mode='OVERRIDE',value=value)
                else:m['sources'][0]['tune']=value
                with self.assertRaises(ValueError):conductor.validate(m)

if __name__=='__main__':unittest.main()

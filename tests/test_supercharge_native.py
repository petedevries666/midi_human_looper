#!/usr/bin/env python3
"""Native RELEASE/SUPERCHARGE regressions; private worker, no JACK or live Pi data."""
import copy,time,unittest
from test_conductor_execution_native import Execution
from test_conductor_persistence import step,block
from test_movement_persistence import movement
import conductor
ov=lambda v:dict(mode='OVERRIDE',value=v)
class Supercharge(Execution):
 def setUp(self):
  super().setUp();self.model=conductor.with_mute_groups(self.model);self.model['movements']=[]
  for source in self.model['sources']:source['muteGroup']=0
  self.sequence=self.model['switches'][0];self.sequence['steps']=[]
 def edge(self,down):self.command('switch_test_edge',switchId=1,edge='press' if down else 'release')
 def cursor(self):return self.call()['switches'][0]['conductor']['step']
 def phrase(self,n=0):return self.model['sources'][n]['id']
 def add_movement(self,trig='SUPERCHARGE_RELEASE'):
  m=movement();m.update(target=dict(type='CC',channel=16,number=119),points=[[0,.2,-.5],[1,.8,0]],retrigger='DIRECT');self.model['movements'].append(m);b=block(m['id'],'MOVEMENT');b['overrides']['trigger']=ov(trig);return m,b
 def charge(self,s,bindings=None):s['supercharge']=dict(thresholdMs=50,fullMs=100,bindings=bindings or [])
 def test_release_current_and_advance(self):
  m,b=self.add_movement('RELEASE');self.sequence['steps']=[step([block(self.phrase()),b])];self.commit();self.edge(True);self.assertEqual(self.cursor(),1);self.edge(False);self.assertEqual(self.cursor(),1);self.assertEqual(self.call()['movements']['active'],1)
  self.command('panic');self.sequence['advance']='RELEASE';self.sequence['steps']=[step([block(self.phrase())]),step([block(self.phrase(1))])];self.commit();self.edge(True);self.assertEqual(self.cursor(),0);self.edge(False);self.assertEqual(self.cursor(),1);self.edge(True);self.assertEqual(self.cursor(),1);self.edge(False);self.edge(False);self.assertEqual(self.cursor(),2)
 def test_charge_duration_factor_and_short_exclusion(self):
  self.sequence['advance']='RELEASE';m,b=self.add_movement();other=movement();other['target']['number']=118;self.model['movements'].append(other);short=block(other['id'],'MOVEMENT');short['overrides']['trigger']=ov('RELEASE');s=step([block(self.phrase()),b,short]);self.sequence['steps']=[s];self.charge(s,[dict(blockId=b['id'],parameter='movementDuration',**{'from':.1,'to':2,'factor':16}),dict(blockId=b['id'],parameter='movementAmplitude',**{'from':0,'to':1,'factor':16})]);self.commit();self.edge(True);time.sleep(.15);self.edge(False);time.sleep(.25);running=self.call()['movements']['running'];self.assertEqual([v['id'] for v in running],[m['id']]);self.assertLess(running[0]['progress'],.4)
  state=self.call();patch=self.c.request(op=4,revision=state['revision'],session=state['engineSessionId']);self.assertEqual(conductor.decode(patch['conductor']),self.model)
 def test_registered_parameter_bounds_and_quantization(self):
  self.sequence['advance']='RELEASE';s=step([block(self.phrase())]);self.sequence['steps']=[s];self.charge(s,[dict(target=dict(type='PARAMETER',instrumentId=1,moduleId=0,kind=1),parameter='parameter',**{'from':0,'to':31,'factor':16})]);self.commit();self.edge(True);time.sleep(.15);self.edge(False);self.wait_for(lambda:self.call()['instruments'][0]['level']==31,'quantized level')
  for field,value in [('factor',17),('factor',float('nan')),('to',128)]:
   invalid=copy.deepcopy(self.model);invalid['switches'][0]['steps'][0]['supercharge']['bindings'][0][field]=value
   with self.assertRaises(ValueError):conductor.validate(invalid)
 def test_midi_charge_and_panic_cancellation(self):
  self.sequence['advance']='RELEASE';s=step([block(self.phrase())]);self.sequence['steps']=[s];self.charge(s);self.commit();self.command('midi',channel=1,note=110,value=127);time.sleep(.06);self.assertTrue(self.call()['switches'][0]['supercharge']['active']);self.assertEqual(self.cursor(),0);self.command('midi',channel=1,note=110,value=0);self.assertEqual(self.cursor(),1)
  self.command('panic');self.commit();self.edge(True);self.command('panic');self.edge(False);self.assertEqual(self.cursor(),0);self.assertFalse(self.call()['instances'])
 def test_release_after_long_press_without_charge(self):
  m,b=self.add_movement('RELEASE');self.sequence['steps']=[step([block(self.phrase()),b])];self.commit();self.edge(True);time.sleep(.7);self.edge(False);self.assertEqual(self.call()['movements']['active'],1)
 def test_charge_waits_for_exact_master_boundary(self):
  state=self.call();self.c.request(op=35,target=0,arg=1,phrase=dict(lengthSeconds=.6,events=[[0,144,70,100],[.55,128,70,0]]),revision=state['revision'],session=state['engineSessionId']);self.sequence.update(advance='RELEASE',transition='END_OF_PHRASE');p=block(self.phrase());p['overrides']['playMode']=ov('ONCE');m,b=self.add_movement();s=step([block(self.phrase(1)),b]);self.charge(s,[dict(blockId=b['id'],parameter='movementDuration',**{'from':.1,'to':2,'factor':2})]);self.sequence['steps']=[step([p]),s];self.commit();self.edge(True);self.edge(False);self.edge(True);time.sleep(.15);self.edge(False);self.assertEqual(self.call()['switches'][0]['conductor']['queuedStep'],2);self.wait_for(lambda:self.cursor()==2 and self.call()['movements']['active']==1,'charged boundary admission');self.assertLess(self.call()['movements']['running'][0]['progress'],.4)
 def test_patch_charge_defaults_and_step_overrides(self):
  self.sequence['advance']='RELEASE';self.model['supercharge']=dict(thresholdMs=50,fullMs=100);m,b=self.add_movement();s=step([block(self.phrase()),b]);self.sequence['steps']=[s];s['supercharge']=dict(bindings=[dict(blockId=b['id'],parameter='movementDuration',**{'from':.1,'to':1,'factor':1})]);self.commit();self.edge(True);time.sleep(.15);self.edge(False);time.sleep(.3);self.assertEqual(self.call()['movements']['active'],1,'inherited full charge duration');self.command('panic')
  s['supercharge']['fullMs']=5000;self.commit();self.edge(True);time.sleep(.15);self.edge(False);time.sleep(.3);self.assertEqual(self.call()['movements']['active'],0,'local full charge override');self.command('panic')
  s['supercharge']['thresholdMs']=1000;self.commit();self.edge(True);time.sleep(.15);self.edge(False);self.assertEqual(self.call()['movements']['active'],0,'local threshold excludes charged release');self.patch('save');self.patch('load');state=self.call();patch=self.c.request(op=4,revision=state['revision'],session=state['engineSessionId']);self.assertEqual(conductor.decode(patch['conductor']),self.model)
 def test_bent_cycles_persist_and_stop(self):
  m,b=self.add_movement('PRESS');self.sequence['steps']=[step([None,b])]
  for mode in ('LOOP','PING_PONG'):
   self.command('panic');m.update(cycleMode=mode,duration=.2);self.commit();self.command('movement_preview',movementId=m['id']);time.sleep(.6);self.assertEqual(self.call()['movements']['active'],1);self.command('movement_stop',movementId=m['id']);self.assertEqual(self.call()['movements']['active'],0);self.patch('save');self.patch('load');state=self.call();patch=self.c.request(op=4,revision=state['revision'],session=state['engineSessionId']);self.assertEqual(conductor.decode(patch['conductor'])['movements'][0],m)
if __name__=='__main__':unittest.main()

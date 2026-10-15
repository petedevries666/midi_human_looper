#!/usr/bin/env python3
"""Native producer/actual DSP, no UI-clock gesture classification."""
import copy,json,sys,time,unittest
from test_conductor_execution_native import Execution
from test_conductor_persistence import step,block
from test_movement_persistence import movement
class Gestures(Execution):
    def setUp(self):
        super().setUp()
        settings=self.call()['switches'][0]['settings'];settings[8]=250
        self.command('switch_commit',switchId=1,settings=settings,sequence=[],name='PRESS HOLD')
        self.model['switches'][0]['steps']=[step([block(self.model['sources'][0]['id']),block(self.model['sources'][1]['id'])])]
        self.model['switches'][0]['steps'][0]['layers'][1]['block']['overrides']['trigger']=dict(mode='OVERRIDE',value='HOLD')
    def down(self):self.command('midi',channel=1,note=110,value=127)
    def up(self):self.command('midi',channel=1,note=110,value=0)
    def test_short_press_long_hold_and_load_stopped(self):
        self.commit();self.down();self.assertEqual([i['phraseId'] for i in self.call()['instances']],[1])
        self.up();time.sleep(.3);self.assertEqual([i['phraseId'] for i in self.call()['instances']],[1])
        self.command('panic');self.down()
        self.wait_for(lambda:len(self.call()['instances'])==2,'native HOLD threshold')
        state=self.call();self.assertEqual([i['phraseId'] for i in state['instances']],[1,2]);ids=[i['id'] for i in state['instances']]
        self.up();time.sleep(.1);self.assertEqual([i['id'] for i in self.call()['instances']],ids,'ONE_SHOT layers survive RELEASE')
        self.command('panic');self.patch('save');self.patch('load');time.sleep(.3)
        self.assertFalse(self.call()['instances'],'LOAD cannot inherit pending gesture')
        state=self.call();p=self.c.request(op=4,revision=state['revision'],session=state['engineSessionId'])
        self.assertEqual(p['conductor'],__import__('conductor').encode(self.model))
    def test_test_hold_same_step_and_movement_one_shot(self):
        m=movement();m.update(duration=1,target=dict(type='CC',channel=3,number=74))
        self.model.update(version=2,ccRate=25,movements=[m])
        held=block(m['id'],'MOVEMENT');held['overrides']['trigger']=dict(mode='OVERRIDE',value='HOLD')
        self.model['switches'][0]['steps'][0]['layers'].append(dict(id=__import__('conductor').uuid.uuid4().__str__(),block=held))
        self.commit();self.command('test',switchId=1)
        self.assertEqual(len(self.call()['instances']),1);self.assertEqual(self.call()['movements']['active'],0)
        self.command('test',switchId=1,gesture='hold');state=self.call()
        self.assertEqual(len(state['instances']),2);self.assertEqual(state['movements']['active'],1)
        self.assertEqual(state['switches'][0]['conductor']['step'],1)
        self.command('conductor_release',switchId=1);self.assertEqual(self.call()['movements']['active'],1)
        self.command('test',switchId=1,gesture='hold');self.assertEqual(len(self.call()['instances']),2)
        self.wait_for(lambda:self.call()['movements']['active']==0,'HOLD movement natural completion')
        self.assertEqual(len(self.call()['instances']),2)
    def test_stop_panic_and_patch_replacement_cancel_pending(self):
        self.commit()
        for action in ('panic','chain_stop'):
            self.down();self.command(action);time.sleep(.3)
            self.assertFalse(self.call()['instances'],action+' must cancel pending HOLD')
            self.up()
        self.down();self.up();self.command('panic');self.commit();time.sleep(.3)
        self.assertFalse(self.call()['instances'])
if __name__=='__main__':
    suite=unittest.TestSuite(Gestures(n) for n in ('test_short_press_long_hold_and_load_stopped','test_test_hold_same_step_and_movement_one_shot','test_stop_panic_and_patch_replacement_cancel_pending'))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

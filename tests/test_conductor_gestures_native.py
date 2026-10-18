#!/usr/bin/env python3
"""Native producer/actual DSP, no UI-clock gesture classification."""
import copy,json,sys,time,unittest
from test_conductor_execution_native import Execution
from test_conductor_persistence import step,block,uid
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
        self.model['switches'][0]['steps'][0]['layers'].append(dict(id=uid(),block=held))
        self.commit();self.command('test',switchId=1)
        self.assertEqual(len(self.call()['instances']),1);self.assertEqual(self.call()['movements']['active'],0)
        self.command('test',switchId=1,gesture='hold');state=self.call()
        self.assertEqual(len(state['instances']),3);self.assertEqual(state['movements']['active'],1)
        self.assertEqual(state['switches'][0]['conductor']['step'],1)
        self.command('conductor_release',switchId=1);self.assertEqual(self.call()['movements']['active'],1)
        self.command('test',switchId=1,gesture='hold');self.assertEqual(len(self.call()['instances']),5,'A new TEST HOLD includes its PRESS and consumes one new step')
        self.wait_for(lambda:self.call()['movements']['active']==0,'HOLD movement natural completion')
        self.assertEqual(len(self.call()['instances']),5)
    def test_new_hold_preview_after_tap_advances_to_next_step(self):
        m=movement();m.update(duration=3,target=dict(type='CC',channel=1,number=5))
        self.model.update(version=2,ccRate=25,movements=[m])
        def held():
            item=block(m['id'],'MOVEMENT');item['overrides']['trigger']=dict(mode='OVERRIDE',value='HOLD');return item
        self.model['switches'][0]['steps']=[step([block(self.model['sources'][i]['id']),held()]) for i in range(2)]
        self.commit();self.command('test',switchId=1);self.assertEqual(self.call()['switches'][0]['conductor']['step'],1)
        self.command('test',switchId=1,gesture='hold');s=self.call()
        self.assertEqual(s['switches'][0]['conductor']['step'],2)
        self.assertEqual({v['phraseId'] for v in s['instances']},{1,2});self.assertEqual(s['movements']['active'],1)
        self.command('test',switchId=1,gesture='hold');s=self.call()
        self.assertEqual(s['switches'][0]['conductor']['step'],1);self.assertEqual(len(s['instances']),3)
    def test_disabled_unassigned_hold_preview_includes_press(self):
        m=movement();m.update(duration=2,target=dict(type='CC',channel=1,number=5))
        self.model.update(version=2,ccRate=25,movements=[m])
        held=block(m['id'],'MOVEMENT');held['overrides']['trigger']=dict(mode='OVERRIDE',value='HOLD')
        self.model['switches'][0]['steps'][0]['layers'].append(dict(id=uid(),block=held))
        settings=list(self.call()['switches'][0]['settings']);settings[0]=settings[1]=0
        self.command('switch_commit',switchId=1,settings=settings,sequence=[],name='UNASSIGNED')
        self.commit();self.command('test',switchId=1,gesture='hold');s=self.call()
        self.assertFalse(s['switches'][0]['enabled']);self.assertEqual(s['switches'][0]['kind'],0)
        self.assertEqual(len(s['instances']),2);self.assertEqual(s['movements']['active'],1)
        self.assertEqual(s['switches'][0]['conductor']['step'],1)
    def test_stop_panic_and_patch_replacement_cancel_pending(self):
        self.commit()
        for action in ('panic','chain_stop'):
            self.down();self.command(action);time.sleep(.3)
            self.assertFalse(self.call()['instances'],action+' must cancel pending HOLD')
            self.up()
        self.down();self.up();self.command('panic');self.commit();time.sleep(.3)
        self.assertFalse(self.call()['instances'])
if __name__=='__main__':
    suite=unittest.TestSuite(Gestures(n) for n in ('test_short_press_long_hold_and_load_stopped','test_test_hold_same_step_and_movement_one_shot','test_stop_panic_and_patch_replacement_cancel_pending','test_disabled_unassigned_hold_preview_includes_press','test_new_hold_preview_after_tap_advances_to_next_step'))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

#!/usr/bin/env python3
"""Actual native callback/API; raw Note On/Off evidence is in the JACK/EEL fixtures."""
import copy,sys,json,urllib.request,unittest
from test_native_free_capture import FreeCapture
from test_conductor_persistence import fixture,step,block,uid
from server import Control
import conductor

class Execution(FreeCapture):
    def setUp(self):
        self.command('panic')
        self.c=Control(self.sock)
        state=self.call();legacy=self.c.request(op=4,revision=state['revision'],session=state['engineSessionId']);legacy.pop('conductor',None)
        self.c.request(op=5,target=7,patch=legacy,revision=state['revision'],session=state['engineSessionId'])
        for instrument in (2,3):self.command('instrument_route',instrumentId=instrument,field='enabled',value=0)
        sw=self.call()['switches'][0];settings=list(sw['settings']);settings[:4]=[1,1,0,110]
        self.command('switch_commit',switchId=1,settings=settings,sequence=[],name='CONDUCTOR')
        for p,pitch in enumerate((60,62,64,65)):
            self.command('parameter_set',targetId=p+1,kind=20,value=1)
            state=self.call();self.c.request(op=35,target=p,arg=1,phrase=dict(lengthSeconds=60,events=[[0,144,pitch,100],[59,128,pitch,0]]),revision=state['revision'],session=state['engineSessionId'])
        state=self.call();self.original=self.c.request(op=4,revision=state['revision'],session=state['engineSessionId'])
        self.model=conductor.migrate(self.original)
        sources=self.model['sources']
        self.model['switches']=[dict(switchId=1,traversal='SEQUENTIAL',transition='IMMEDIATE',gesture='INSTANT',steps=[step([block(sources[i]['id']),None]) for i in range(4)])]
    def commit(self,model=None):self.command('conductor_commit',conductor=model or self.model)
    def press(self):
        self.command('test',switchId=1)
        self.wait_for(lambda:self.call()['switches'][0]['conductor']['admitted']>0,'actual admission')
    def test_steps_coexist_wrap_capacity_and_persistence(self):
        self.commit()
        for i in range(5):
            self.press();state=self.call()
            self.assertEqual(state['switches'][0]['conductor']['step'],i%4+1)
            self.assertEqual(len(state['instances']),i+1)
        self.assertEqual({x['phraseId'] for x in state['instances']},{1,2,3,4})
        for _ in range(7):self.press()
        before=self.call();self.command('test',switchId=1)
        self.wait_for(lambda:self.call()['switches'][0]['conductor']['result']==2,'bounded saturation refusal')
        self.assertEqual([v['id'] for v in before['instances']],[v['id'] for v in self.call()['instances']])
        self.command('panic');self.assertFalse(self.call()['instances'])
        self.patch('save');self.patch('load')
        self.assertFalse(self.call()['instances']);self.assertEqual(self.call()['switches'][0]['conductor']['step'],0)
        self.press();self.assertEqual(self.call()['instances'][0]['phraseId'],1)
    def test_layers_missing_and_unsupported_no_fallback(self):
        model=copy.deepcopy(self.model)
        model['switches'][0]['steps']=[step([block(model['sources'][0]['id']),block(model['sources'][1]['id'])])]
        self.commit(model);self.press();self.assertEqual(len(self.call()['instances']),2)
        self.command('panic')
        model['switches'][0]['steps'][0]['layers'][0]['block']['sourceId']=uid()
        self.commit(model);self.press();state=self.call()
        self.assertEqual([v['phraseId'] for v in state['instances']],[2]);self.assertEqual(state['switches'][0]['conductor']['missing'],1)
        self.command('panic')
        model['switches'][0]['steps'][0]['layers'][1]['block']['overrides']['entry']=dict(mode='OVERRIDE',value='REVEAL')
        self.commit(model);self.command('test',switchId=1)
        self.wait_for(lambda:self.call()['switches'][0]['conductor']['result']==4,'unsupported execution rejected')
        self.assertFalse(self.call()['instances'])
    def test_local_hold_release_overrides_and_source_isolation(self):
        for mode in ('HOLD','LOOP','ONCE'):
            self.command('panic')
            model=copy.deepcopy(self.model);model['switches'][0]['steps']=[step([block(model['sources'][0]['id'])])]
            model['switches'][0]['steps'][0]['layers'][0]['block']['overrides']=dict(playMode=dict(mode='OVERRIDE',value=mode),phrase_base_velocity=dict(mode='OVERRIDE',value=.5))
            self.commit(model);self.press();state=self.call()
            self.assertEqual(state['phrases'][0]['mode'],1)
            self.assertEqual(state['phrases'][0]['baseVelocity'],1)
            self.assertEqual(state['instances'][0]['mode'],{'LOOP':0,'ONCE':1,'HOLD':2}[mode])
            self.command('conductor_release',switchId=1)
            if mode=='HOLD':self.wait_for(lambda:not self.call()['instances'],'owned HOLD release')
            else:self.assertEqual(len(self.call()['instances']),1)

if __name__=='__main__':
    suite=unittest.TestSuite(Execution(name) for name in ('test_steps_coexist_wrap_capacity_and_persistence','test_layers_missing_and_unsupported_no_fallback','test_local_hold_release_overrides_and_source_isolation'))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

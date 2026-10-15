#!/usr/bin/env python3
"""Actual native DSP/private-control integration. JACK captures are separate."""
import copy
import sys
import time
import unittest
from test_conductor_gestures_native import Gestures


class Reveal(Gestures):
    def setUp(self):
        super().setUp()
        self.reveal=self.model['switches'][0]['steps'][0]['layers'][1]['block']
        self.reveal['overrides']['entry']=dict(mode='OVERRIDE',value='REVEAL')
        # Separate actual recorded destinations, not an instrument OUT mutation.
        state=self.call()
        result=self.c.request(op=35,target=1,arg=1,phrase=dict(lengthSeconds=30,events=[[0,145,72,100],[29,129,72,0]]),revision=state['revision'],session=state['engineSessionId'])
        self.assertEqual(result['status'],'ok')
        # End a physical pedal gesture left held by the preceding test.
        self.up()

    def test_reveal_latch_and_early_release(self):
        self.commit();self.down()
        self.assertEqual(len(self.call()['instances']),2,'REVEAL notes start internally at PRESS')
        self.up();time.sleep(.3)
        self.assertEqual([v['phraseId'] for v in self.call()['instances']],[1],'early release stops only hidden occurrence')
        self.command('panic');self.down()
        owners=[v['id'] for v in self.call()['instances']]
        time.sleep(.3)
        self.assertEqual([v['id'] for v in self.call()['instances']],owners,'HOLD reveals existing owner, never restarts')
        self.up();time.sleep(.05)
        self.assertEqual([v['id'] for v in self.call()['instances']],owners,'LATCH survives RELEASE')
        self.assertEqual(self.call()['outputOverflow'],0)

    def test_gate_remask_keeps_timeline_and_load_stopped(self):
        self.reveal['overrides']['release']=dict(mode='OVERRIDE',value='GATE')
        self.commit();self.down();owners=[v['id'] for v in self.call()['instances']]
        time.sleep(.3);self.up();time.sleep(.05)
        self.assertEqual([v['id'] for v in self.call()['instances']],owners,'GATE remasks; does not stop its instance')
        self.command('panic');self.patch('save');self.patch('load');time.sleep(.3)
        self.assertFalse(self.call()['instances'])
        state=self.call()
        loaded=self.c.request(op=4,revision=state['revision'],session=state['engineSessionId'])
        self.assertEqual(loaded['conductor'],__import__('conductor').encode(self.model),'GATE/REVEAL overrides must survive actual SAVE/LOAD')
        self.assertEqual(self.call()['outputOverflow'],0)

    def test_natural_end_and_original_all_channel_ownership(self):
        original=self.export(2)
        self.command('phrase_output',phraseId=2,channel=17)
        self.commit();self.down()
        self.wait_for(lambda:self.call()['reveals'] and self.call()['reveals'][0]['ownedChannels']==65535,'ALL CC7 targets reserved before attacks')
        self.assertEqual(self.call()['activeNotes'],17,'one bass + sixteen actual broadcast pad attacks')
        self.assertEqual(self.export(2),original,'routing must not bake CC7 or remap source MIDI')
        self.command('phrase_stop',phraseId=2)
        self.wait_for(lambda:not self.call()['reveals'],'targeted STOP releases all CC7 leases')
        self.assertEqual([v['phraseId'] for v in self.call()['instances']],[1])
        self.command('panic');self.up();self.command('phrase_output',phraseId=2,channel=0)
        state=self.call()
        self.c.request(op=35,target=1,arg=1,phrase=dict(lengthSeconds=.6,events=[[0,145,72,100],[.5,129,72,0]]),revision=state['revision'],session=state['engineSessionId'])
        self.commit();self.down()
        self.wait_for(lambda:not self.call()['reveals'],'natural completion retires CC7 owner')
        self.assertEqual([v['phraseId'] for v in self.call()['instances']],[1])
        self.assertEqual(self.call()['outputOverflow'],0)

    def test_source_cc7_refusal_and_missing_reference(self):
        # SMF import deliberately accepts notes only. Exercise the real legacy
        # patch loader for a source containing CC7; never ignore an import error.
        state=self.call()
        patch=self.c.request(op=4,revision=state['revision'],session=state['engineSessionId'])
        offset=2048*5
        patch['memory'][offset:offset+15]=[0,177,7,90,0,0,145,72,100,0,2*48000,129,72,0,0]
        patch['memory'][16*2048*5+1]=3
        result=self.c.request(op=5,target=7,patch=patch,revision=state['revision'],session=state['engineSessionId'])
        self.assertEqual(result['status'],'ok')
        self.commit();self.down();time.sleep(.05)
        self.assertFalse(self.call()['instances'],'unsupported source CC7 must refuse whole STEP before attacks')
        self.assertEqual(self.call()['switches'][0]['conductor']['result'],3)
        self.up();self.command('panic')
        missing=self.reveal['sourceId'];self.model['sources']=[s for s in self.model['sources'] if s['id']!=missing]
        self.commit();self.command('test',switchId=1);time.sleep(.3)
        self.assertEqual([v['phraseId'] for v in self.call()['instances']],[1])
        self.assertFalse(self.call()['reveals'])
        self.assertEqual(self.call()['switches'][0]['conductor']['missing'],1)

if __name__=='__main__':
    suite=unittest.TestSuite(Reveal(n) for n in ('test_reveal_latch_and_early_release','test_gate_remask_keeps_timeline_and_load_stopped','test_natural_end_and_original_all_channel_ownership','test_source_cc7_refusal_and_missing_reference'))
    sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())

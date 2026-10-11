#!/usr/bin/env python3
"""Playback policy through the real native host, HTTP worker and shared EEL."""
import json,sys,time,unittest,urllib.request
from test_snapshots import SnapshotTests

class GestureTests(SnapshotTests):
    def setUp(self):
        super().setUp()
        for instrument in self.call()['instruments']:
            for module in instrument['transformers']:
                self.command('module_structure',instrumentId=instrument['id'],moduleId=module['id'],operation='delete')
    def policy(self,value):
        self.command('parameter_set',targetId=1,kind=20,value=1)
        self.command('parameter_set',targetId=1,kind=25,value=value)
        self.wait_for(lambda:self.call()['phrases'][0]['playbackPolicy']==value,'applied playback policy')
    def test_held_loop_release_and_no_retrigger(self):
        self.policy(2)
        self.command('phrase_play',phraseId=1)
        self.assertGreater(self.call()['activeNotes'],0,'manual PRESS retains its first Note On')
        initial=self.call()['midiCount'];time.sleep(.7)
        self.assertGreater(self.call()['midiCount'],initial,'actual MIDI continues into a second source pass')
        self.command('phrase_release',phraseId=1)
        self.assertEqual(self.call()['activeNotes'],0)
        count=self.call()['midiCount'];time.sleep(.55)
        self.assertEqual(self.call()['midiCount'],count,'released loop schedules no further MIDI')
        self.policy(1)
        self.command('phrase_play',phraseId=1)
        self.assertGreater(self.call()['activeNotes'],0)
        self.assertEqual(self.call()['phrases'][0]['playbackError'],0)
        self.command('phrase_play',phraseId=1)
        self.assertEqual(self.call()['activeNotes'],0,'second PRESS stops without restarting')
        self.command('phrase_release',phraseId=1)
        self.command('phrase_play',phraseId=1);self.command('panic')
        self.assertEqual(self.call()['activeNotes'],0)
    def test_controller_snapshot_and_patch_policy_roundtrip(self):
        self.policy(0)
        self.command('controller_source',sourceId=101,kind=2,channel=2,number=21)
        self.command('mapping_commit',mapping=dict(id=1,sourceId=101,targetId=201,instrumentId=1,moduleId=0,kind=25,points=[[0,0,0],[1,1,0]],takeover=0))
        self.command('midi_cc',channel=2,number=21,value=127)
        self.wait_for(lambda:self.call()['phrases'][0]['playbackPolicy']==2,'Controller Engine controls held policy')
        snapshot=self.capture()
        data=json.load(urllib.request.urlopen(self.base+'/api/v1/snapshot/'+str(snapshot['id'])))
        self.assertTrue(any(p['kind']==25 and p['instrumentId']==1 for p in data['parameters']))
        self.command('parameter_set',targetId=1,kind=25,value=1)
        self.command('snapshot_recall',snapshotId=snapshot['id'],seconds=0)
        self.wait_for(lambda:self.call()['phrases'][0]['playbackPolicy']==2,'instant snapshot recalls policy')
        self.patch('save');self.command('parameter_set',targetId=1,kind=25,value=0)
        self.patch('load')
        # Patch saves committed controller bases; the recalled snapshot remains separate.
        self.assertEqual(self.call()['phrases'][0]['playbackPolicy'],1)
        self.command('snapshot_recall',snapshotId=snapshot['id'],seconds=0)
        self.wait_for(lambda:self.call()['phrases'][0]['playbackPolicy']==2,'reloaded snapshot recalls held policy')
        self.command('parameter_set',targetId=1,kind=25,value=3,expected=400)

if __name__=='__main__':
    suite=unittest.TestSuite(GestureTests(name) for name in GestureTests.__dict__ if name.startswith('test_'))
    sys.exit(not unittest.TextTestRunner().run(suite).wasSuccessful())

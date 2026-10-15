"""Portable serialization through the real native EEL2 engine, not a fake store."""
import sys
import unittest
from test_headless_mvp import HeadlessTests
sys.path.insert(0,str(__import__("pathlib").Path(__file__).resolve().parents[1]/"headless"))
from server import Control
import portable_project as p

class PortableEngineTests(HeadlessTests):
    def test_portable_roundtrip_and_guarded_capture(self):
        control=Control(self.sock)
        self.command('phrase_record',phraseId=3)
        self.command('midi',channel=2,note=66,value=99)
        self.command('midi',channel=2,note=66,value=0)
        self.command('phrase_finish',phraseId=3);self.command('panic')
        state=self.call()
        patch=control.request(op=4,arg=1,revision=state['revision'],session=state['engineSessionId'])
        project=p.capture(patch,state['sampleRate'])
        restored=p.materialize(project,state['sampleRate'])
        result=control.request(op=5,arg=1,target=7,patch=restored,revision=state['revision'],session=state['engineSessionId'])
        self.assertEqual(result['status'],'ok')
        # Even with a fresh revision, an old raw baseline cannot overwrite a
        # parameter edited between capture and apply.
        self.command('parameter_set',targetId=1,kind=1,value=77)
        changed=self.call()
        rejected=control.request(op=5,arg=1,target=7,patch=restored,revision=changed['revision'],session=changed['engineSessionId'])
        self.assertNotEqual(rejected['status'],'ok')
        self.assertEqual(self.call()['instruments'][0]['level'],77)
        data=control.request(op=35,target=2,revision=-1)['phraseData']
        self.assertEqual([e[2:] for e in data['events']],[[66,99],[66,0]])
        self.command('phrase_play',phraseId=3)
        state=self.call()
        rejected=control.request(op=4,arg=1,revision=state['revision'],session=state['engineSessionId'])
        self.assertNotEqual(rejected.get('format'),'MIDI_HUMAN_LOOPER_PATCH')
        self.command('panic');self.assertEqual(self.call()['activeNotes'],0)

if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.TestSuite([PortableEngineTests('test_portable_roundtrip_and_guarded_capture')]))
    sys.exit(not result.wasSuccessful())

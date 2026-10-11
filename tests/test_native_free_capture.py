#!/usr/bin/env python3
"""Actual native engine + HTTP + source SMF; no JACK or hardware simulation claim."""
import socket, subprocess, sys, tempfile, time, unittest, urllib.request
from pathlib import Path
from test_snapshots import SnapshotTests
from test_headless_mvp import BINARY, ROOT
sys.path.insert(0,str(ROOT/"headless"))
from phrase_midi import read_smf

class FreeCapture(SnapshotTests):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='mbmf-free-')
        cls.sock=str(Path(cls.temp.name)/'engine.sock')
        cls.engine=subprocess.Popen([BINARY,str(ROOT/'midi_human_looper.jsfx'),cls.sock,'--chain'],
                                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        cls.wait_for(lambda:Path(cls.sock).exists(),'native engine')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1]
        cls.base='http://127.0.0.1:'+str(cls.port);cls.start_web()

    def export(self,phrase):
        return urllib.request.urlopen(self.base+f'/api/v1/phrase/{phrase}/midi',timeout=5).read()

    def test_free_capture(self):
        self.assertEqual(self.call()['chainCaptureMode'],'free-time')
        for mode in (0,1,2):
            self.command('panic');self.command('phrase_clear',phraseId=3)
            self.command('parameter_set',targetId=3,kind=20,value=mode)
            self.command('phrase_record',phraseId=3)
            time.sleep(4.3 if mode==0 else .05) # longer than the former two-bar window
            state=self.call()
            self.assertTrue(state['chainArmed']);self.assertFalse(state['chainRecording'])
            self.assertEqual(state['phrases'][2]['events'],0)
            self.command('midi',channel=3,note=65,value=97)
            self.wait_for(lambda:self.call()['chainRecording'],'first-note capture')
            self.assertFalse(self.call()['chainArmed'])
            time.sleep(.08);self.command('midi',channel=3,note=65,value=0)
            time.sleep(.12);self.command('midi',channel=4,note=69,value=83)
            time.sleep(.06);self.command('midi',channel=4,note=69,value=0)
            self.command('phrase_finish',phraseId=3)
            state=self.call()
            self.assertFalse(state['chainRecording']);self.assertFalse(state['chainArmed'])
            self.assertEqual(state['phrases'][2]['mode'],mode)
            self.command('panic')
            source=read_smf(self.export(3));events=source['events']
            self.assertEqual(events[0],[0,146,65,97])
            self.assertEqual([e[2] for e in events],[65,65,69,69])
            self.assertGreater(events[2][0],events[1][0])
            self.assertLess(source['lengthSeconds'],1)
            before=self.export(3);self.patch('save');self.patch('load')
            self.assertEqual(self.export(3),before)
            self.assertEqual(self.call()['activeNotes'],0)
        self.command('phrase_record',phraseId=4);self.command('panic')
        self.assertFalse(self.call()['chainArmed'])
        self.assertEqual(self.call()['phrases'][3]['events'],0)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([FreeCapture('test_free_capture')]))
    raise SystemExit(not result.wasSuccessful())

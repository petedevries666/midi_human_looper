#!/usr/bin/env python3
"""Actual native engine + HTTP + source SMF; no JACK or hardware simulation claim."""
import base64, json, socket, subprocess, sys, tempfile, time, unittest, urllib.request
from pathlib import Path
from test_snapshots import SnapshotTests
from test_headless_mvp import BINARY, ROOT
sys.path.insert(0,str(ROOT/"headless"))
from phrase_midi import read_smf, write_smf

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
        # Free-time interchange must not inherit the old native grid capacity
        # or silently force an imported ONCE phrase into LOOP.
        raw=write_smf(dict(lengthSeconds=8,bpm=120,events=[[0,145,60,81],[8,129,60,23]]))
        state=self.call()
        body=dict(file=base64.b64encode(raw).decode(),phraseId=4,mode='replace',
                  expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'])
        request=urllib.request.Request(self.base+'/api/v1/phrase/midi',data=json.dumps(body).encode(),
                                       headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=5) as response:
            self.assertEqual(response.status,200)
        self.assertEqual(self.call()['phrases'][3]['mode'],1)
        imported=read_smf(self.export(4))
        self.assertEqual(imported['events'],[[0,145,60,81],[8,129,60,23]])
        self.patch('save');self.patch('load')
        self.assertEqual(read_smf(self.export(4))['events'],imported['events'])

    def test_overdub_cancel_and_independent_loop(self):
        self.command('panic')
        for phrase,pitch in ((5,48),(6,60)):
            self.command('phrase_clear',phraseId=phrase)
            raw=write_smf(dict(lengthSeconds=.8,bpm=120,events=[[0,144,pitch,81],[.6,128,pitch,23]]))
            state=self.call()
            body=dict(file=base64.b64encode(raw).decode(),phraseId=phrase,mode='replace',expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'])
            request=urllib.request.Request(self.base+'/api/v1/phrase/midi',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
            json.load(urllib.request.urlopen(request,timeout=5))
        original=self.export(6)
        self.command('phrase_record',phraseId=6)
        self.assertEqual(self.call()['phrases'][5]['state'],'OVERDUB ARMED')
        self.command('midi',channel=3,note=67,value=92)
        self.wait_for(lambda:self.call()['phrases'][5]['state']=='OVERDUB ACTIVE','overdub capture')
        self.command('midi',channel=3,note=67,value=0)
        self.command('phrase_cancel',phraseId=6);self.command('panic')
        self.assertEqual(self.export(6),original,'cancel must preserve the entire original source')
        self.command('parameter_set',targetId=5,kind=20,value=0)
        self.command('phrase_play',phraseId=5)
        self.wait_for(lambda:self.call()['phrases'][4]['state']=='PLAYING','independent loop')
        self.command('phrase_record',phraseId=6)
        self.command('midi',channel=3,note=67,value=92)
        self.wait_for(lambda:self.call()['phrases'][5]['state']=='OVERDUB ACTIVE','simultaneous overdub')
        self.assertEqual(self.call()['phrases'][4]['state'],'PLAYING')
        time.sleep(.08);self.command('midi',channel=3,note=67,value=0)
        self.command('phrase_finish',phraseId=6)
        self.assertEqual(self.call()['phrases'][4]['state'],'PLAYING','FINISH must preserve unrelated playback')
        self.command('panic')
        notes=read_smf(self.export(6))['events']
        self.assertEqual(len(notes),4)
        self.assertEqual(notes[0][0],0)
        self.assertEqual(sorted(e[2] for e in notes),[60,60,67,67])
        self.assertAlmostEqual(read_smf(self.export(6))['lengthSeconds'],.8,places=3)
        before=self.export(6);self.patch('save');self.patch('load');self.assertEqual(self.export(6),before)
        self.assertEqual(self.call()['activeNotes'],0)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([FreeCapture('test_free_capture'),FreeCapture('test_overdub_cancel_and_independent_loop')]))
    raise SystemExit(not result.wasSuccessful())

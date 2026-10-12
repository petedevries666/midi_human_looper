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

    def test_hardware_stop_state_and_record_finalization(self):
        self.command('panic')
        self.command('phrase_clear',phraseId=8)
        self.command('phrase_record',phraseId=8)
        self.command('midi',channel=2,note=64,value=98)
        time.sleep(.1)
        self.assertEqual(self.call()['phrases'][7]['state'],'RECORDING')
        self.command('chain_stop')
        self.wait_for(lambda:self.call()['activeNotes']==0,'STOP releases monitor')
        source=read_smf(self.export(8))
        self.assertEqual([e[1:4] for e in source['events']],[[145,64,98],[129,64,0]])
        self.assertGreater(source['events'][1][0],.05)
        self.assertEqual(source['events'][0][0],0)
        self.command('parameter_set',targetId=8,kind=20,value=0)
        for stop in ('chain_stop','panic'):
            self.command('phrase_play',phraseId=8)
            self.wait_for(lambda:self.call()['phrases'][7]['state']=='PLAYING','LOOP playing')
            self.command(stop)
            time.sleep(.3)
            state=self.call()
            self.assertFalse(state['chainRunning'])
            self.assertNotEqual(state['phrases'][7]['state'],'PLAYING')
            self.assertEqual(state['activeNotes'],0)
            self.command('phrase_clear',phraseId=8)
            self.assertEqual(self.call()['phrases'][7]['events'],0)
            # Keep a source for the second iteration.
            self.command('phrase_record',phraseId=8)
            self.command('midi',channel=2,note=64,value=98)
            time.sleep(.06)
            self.command('phrase_finish',phraseId=8)
            self.command('panic')

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

    def test_inactive_clear_and_targeted_loop_stop(self):
        self.command('panic')
        for phrase,pitch in ((9,48),(10,60)):
            self.command('phrase_clear',phraseId=phrase)
            self.command('parameter_set',targetId=phrase,kind=20,value=0)
            self.command('phrase_record',phraseId=phrase)
            self.command('midi',channel=1,note=pitch,value=91)
            time.sleep(.12)
            self.command('phrase_finish',phraseId=phrase)
            self.command('panic')
        self.command('phrase_play',phraseId=9)
        self.wait_for(lambda:self.call()['phrases'][8]['state']=='PLAYING','first loop')
        # The inactive target can be cleared without stopping the other loop.
        self.command('phrase_clear',phraseId=10)
        self.assertEqual(self.call()['phrases'][9]['events'],0)
        self.assertEqual(self.call()['phrases'][8]['state'],'PLAYING')
        self.command('phrase_stop',phraseId=9)
        self.wait_for(lambda:self.call()['activeNotes']==0,'target loop releases held notes')
        self.assertNotEqual(self.call()['phrases'][8]['state'],'PLAYING')
        self.command('phrase_clear',phraseId=9)
        self.assertEqual(self.call()['phrases'][8]['events'],0)

    def test_controller_removal_sequence_and_clear_patch(self):
        from controller_config import decode
        self.command('panic')
        self.command('controller_rename',sourceId=401,name='EXP TEST',create=True)
        self.command('controller_rename',sourceId=402,name='OTHER',create=True)
        self.command('controller_source',sourceId=401,kind=2,channel=3,number=31)
        self.command('mapping_commit',mapping=dict(id=401,sourceId=401,targetId=401,instrumentId=1,kind=1,points=[[0,0,0],[1,1,0]]))
        self.command('controller_learn',sourceId=401)
        self.command('controller_remove',sourceId=401)
        config=decode(self.call()['controllerEngine'])
        self.assertNotIn(401,[s['id'] for s in config['sources']])
        self.assertIn(402,[s['id'] for s in config['sources']])
        self.assertFalse(config['mappings'])
        self.assertEqual(self.call()['controllerLearn']['target'],0)
        for instrument in (1,2,3):
            self.command('instrument_route',instrumentId=instrument,field='enabled',value=1)
            self.command('instrument_route',instrumentId=instrument,field='input',value=instrument)
            self.command('instrument_route',instrumentId=instrument,field='output',value=instrument)
        for phrase,channel,pitch in ((11,1,48),(12,2,64),(13,3,67)):
            self.command('phrase_clear',phraseId=phrase)
            self.command('phrase_record',phraseId=phrase)
            self.command('midi',channel=channel,note=pitch,value=90)
            time.sleep(.07)
            self.command('phrase_finish',phraseId=phrase);self.command('panic')
        sw=self.call()['switches'][0];settings=sw['settings'];settings[0]=1;settings[1]=1;settings[2]=3;settings[3]=99;settings[12]=1
        for mode,steps in ((0,[1,2,3,1]),(1,[3,2,1,3]),(2,[1,2,3,2,1])):
            settings[9]=mode;settings[10]=0
            self.command('switch_commit',switchId=sw['id'],settings=settings,sequence=[11,12,13],name='SEQUENCER')
            for step in steps:
                state=self.command('test',switchId=sw['id'],gesture='tap')
                self.assertEqual(state['switches'][0]['step'],step)
                self.assertEqual(state['lastEvent'][2],{1:48,2:64,3:67}[step]);self.assertEqual(state['lastEvent'][1]&15,step-1)
        settings[9]=3
        self.command('switch_commit',switchId=sw['id'],settings=settings,sequence=[11,12,13],name='SEQUENCER')
        steps=[self.command('test',switchId=sw['id'],gesture='tap')['switches'][0]['step'] for _ in range(3)]
        self.assertEqual(sorted(steps),[1,2,3])
        settings[9]=0;settings[10]=1
        self.command('switch_commit',switchId=sw['id'],settings=settings,sequence=[11,12,13],name='SEQUENCER')
        state=self.command('midi',channel=4,note=99,value=100)
        self.assertEqual(state['switches'][0]['step'],1);self.assertEqual(state['lastEvent'][1:3],[144,48])
        self.command('midi',channel=4,note=99,value=0)
        other=self.call()['switches'][1];other_settings=other['settings'];other_settings[0]=1;other_settings[12]=1
        self.command('switch_commit',switchId=other['id'],settings=other_settings,sequence=[12],name='OTHER SEQUENCE')
        self.command('test',switchId=other['id'],gesture='tap')
        state=self.command('midi',channel=4,note=99,value=100)
        self.assertEqual(state['switches'][0]['step'],1,'RESET ON RE-ENTRY restarts the first switch')
        self.command('midi',channel=4,note=99,value=0)
        self.command('panic');state=self.call();self.assertFalse(state['chainRunning']);self.assertFalse(any(p['state']=='PLAYING' for p in state['phrases']));self.capture();self.patch('save')
        self.command('patch_clear',confirm=False,expected=400)
        self.command('patch_clear',confirm=True)
        state=self.call()
        self.assertTrue(all(p['events']==0 and p['mode']==1 for p in state['phrases']))
        self.assertFalse(decode(state['controllerEngine'])['sources'])
        self.assertFalse(state['snapshots'])
        self.assertEqual(len(state['instruments']),3)
        self.assertTrue(all(not i['transformers'] for i in state['instruments']))
        self.assertEqual(state['activeNotes'],0)
        self.patch('save');self.patch('load')
        self.assertTrue(all(p['events']==0 for p in self.call()['phrases']))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite([FreeCapture(name) for name in ['test_hardware_stop_state_and_record_finalization','test_free_capture','test_overdub_cancel_and_independent_loop','test_inactive_clear_and_targeted_loop_stop','test_controller_removal_sequence_and_clear_patch']]))
    raise SystemExit(not result.wasSuccessful())

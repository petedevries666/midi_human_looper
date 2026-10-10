#!/usr/bin/env python3
"""Actual JSFX engine interchange, recording and persisted restart workflow."""
import base64,json,sys,time,unittest,urllib.request,subprocess
from test_snapshots import SnapshotTests
from test_headless_mvp import BINARY,ROOT
from test_phrase_midi import fixture
from phrase_midi import read_smf
class InterchangeTests(SnapshotTests):
    def upload(self, raw, dest=4, mode='replace', expected=200, state=None):
        state=state or self.call()
        body=dict(file=base64.b64encode(raw).decode(),phraseId=dest,mode=mode,
                  expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'])
        request=urllib.request.Request(self.base+'/api/v1/phrase/midi',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        try: response=urllib.request.urlopen(request,timeout=5)
        except urllib.error.HTTPError as e: response=e
        self.assertEqual(response.status,expected);return json.load(response)
    def export(self,id):
        try:return urllib.request.urlopen(self.base+f'/api/v1/phrase/{id}/midi',timeout=5).read()
        except urllib.error.HTTPError as error:raise AssertionError(error.read().decode())
    def test_record_export_import_play_overdub_restart(self):
        self.command('phrase_record',phraseId=3)
        self.command('midi',channel=3,note=83,value=91);time.sleep(.04)
        self.command('midi',channel=3,note=83,value=0)
        self.command('phrase_finish',phraseId=3);self.command('panic')
        recorded=self.export(3);original=read_smf(recorded)
        self.assertTrue(any(e[2]==83 and e[3]==91 for e in original['events']))
        untouched=self.export(2)
        state=self.call();self.upload(recorded,4,'preview')
        self.assertEqual(self.call()['revision'],state['revision'])
        self.upload(recorded,4)
        cloned=read_smf(self.export(4))
        self.assertEqual([e[1:] for e in cloned['events']],[e[1:] for e in original['events']])
        for a,b in zip(original['events'],cloned['events']):self.assertAlmostEqual(a[0],b[0],places=4)
        self.assertEqual(self.export(2),untouched)
        stale=self.call();self.command('parameter_set',targetId=1,kind=1,value=77)
        self.upload(fixture(),5,state=stale,expected=409)
        self.assertEqual(self.call()['phrases'][4]['events'],0)
        self.upload(fixture(),5)
        source_before=self.export(5)
        self.command('module_structure',instrumentId=1,operation='add',engineType=1)
        tf=self.call()['instruments'][0]['transformers'][0]['id']
        self.command('module_commit',instrumentId=1,moduleId=tf,parameters=[dict(kind=7,value=12)])
        self.assertEqual(self.export(5),source_before) # Never bake the pedalboard into export.
        self.command('phrase_play',phraseId=5);time.sleep(.5)
        self.assertGreater(self.call()['midiCount'],0)
        self.upload(recorded,4,expected=422) # Playing processor is never mutated.
        self.command('panic');self.assertEqual(self.call()['activeNotes'],0)
        before_bad=self.export(5)
        for bad in (b'broken',fixture()[:-5],fixture().replace(b'\x82\x3c\x20',b'\xb2\x01\x20')):
            self.upload(bad,5,expected=422)
        self.assertEqual(self.export(5),before_bad)
        prior=self.export(5);self.patch('save')
        self.stop_web();self.engine.terminate();self.engine.communicate(timeout=5)
        self.engine=subprocess.Popen([BINARY,str(ROOT/'midi_human_looper.jsfx'),self.sock],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        type(self).engine=self.engine
        self.wait_for(lambda: __import__('pathlib').Path(self.sock).exists(),'restarted socket');self.start_web()
        self.patch('load');self.assertEqual(self.export(5),prior)
        self.command('phrase_play',phraseId=5);time.sleep(.5);self.command('panic')
        self.assertEqual(self.call()['activeNotes'],0)
        self.command('phrase_record',phraseId=5);self.command('midi',channel=3,note=77,value=84)
        time.sleep(.04);self.command('midi',channel=3,note=77,value=0);self.command('phrase_finish',phraseId=5);self.command('panic')
        self.assertTrue(any(e[2]==77 for e in read_smf(self.export(5))['events']))
if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.TestSuite([InterchangeTests('test_record_export_import_play_overdub_restart')]))
    sys.exit(not result.wasSuccessful())

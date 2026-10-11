"""Persistent names through actual EEL storage, portable contracts and HTTP guards."""
import json,sys,unittest,urllib.request
from pathlib import Path
from test_headless_mvp import HeadlessTests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'headless'))
from server import Control
import portable_project
class Names(HeadlessTests):
    def patch(self,action):
        state=self.call()
        req=urllib.request.Request(self.base+'/api/v1/patch/'+action,data=json.dumps(dict(slot=1,expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'])).encode(),headers={'Content-Type':'application/json'})
        return json.load(urllib.request.urlopen(req))
    def test_names_persistence_isolation_and_portable_memory(self):
        before=self.call()
        self.command('phrase_rename',phraseId=1,name='BASS INTRO')
        self.command('instrument_rename',instrumentId=2,name='PIANO')
        state=self.call()
        self.assertEqual(state['phrases'][0]['name'],'BASS INTRO')
        self.assertEqual(state['instruments'][1]['name'],'PIANO')
        self.assertEqual(state['phrases'][1]['name'],before['phrases'][1]['name'])
        self.assertEqual(state['instruments'][0]['name'],before['instruments'][0]['name'])
        self.patch('save')
        self.command('phrase_rename',phraseId=1,name='OTHER')
        self.command('instrument_rename',instrumentId=2,name='OTHER')
        self.patch('load')
        state=self.call()
        self.assertEqual(state['phrases'][0]['name'],'BASS INTRO')
        self.assertEqual(state['instruments'][1]['name'],'PIANO')
        control=Control(self.sock)
        patch=control.request(op=4,arg=1,revision=state['revision'],session=state['engineSessionId'])
        project=portable_project.capture(patch,state['sampleRate'])
        restored=portable_project.materialize(project,state['sampleRate'])
        self.assertEqual(restored['memory'],patch['memory'])
        self.command('phrase_rename',phraseId=1,name='')
        self.assertEqual(self.call()['phrases'][0]['name'],'') # Legacy default label.
    def test_names_validation_stale_commands_and_deleted_ids(self):
        for name in ('a'*17,'bad\nname','écho'):
            self.command('phrase_rename',phraseId=1,name=name,expected=400)
        state=self.call()
        self.command('instrument_rename',instrumentId=1,name='ONE')
        self.call(dict(protocolVersion=1,action='instrument_rename',instrumentId=1,name='STALE',expectedRevision=state['revision']),expected=409)
        self.command('instrument_delete',instrumentId=3)
        self.command('instrument_rename',instrumentId=3,name='DELETED',expected=400)
        self.assertEqual(self.call()['instruments'][0]['name'],'ONE')
if __name__=='__main__':
    suite=unittest.TestSuite(Names(name) for name in ('test_names_persistence_isolation_and_portable_memory','test_names_validation_stale_commands_and_deleted_ids'))
    sys.exit(not unittest.TextTestRunner().run(suite).wasSuccessful())

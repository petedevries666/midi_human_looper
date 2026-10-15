"""Actual native persistence authority, independent of browser/bridge lifetime."""
import json,subprocess,sys,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
from test_headless_mvp import HeadlessTests,ROOT,BINARY
sys.path.insert(0,str(ROOT/'headless'))
from project_sync import ProjectStore
from server import Control
class AuthorityTests(HeadlessTests):
    def remote(self,path,data=None,status=200):
        request=urllib.request.Request(self.base+'/api/v1/project/'+path,
            data=json.dumps(data).encode() if data is not None else None,
            headers={'Content-Type':'application/json'})
        try:response=urllib.request.urlopen(request,timeout=5)
        except urllib.error.HTTPError as e:response=e
        self.assertEqual(response.status,status);return json.load(response)
    def test_authority(self):
        info=self.remote('status');self.assertEqual(info['restartAuthority'],'none')
        self.assertFalse(info['liveMatchesRestart'])
        now=self.call();body=dict(expectedActiveRevisionId=None,expectedRevision=now['revision'],expectedEngineSessionId=now['engineSessionId'])
        first=self.remote('checkpoint',body);info=self.remote('status')
        self.assertEqual(info['savedRevisionId'],first['revisionId']);self.assertTrue(info['liveMatchesRestart'])
        self.assertEqual(self.call()['revision'],now['revision'],'commit must not reload or start the live engine')
        self.command('parameter_set',targetId=1,kind=1,value=56)
        self.assertFalse(self.remote('status')['liveMatchesRestart'])
        self.remote('checkpoint',body,409)
        now=self.call();body.update(expectedActiveRevisionId=first['revisionId'],expectedRevision=now['revision'])
        second=self.remote('checkpoint',body)
        self.assertNotEqual(first['revisionId'],second['revisionId'])
        # Slot SAVE must not replace autonomous authority.
        now=self.call();payload=dict(slot=1,expectedRevision=now['revision'],expectedEngineSessionId=now['engineSessionId'])
        response=urllib.request.urlopen(urllib.request.Request(self.base+'/api/v1/patch/save',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'}))
        self.assertEqual(response.status,200)
        self.assertEqual(self.remote('status')['savedRevisionId'],second['revisionId'])
        self.assertEqual(self.remote('status')['legacySlots'],[1])
        self.command('parameter_set',targetId=1,kind=1,value=65)
        store=ProjectStore(Path(self.temp.name)/'patches',Control(self.sock));before=store.manifest();now=self.call()
        with patch('project_sync.atomic_json',side_effect=OSError('injected disk failure')):
            with self.assertRaises(OSError):store.checkpoint(dict(expectedActiveRevisionId=before['revisionId'],expectedRevision=now['revision'],expectedEngineSessionId=now['engineSessionId']))
        self.assertEqual(store.manifest(),before)
        self.assertEqual(self.call()['instruments'][0]['level'],65)
        import project_sync
        original_atomic=project_sync.atomic_json;failed=[False]
        def after_rename(path,value):
            original_atomic(path,value)
            if Path(path).name=='active.json' and not failed[0]:
                failed[0]=True;raise OSError('injected failure after rename')
        with patch('project_sync.atomic_json',side_effect=after_rename):
            with self.assertRaises(OSError):store.checkpoint(dict(expectedActiveRevisionId=before['revisionId'],expectedRevision=now['revision'],expectedEngineSessionId=now['engineSessionId']))
        self.assertEqual(store.manifest(),before)
        self.command('midi',channel=1,note=95,value=100)
        self.assertIsNone(self.remote('status')['liveMatchesRestart'])
        self.remote('checkpoint',dict(expectedActiveRevisionId=before['revisionId'],expectedRevision=self.call()['revision'],expectedEngineSessionId=now['engineSessionId']),409)
        self.command('panic')
        self.stop_web();self.engine.terminate();self.engine.communicate(timeout=5)
        type(self).engine=subprocess.Popen([BINARY,str(ROOT/'midi_human_looper.jsfx'),self.sock],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.wait_for(lambda:Path(self.sock).exists(),'restarted engine')
        store.restore();self.assertEqual(store.control.request()['instruments'][0]['level'],56)
        self.assertEqual(store.control.request()['activeNotes'],0)
        self.start_web();self.assertTrue(self.remote('status')['liveMatchesRestart'])
if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.TestSuite([AuthorityTests('test_authority')]))
    sys.exit(not result.wasSuccessful())

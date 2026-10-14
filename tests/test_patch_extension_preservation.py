"""Production native HTTP + immutable project staging: reject lossy envelopes."""
import copy
import json
from pathlib import Path
import sys
import unittest
import urllib.request
import urllib.error
from test_headless_mvp import HeadlessTests,ROOT
sys.path.insert(0,str(ROOT/'headless'))
from server import Control,validate_patch_extensions
import portable_project as portable

class PatchEnvelopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        HeadlessTests.setUpClass();cls.api=HeadlessTests('runTest');cls.control=Control(cls.api.sock)
    @classmethod
    def tearDownClass(cls):HeadlessTests.tearDownClass()
    def setUp(self):
        self.api.command('panic')
        state=self.api.call();self.patch=self.control.request(op=4,revision=state['revision'],session=state['engineSessionId'])
        self.file=Path(self.api.temp.name)/'patches/patch1.json';self.file.parent.mkdir(exist_ok=True)
    def remote(self,path,body,expected):
        req=urllib.request.Request(self.api.base+'/api/v1/'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        try:response=urllib.request.urlopen(req,timeout=5)
        except urllib.error.HTTPError as error:response=error
        self.assertEqual(response.status,expected);return json.load(response)
    def slot(self,action,expected):
        state=self.api.call()
        return self.remote('patch/'+action,dict(slot=1,expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId']),expected)
    def test_unknown_extension_fields_refuse_save_load_export_without_mutation(self):
        for extension in ('controllerEngine','globalSnapshots'):
            patch=copy.deepcopy(self.patch);patch[extension]['futurePerformanceData']={'preserve':[1,2,3]}
            self.file.write_text(json.dumps(patch));original=self.file.read_bytes()
            revision=self.api.call()['revision']
            for action in ('save','load','export'):
                with self.subTest(extension=extension,action=action):
                    response=self.slot(action,422);self.assertIn('preserved',response['error'])
                    self.assertEqual(self.file.read_bytes(),original)
                    self.assertEqual(self.api.call()['revision'],revision)
    def test_known_generated_envelopes_save_load_and_source_roundtrip(self):
        self.file.unlink(missing_ok=True)
        self.slot('save',200);saved=json.loads(self.file.read_text())
        for key in ('controllerEngine','globalSnapshots'):self.assertEqual(set(saved[key]),{'version','configuration'})
        self.slot('load',200);self.slot('save',200)
        after=json.loads(self.file.read_text())
        for key in ('controllerEngine','globalSnapshots'):self.assertEqual(after[key],saved[key])
    def test_legacy_without_native_extensions_still_loads(self):
        patch=copy.deepcopy(self.patch)
        patch.pop('controllerEngine');patch.pop('globalSnapshots')
        self.file.write_text(json.dumps(patch));self.slot('load',200)
    def test_unknown_data_cannot_be_staged_as_executable_portable_revision(self):
        for extension in ('controllerEngine','globalSnapshots'):
            project=portable.capture(self.patch,self.api.call()['sampleRate'])
            project['payload']['patch'][extension]['futurePerformanceData']={'preserve':True}
            unsigned={key:value for key,value in project.items() if key not in ('revisionId','contentHash')}
            project['revisionId']=portable.digest(unsigned)
            project['contentHash']=portable.digest({key:value for key,value in project.items() if key!='contentHash'})
            state=self.api.call()
            self.remote('project/stage',dict(project=project,expectedActiveRevisionId=None),422)
            projects=self.file.parent/'projects'
            self.assertFalse((projects/(project['revisionId']+'.json')).exists())
            self.assertFalse((projects/'active.json').exists())
            self.assertEqual(self.api.call()['revision'],state['revision'])
    def test_missing_configuration_is_not_silently_overwritten(self):
        for extension in ('controllerEngine','globalSnapshots'):
            patch=copy.deepcopy(self.patch);del patch[extension]['configuration']
            self.file.write_text(json.dumps(patch));original=self.file.read_bytes()
            self.slot('save',422);self.assertEqual(self.file.read_bytes(),original)
if __name__=='__main__':unittest.main()

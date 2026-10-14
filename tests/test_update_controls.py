"""Actual HTTP/Unix update bridge and filesystem rollback; no device services."""
import base64
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'zynthian/update'));sys.path.insert(0,str(ROOT/'headless'))
import backend
from server import make_server
SHA='a'*40
PASSWORD='test-admin-password'

def release_fetch(url):
    if url.endswith('/latest'):return dict(draft=False,prerelease=False,tag_name='v-test',name='Test release',body='Reviewed changes',assets=[dict(name='mbmf-update.json',browser_download_url='https://github.com/'+backend.REPO+'/releases/download/v-test/mbmf-update.json')])
    if url.endswith('mbmf-update.json'):return dict(version=1,revision=SHA,components=dict(engine=1,adapter=1,editor=1))
    if '/compare/' in url:return dict(status='ahead',merge_base_commit=dict(sha=SHA))
    return dict(sha=SHA)

class UpdateControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name);self.config=self.directory/'install.json'
        self.config.write_text(json.dumps(dict(version=1,repository=str(ROOT),binary='unused',runtime_revision='b'*40,unknown={'keep':True})))
        (self.directory/'update-admin.json').write_text(json.dumps(backend.password_record(PASSWORD)))
        self.backend=backend.Backend(self.config,fetch=release_fetch)
    def wait(self):
        deadline=time.monotonic()+5
        while self.backend.busy and time.monotonic()<deadline:time.sleep(.01)
        self.assertFalse(self.backend.busy)
    def test_published_release_requires_components_merged_sha_and_matching_tag(self):
        self.assertEqual(backend.reviewed_release(release_fetch)['revision'],SHA)
        for key,value in [('draft',True),('prerelease',True)]:
            def bad(url):
                result=release_fetch(url)
                if url.endswith('/latest'):result[key]=value
                return result
            with self.assertRaisesRegex(ValueError,'published stable'):backend.reviewed_release(bad)
        def unmerged(url):
            if '/compare/' in url:return dict(status='diverged',merge_base_commit=dict(sha='c'*40))
            return release_fetch(url)
        with self.assertRaisesRegex(ValueError,'merged'):backend.reviewed_release(unmerged)
        def mismatch(url):
            if '/commits/' in url:return dict(sha='c'*40)
            return release_fetch(url)
        with self.assertRaisesRegex(ValueError,'tag'):backend.reviewed_release(mismatch)
        def incompatible(url):
            result=release_fetch(url)
            if url.endswith('mbmf-update.json'):result['components']['engine']=2
            return result
        with self.assertRaisesRegex(ValueError,'component'):backend.reviewed_release(incompatible)
    def test_separate_password_confirmation_revision_and_busy_gates(self):
        with self.assertRaises(PermissionError):self.backend.request(dict(action='check',password='editor-token'))
        self.backend.request(dict(action='check',password=PASSWORD));self.wait()
        self.assertEqual(self.backend.status()['available']['revision'],SHA)
        with self.assertRaisesRegex(ValueError,'confirmation'):self.backend.request(dict(action='install',password=PASSWORD,revision=SHA))
        with self.assertRaisesRegex(ValueError,'exact revision'):self.backend.request(dict(action='install',password=PASSWORD,confirm=True,revision='main'))
        self.backend.busy=True
        with self.assertRaisesRegex(ValueError,'already'):self.backend.request(dict(action='check',password=PASSWORD))
    def test_archive_cache_integrity_refuses_changed_binary(self):
        import hashlib
        root=self.directory/'releases'/SHA;root.mkdir(parents=True)
        (root/'.mbmf-release-revision').write_text(SHA)
        files={}
        for name in ('.build/midi-headless-engine','midi_human_looper.jsfx','headless/server.py','zynthian/zynthian_engine_mbh.py'):
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixed source')
            files[name]=hashlib.sha256(path.read_bytes()).hexdigest()
        (root/'.mbmf-release-integrity.json').write_text(json.dumps(files))
        with patch.object(self.backend.u.shutil,'which',return_value='/tool'):
            self.assertEqual(self.backend.u.build(self.directory,SHA)[0],root)
            (root/'.build/midi-headless-engine').write_bytes(b'changed executable')
            with self.assertRaisesRegex(ValueError,'modified'):self.backend.u.build(self.directory,SHA)
    def test_no_eligible_release_never_retains_old_candidate(self):
        self.backend.available={'revision':SHA}
        self.backend.fetch=lambda url:(_ for _ in ()).throw(ValueError('No published release'))
        self.backend.request(dict(action='check',password=PASSWORD));self.wait()
        self.assertIsNone(self.backend.status()['available']);self.assertEqual(self.backend.status()['progress']['phase'],'error')
    def test_live_playback_refusal_occurs_before_build_and_activation(self):
        runtime=type('Runtime',(),{'checkpoint':lambda *a:(_ for _ in ()).throw(ValueError('STOP all MBMF processors'))})()
        self.backend.available={'revision':SHA}
        with patch.object(self.backend.u,'Runtime',return_value=runtime),patch.object(self.backend.u,'build') as build:
            self.backend.request(dict(action='install',password=PASSWORD,confirm=True,revision=SHA));self.wait()
            build.assert_not_called()
            self.assertIn('STOP',self.backend.status()['progress']['message'])
        self.assertEqual(json.loads(self.config.read_text())['unknown'],{'keep':True})
    def test_components_and_config_restore_after_health_failure(self):
        adapter=self.directory/'adapter.py';adapter.write_bytes(b'old adapter')
        journal=dict(version=1,phase='pending',previous=json.loads(self.config.read_text()),candidate={},expected={},components=[dict(path=str(adapter),before=base64.b64encode(b'old adapter').decode(),after=base64.b64encode(b'new adapter').decode(),mode=0o640)])
        calls=[]
        class Runtime:
            apply_components=self.backend.apply_components
            restore_components=self.backend.restore_components
            def service(self,action):calls.append(action)
            def healthy(self,config,expected):
                if config.get('runtime_revision')==SHA:raise ValueError('candidate health failed')
        old=self.config.read_bytes()
        with self.assertRaisesRegex(ValueError,'health'):
            self.backend.u.activate(self.config,{**json.loads(old),'runtime_revision':SHA},Runtime(),{},journal)
        self.assertEqual(adapter.read_bytes(),b'old adapter')
        self.assertEqual(json.loads(self.config.read_text()),json.loads(old))
        self.assertEqual(json.loads((self.directory/'runtime-update.json').read_text())['phase'],'rolled-back')
        self.assertEqual(calls,['stop','start','stop','start'])
    def test_actual_http_to_unix_worker_auth_csrf_and_native_field_rejection(self):
        # Cloud user is not root: only kernel credential identity is a fixture.
        # HTTP, Unix sockets, password verification and backend remain real.
        peers=patch.object(backend,'peer_uid',return_value=0);peers.start();self.addCleanup(peers.stop)
        socket_path=self.directory/'update.sock';stop=threading.Event()
        worker=threading.Thread(target=backend.serve,args=(self.backend,socket_path,stop),daemon=True);worker.start()
        deadline=time.monotonic()+2
        while not socket_path.exists() and time.monotonic()<deadline:time.sleep(.01)
        server=make_server('127.0.0.1',0,'unused',patch_dir=str(self.directory))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        def request(data,origin_header=origin):
            headers={'Content-Type':'application/json'}
            if origin_header:headers['Origin']=origin_header
            req=urllib.request.Request(origin+'/api/v1/update',data=json.dumps(data).encode(),headers=headers)
            return json.load(urllib.request.urlopen(req))
        try:
            with patch.object(backend,'client',wraps=lambda action,**fields:original(action,socket_path,**fields)):
                self.assertEqual(json.load(urllib.request.urlopen(origin+'/api/v1/update'))['installed'],'b'*40)
                for data,orig in [(dict(action='check'),origin),(dict(action='check',password=PASSWORD),None),(dict(action='check',password=PASSWORD),'http://evil.local'),(dict(action='check',native=True),origin)]:
                    with self.assertRaises(urllib.error.HTTPError) as error:request(data,orig)
                    self.assertEqual(error.exception.code,403)
                self.assertTrue(request(dict(action='check',password=PASSWORD))['accepted']);self.wait()
                self.assertEqual(json.load(urllib.request.urlopen(origin+'/api/v1/update'))['progress']['phase'],'ready')
                self.assertEqual(urllib.request.urlopen(origin+'/update.js').status,200)
        finally:
            server.shutdown();server.server_close();thread.join(2);stop.set();worker.join(2)

original=backend.client
if __name__=='__main__':unittest.main()

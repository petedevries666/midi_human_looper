#!/usr/bin/env python3
"""Filesystem transactions with explicit mocked UI restart, never device access."""
import importlib.util,json,tempfile,unittest,os,subprocess,time,threading,types
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('update',ROOT/'scripts/zynthian-update.py')
u=importlib.util.module_from_spec(spec);spec.loader.exec_module(u)
class Service:
    def __init__(self,fail=False):self.calls=[];self.fail=fail
    def service(self,action):self.calls.append(action)
    def healthy(self,config,expected):
        self.calls.append(config['binary'])
        if self.fail and config['binary']=='new':raise ValueError('candidate failed')
class Updates(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name);self.config=self.directory/'install.json'
        self.old={'version':1,'repository':'old','binary':'old','token_file':'kept','web_port_base':8765,'unknown':{'preserve':True}}
        u.atomic(self.config,self.old);self.config.chmod(0o640)
        self.new={**self.old,'repository':'new','binary':'new','runtime_revision':'a'*40}
    def test_upgrade_atomic_preserves_configuration_and_file_mode(self):
        service=Service();u.activate(self.config,self.new,service,{'processor-2':'fingerprint'})
        self.assertEqual(json.loads(self.config.read_text()),self.new)
        self.assertEqual(self.config.stat().st_mode&0o777,0o640)
        self.assertEqual(service.calls,['stop','start','new'])
        history=json.loads((self.directory/'runtime-update.json').read_text())
        self.assertEqual(history['previous'],self.old);self.assertEqual(history['phase'],'active')
    def test_preflight_journal_refuses_concurrent_config_edit_before_any_mutation(self):
        history=self.directory/'runtime-update.json';history.write_text(json.dumps(dict(version=1,phase='active',previous=self.old,candidate=self.new,expected={})))
        prior=history.read_bytes();changed={**self.old,'web_port_base':9000,'unknown':{'keep':'concurrent'}}
        u.atomic(self.config,changed);config_bytes=self.config.read_bytes()
        journal=dict(version=1,phase='pending',previous=self.old,candidate=self.new,expected={})
        service=Service()
        with self.assertRaisesRegex(ValueError,'changed after preflight'):
            u.activate(self.config,self.new,service,{},journal)
        self.assertEqual(service.calls,[])
        self.assertEqual(self.config.read_bytes(),config_bytes)
        self.assertEqual(history.read_bytes(),prior)
    def test_legacy_cli_expected_configuration_uses_same_refusal(self):
        changed={**self.old,'web_port_base':9000};u.atomic(self.config,changed);service=Service()
        with self.assertRaisesRegex(ValueError,'changed after preflight'):
            u.activate(self.config,self.new,service,{},expected_config=self.old)
        self.assertEqual(service.calls,[])
        self.assertEqual(json.loads(self.config.read_text()),changed)
        self.assertFalse((self.directory/'runtime-update.json').exists())
    def test_matching_preflight_journal_still_activates(self):
        journal=dict(version=1,phase='pending',previous=self.old,candidate=self.new,expected={})
        service=Service();u.activate(self.config,self.new,service,{},journal)
        self.assertEqual(service.calls,['stop','start','new'])
        self.assertEqual(json.loads(self.config.read_text()),self.new)
    def test_failed_activation_restores_old_configuration(self):
        service=Service(True)
        with self.assertRaisesRegex(ValueError,'candidate failed'):u.activate(self.config,self.new,service,{})
        self.assertEqual(json.loads(self.config.read_text()),self.old)
        self.assertEqual(service.calls,['stop','start','new','stop','start','old'])
        self.assertEqual(json.loads((self.directory/'runtime-update.json').read_text())['phase'],'rolled-back')
    def test_rollback_keeps_new_project_content(self):
        project=self.directory/'processor-2';project.mkdir();(project/'patch1.json').write_text('musical edits')
        service=Service();u.activate(self.config,self.new,service,{})
        prior=json.loads((self.directory/'runtime-update.json').read_text())['previous']
        u.activate(self.config,prior,service,{})
        self.assertEqual(json.loads(self.config.read_text()),self.old)
        self.assertEqual((project/'patch1.json').read_text(),'musical edits')
    def test_interruption_leaves_recoverable_journal_before_stop(self):
        service=Service()
        service.service=lambda action:(_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaisesRegex(RuntimeError,'rollback needs recovery'):u.activate(self.config,self.new,service,{})
        journal=json.loads((self.directory/'runtime-update.json').read_text())
        self.assertEqual(journal['phase'],'pending');self.assertEqual(journal['previous'],self.old)
        self.assertEqual(json.loads(self.config.read_text()),self.old)
    def test_repeated_activation_keeps_immediate_previous(self):
        service=Service();u.activate(self.config,self.new,service,{})
        newer={**self.new,'runtime_revision':'b'*40};u.activate(self.config,newer,service,{})
        self.assertEqual(json.loads((self.directory/'runtime-update.json').read_text())['previous'],self.new)
    def test_build_rejects_bad_revision_before_network(self):
        with patch.object(u,'run') as run:
            with self.assertRaises(ValueError):u.build(self.directory,'main;evil')
            run.assert_not_called()
    @unittest.skipUnless(os.environ.get('HEADLESS_BINARY'),'Actual engine not configured')
    def test_real_native_preflight_engine(self):
        runtime=u.Runtime(ROOT)
        runtime.preflight({'binary':os.environ['HEADLESS_BINARY'],'repository':str(ROOT)},self.directory)
    @unittest.skipUnless(os.environ.get('HEADLESS_BINARY'),'Actual engine not configured')
    def test_authenticated_real_web_health_and_revision(self):
        runtime=u.Runtime(ROOT);data=self.directory/'processor-1';data.mkdir()
        socket=data/'control.sock';token=self.directory/'token';token.write_text('test-private-token')
        process=subprocess.Popen([os.environ['HEADLESS_BINARY'],str(ROOT/'midi_human_looper.jsfx'),str(socket),'--demo'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            deadline=time.monotonic()+5
            while not socket.exists():
                if process.poll() is not None or time.monotonic()>deadline:self.fail('native startup failed')
                time.sleep(.01)
            from server import make_server
            server=make_server('127.0.0.1',0,str(socket),'test-private-token',str(data))
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:
                capture=runtime.ProjectStore(data,runtime.Control(str(socket))).capture()
                config={**self.old,'_directory':str(self.directory),'token_file':str(token),
                        'runtime_revision':runtime.Control(str(socket)).request()['buildRevision'],
                        'web_port_base':server.server_address[1]-1}
                expected={'processor-1':{'fingerprint':capture['fingerprint'],'buildRevision':config['runtime_revision']}}
                with patch.object(u.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)):
                    runtime.healthy(config,expected,timeout=2)
                    with self.assertRaisesRegex(ValueError,'health/state'):
                        runtime.healthy({**config,'runtime_revision':'wrong'},expected,timeout=.1)
            finally:server.shutdown();server.server_close();thread.join(timeout=2)
        finally:process.terminate();process.wait(timeout=5)
    def test_grid_rollback_rejects_free_time_without_mutating_source(self):
        import copy
        for rate in (44100,48000,96000):
            for block in (64,128,512,1024):
                for timing in (1,2):
                    state=dict(sampleRate=rate,blockSize=block,chainBpm=123)
                    exact=rate*480/123
                    period=int(exact+.5) if timing==2 else int(exact/block+.5)*block
                    memory=[0]*164000;memory[163840]=2;memory[163952]=period
                    patch=dict(globals=[period],memory=memory)
                    u.validate_grid_restore(patch,state,timing)
                    patch['globals'][0]=period+1;original=copy.deepcopy(patch)
                    with self.assertRaisesRegex(ValueError,'no truncation'):u.validate_grid_restore(patch,state,timing)
                    self.assertEqual(patch,original)
                    patch['globals'][0]=period;memory[163952]=period+4096
                    with self.assertRaisesRegex(ValueError,'independent LOOP'):u.validate_grid_restore(patch,state,timing)
                    memory[163904]=1 # ONCE supports its own length on the previous runtime.
                    u.validate_grid_restore(patch,state,timing)
    def test_independent_instance_rest_or_movement_refuses_checkpoint(self):
        runtime=u.Runtime(ROOT)
        for state in ({'instances':[{'active':True,'ownedOutputs':0}]},{'movements':{'active':1}}):
            data=self.directory/'processor-1';data.mkdir(exist_ok=True)
            (data/'control.sock').touch()
            runtime.Control=lambda path:types.SimpleNamespace(request=lambda:state)
            with self.assertRaisesRegex(ValueError,'STOP all'):runtime.checkpoint(self.directory)
    def test_checkpoint_precedes_candidate_validation(self):
        source=(ROOT/'scripts/zynthian-update.py').read_text()
        self.assertLess(source.index('expected=runtime.checkpoint(directory)'),source.index('verified_revision=runtime.preflight(new,directory)'))
    def test_arm64_signed_char_applies_to_library_and_host(self):
        source=(ROOT/'scripts/zynthian-update.py').read_text()
        self.assertIn('-DCMAKE_C_FLAGS=-fsigned-char',source)
        self.assertIn('-DCMAKE_CXX_FLAGS=-fsigned-char',source)
        self.assertIn('-fsigned-char',(ROOT/'scripts/headless-build.sh').read_text())
        self.assertNotIn('apt-get',source)
if __name__=='__main__':unittest.main()

"""Reviewed updates. Runs outside JACK, independently of editor / Zynthian UI.

The only network release authority is a published GitHub release with an explicit
component contract. Editor tokens never authorize executable installation.
"""
import base64
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import threading
import time
import urllib.request
import urllib.parse
import urllib.error

REPO = 'petedevries666/midi_human_looper'
ROOT = Path(__file__).resolve().parents[2]
CONFIG = Path('/zynthian/zynthian-my-data/midi-human-looper/install.json')
SOCKET = '/run/mbmf-update.sock'

def updater():
    spec = importlib.util.spec_from_file_location('mbmf_runtime_update', ROOT/'scripts/zynthian-update.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

def password_record(password):
    if len(password) < 12:raise ValueError('Use at least 12 characters for the update administrator password')
    salt = os.urandom(16)
    return dict(salt=salt.hex(), digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,300000).hex())

def verify_password(password, record):
    return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(record['salt']),300000).hex(),record['digest'])

def fetch_json(url):
    request=urllib.request.Request(url,headers={'Accept':'application/vnd.github+json','User-Agent':'MBMF-reviewed-updater'})
    with urllib.request.urlopen(request,timeout=15) as response:
        data=response.read(131073)
    if len(data)>131072:raise ValueError('Release metadata exceeds limit')
    return json.loads(data)

def reviewed_release(fetch=fetch_json):
    try:release=fetch('https://api.github.com/repos/'+REPO+'/releases/latest')
    except urllib.error.HTTPError as error:
        if error.code==404:raise ValueError('No published reviewed stable release available') from error
        raise
    if release.get('draft') or release.get('prerelease'):raise ValueError('Only published stable releases are eligible')
    assets=[a for a in release.get('assets',[]) if a.get('name')=='mbmf-update.json']
    if len(assets)!=1:raise ValueError('No reviewed component manifest; no update offered')
    url=assets[0]['browser_download_url']
    if not url.startswith('https://github.com/'+REPO+'/releases/download/'):raise ValueError('Unexpected manifest origin')
    contract=fetch(url)
    revision=contract.get('revision','')
    if len(revision)!=40 or any(c not in '0123456789abcdef' for c in revision):raise ValueError('Release requires a pinned full SHA')
    if contract.get('version')!=1 or contract.get('components')!={'engine':1,'adapter':1,'editor':1}:
        raise ValueError('Incompatible component contract')
    # Published release alone is insufficient: only merged main ancestors may be
    # installed. Draft branches and release tags pointing at them are rejected.
    comparison=fetch('https://api.github.com/repos/'+REPO+'/compare/'+revision+'...main')
    if comparison.get('status') not in ('ahead','identical') or comparison.get('merge_base_commit',{}).get('sha')!=revision:
        raise ValueError('Release commit is not merged into main')
    tag=release.get('tag_name','')
    commit=fetch('https://api.github.com/repos/'+REPO+'/commits/'+urllib.parse.quote(tag,safe=''))
    if commit.get('sha')!=revision:raise ValueError('Release tag and manifest revision differ')
    return dict(revision=revision, name=release.get('name') or tag,
                changes=str(release.get('body',''))[:8000], components=contract['components'])

class Backend:
    def __init__(self, config=CONFIG, fetch=fetch_json):
        self.config=Path(config); self.directory=self.config.parent; self.u=updater();self.fetch=fetch
        self.lock=threading.Lock(); self.available=None; self.busy=False
        self.progress=dict(phase='idle',message='No update running')
        self.status_file=self.directory/'update-control-status.json'
        if self.status_file.exists():
            self.progress=json.loads(self.status_file.read_text())
            if self.progress.get('phase') in ('checking','building','preflight','activating'):
                self.progress=dict(phase='interrupted',message='Previous worker interrupted; recover before installing')
    def report(self, phase, message):
        with self.lock:
            self.progress=dict(phase=phase,message=message,time=time.time())
            self.u.atomic(self.status_file,self.progress)
    def status(self):
        config=json.loads(self.config.read_text())
        installed=config.get('runtime_revision')
        observed=[]
        for path in self.directory.glob('processor-*/control.sock'):
            try:
                runtime=self.u.Runtime(config['repository'])
                observed.append(runtime.Control(str(path)).request()['buildRevision'])
            except (OSError,ValueError,KeyError):pass
        if observed:installed=', '.join(sorted(set(observed)))
        if not installed:
            installed='unknown (no active processor or recorded installed revision)'
        history=self.directory/'runtime-update.json'
        journal=json.loads(history.read_text()) if history.exists() else {}
        with self.lock:
            return dict(installed=installed,available=self.available,progress=dict(self.progress),busy=self.busy,
                        rollbackAvailable=journal.get('phase')=='active',recoveryRequired=journal.get('phase')=='pending',
                        version=self.application_version(config),restart='Zynthian UI (MBMF children are UI-owned); JACK and LUMAZ are not restarted')
    def application_version(self, config):
        import re
        try:
            match=re.search(r'^desc:.* v(\d+\.\d+\.\d+)',(Path(config['repository'])/'midi_human_looper.jsfx').read_text(),re.M)
            return match.group(1) if match else 'unknown'
        except OSError:return 'unknown'
    def authorize(self, request, native=False):
        if native:return # Kernel-verified root peer, never an HTTP field.
        password=request.get('password','')
        if not isinstance(password,str) or len(password)>512:raise PermissionError('Administrator authorization required')
        record=json.loads((self.directory/'update-admin.json').read_text())
        if not verify_password(password,record):raise PermissionError('Administrator authorization required')
    def request(self, request, native=False):
        action=request.get('action')
        if action=='status':return self.status()
        if action not in ('check','install','rollback','recover'):raise ValueError('Unknown update action')
        # Check can consume network/CPU; authorize it too. Tokenless LAN callers
        # cannot start jobs or grind password hashing without a bounded worker.
        self.authorize(request,native)
        with self.lock:
            if self.busy:raise ValueError('An update operation is already running')
            if action!='check' and request.get('confirm') is not True:raise ValueError('Explicit confirmation required')
            if action=='install' and (not self.available or request.get('revision')!=self.available['revision']):
                raise ValueError('Check reviewed release and confirm its exact revision first')
            self.busy=True
        thread=threading.Thread(target=self.work,args=(action,),daemon=True);thread.start()
        return dict(accepted=True,action=action)
    def work(self, action):
        try:
            if action=='check':
                with self.lock:self.available=None
                self.report('checking','Checking published stable release and merged ancestry')
                candidate=reviewed_release(self.fetch)
                with self.lock:self.available=candidate
                self.report('ready','Reviewed release '+candidate['revision'][:12]);return
            import fcntl
            with (self.directory/'runtime-update.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                old=json.loads(self.config.read_text());runtime=self.u.Runtime(old['repository'])
                history=self.directory/'runtime-update.json'
                previous=json.loads(history.read_text()) if history.exists() else {}
                if action=='recover':
                    if previous.get('phase') in ('active','rolled-back') and (self.directory/'update-admission.json').exists():
                        runtime.resume_admission(self.directory)
                        self.report('complete','Verified runtime retained; interrupted admission fence released');return
                    if previous.get('phase')!='pending':raise ValueError('No interrupted activation')
                    with runtime.quiesce(self.directory,recover=True) as gate:
                        gate.retain=True
                        runtime.service('stop');self.restore_components(previous)
                        self.u.atomic(self.config,previous['previous']);runtime.service('start')
                        runtime.healthy({**previous['previous'],'_directory':str(self.directory)},previous['expected'])
                        self.u.atomic(history,{**previous,'phase':'rolled-back'})
                        gate.retain=False
                    self.report('complete','Interrupted activation recovered');return
                if previous.get('phase')=='pending':raise ValueError('Recover interrupted activation before retrying')
                # Refuse playback before network, build or checkpoint work.
                self.report('preflight','Verifying all processors are stopped; checkpointing projects')
                expected=runtime.checkpoint(self.directory)
                if action=='rollback':
                    if previous.get('phase')!='active':raise ValueError('No working previous version')
                    new=previous['previous']
                else:
                    with self.lock:reviewed=dict(self.available)
                    # Revalidate authority immediately before execution.
                    current=reviewed_release(self.fetch)
                    if current['revision']!=reviewed['revision']:raise ValueError('Release changed; check and confirm again')
                    self.report('building','Building reviewed archive using existing checkout; no second clone')
                    root,binary=self.u.build(self.directory,reviewed['revision'],self.checkout(old))
                    new={**old,'repository':str(root),'binary':str(binary),'runtime_revision':reviewed['revision'],'update_checkout':str(self.checkout(old))}
                runtime.require_update_controls=action=='install'
                self.report('preflight','Validating candidate engine, projects and adapter ownership')
                revision=runtime.preflight(new,self.directory)
                if revision!=new.get('runtime_revision'):raise ValueError('Candidate binary identity differs')
                journal=dict(version=1,phase='pending',previous=old,candidate=new,expected=expected)
                journal['components']=self.prepare_components(new,previous if action=='rollback' else None)
                # Check again after the potentially long build: never switch after
                # somebody resumes playback while the progress view is open.
                expected=runtime.checkpoint(self.directory)
                journal['expected']=expected
                runtime.apply_components=self.apply_components;runtime.restore_components=self.restore_components
                self.report('activating','Restarting UI-owned runtime; JACK service unchanged')
                self.u.activate(self.config,new,runtime,expected,journal)
                self.report('complete','Activated '+revision[:12]+'; musical projects verified')
        except Exception as error:self.report('error',str(error))
        finally:
            with self.lock:self.busy=False
    def checkout(self, config):
        path=Path(config.get('update_checkout',config['repository']))
        subprocess.run(['git','-C',str(path),'rev-parse','--git-dir'],check=True,stdout=subprocess.DEVNULL)
        return path
    def prepare_components(self,new,previous=None):
        # Registration/routing policies cannot be silently upgraded by a runtime
        # update. Owned adapter alone is supported, with its installer manifest.
        manifest=self.directory/'installation.json'
        metadata=json.loads(manifest.read_text())
        if metadata.get('version')!=2:raise ValueError('Upgrade installer ownership manifest before using UPDATE')
        adapter=Path('/zynthian/zynthian-ui/zyngine/zynthian_engine_mbh.py')
        record=metadata['files']['adapter']
        if hashlib.sha256(adapter.read_bytes()).hexdigest()!=record['installed_sha256']:
            raise ValueError('Installed adapter was edited; refusing overwrite')
        candidate=Path(new['repository'])/'zynthian/zynthian_engine_mbh.py'
        content=candidate.read_bytes()
        import ast
        tree=ast.parse(content)
        classes=[node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='zynthian_engine_mbh']
        if not previous and (not classes or not any(isinstance(node,ast.FunctionDef) and node.name=='update_control' for node in classes[0].body)):
            raise ValueError('Candidate adapter lacks UPDATE protocol-1 controls')
        # Helpers affecting #67 filtering must retain their precise installed
        # identity. A release requiring new native routing needs reviewed setup.
        for key,relative in [('helper','zynthian/zynthian_engine_mbh_catalog.py'),('router','zynthian/zynthian_engine_mbh_router.py')]:
            if key in metadata['files']:
                path=Path(new['repository'])/relative
                if hashlib.sha256(path.read_bytes()).hexdigest()!=metadata['files'][key]['installed_sha256']:
                    raise ValueError('Release requires separate reviewed '+key+' integration upgrade')
        before=adapter.read_bytes();after_metadata=json.loads(json.dumps(metadata))
        after_metadata['files']['adapter']['installed_sha256']=hashlib.sha256(content).hexdigest()
        if previous and previous.get('components'):
            originals={v['path']:base64.b64decode(v['before']) for v in previous['components']}
            content=originals[str(adapter)]
            after_metadata=json.loads(originals[str(manifest)])
        return [dict(path=str(path),before=base64.b64encode(before_bytes).decode(),after=base64.b64encode(after_bytes).decode(),mode=path.stat().st_mode&0o777)
                for path,before_bytes,after_bytes in [(adapter,before,content),(manifest,manifest.read_bytes(),json.dumps(after_metadata,indent=2).encode())]]
    def write_components(self,journal,side):
        for change in journal.get('components',[]):
            path=Path(change['path']);data=base64.b64decode(change[side]);mode=change['mode']
            import tempfile
            fd,name=tempfile.mkstemp(dir=path.parent,prefix='.'+path.name)
            try:
                with os.fdopen(fd,'wb') as stream:
                    os.fchmod(stream.fileno(),mode);stream.write(data);stream.flush();os.fsync(stream.fileno())
                os.replace(name,path)
                parent=os.open(path.parent,os.O_RDONLY)
                try:os.fsync(parent)
                finally:os.close(parent)
            finally:
                if os.path.exists(name):os.unlink(name)
    def apply_components(self,journal):self.write_components(journal,'after')
    def restore_components(self,journal):self.write_components(journal,'before')

def client(action, socket_path=SOCKET, **fields):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(5);connection.connect(str(socket_path))
        connection.sendall(json.dumps(dict(action=action,**fields)).encode()+b'\n')
        stream=connection.makefile('rb');response=json.loads(stream.readline(65537))
    if 'error' in response:raise ValueError(response['error'])
    return response

def peer_uid(connection):
    return struct.unpack('3i',connection.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]

def serve(backend,path=SOCKET,stop=None):
    # One bounded serial request handler: credential hashing and client workload
    # cannot allocate unlimited threads or interfere with the MIDI callback.
    with socket.socket(socket.AF_UNIX) as server:
        if os.path.exists(path):raise ValueError('Occupied updater socket; do not remove an active worker')
        server.bind(str(path));os.chmod(path,0o600);server.listen(4);server.settimeout(.25)
        try:
            while stop is None or not stop.is_set():
                try:connection,_=server.accept()
                except socket.timeout:continue
                with connection:
                    connection.settimeout(3)
                    try:
                        uid=peer_uid(connection)
                        if uid!=0:raise PermissionError('Root local peer required')
                        request=json.loads(connection.makefile('rb').readline(4097))
                        if not isinstance(request,dict):raise ValueError('Invalid request')
                        native=request.pop('native',False) is True
                        response=backend.request(request,native=native)
                    except (OSError,ValueError,PermissionError,KeyError) as error:response={'error':str(error)}
                    try:connection.sendall(json.dumps(response).encode()+b'\n')
                    except OSError:pass
        finally:os.unlink(path)

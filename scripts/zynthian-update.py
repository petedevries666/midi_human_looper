#!/usr/bin/env python3
"""Runtime-only update. No package, registration, JACK graph or OS changes."""
import argparse
import fcntl
import importlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time

PIN='8077347ccf4115567aed81400281dca57acbb0cc'
REPOSITORY='https://github.com/petedevries666/midi_human_looper.git'

def run(*args, **kw):
    return subprocess.run(args, check=True, **kw)

def atomic(path, value):
    path=Path(path)
    mode=path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd,name=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            os.fchmod(stream.fileno(),mode)
            json.dump(value,stream);stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
        fd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if os.path.exists(name):os.unlink(name)

def build(directory, revision):
    if platform.machine() not in ('aarch64','armv7l','x86_64'):
        raise ValueError('Unsupported CPU; no installation changed')
    if len(revision)!=40 or any(c not in '0123456789abcdef' for c in revision):
        raise ValueError('Use a reviewed full 40-character commit SHA')
    for tool in ('git','cmake','c++','pkg-config'):
        if not shutil.which(tool):raise ValueError('Missing '+tool+'; prepare build dependencies separately')
    root=directory/'releases'/revision
    if root.exists():
        actual=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
        dirty=subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'],text=True)
        if actual!=revision or dirty:raise ValueError('Existing release was modified; refusing reuse')
    else:
        root.parent.mkdir(exist_ok=True)
        run('git','clone','--no-checkout',REPOSITORY,str(root))
        run('git','-C',str(root),'checkout','--detach',revision)
    # Rebuild the entire pinned library with signed char, including WDL on ARM64.
    ysfx=root/'.build/ysfx'
    ysfx.parent.mkdir(parents=True,exist_ok=True)
    if not ysfx.exists():run('git','clone','https://github.com/jpcima/ysfx.git',str(ysfx))
    if subprocess.check_output(['git','-C',str(ysfx),'status','--porcelain'],text=True).strip():
        raise ValueError('Modified third-party source; refusing build')
    run('git','-C',str(ysfx),'checkout',PIN)
    run('git','-C',str(ysfx),'submodule','update','--init','--recursive')
    run('cmake','-S',str(ysfx),'-B',str(ysfx/'build'),'-DYSFX_PLUGIN=OFF','-DYSFX_TOOLS=ON',
        '-DCMAKE_BUILD_TYPE=Release','-DCMAKE_C_FLAGS=-fsigned-char','-DCMAKE_CXX_FLAGS=-fsigned-char')
    run('cmake','--build',str(ysfx/'build'),'--parallel','2')
    binary=root/'.build/midi-headless-engine'
    run('bash',str(root/'scripts/headless-build.sh'),env={**os.environ,
        'YSFX_SOURCE':str(ysfx),'YSFX_BUILD':str(ysfx/'build'),'HEADLESS_BINARY':str(binary)})
    return root,binary

class Runtime:
    def __init__(self, root):
        sys.path.insert(0,str(Path(root)/'headless'))
        self.Control=importlib.import_module('server').Control
        self.ProjectStore=importlib.import_module('project_sync').ProjectStore
    def checkpoint(self, directory):
        result={}
        for socket in directory.glob('processor-*/control.sock'):
            state=self.Control(str(socket)).request()
            if state.get('chainRunning') or state.get('chainRecording') or state.get('chainArmed') or state.get('recording') or state.get('activeNotes') or state.get('targetSnapshotId'):
                raise ValueError('STOP all MBMF processors, finish REC and morphs before updating')
            store=self.ProjectStore(socket.parent,self.Control(str(socket)))
            captured=store.capture()
            result[socket.parent.name]={'fingerprint':captured['fingerprint'],'buildRevision':state['buildRevision']}
            store.checkpoint(dict(expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'],
                                  expectedActiveRevisionId=captured['activeRevisionId']))
        return result
    def preflight(self, config, directory):
        run(config['binary'],'--queue-test')
        with tempfile.TemporaryDirectory(prefix='mbmf-preflight-') as temporary:
            socket=str(Path(temporary)/'control.sock')
            with open(Path(temporary)/'engine.log','w+') as log:
                process=subprocess.Popen([config['binary'],str(Path(config['repository'])/'midi_human_looper.jsfx'),socket],stdout=log,stderr=log)
                try:
                    deadline=time.monotonic()+30
                    while not Path(socket).exists():
                        if process.poll() is not None:raise ValueError('Preflight engine failed')
                        if time.monotonic()>deadline:raise ValueError('Preflight startup timed out')
                        time.sleep(.1)
                    control=self.Control(socket);state=control.request()
                    if state.get('status')!='ok':raise ValueError('Preflight protocol failed')
                    for data in directory.glob('processor-*'):
                        if data.is_dir():self.ProjectStore(data,control).restore()
                    return state['buildRevision']
                finally:
                    process.terminate()
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
    def service(self, action):
        run('systemctl',action,'zynthian')
    def healthy(self, config, expected, timeout=60):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                if subprocess.run(['systemctl','is-active','--quiet','zynthian']).returncode:raise ValueError('UI inactive')
                for name,observation in expected.items():
                    data=Path(config['_directory'])/name
                    store=self.ProjectStore(data,self.Control(str(data/'control.sock')))
                    capture=store.capture()
                    state=store.control.request()
                    if state.get('buildRevision')!=config.get('runtime_revision',observation['buildRevision']) or capture['fingerprint']!=observation['fingerprint']:
                        raise ValueError('Restored processor revision or musical state differs')
                    import urllib.request
                    port=config.get('web_port_base',8765)+int(name.split('-')[1])
                    headers={}
                    if config.get('token_file'):headers['X-Engine-Token']=Path(config['token_file']).read_text().strip()
                    host=config.get('web_bind','127.0.0.1')
                    if host=='0.0.0.0':host='127.0.0.1'
                    request=urllib.request.Request('http://'+host+':'+str(port)+'/api/v1/state',headers=headers)
                    with urllib.request.urlopen(request,timeout=2) as response:web=json.load(response)
                    if web['engineSessionId']!=state['engineSessionId']:raise ValueError('Web runtime/session mismatch')
                return
            except (OSError,ValueError,RuntimeError):time.sleep(.5)
        raise ValueError('Runtime health/state verification failed; inspect engine.log')

def activate(config_path, new, runtime, expected, journal=None):
    """Journal precedes stop/config replacement; every failure restores old config."""
    config_path=Path(config_path);directory=config_path.parent
    history=directory/'runtime-update.json'
    old=json.loads(config_path.read_text())
    if journal is None:journal={'version':1,'phase':'pending','previous':old,'candidate':new,'expected':expected}
    atomic(history,journal)
    try:
        runtime.service('stop')
        atomic(config_path,new)
        runtime.service('start')
        runtime.healthy({**new,'_directory':str(directory)},expected)
    except BaseException as activation_error:
        try:
            try:runtime.service('stop')
            finally:atomic(config_path,old)
            runtime.service('start')
            runtime.healthy({**old,'_directory':str(directory)},expected)
        except BaseException as rollback_error:
            raise RuntimeError('Activation failed ('+str(activation_error)+'); rollback needs recovery ('+str(rollback_error)+')') from rollback_error
        atomic(history,{**journal,'phase':'rolled-back'})
        raise
    atomic(history,{**journal,'phase':'active'})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=Path('/zynthian/zynthian-my-data/midi-human-looper/install.json'))
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--revision');group.add_argument('--rollback',action='store_true')
    args=parser.parse_args()
    if os.geteuid()!=0:raise ValueError('Run with sudo; only the existing zynthian UI service is restarted')
    directory=args.config.parent
    with open(directory/'runtime-update.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old=json.loads(args.config.read_text())
        if old.get('version')!=1:raise ValueError('Unsupported installation configuration')
        runtime=Runtime(old['repository'])
        history=directory/'runtime-update.json'
        if history.exists() and json.loads(history.read_text()).get('phase')=='pending':
            pending=json.loads(history.read_text())
            runtime.service('stop');atomic(args.config,pending['previous']);runtime.service('start')
            runtime.healthy({**pending['previous'],'_directory':str(directory)},pending['expected'])
            atomic(history,{**pending,'phase':'rolled-back'})
            raise ValueError('Recovered interrupted activation; inspect state before retrying')
        run('systemctl','is-active','--quiet','zynthian')
        if args.rollback:
            previous=json.loads(history.read_text())
            if previous.get('phase')!='active':raise ValueError('No completed update to roll back')
            new=previous['previous']
        else:
            root,binary=build(directory,args.revision)
            new={**old,'repository':str(root),'binary':str(binary),'runtime_revision':args.revision}
        verified_revision=runtime.preflight(new,directory)
        if not args.rollback and verified_revision!=args.revision:raise ValueError('Candidate binary revision differs from reviewed commit')
        new={**new,'runtime_revision':verified_revision}
        expected=runtime.checkpoint(directory)
        backup=directory/'backups'/str(time.time_ns())
        backup.mkdir(parents=True,mode=0o700)
        shutil.copy2(args.config,backup/'install.json')
        for data in directory.glob('processor-*'):
            if data.is_dir():shutil.copytree(data,backup/data.name,ignore=shutil.ignore_patterns('*.sock','*.log'))
        if old.get('token_file'):shutil.copy2(old['token_file'],backup/'token')
        activate(args.config,new,runtime,expected)
        print('Runtime activated. Backup:',backup,'Revision:',new.get('runtime_revision','legacy'))

if __name__=='__main__':
    try:main()
    except Exception as error:sys.exit('MBMF update failed: '+str(error))

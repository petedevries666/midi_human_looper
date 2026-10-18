#!/usr/bin/env python3
"""Runtime-only update. No package, registration, JACK graph or OS changes."""
import argparse
import fcntl
import importlib
import json
import hashlib
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import select
import urllib.request
import urllib.error

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

def build(directory, revision, checkout=None):
    if platform.machine() not in ('aarch64','armv7l','x86_64'):
        raise ValueError('Unsupported CPU; no installation changed')
    if len(revision)!=40 or any(c not in '0123456789abcdef' for c in revision):
        raise ValueError('Use a reviewed full 40-character commit SHA')
    for tool in ('git','cmake','c++','pkg-config'):
        if not shutil.which(tool):raise ValueError('Missing '+tool+'; prepare build dependencies separately')
    root=directory/'releases'/revision
    if root.exists() and (root/'.mbmf-release-revision').exists():
        if (root/'.mbmf-release-revision').read_text().strip()!=revision:
            raise ValueError('Existing archive identity differs')
        integrity=root/'.mbmf-release-integrity.json'
        if integrity.exists():
            files=json.loads(integrity.read_text())
            required={'.build/midi-headless-engine','midi_human_looper.jsfx','headless/server.py','zynthian/zynthian_engine_mbh.py'}
            if not isinstance(files,dict) or not required.issubset(files):raise ValueError('Incomplete release integrity manifest')
            if any(Path(name).is_absolute() or '..' in Path(name).parts for name in files):raise ValueError('Invalid release integrity path')
            if any(not (root/name).is_file() or hashlib.sha256((root/name).read_bytes()).hexdigest()!=sha for name,sha in files.items()):
                raise ValueError('Existing release was modified; refusing reuse')
            return root,root/'.build/midi-headless-engine'
        # Incomplete archive/build is never active: refuse deleting a currently
        # selected tree or the previous working rollback tree.
        config=json.loads((directory/'install.json').read_text())
        history=directory/'runtime-update.json'
        journal=json.loads(history.read_text()) if history.exists() else {}
        referenced=[config.get('repository'),journal.get('previous',{}).get('repository')]
        if str(root) in referenced:raise ValueError('Incomplete active release; recovery required')
        shutil.rmtree(root)
    if root.exists():
        actual=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
        dirty=subprocess.check_output(['git','-C',str(root),'status','--porcelain','--untracked-files=no'],text=True)
        if actual!=revision or dirty:raise ValueError('Existing release was modified; refusing reuse')
    else:
        root.parent.mkdir(exist_ok=True)
        if checkout is None:
            installed=json.loads((directory/'install.json').read_text())
            checkout=Path(installed.get('update_checkout',installed['repository']))
        checkout=Path(checkout)
        run('git','-C',str(checkout),'fetch',REPOSITORY,revision)
        root.mkdir()
        # Git archive is staged runtime data for rollback, not a second clone.
        archive=subprocess.Popen(['git','-C',str(checkout),'archive',revision],stdout=subprocess.PIPE)
        try:
            run('tar','-x','-C',str(root),stdin=archive.stdout)
            archive.stdout.close()
            if archive.wait():raise ValueError('Release archive failed')
            (root/'.mbmf-release-revision').write_text(revision+'\n')
        except BaseException:
            archive.kill();archive.wait();shutil.rmtree(root);raise
    # Rebuild the entire pinned library with signed char, including WDL on ARM64.
    ysfx=directory/'build-cache/ysfx'
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
    files={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest()
           for path in root.rglob('*') if path.is_file() and not path.is_symlink()}
    atomic(root/'.mbmf-release-integrity.json',files)
    return root,binary

def validate_grid_restore(patch, state, timing_version):
    """Reject incompatible execution before stopping the installed runtime."""
    rate=state['sampleRate'];block=state['blockSize'];bpm=state.get('chainBpm',120)
    if rate<=0 or block<=0 or bpm<=0:raise ValueError('Invalid current processor clock')
    exact=rate*480/bpm
    period=int(exact+.5) if timing_version==2 else int(exact/block+.5)*block
    memory=patch['memory'];counts=memory[163840:163856]
    if not any(counts):return
    if patch['globals'][0]!=period:
        raise ValueError('Grid-only runtime cannot restore this free-time project; no truncation performed. Keep the current runtime or restore a separate compatible project.')
    for phrase,count in enumerate(counts):
        if count and memory[163904+phrase]==0 and memory[163952+phrase]!=period:
            raise ValueError('Grid-only runtime cannot restore independent LOOP durations; no installation changed')

class Runtime:
    def __init__(self, root):
        sys.path.insert(0,str(Path(root)/'headless'))
        self.Control=importlib.import_module('server').Control
        self.ProjectStore=importlib.import_module('project_sync').ProjectStore
    def web_preflight(self, config, socket_path, temporary, revision):
        # Probe the candidate Python/API as well as the native binary, privately
        # without JACK. No candidate activation or user project mutation here.
        command=[sys.executable,str(Path(config['repository'])/'headless/server.py'),
                 '--socket',socket_path,'--port','0','--patch-dir',str(Path(temporary)/'web-projects')]
        with open(Path(temporary)/'web.log','w') as errors:
            web=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=errors)
            try:
                if not select.select([web.stdout],[],[],15)[0]:raise ValueError('Candidate Web startup timed out')
                line=web.stdout.readline().decode().strip()
                if not line.startswith('EDITOR http://127.0.0.1:'):raise ValueError('Candidate Web startup failed')
                url=line.split(' ',1)[1]
                with urllib.request.urlopen(url+'/api/v1/state',timeout=5) as response:state=json.load(response)
                if state.get('buildRevision')!=revision:raise ValueError('Candidate Web/engine revision mismatch')
                with urllib.request.urlopen(url+'/api/v1/descriptors',timeout=5) as response:descriptors=json.load(response)
                if not descriptors.get('parameters'):raise ValueError('Candidate editor descriptors unavailable')
                if getattr(self,'require_update_controls',False):
                    # Protocol-1 candidates must retain the administration interface
                    # so a successful update cannot erase the rollback entry point.
                    with urllib.request.urlopen(url+'/update.js',timeout=5) as response:
                        if not response.read(131072):raise ValueError('Candidate UPDATE editor missing')
                    try:
                        with urllib.request.urlopen(url+'/api/v1/update',timeout=5) as response:update_state=json.load(response)
                        if 'installed' not in update_state:raise ValueError('Candidate UPDATE API differs')
                    except urllib.error.HTTPError as error:
                        data=json.load(error)
                        if error.code!=503 or data.get('error')!='UPDATE worker not installed; musical engine is unaffected':raise ValueError('Candidate UPDATE API unavailable') from error
            finally:
                web.terminate()
                try:web.wait(timeout=5)
                except subprocess.TimeoutExpired:web.kill();web.wait()
                web.stdout.close()
    def checkpoint(self, directory):
        result={}
        for socket in directory.glob('processor-*/control.sock'):
            state=self.Control(str(socket)).request()
            if state.get('chainRunning') or state.get('chainRecording') or state.get('chainArmed') or state.get('recording') or state.get('activeNotes') or state.get('targetSnapshotId') or state.get('movements',{}).get('active') or state.get('instances'):
                raise ValueError('STOP all MBMF processors, finish REC and morphs before updating')
            store=self.ProjectStore(socket.parent,self.Control(str(socket)))
            captured=store.capture()
            result[socket.parent.name]={'fingerprint':captured['fingerprint'],'buildRevision':state['buildRevision']}
            store.checkpoint(dict(expectedRevision=state['revision'],expectedEngineSessionId=state['engineSessionId'],
                                  expectedActiveRevisionId=captured['activeRevisionId']))
        return result
    def preflight(self, config, directory):
        run(config['binary'],'--queue-test')
        # Probe the actual candidate's execution capabilities; a header/version
        # string cannot establish whether old grid-only playback is safe.
        mode='two-bar-grid'
        verified=None
        for chain in (True,False):
            with tempfile.TemporaryDirectory(prefix='mbmf-preflight-') as temporary:
                socket=str(Path(temporary)/'control.sock')
                args=[config['binary'],str(Path(config['repository'])/'midi_human_looper.jsfx'),socket]
                if chain:
                    args+=['--chain','--chain-timing',str(config.get('chain_timing_version',1))]
                    if config.get('chain_grid_capture',False):args+=['--chain-grid-capture']
                with open(Path(temporary)/'engine.log','w+') as log:
                    process=subprocess.Popen(args,stdout=log,stderr=log)
                    try:
                        deadline=time.monotonic()+30
                        while not Path(socket).exists():
                            if process.poll() is not None:raise ValueError('Preflight engine failed')
                            if time.monotonic()>deadline:raise ValueError('Preflight startup timed out')
                            time.sleep(.1)
                        control=self.Control(socket);state=control.request()
                        if state.get('status')!='ok':raise ValueError('Preflight protocol failed')
                        verified=state['buildRevision']
                        if chain:self.web_preflight(config,socket,temporary,verified)
                        if chain:
                            mode=state.get('chainCaptureMode','two-bar-grid')
                        else:
                            portable=importlib.import_module('portable_project')
                            sync=importlib.import_module('project_sync')
                            for data in directory.glob('processor-*'):
                                if not data.is_dir():continue
                                store=self.ProjectStore(data,control)
                                manifest=store.manifest()
                                if manifest and mode=='two-bar-grid':
                                    live=data/'control.sock'
                                    if not live.exists():raise ValueError('Cannot verify grid rollback without the current processor clock; runtime unchanged')
                                    current=self.Control(str(live)).request()
                                    validate_grid_restore(portable.materialize(sync.read(store.directory/(manifest['revisionId']+'.json')),current['sampleRate']),current,config.get('chain_timing_version',1))
                                store.restore()
                    finally:
                        process.terminate()
                        try:process.wait(timeout=10)
                        except subprocess.TimeoutExpired:process.kill();process.wait()
        return verified
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

def activate(config_path, new, runtime, expected, journal=None, expected_config=None):
    """Journal precedes stop/config replacement; every failure restores old config."""
    config_path=Path(config_path);directory=config_path.parent
    history=directory/'runtime-update.json'
    old=json.loads(config_path.read_text())
    baseline=expected_config if expected_config is not None else journal.get('previous') if journal is not None else old
    if old!=baseline:
        raise ValueError('Installation configuration changed after preflight; no activation performed. Check and confirm again.')
    if journal is None:journal={'version':1,'phase':'pending','previous':old,'candidate':new,'expected':expected}
    atomic(history,journal)
    try:
        runtime.service('stop')
        if hasattr(runtime,'apply_components'):runtime.apply_components(journal)
        atomic(config_path,new)
        runtime.service('start')
        runtime.healthy({**new,'_directory':str(directory)},expected)
    except BaseException as activation_error:
        try:
            try:runtime.service('stop')
            finally:
                if hasattr(runtime,'restore_components'):runtime.restore_components(journal)
                atomic(config_path,old)
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
    parser.add_argument('--backup',action='store_true',help='Opt in to a full pre-update copy of processor data, install config and token (disabled by default)')
    args=parser.parse_args()
    if os.geteuid()!=0:raise ValueError('Run with sudo; only the existing zynthian UI service is restarted')
    directory=args.config.parent
    with open(directory/'runtime-update.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        old=json.loads(args.config.read_text())
        if old.get('version')!=1:raise ValueError('Unsupported installation configuration')
        runtime=Runtime(old['repository'])
        history=directory/'runtime-update.json'
        if history.exists() and json.loads(history.read_text()).get('components'):
            raise ValueError('Component update journal requires the authorized UPDATE worker for rollback/recovery; legacy CLI will not partially restore it')
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
            new={**old,'repository':str(root),'binary':str(binary),'runtime_revision':args.revision,
                 'update_checkout':old.get('update_checkout',old['repository'])}
        # Checkpoint current stopped musical data before validating the candidate.
        expected=runtime.checkpoint(directory)
        verified_revision=runtime.preflight(new,directory)
        if not args.rollback and verified_revision!=args.revision:raise ValueError('Candidate binary revision differs from reviewed commit')
        new={**new,'runtime_revision':verified_revision}
        # Full copies are optional. Runtime checkpoint, activation journal and
        # automatic config rollback remain mandatory safety mechanisms.
        backup=None
        if args.backup:
            backup=directory/'backups'/str(time.time_ns())
            backup.mkdir(parents=True,mode=0o700)
            shutil.copy2(args.config,backup/'install.json')
            for data in directory.glob('processor-*'):
                if data.is_dir():shutil.copytree(data,backup/data.name,ignore=shutil.ignore_patterns('*.sock','*.log'))
            if old.get('token_file'):shutil.copy2(old['token_file'],backup/'token')
        activate(args.config,new,runtime,expected,expected_config=old)
        print('Runtime activated. Backup:',backup if backup else 'skipped (opt in with --backup)',
              'Revision:',new.get('runtime_revision','legacy'))

if __name__=='__main__':
    try:main()
    except Exception as error:sys.exit('MBMF update failed: '+str(error))

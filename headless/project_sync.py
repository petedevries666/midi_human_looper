"""Control-thread immutable staging and guarded STOP-only activation.

A committed active manifest is the restart boundary. Crashes before manifest
commit restore the previous revision; no partially written file is executable.
"""
import json
import os
from pathlib import Path
import tempfile
import threading
import portable_project as portable

class Conflict(ValueError):
    pass


def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,temporary=tempfile.mkstemp(prefix='.'+path.name,dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(portable.canonical(value));f.flush();os.fsync(f.fileno())
        os.replace(temporary,path)
        # Windows has atomic replacement but no POSIX directory descriptor.
        # Native Zynthian runs the durable Linux path; desktop job spools can
        # still operate on Windows without failing after a successful rename.
        if os.name!='nt':
            descriptor=os.open(path.parent,os.O_RDONLY)
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
    finally:
        if os.path.exists(temporary):os.unlink(temporary)


def read(path):
    if path.stat().st_size>portable.MAX_BYTES:raise ValueError('Oversized persisted project')
    return json.loads(path.read_text())

def executable(project,state):
    patch=portable.materialize(project,state['sampleRate'])
    adopted=False
    if state.get('chainMode'):
        # Empty studio patches have no loop duration yet. The existing native
        # transport owns that grid; adopting it cannot move or truncate notes.
        if patch['globals'][0]==0 and not any(patch['memory'][portable.COUNT:portable.COUNT+portable.LAYERS]):
            patch['globals'][0]=state['chainLength'];adopted=True
        if patch['globals'][0]!=state['chainLength']:
            raise Conflict('Portable loop does not match the native two-bar grid; no timing adaptation or truncation performed')
    return patch,adopted

class ProjectStore:
    def __init__(self,directory,control):
        self.directory=Path(directory)/'projects'
        self.control=control
        self.lock=threading.RLock()
    def manifest(self):
        path=self.directory/'active.json'
        if not path.exists():return None
        value=read(path)
        if not isinstance(value,dict) or set(value)!={'version','projectId','revisionId','fingerprint'} or type(value['version']) is not int or value['version']!=1:
            raise ValueError('Unsupported active manifest; refusing overwrite')
        import uuid
        uuid.UUID(value['projectId'])
        for field in ('revisionId','fingerprint'):
            text=value[field]
            if not isinstance(text,str) or len(text)!=64 or any(c not in '0123456789abcdef' for c in text):raise ValueError('Invalid active manifest hash')
        return value
    def current(self,expected=None):
        state=self.control.request()
        if expected:
            if expected.get('expectedRevision')!=state['revision'] or expected.get('expectedEngineSessionId')!=state['engineSessionId']:
                raise Conflict('Engine session/revision changed; refresh before synchronization')
        patch=self.control.request(op=4,arg=1,revision=state['revision'],session=state['engineSessionId'])
        if patch.get('format')!='MIDI_HUMAN_LOOPER_PATCH':
            raise Conflict('STOP playback, recording, notes and morphs before synchronization')
        portable.validate_patch(patch)
        fingerprint=portable.digest(portable.timing(patch,1/state['sampleRate']))
        return state,patch,fingerprint
    def capture(self,name=None):
        with self.lock,self.control.lock:
            state,patch,fingerprint=self.current()
            manifest=self.manifest()
            if name is None:
                name=portable.validate(read(self.directory/(manifest['revisionId']+'.json')))['payload']['name'] if manifest else 'Untitled'
            project=portable.capture(patch,state['sampleRate'],manifest['projectId'] if manifest else None,
                                     manifest['revisionId'] if manifest else None,name)
            return dict(project=project,activeRevisionId=manifest['revisionId'] if manifest else None,
                        fingerprint=fingerprint,engineRevision=state['revision'],engineSessionId=state['engineSessionId'],
                        dirty=bool(manifest and fingerprint!=manifest['fingerprint']))
    def stage(self,data):
        project=portable.validate(data['project'])
        with self.lock:
            manifest=self.manifest();active=manifest['revisionId'] if manifest else None
            if data.get('expectedActiveRevisionId')!=active or project['parentRevisionId']!=active:
                raise Conflict('Project ancestry changed; PULL or explicitly fork instead of overwriting')
            if manifest and project['projectId']!=manifest['projectId']:
                raise Conflict('Different project identity; activation refused')
            path=self.directory/(project['revisionId']+'.json')
            if path.exists():
                prior=read(path)
                if portable.canonical(prior)!=portable.canonical(project):
                    raise ValueError('Immutable revision file differs; preserving existing data')
                portable.validate(prior)
            else:atomic_json(path,project)
            return dict(status='staged',revisionId=project['revisionId'])
    def activate(self,data):
        revision=data.get('revisionId')
        if not isinstance(revision,str) or len(revision)!=64 or any(c not in '0123456789abcdef' for c in revision):raise ValueError('Invalid revision')
        with self.lock,self.control.lock:
            project=portable.validate(read(self.directory/(revision+'.json')))
            if project['revisionId']!=revision:raise ValueError('Staged filename/content mismatch')
            manifest=self.manifest();active=manifest['revisionId'] if manifest else None
            if data.get('expectedActiveRevisionId')!=active or project['parentRevisionId']!=active:
                raise Conflict('Active project changed')
            state,previous,fingerprint=self.current(data)
            if data.get('expectedFingerprint')!=fingerprint:
                raise Conflict('Live configuration changed; PULL before PUSH')
            patch,adopted=executable(project,state)
            result=self.control.request(op=5,arg=1,target=7,patch=patch,revision=state['revision'],session=state['engineSessionId'])
            if result.get('status')!='ok':raise Conflict('Engine rejected activation; previous revision remains active')
            try:
                after,applied,baseline=self.current()
                atomic_json(self.directory/'active.json',dict(version=1,projectId=project['projectId'],revisionId=revision,fingerprint=baseline))
            except BaseException:
                now,_,_=self.current()
                rollback=self.control.request(op=5,arg=1,target=7,patch=previous,revision=now['revision'],session=now['engineSessionId'])
                if rollback.get('status')!='ok':raise RuntimeError('Activation persistence failed and rollback rejected; STOP and reload prior revision')
                # A directory fsync may fail after rename. Restore the previous
                # pointer too, rather than leaving restart on the rejected state.
                if self.manifest()!=manifest:
                    if manifest:atomic_json(self.directory/'active.json',manifest)
                    else:(self.directory/'active.json').unlink(missing_ok=True)
                raise
            return dict(status='active',revisionId=revision,engineRevision=after['revision'],engineSessionId=after['engineSessionId'],fingerprint=baseline,emptyGridAdopted=adopted)
    def restore(self):
        """Opt-in startup only; an explicit Zynthian snapshot has priority."""
        with self.lock,self.control.lock:
            manifest=self.manifest()
            if not manifest:return None
            project=portable.validate(read(self.directory/(manifest['revisionId']+'.json')))
            if project['revisionId']!=manifest['revisionId'] or project['projectId']!=manifest['projectId']:raise ValueError('Active manifest/content mismatch')
            state,_,_=self.current()
            patch,_=executable(project,state)
            result=self.control.request(op=5,arg=1,target=7,patch=patch,revision=state['revision'],session=state['engineSessionId'])
            if result.get('status')!='ok':raise Conflict('Persisted project restoration rejected')
            return manifest

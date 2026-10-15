"""Worker-only UPDATE boundary. No calls from the MIDI processing thread.

The adapter holds a shared startup lock until its control socket is ready. An
updater exclusively publishes the startup fence and acquires every native lease.
New processors inherit the fence; no chain identity enters portable project data.
"""
import contextlib
import fcntl
import json
from pathlib import Path
import secrets
import time

@contextlib.contextmanager
def file_guard(directory, shared=False):
    Path(directory).mkdir(parents=True,exist_ok=True)
    with (Path(directory)/'musical-admission.lock').open('a') as lock:
        deadline=time.monotonic()+3
        while True:
            try:
                fcntl.flock(lock, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX)|fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if shared or time.monotonic()>=deadline:raise ValueError('MBMF processor startup / UPDATE boundary busy; retry at rest')
                time.sleep(.01)
        try:yield
        finally:fcntl.flock(lock,fcntl.LOCK_UN)

def startup_owner(directory):
    path=Path(directory)/'update-admission.json'
    if not path.exists():return 0
    if path.is_symlink():raise ValueError('Invalid UPDATE admission marker')
    record=json.loads(path.read_text());owner=record.get('owner')
    if record.get('version')!=1 or type(owner) is not int or not 0<owner<=16777215:raise ValueError('Invalid UPDATE admission marker')
    return owner

class Admission:
    def __init__(self,directory,Control,atomic,checkpoint=None,recover=False):
        self.directory=Path(directory);self.Control=Control;self.atomic=atomic
        self.checkpoint=checkpoint;self.recover=recover;self.owner=0;self.expected=None;self.retain=False;self.acquired=[]
    def command(self,path,release=False):
        c=self.Control(str(path));s=c.request()
        if s.get('updateAdmissionVersion')!=1 or not s.get('admissionManaged'):
            raise ValueError('Runtime/adapter lacks safe UPDATE admission; reviewed setup upgrade required')
        r=c.request(op=50,target=self.owner,arg=int(release),revision=s['revision'],session=s['engineSessionId'])
        if r.get('status')!='ok' or bool(r.get('admissionClosed'))==release:
            raise ValueError('STOP all MBMF activity; admission lease refused or changed')
    def __enter__(self):
        with file_guard(self.directory):
            existing=startup_owner(self.directory)
            if existing and not self.recover:raise ValueError('Interrupted UPDATE admission fence; use RECOVER')
            self.owner=existing or secrets.randbelow(16777215)+1
            self.atomic(self.directory/'update-admission.json',dict(version=1,owner=self.owner))
            try:
                for path in sorted(self.directory.glob('processor-*/control.sock')):
                    self.command(path);self.acquired.append(path)
                if self.checkpoint:self.expected=self.checkpoint(self.directory)
            except BaseException:
                # Never remove an interrupted fence we do not newly own.
                failed=False
                if not existing:
                    for path in reversed(self.acquired):
                        try:self.command(path,True)
                        except Exception:failed=True
                if not existing and not failed:(self.directory/'update-admission.json').unlink()
                raise
        return self
    def __exit__(self,kind,error,tb):
        if self.retain:return
        with file_guard(self.directory):
            if startup_owner(self.directory)!=self.owner:raise ValueError('UPDATE admission ownership changed; fence retained')
            # Startup is excluded during this complete release transaction.
            for path in sorted(self.directory.glob('processor-*/control.sock')):
                s=self.Control(str(path)).request()
                if s.get('updateAdmissionVersion')!=1 or not s.get('admissionManaged'):raise ValueError('Unmanaged runtime appeared; UPDATE fence retained')
                if s.get('admissionClosed'):self.command(path,True)
            (self.directory/'update-admission.json').unlink()

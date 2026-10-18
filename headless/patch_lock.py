"""Serialize editor patch writes and host recall across process boundaries."""
from contextlib import contextmanager
import os

@contextmanager
def library_lock(directory):
    from pathlib import Path
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    with (directory/'.patch-operation.lock').open('a+b') as stream:
        if os.name!='nt':
            import fcntl
            try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise ValueError('A patch save or recall is already in progress')
        try:yield
        finally:
            if os.name!='nt':fcntl.flock(stream,fcntl.LOCK_UN)

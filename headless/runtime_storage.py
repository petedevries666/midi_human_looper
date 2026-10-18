"""Control-thread recovery of abandoned UNIX endpoints and stable patch storage."""
import os
from pathlib import Path
import shutil
import stat
import tempfile


def recover_socket(path):
    path=Path(path)
    try:before=path.lstat()
    except FileNotFoundError:return
    if not stat.S_ISSOCK(before.st_mode) or before.st_uid!=os.geteuid():
        raise RuntimeError('Refusing non-owned/non-socket MBMF endpoint: '+str(path))
    # Bound sockets need not be listening yet. A connect() probe alone cannot
    # distinguish a dead endpoint from another engine still starting.
    table=Path('/proc/net/unix')
    if not table.is_file():raise RuntimeError('Cannot verify UNIX socket ownership')
    for line in table.read_text().splitlines()[1:]:
        fields=line.split(maxsplit=7)
        if len(fields)==8 and fields[7]==str(path):
            raise RuntimeError('MBMF socket still owned by a process: '+str(path))
    after=path.lstat()
    if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino):
        raise RuntimeError('MBMF socket changed during recovery: '+str(path))
    path.unlink()


def patch_library(data,configured=None):
    """Seed once from the current legacy instance; never merge over saved slots."""
    data=Path(data);library=Path(configured) if configured else data.parent/'patch-library'
    if library.is_symlink():raise RuntimeError('Patch library must be a real directory')
    if library.exists():
        if not library.is_dir():raise RuntimeError('Invalid patch library path')
        return library
    if (data/'smart-switch-preset-transaction.json').exists():
        raise RuntimeError('Recover pending legacy preset transaction before migration')
    library.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.patch-library-',dir=library.parent) as temporary:
        stage=Path(temporary)/'library';stage.mkdir()
        names=['patch-names.json','smart-switch-presets.json']
        names += [f'patch{i}{suffix}.json' for i in range(1,5) for suffix in ('','-reaper')]
        for name in names:
            source=data/name
            if source.is_symlink():raise RuntimeError('Refusing symlink in patch migration')
            if source.is_file():shutil.copy2(source,stage/name)
        projects=data/'projects'
        if projects.exists():
            if projects.is_symlink() or any(p.is_symlink() for p in projects.rglob('*')):
                raise RuntimeError('Refusing symlink in project migration')
            shutil.copytree(projects,stage/'projects')
        os.rename(stage,library)
    return library

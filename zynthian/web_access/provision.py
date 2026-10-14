#!/usr/bin/env python3
"""Install only MBMF Webconf integration. No MIDI/UI/Avahi service restart."""
import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

SOURCE=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('mbmf_owned_install',SOURCE/'zynthian/install.py')
owned=importlib.util.module_from_spec(spec);spec.loader.exec_module(owned)
ANCHOR='    app = make_app()\n'
FILES=('mbmf_web_entry.py','mbmf_web_policy.py','mbmf_web_mdns.py')
def hook(lib):
    return ('    # BEGIN MBMF local Web access\n'
            '    try:\n'
            '        sys.path.insert(0, '+repr(str(lib))+')\n'
            '        from mbmf_web_entry import register as register_mbmf_entry\n'
            '        register_mbmf_entry(app)\n'
            '    except Exception:\n'
            '        import logging\n'
            '        logging.exception("MBMF Web access unavailable; retaining normal Webconf")\n'
            '    # END MBMF local Web access\n')

def trusted_parent(path,boundary=Path("/")):
    path,boundary=Path(path),Path(boundary)
    if not path.is_absolute() or not path.is_relative_to(boundary):raise ValueError("outside trusted directory boundary")
    for directory in (path,*path.parents):
        if not directory.is_relative_to(boundary):break
        if not directory.exists():continue
        info=directory.lstat()
        if directory.is_symlink():raise ValueError('trusted directory is a symlink: '+str(directory))
        # /tmp's sticky-bit boundary is acceptable for isolated fixture/staging roots.
        if directory==Path('/tmp') and info.st_mode & 0o1000:continue
        if info.st_uid not in (0,os.geteuid()) or info.st_mode & 0o022:
            raise ValueError('trusted directory is writable by other accounts: '+str(directory))

def configure(webconf,lib,data,mode=None,rollback=False,check=False,dependencies=True,trust_root=Path("/")):
    webconf,lib,data=map(Path,(webconf,lib,data))
    trusted_parent(lib,trust_root);trusted_parent(data,trust_root);trusted_parent(webconf.parent,trust_root)
    config=data/'web-access.json';manifest=data/'web-access-installation.json'
    paths=[webconf,config,*[lib/f for f in FILES]]
    for path in [*paths,manifest,lib,data]:
        if path.is_symlink():raise ValueError('refusing managed symlink: '+str(path))
    metadata=json.loads(manifest.read_text()) if manifest.exists() else None
    if metadata:
        if metadata.get('version')!=1 or set(metadata.get('files',{}))!={str(p) for p in paths}:raise ValueError('invalid Web access manifest')
        for path in paths:
            record=metadata['files'][str(path)]
            if not isinstance(record,dict) or set(record)!={'original','mode','installed'} or type(record['mode']) is not int or not 0<=record['mode']<=0o777:
                raise ValueError('invalid owned Web access record')
            for sha in (record['installed'],record['original']):
                if sha is not None and (not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha)):
                    raise ValueError('invalid owned Web access digest')
            if not path.is_file() or owned.digest(path.read_bytes())!=record['installed']:
                raise ValueError('owned Web access file changed: '+str(path))
    elif any(p.exists() for p in paths[1:]) or 'BEGIN MBMF local Web access' in webconf.read_text():
        raise ValueError('unmanaged Web access files; refusing adoption')
    before=webconf.read_text()
    if metadata:before=before.replace(hook(lib),'')
    if before.count(ANCHOR)!=1 or 'def amain(' not in before:
        raise ValueError('unsupported Webconf startup; expected async make_app anchor')
    if rollback:
        if not metadata:raise ValueError('no owned Web access installation')
        changes=[]
        if (data/'web-access-backups').is_symlink():raise ValueError('backup directory is a symlink')
        for path in paths:
            record=metadata['files'][str(path)]
            original=None
            if record['original'] is not None:
                backup=data/'web-access-backups'/(record['original']+'.bin')
                if backup.is_symlink() or not backup.is_file() or owned.digest(backup.read_bytes())!=record['original']:
                    raise ValueError('Web access backup missing or changed')
                original=backup.read_text()
            changes.append((path,original,record['mode']))
        changes.append((manifest,None,0));owned.transaction(changes);return
    if dependencies:
        subprocess.run([sys.executable,'-c','import tornado.web; import dbus'],check=True,capture_output=True)
        subprocess.run(['/usr/sbin/ip','-j','-4','address','show','up'],check=True,capture_output=True)
    install=json.loads((data/'install.json').read_text())
    selected=mode or (json.loads(config.read_text())['auth'] if metadata else 'none')
    if selected not in ('none','token'):raise ValueError('auth must be none or token')
    if selected=='token':
        token=Path(install.get('token_file',''))
        if not token.is_file() or token.is_symlink() or not token.read_text().strip():
            raise ValueError('token mode requires an existing editor token; none was modified')
    after={webconf:before.replace(ANCHOR,ANCHOR+hook(lib)),config:json.dumps(dict(version=1,auth=selected),indent=2)+'\n'}
    for f in FILES:after[lib/f]=(SOURCE/'zynthian/web_access'/f).read_text()
    for path,text in after.items():
        if path.suffix=='.py':ast.parse(text)
    if check:return dict(auth=selected,webconfCompatible=True,writesPerformed=False)
    changes=[];records={}
    backup_dir=data/'web-access-backups'
    if backup_dir.is_symlink():raise ValueError('backup directory is a symlink')
    # Dependencies first, source activation last; no service operation here.
    for path in [*[lib/f for f in FILES],config,webconf]:
        text=after[path]
        if metadata:record=dict(metadata['files'][str(path)])
        else:
            original=path.read_bytes() if path.exists() else None
            sha=owned.digest(original) if original is not None else None
            record=dict(original=sha,mode=path.stat().st_mode & 0o777 if original is not None else 0)
            if sha:
                backup=backup_dir/(sha+'.bin')
                if backup.is_symlink() or (backup.exists() and backup.read_bytes()!=original):raise ValueError('backup conflict')
                changes.append((backup,original.decode(),0o600))
        record['installed']=owned.digest(text.encode());records[str(path)]=record
        changes.append((path,text,0o600 if path==config else 0o644))
    changes.append((manifest,json.dumps(dict(version=1,files=records),indent=2)+'\n',0o600))
    owned.transaction(changes)
    return dict(auth=selected,webconfCompatible=True,writesPerformed=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--webconf',type=Path,default=Path('/zynthian/zynthian-webconf/zynthian_webconf.py'))
    p.add_argument('--lib',type=Path,default=Path('/usr/local/lib/mbmf-web-access'))
    p.add_argument('--data',type=Path,default=Path('/zynthian/zynthian-my-data/midi-human-looper'))
    p.add_argument('--auth',choices=('none','token'),help='explicit trusted/private-network none, or retained token')
    p.add_argument('--check',action='store_true');p.add_argument('--rollback',action='store_true')
    a=p.parse_args()
    if a.check and a.rollback:p.error('check and rollback are mutually exclusive')
    print(json.dumps(configure(a.webconf,a.lib,a.data,a.auth,a.rollback,a.check),indent=2))
    print('No services restarted. Reload only zynthian-webconf when ready; MIDI/UI/JACK remain running.')
if __name__=='__main__':main()

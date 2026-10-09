#!/usr/bin/env python3
"""Install/revert the minimal MIDI Tool registration without replacing Zynthian routing.
No services are restarted. Build with scripts/headless-setup.sh first.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import tempfile

IMPORT='from zyngine.zynthian_engine_mbh import zynthian_engine_mbh  # MBH issue26\n'
MULTI='elif eng_code in ("SF", "PD", "MB"):  # MBH issue26 multi'
ORIGINAL_MULTI='elif eng_code in ("SF", "PD"):'
CLASS='    "MB": zynthian_engine_mbh,  # MBH issue26\n'
INFO='''        # BEGIN MBH issue26
        cls.engine_info["MB"] = {"NAME":"MIDI Bad Mother Fucker", "TITLE":"MIDI Bad Mother Fucker",
            "TYPE":"MIDI Tool", "CAT":"Other", "ENABLED":True, "INDEX":999,
            "URL":"", "UI":"", "DESCR":"Independent synchronized MIDI phrase looper", "QUALITY":0,
            "COMPLEX":1, "EDIT":0}
        # END MBH issue26
'''
def registration(text, remove=False):
    if remove:return text.replace(IMPORT,'').replace(CLASS,'').replace(INFO,'').replace(MULTI,ORIGINAL_MULTI)
    if '# MBH issue26' in text or '# BEGIN MBH issue26' in text:
        if IMPORT not in text or CLASS not in text or INFO not in text or MULTI not in text:raise ValueError('registration changed; inspect before reinstall')
        return text
    anchors=('from zyngine import *\n','engine2class = {\n','        cls.engine_info = eng_info\n',ORIGINAL_MULTI)
    for anchor in anchors:
        if text.count(anchor)!=1:raise ValueError('unsupported Zynthian chain manager; registration anchor missing/ambiguous')
    text=text.replace(anchors[0],anchors[0]+IMPORT).replace(anchors[1],anchors[1]+CLASS).replace(anchors[2],anchors[2]+INFO).replace(ORIGINAL_MULTI,MULTI)
    ast.parse(text)
    return text
def atomic(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    mode=path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd,name=tempfile.mkstemp(prefix=path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.chmod(name,mode);os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ui-dir',type=Path,default=Path('/zynthian/zynthian-ui'))
    parser.add_argument('--data-dir',type=Path,default=Path('/zynthian/zynthian-my-data'))
    parser.add_argument('--binary',type=Path)
    parser.add_argument('--lan',action='store_true')
    parser.add_argument('--rollback',action='store_true')
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    manager=args.ui_dir/'zyngine/zynthian_chain_manager.py';adapter=args.ui_dir/'zyngine/zynthian_engine_mbh.py'
    directory=args.data_dir/'midi-human-looper';manifest=directory/'installation.json'
    before=manager.read_text()
    if args.rollback:
        metadata=json.loads(manifest.read_text())
        after=registration(before,True)
        if hashlib.sha256(after.encode()).hexdigest()!=metadata['original_sha256']:
            raise ValueError('Zynthian UI changed since installation: refusing to overwrite; remove the three MBH registration blocks manually')
        if adapter.exists():
            if hashlib.sha256(adapter.read_bytes()).hexdigest()!=metadata['adapter_sha256']:raise ValueError('adapter changed; retain and inspect it')
        atomic(manager,after)
        if adapter.exists():adapter.unlink()
        manifest.unlink();print('Registration removed. Saved patches and install configuration retained. Restart only the UI when ready.');return
    binary=(args.binary or root/'.build/midi-headless-engine').resolve()
    if not binary.is_file() or not os.access(binary,os.X_OK):raise ValueError('build the native engine first')
    source=(root/'zynthian/zynthian_engine_mbh.py').read_text();ast.parse(source)
    if adapter.exists() and adapter.read_text()!=source:raise ValueError('existing adapter differs; rollback old installation before upgrading')
    after=registration(before)
    directory.mkdir(parents=True,exist_ok=True)
    if not manifest.exists():
        if after==before:raise ValueError('registered without installation manifest; inspect before adopting')
        atomic(directory/'zynthian_chain_manager.py.original',before)
        atomic(manifest,json.dumps(dict(version=1,original_sha256=hashlib.sha256(before.encode()).hexdigest(),adapter_sha256=hashlib.sha256(source.encode()).hexdigest()),indent=2))
    atomic(adapter,source);os.chmod(adapter,0o644)
    config=directory/'install.json'
    if not config.exists():
        token=directory/'editor.token'
        if args.lan:
            import secrets
            atomic(token,secrets.token_urlsafe(32)+'\n');os.chmod(token,0o600)
        atomic(config,json.dumps(dict(version=1,repository=str(root),binary=str(binary),web_port_base=8765,web_bind='0.0.0.0' if args.lan else '127.0.0.1',token_file=str(token) if args.lan else ''),indent=2))
    atomic(manager,after)
    print('Installed native MIDI Tool registration. No JACK connections/services changed. Restart only Zynthian UI when ready.')
if __name__=='__main__':main()

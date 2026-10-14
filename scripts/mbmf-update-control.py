#!/usr/bin/env python3
"""Opt-in root update worker; never an audio / MIDI service."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'zynthian/update'))
from backend import Backend, CONFIG, SOCKET, password_record, serve

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=CONFIG)
    parser.add_argument('--socket',default=SOCKET)
    parser.add_argument('--configure',action='store_true')
    args=parser.parse_args()
    if os.geteuid()!=0:raise ValueError('Root authorization required')
    for path in [args.config,*args.config.parents]:
        if path.is_symlink() or path.stat().st_uid!=0 or path.stat().st_mode&0o022:
            raise ValueError('Update configuration must be root-owned, not writable by other users')
    backend=Backend(args.config)
    if args.configure:
        first=getpass.getpass('Separate UPDATE administrator password (12+ characters): ')
        if first!=getpass.getpass('Confirm: '):raise ValueError('Passwords differ')
        path=args.config.parent/'update-admin.json'
        if path.is_symlink():raise ValueError('Refusing credential symlink')
        backend.u.atomic(path,password_record(first));path.chmod(0o600)
        config=json.loads(args.config.read_text())
        config.setdefault('update_checkout',str(Path(__file__).resolve().parents[1]))
        backend.u.atomic(args.config,config)
        print('UPDATE password configured. Editor token unchanged. No runtime restart.');return
    credentials=args.config.parent/'update-admin.json'
    if credentials.is_symlink() or credentials.stat().st_uid!=0 or credentials.stat().st_mode&0o077:
        raise ValueError('Update password record must be root-owned mode 600')
    serve(backend,args.socket)

if __name__=='__main__':main()

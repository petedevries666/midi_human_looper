#!/usr/bin/env python3
"""Install/revert the minimal MIDI Tool registration without replacing Zynthian routing.
No services are restarted. Build with scripts/headless-build.sh first.
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
# The issue-26 INFO block is retained above solely to recognize/remove v1 installs.
# Metadata now belongs to zynthian_lv2, before its category/type index is built.
CATALOG_STANDALONE = """# BEGIN MBH Oram standalone
from zyngine.zynthian_engine_mbh_catalog import register_standalone_mbh
register_standalone_mbh(standalone_engine_info, engine_categories)
# END MBH Oram standalone
"""
CATALOG_INDEX = """    # BEGIN MBH Oram index
    from zyngine.zynthian_engine_mbh_catalog import register_mbh
    register_mbh(engines, engine_categories)
    # END MBH Oram index
"""


def registration(text, remove=False):
    if '# MBH issue26' in text or '# BEGIN MBH issue26' in text:
        for part in (IMPORT, CLASS, MULTI):
            if text.count(part) != 1:
                raise ValueError('registration changed; inspect before reinstall')
        if '# BEGIN MBH issue26' in text and text.count(INFO) != 1:
            raise ValueError('legacy MB metadata changed; inspect before reinstall')
        text = text.replace(IMPORT, '').replace(CLASS, '').replace(INFO, '').replace(MULTI, ORIGINAL_MULTI)
        if 'MBH issue26' in text:
            raise ValueError('unknown MB registration marker')
    if remove:
        ast.parse(text)
        return text
    anchors = ('from zyngine import *\n', 'engine2class = {\n',
               '        cls.engine_info = eng_info\n', ORIGINAL_MULTI)
    for anchor in anchors:
        if text.count(anchor) != 1:
            raise ValueError('unsupported Zynthian chain manager; registration anchor missing/ambiguous')
    text = text.replace(anchors[0], anchors[0] + IMPORT).replace(anchors[1], anchors[1] + CLASS).replace(ORIGINAL_MULTI, MULTI)
    ast.parse(text)
    return text


def catalog_registration(text, remove=False):
    if 'MBH Oram' in text:
        if text.count(CATALOG_STANDALONE) != 1 or text.count(CATALOG_INDEX) != 1:
            raise ValueError('MB catalog hooks changed; inspect before reinstall')
        text = text.replace(CATALOG_STANDALONE, '').replace(CATALOG_INDEX, '')
        if 'MBH Oram' in text:
            raise ValueError('unknown MB catalog marker')
    tree = ast.parse(text)
    if remove:
        return text
    assignments = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assignments.setdefault(target.id, []).append(node)
    for name in ('engine_categories', 'standalone_engine_info'):
        if len(assignments.get(name, [])) != 1:
            raise ValueError('unsupported Oram catalog: missing/ambiguous ' + name)
    categories = ast.literal_eval(assignments['engine_categories'][0].value)
    if 'Other' not in categories.get('MIDI Tool', ()):
        raise ValueError('Oram MIDI Tool category Other is not available')
    standalone = assignments['standalone_engine_info'][0]
    if 'MB' in ast.literal_eval(standalone.value):
        raise ValueError('unmanaged MB standalone registration already exists')
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'get_engines_by_type']
    if len(functions) != 1:
        raise ValueError('unsupported Oram catalog: missing/ambiguous type-index builder')
    function = functions[0]
    globals_ = [node for node in function.body if isinstance(node, ast.Global) and node.names == ['engines_by_type']]
    if len(globals_) != 1:
        raise ValueError('unsupported Oram catalog: missing/ambiguous type-index global')
    lines = text.splitlines(keepends=True)
    if lines[globals_[0].lineno - 1] != '    global engines_by_type\n':
        raise ValueError('unsupported Oram catalog indentation')
    # Apply later insertion first, preserving every existing source byte.
    for line, addition in sorted([(standalone.end_lineno, CATALOG_STANDALONE),
                                  (globals_[0].end_lineno, CATALOG_INDEX)], reverse=True):
        lines.insert(line, addition)
    proposed = ''.join(lines)
    ast.parse(proposed)
    return proposed


ROUTER_DISCOVER = "    # BEGIN MBH channel source discover\n    from zyngine.zynthian_engine_mbh_router import discover\n    import sys\n    discover(sys.modules[__name__])\n    # END MBH channel source discover\n"
ROUTER_CONFIGURE = "    # BEGIN MBH channel source configure\n    from zyngine.zynthian_engine_mbh_router import configure\n    import sys\n    configure(sys.modules[__name__], required_routes)\n    # END MBH channel source configure\n"

def router_registration(text, remove=False):
    if 'MBH channel source' in text:
        if text.count(ROUTER_DISCOVER)!=1 or text.count(ROUTER_CONFIGURE)!=1:
            raise ValueError('MB router hooks changed; refusing overwrite')
        text=text.replace(ROUTER_DISCOVER,'').replace(ROUTER_CONFIGURE,'')
    if not remove:
        anchors=('    update = False\n    host_usb_connected = is_host_usb_connected()\n',
                 '    # Connect and disconnect routes\n    for dst, sources in required_routes.items():\n')
        functions=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='midi_autoconnect']
        if len(functions)!=1 or text.count(anchors[0])!=1:raise ValueError('unsupported Oram autoconnect anchors')
        function=functions[0];lines=text.splitlines(keepends=True)
        segment=''.join(lines[function.lineno-1:function.end_lineno])
        if segment.count(anchors[1])!=1:raise ValueError('unsupported Oram MIDI connection anchor')
        segment=segment.replace(anchors[1],ROUTER_CONFIGURE+anchors[1])
        text=''.join(lines[:function.lineno-1])+segment+''.join(lines[function.end_lineno:])
        text=text.replace(anchors[0],ROUTER_DISCOVER+anchors[0])
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
def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return path.read_bytes().decode('utf-8')


def checked_owned_files(metadata, paths, directory):
    """Validate all ownership and recovery data before writing anything."""
    if metadata['version'] == 1:
        original = registration(read(paths['manager']), True).encode()
        if digest(original) != metadata['original_sha256']:
            raise ValueError('Zynthian manager changed since installation; refusing upgrade/rollback')
        if not paths['adapter'].is_file() or digest(paths['adapter'].read_bytes()) != metadata['adapter_sha256']:
            raise ValueError('installed adapter changed; retain and inspect it')
        backup = directory / 'zynthian_chain_manager.py.original'
        if not backup.is_file() or digest(backup.read_bytes()) != metadata['original_sha256']:
            raise ValueError('original manager backup is missing or changed')
        return
    if metadata['version'] != 2 or set(metadata.get('files', {})) != set(paths):
        raise ValueError('unsupported installation manifest')
    for name, path in paths.items():
        record = metadata['files'][name]
        if not path.is_file() or digest(path.read_bytes()) != record['installed_sha256']:
            raise ValueError(name + ' changed since installation; refusing overwrite')
        if record['original_sha256'] is not None:
            backup = directory / (path.name + '.original')
            if not backup.is_file() or digest(backup.read_bytes()) != record['original_sha256']:
                raise ValueError(name + ' original backup is missing or changed')


def transaction(changes):
    """Atomic files plus compensating rollback for any caught installation failure.

    UI restart is explicit. No catalog JSON, routing or service state is touched.
    """
    saved = {path: (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else None
             for path, data, mode in changes}
    written = []
    try:
        for path, data, mode in changes:
            if data is None:
                if path.exists():
                    path.unlink()
                    written.append(path)
            elif not path.exists() or path.read_bytes() != data.encode() or path.stat().st_mode & 0o777 != mode:
                # Include the path before atomic(), which can fail after replacement.
                written.append(path)
                atomic(path, data)
                os.chmod(path, mode)
    except BaseException:
        for path in reversed(written):
            previous = saved[path]
            if previous is None:
                if path.exists(): path.unlink()
            else:
                if not path.exists() or path.read_bytes() != previous[0]:
                    atomic(path, previous[0].decode('utf-8'))
                os.chmod(path, previous[1])
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ui-dir',type=Path,default=Path('/zynthian/zynthian-ui'))
    parser.add_argument('--data-dir',type=Path,default=Path('/zynthian/zynthian-my-data'))
    parser.add_argument('--binary',type=Path)
    parser.add_argument('--lan',action='store_true')
    parser.add_argument('--native-channel-routing',action='store_true',help='register dedicated MB output as a filtered ZynMidiRouter input')
    actions=parser.add_mutually_exclusive_group()
    actions.add_argument('--rollback',action='store_true')
    actions.add_argument('--rollback-channel-routing',action='store_true',help='remove only the owned native input hooks; retain MB registration/runtime/config')
    actions.add_argument('--upgrade-adapter',action='store_true',help='explicitly update the owned Python adapter, retaining its previous bytes')
    actions.add_argument('--rollback-adapter',action='store_true',help='restore the previous owned adapter only; retain registration/runtime/config')
    parser.add_argument('--check',action='store_true',help='validate ownership, binary and Oram anchors without writes')
    args=parser.parse_args(argv);root=Path(__file__).resolve().parents[1]
    if args.check and (args.rollback or args.rollback_adapter or args.rollback_channel_routing):parser.error('--check and rollback are mutually exclusive')
    paths = {
        'manager': args.ui_dir/'zyngine/zynthian_chain_manager.py',
        'catalog': args.ui_dir/'zyngine/zynthian_lv2.py',
        'adapter': args.ui_dir/'zyngine/zynthian_engine_mbh.py',
        'helper': args.ui_dir/'zyngine/zynthian_engine_mbh_catalog.py',
    }
    directory=args.data_dir/'midi-human-looper';manifest=directory/'installation.json'
    config=directory/'install.json';token=directory/'editor.token'
    for path in [*paths.values(),manifest,config,token,
                 *(directory/(p.name+'.original') for p in paths.values())]:
        if path.is_symlink():raise ValueError('refusing managed symlink: '+str(path))
    metadata=json.loads(read(manifest)) if manifest.exists() else None
    before={name:read(path) if path.exists() else None for name,path in paths.items()}
    if before['manager'] is None or before['catalog'] is None:
        raise ValueError('Zynthian Oram manager/catalog sources are missing')
    extra_paths={'router':args.ui_dir/'zyngine/zynthian_engine_mbh_router.py',
                 'autoconnect':args.ui_dir/'zynautoconnect/zynthian_autoconnect.py'}
    # Oram commonly ships zynautoconnect as a package __init__.py.
    if not extra_paths['autoconnect'].exists():extra_paths['autoconnect']=args.ui_dir/'zynautoconnect/__init__.py'
    if metadata:
        owned={**paths,**{k:v for k,v in extra_paths.items() if k in metadata.get('files',{})}}
        checked_owned_files(metadata,owned,directory)
    if args.native_channel_routing or (metadata and 'router' in metadata.get('files',{})):
        paths.update(extra_paths)
        for name,path in extra_paths.items():
            if path.is_symlink() or (directory/(path.name+'.original')).is_symlink():raise ValueError('refusing managed symlink: '+str(path))
            before[name]=read(path) if path.exists() else None
        if before['autoconnect'] is None:raise ValueError('Oram autoconnect source missing')
    if args.rollback_channel_routing:
        if not metadata or 'router' not in metadata.get('files',{}):
            raise ValueError('no owned native-channel installation to roll back')
        changes=[]
        for name in ('autoconnect','router'):
            record=metadata['files'].pop(name);path=paths[name]
            original=read(directory/(path.name+'.original')) if record['original_sha256'] is not None else None
            changes.append((path,original,record['original_mode']))
        changes.append((manifest,json.dumps(metadata,indent=2),0o600))
        transaction(changes)
        print('Native source hooks removed. MB registration, adapter, runtime, token and patches retained. Restart UI when ready.');return
    if args.rollback_adapter:
        if not metadata or metadata['version'] != 2 or not metadata.get('adapter_previous'):
            raise ValueError('no owned adapter update to roll back')
        previous=metadata['adapter_previous'];sha=previous.get('sha256', '')
        if not isinstance(sha,str) or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
            raise ValueError('invalid adapter backup identity')
        backup_dir=directory/'adapter-upgrades';backup=backup_dir/(sha+'.py')
        if backup_dir.is_symlink() or backup.is_symlink() or not backup.is_file() or digest(backup.read_bytes())!=sha:
            raise ValueError('adapter backup missing or changed; refusing rollback')
        original=read(backup);ast.parse(original)
        mode=previous.get('mode')
        if type(mode) is not int or not 0 <= mode <= 0o777:raise ValueError('invalid adapter backup mode')
        metadata['files']['adapter']['installed_sha256']=sha
        del metadata['adapter_previous']
        transaction([(paths['adapter'],original,mode),(manifest,json.dumps(metadata,indent=2),0o600)])
        print('Previous owned adapter restored. Runtime, registration, configuration and projects retained. Restart UI when ready.');return
    if args.rollback:
        if not metadata:raise ValueError('no installation manifest; nothing owned to remove')
        if metadata['version']==1:
            changes=[(paths['manager'],registration(before['manager'],True),paths['manager'].stat().st_mode & 0o777),
                     (paths['adapter'],None,0)]
        else:
            changes=[]
            for name in paths:
                record=metadata['files'][name];path=paths[name]
                original=read(directory/(path.name+'.original')) if record['original_sha256'] is not None else None
                changes.append((path,original,record['original_mode']))
        changes.append((manifest,None,0));transaction(changes)
        print('Registration removed. Saved patches, configuration, token and backups retained. Restart only the UI when ready.');return
    binary=(args.binary or root/'.build/midi-headless-engine').resolve()
    if not binary.is_file() or not os.access(binary,os.X_OK):raise ValueError('build the native engine first or pass the installed --binary')
    if metadata is None and (paths['adapter'].exists() or paths['helper'].exists() or
                            'MBH issue26' in before['manager'] or 'MBH Oram' in before['catalog']):
        raise ValueError('unmanaged registration/files without manifest; inspect before adopting')
    if metadata and metadata['version']==1 and (paths['helper'].exists() or 'MBH Oram' in before['catalog']):
        raise ValueError('unmanaged catalog hooks/helper on legacy installation')
    after={'manager':registration(before['manager']), 'catalog':catalog_registration(before['catalog']),
           'helper':read(root/'zynthian/zynthian_engine_mbh_catalog.py'),
           # A catalog-only upgrade must not change the existing adapter's runtime ABI.
           'adapter':before['adapter'] if metadata and not args.upgrade_adapter else read(root/'zynthian/zynthian_engine_mbh.py')}
    if 'router' in paths:
        if before['router'] is not None and not (metadata and 'router' in metadata.get('files',{})):raise ValueError('unmanaged MB router helper')
        if 'MBH channel source' in before['autoconnect'] and not (metadata and 'autoconnect' in metadata.get('files',{})):raise ValueError('unmanaged MB router hooks')
        after.update(router=read(root/'zynthian/zynthian_engine_mbh_router.py'),autoconnect=router_registration(before['autoconnect']))
    for source in after.values():ast.parse(source)
    adapter_backup_change=None
    previous=metadata.get('adapter_previous') if metadata else None
    if metadata and args.upgrade_adapter and after['adapter']!=before['adapter']:
        sha=digest(before['adapter'].encode());backup_dir=directory/'adapter-upgrades';backup=backup_dir/(sha+'.py')
        if backup_dir.is_symlink() or backup.is_symlink() or (backup.exists() and read(backup)!=before['adapter']):
            raise ValueError('adapter backup conflict; refusing update')
        previous=dict(sha256=sha,mode=paths['adapter'].stat().st_mode & 0o777)
        adapter_backup_change=(backup,before['adapter'],0o600)
    if args.check:
        print(json.dumps(dict(registrationCompatible=True,catalogCompatible=True,category='Other',
            binary=str(binary),managedUpgrade=bool(metadata and metadata['version']==1),
            adapterPreserved=bool(metadata and not args.upgrade_adapter),upgradeRequiresRollback=False,
            existingConfigurationPreserved=config.exists(),writesPerformed=False),indent=2));return
    changes=[];records={}
    for name,path in paths.items():
        if metadata and metadata['version']==2 and name in metadata['files']:
            record=dict(metadata['files'][name])
        else:
            if metadata and name=='manager':
                original=registration(before[name],True)
            elif metadata and name=='adapter':
                original=None
            else:
                original=before[name]
            record={'original_sha256':digest(original.encode()) if original is not None else None,
                    'original_mode':path.stat().st_mode & 0o777 if original is not None else 0}
            if original is not None:
                backup=directory/(path.name+'.original')
                if backup.exists() and read(backup)!=original:raise ValueError('backup conflict: '+str(backup))
                changes.append((backup,original,0o600))
        record['installed_sha256']=digest(after[name].encode());records[name]=record
    if metadata and metadata['version']==1:
        recovery=directory/'pre-oram-upgrade'
        for name in ('manager','catalog','adapter'):
            backup=recovery/paths[name].name
            if backup.is_symlink() or (backup.exists() and read(backup)!=before[name]):raise ValueError('upgrade backup conflict: '+str(backup))
            changes.append((backup,before[name],0o600))
        backup=recovery/'installation.json'
        if backup.is_symlink() or (backup.exists() and read(backup)!=read(manifest)):
            raise ValueError('upgrade manifest backup conflict: '+str(backup))
        changes.append((backup,read(manifest),0o600))
    if not config.exists():
        if args.lan:
            if token.exists():raise ValueError('unmanaged editor token without install configuration')
            import secrets
            changes.append((token,secrets.token_urlsafe(32)+'\n',0o600))
        changes.append((config,json.dumps(dict(version=1,chain_timing_version=2,repository=str(root),binary=str(binary),
            web_port_base=8765,web_bind='0.0.0.0' if args.lan else '127.0.0.1',token_file=str(token) if args.lan else ''),indent=2),0o600))
    if adapter_backup_change:changes.append(adapter_backup_change)
    # Dependencies first; source activation last. No running services are restarted.
    for name in ('helper','adapter','manager','catalog',*(('router','autoconnect') if 'router' in paths else ())):
        path=paths[name];mode=path.stat().st_mode & 0o777 if path.exists() else 0o644
        changes.append((path,after[name],mode))
    updated=dict(version=2,files=records)
    if previous:updated['adapter_previous']=previous
    changes.append((manifest,json.dumps(updated,indent=2),0o600))
    transaction(changes)
    print('Installed Oram MIDI Tool / Other discovery. Configuration preserved; adapter '+('updated explicitly with backup' if args.upgrade_adapter else 'preserved on upgrade')+'. No JACK connections/services changed. Restart only Zynthian UI when ready.')
if __name__=='__main__':main()

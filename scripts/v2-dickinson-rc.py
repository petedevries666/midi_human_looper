#!/usr/bin/env python3
"""Prepare an auditable V2 DICKINSON update; never touch Zynthian without install/rollback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import time

DEFAULT_CONFIG = Path('/zynthian/zynthian-my-data/midi-human-looper/install.json')
DEFAULT_SNAPSHOTS = Path('/zynthian/zynthian-my-data/snapshots')
MIN_BUILD_HEADROOM = 1024 * 1024 * 1024


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def checked_paths(config_path, snapshot_path):
    if config_path.is_symlink() or snapshot_path.is_symlink():
        raise ValueError('Installation config and snapshot root must not be symlinks')
    config_path = config_path.resolve(strict=True)
    snapshot_path = snapshot_path.resolve(strict=True)
    data_root = Path('/zynthian/zynthian-my-data').resolve(strict=True)
    if not config_path.is_relative_to(data_root) or not snapshot_path.is_relative_to(data_root):
        raise ValueError('Config and snapshots must be under Zynthian user data')
    if not config_path.is_file() or not snapshot_path.is_dir():
        raise ValueError('Installation config or snapshot directory is missing')
    config = json.loads(config_path.read_text())
    if config.get('version') != 1:
        raise ValueError('Unsupported installation configuration')
    repository = Path(config['repository']).resolve(strict=True)
    binary = Path(config['binary']).resolve(strict=True)
    updater = repository / 'scripts/zynthian-update.py'
    if not repository.is_dir() or not binary.is_file() or not updater.is_file():
        raise ValueError('Current MBMF checkout, binary, or rollback-capable updater is missing')
    if '--backup' not in updater.read_text():
        raise ValueError('Installed updater lacks mandatory backup support')
    if not (repository / 'midi_human_looper.jsfx').is_file():
        raise ValueError('Current MBMF source is incomplete')
    return config, repository, updater, data_root


def files_in(root, omit=()):
    root = root.resolve(strict=True)
    for directory, dirs, files in os.walk(root, followlinks=False):
        here = Path(directory)
        dirs[:] = [name for name in dirs if name not in omit]
        for name in dirs + files:
            path = here / name
            if path.is_symlink():
                raise ValueError(f'Backup source contains a symlink: {path}')
        for name in files:
            yield here / name


def backup_size(repository, snapshots, app_data):
    source = sum(p.stat().st_size for p in files_in(repository, {'.git', '.build', '__pycache__'}))
    builds = repository / '.build'
    source += sum(p.stat().st_size for p in builds.glob('midi-headless-engine*') if p.is_file() and not p.is_symlink()) if builds.exists() else 0
    musical = sum(p.stat().st_size for p in files_in(snapshots))
    for processor in app_data.glob('processor-*'):
        if processor.is_dir():
            musical += sum(p.stat().st_size for p in files_in(processor) if p.name != 'control.sock')
    return source + musical


def prepare(config_path, snapshots, revision=None):
    if platform.machine() not in ('aarch64', 'armv7l'):
        raise ValueError('This release procedure is for the Zynthian Raspberry Pi')
    if revision is not None and (len(revision) != 40 or any(c not in '0123456789abcdef' for c in revision)):
        raise ValueError('Use the reviewed full 40-character RC commit SHA')
    config, repository, updater, data_root = checked_paths(config_path, snapshots)
    app_data = config_path.resolve().parent
    estimate = backup_size(repository, snapshots, app_data)
    free = shutil.disk_usage(app_data).free
    if free < estimate + MIN_BUILD_HEADROOM:
        raise ValueError(f'Insufficient free space for mandatory backup and build: need {estimate + MIN_BUILD_HEADROOM} bytes, have {free}')
    if subprocess.run(['systemctl', 'is-active', '--quiet', 'zynthian']).returncode:
        raise ValueError('Zynthian service is not active; no update attempted')
    return dict(config=config, repository=repository, updater=updater, data_root=data_root,
                app_data=app_data, estimate=estimate, free=free)


def archive_backup(state, config_path, snapshots, backup_root, revision):
    backup_root = Path(backup_root)
    if backup_root.exists() and backup_root.is_symlink():
        raise ValueError('Backup root must not be a symlink')
    if backup_root.resolve().is_relative_to(snapshots.resolve()) or backup_root.resolve().is_relative_to(state['repository'].resolve()):
        raise ValueError('Backup root must be outside source and snapshot trees')
    backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if backup_root.resolve() != backup_root or not backup_root.resolve().is_relative_to(state['data_root']):
        raise ValueError('Backup root must be a real directory in Zynthian user data')
    backup_root.chmod(0o700)
    name = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '-' + revision[:12]
    target = backup_root / name
    target.mkdir(mode=0o700)
    try:
        archive = target / 'before.tar.gz'
        with tarfile.open(archive, 'w:gz', dereference=False) as package:
            package.add(config_path, arcname='mbmf-install.json', recursive=False)
            for path in files_in(state['repository'], {'.git', '.build', '__pycache__'}):
                package.add(path, arcname='mbmf-source/' + path.relative_to(state['repository']).as_posix(), recursive=False)
            for path in (state['repository'] / '.build').glob('midi-headless-engine*'):
                if path.is_file() and not path.is_symlink():
                    package.add(path, arcname='mbmf-source/.build/' + path.name, recursive=False)
            for path in files_in(snapshots):
                package.add(path, arcname='zynthian-snapshots/' + path.relative_to(snapshots).as_posix(), recursive=False)
        archive.chmod(0o600)
        manifest = dict(version=1,kind='MBMF V2 DICKINSON before-install',candidate=revision,
                        currentRepository=str(state['repository']),snapshots=str(snapshots),
                        archiveSha256=sha256(archive),createdUtc=name)
        (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (target / 'manifest.json').chmod(0o600)
    except BaseException:
        shutil.rmtree(target)
        raise
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'install', 'rollback'))
    parser.add_argument('--revision', help='Reviewed full 40-character RC commit SHA, required for install')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--snapshots', type=Path, default=DEFAULT_SNAPSHOTS)
    parser.add_argument('--backup-root', type=Path,
                        default=DEFAULT_CONFIG.parent / 'backups/v2-dickinson')
    args = parser.parse_args()
    if args.action == 'install' and not args.revision:
        parser.error('install requires --revision')
    if args.action != 'install' and args.revision:
        parser.error('--revision belongs to install')
    if os.geteuid() != 0:
        raise ValueError('Run as root on the Zynthian')
    state = prepare(args.config, args.snapshots, args.revision)
    print(f"Preflight OK: {platform.machine()}, backup estimate {state['estimate']} bytes, free {state['free']} bytes")
    if args.action == 'preflight':
        return
    if args.action == 'install':
        backup = archive_backup(state, args.config.resolve(), args.snapshots.resolve(), args.backup_root, args.revision)
        print(f'Mandatory source/snapshot backup: {backup}', flush=True)
        command = [sys.executable, str(state['updater']), '--config', str(args.config), '--revision', args.revision, '--backup']
    else:
        command = [sys.executable, str(state['updater']), '--config', str(args.config), '--rollback', '--backup']
    subprocess.run(command, check=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        sys.exit('V2 DICKINSON update refused: ' + str(error))

"""Isolated release backup contract; no Zynthian service or hardware involved."""
import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'scripts/v2-dickinson-rc.py'
spec = importlib.util.spec_from_file_location('v2_dickinson_rc', MODULE)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class BackupTest(unittest.TestCase):
    def test_archive_preserves_source_and_snapshot_without_git(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repository = root / 'source'
            (repository / '.git').mkdir(parents=True)
            (repository / '.git/config').write_text('do not archive')
            (repository / '.build').mkdir()
            (repository / '.build/midi-headless-engine').write_bytes(b'engine')
            (repository / 'midi_human_looper.jsfx').write_text('source')
            snapshots = root / 'snapshots'
            (snapshots / '001-MBMF').mkdir(parents=True)
            (snapshots / '001-MBMF/001-test.zss').write_text('chains')
            config = root / 'install.json'
            config.write_text('{"version": 1}')
            backup = release.archive_backup({'repository': repository, 'data_root': root},
                                            config, snapshots, root / 'backups', 'a' * 40)
            manifest = json.loads((backup / 'manifest.json').read_text())
            self.assertEqual(manifest['archiveSha256'], release.sha256(backup / 'before.tar.gz'))
            with tarfile.open(backup / 'before.tar.gz') as archive:
                names = set(archive.getnames())
                self.assertIn('mbmf-install.json', names)
                self.assertIn('mbmf-source/midi_human_looper.jsfx', names)
                self.assertIn('mbmf-source/.build/midi-headless-engine', names)
                self.assertIn('zynthian-snapshots/001-MBMF/001-test.zss', names)
                self.assertNotIn('mbmf-source/.git/config', names)


if __name__ == '__main__':
    unittest.main()

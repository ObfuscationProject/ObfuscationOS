"""Hosted actual logging code and executed packaging policy, never guest evidence."""
from pathlib import Path
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import journalled_rootfs_policy as journal
import rootfs_policy as bootstrap
import stage_rootfs as stage


class LoggingImplementationTests(unittest.TestCase):
    def test_actual_code_with_syscall_faults(self):
        sdk = Path(os.environ['OK_TEST_KERNEL_SDK']).resolve()
        self.assertTrue((sdk / 'manifest.json').is_file())
        with tempfile.TemporaryDirectory(prefix='ok-log-code-') as temporary:
            binary = Path(temporary) / 'logging'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-Wno-misleading-indentation', '-fsanitize=address,undefined',
                            '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                            '-I', str(ROOT / 'lib/okcrt/include'), '-I', str(sdk / 'include'),
                            '-idirafter', str(ROOT / 'sdk/include'),
                            str(ROOT / 'tests/logging_tests.c'), '-o', str(binary)], check=True)
            # LeakSanitizer cannot operate under this host's ptrace execution;
            # the harness checks its descriptor ledger at every fixture teardown.
            environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
            result = subprocess.run([str(binary)], check=True, capture_output=True,
                                    env=environment, timeout=30)
            self.assertIn(b'fault controls passed', result.stdout)


@unittest.skipUnless(all(shutil.which(p) for p in ('mke2fs', 'debugfs', 'e2fsck')), 'ext4 tools required')
class LoggingPackagingTests(unittest.TestCase):
    def fixture(self, work):
        apps = work / 'apps'; apps.mkdir()
        for name in (*stage.APPS, 'login'):
            (apps / (name + '.elf')).write_bytes(b'Hosted fixture ' + name.encode())
        root = work / 'root'
        subprocess.run([sys.executable, str(ROOT / 'tools/stage_rootfs.py'),
                        '--apps-dir', str(apps), '--out', str(root), '--console-login'],
                       check=True, capture_output=True)
        self.assertEqual((root / 'var/log').stat().st_mode & 0o7777, 0o700)
        self.assertEqual((root / 'var/log/system.log').read_bytes(), stage.CHECKPOINT0)
        self.assertEqual((root / 'var/log/system.log').stat().st_mode & 0o7777, 0o600)
        self.assertEqual((root / 'bin/logger').read_bytes(), (apps / 'logger.elf').read_bytes())
        manifest = (root / 'etc/services.conf').read_text()
        self.assertIn('service logd notify /bin/logd - 0 0\n', manifest)
        self.assertIn('service console simple /bin/login - 0 0\n', manifest)
        # Deliberately hostile host modes must not determine guest permissions.
        (root / 'var/log').chmod(0o2777)
        for name in ('system.log', 'system.prev'):
            (root / 'var/log' / name).write_bytes(b'Hosted packaging bytes\n')
            (root / 'var/log' / name).chmod(0o7777)
        return root, apps

    def test_both_real_normalizers_and_profile_selection(self):
        with tempfile.TemporaryDirectory(prefix='ok-log-package-') as temporary:
            work = Path(temporary); root, apps = self.fixture(work)
            image = work / 'bootstrap.img'
            subprocess.run(['mke2fs', '-q', '-t', 'ext4', '-b', '4096', '-I', '256',
                            '-O', 'none,extent,filetype,sparse_super,large_file',
                            '-E', 'lazy_itable_init=0', '-m', '0', '-d', str(root), str(image), '32M'],
                           check=True, capture_output=True)
            normalized = bootstrap.Ext4(bootstrap.normalize_bootstrap_root(image.read_bytes(), root))
            for name, mode in (('/var', 0o40755), ('/var/log', 0o40700),
                               ('/var/log/system.log', 0o100600), ('/var/log/system.prev', 0o100600),
                               ('/etc/hosts', 0o100644), ('/bin/resolved', 0o100755), ('/bin/resolvectl', 0o100755)):
                observed = normalized.metadata(normalized.paths()[name])
                self.assertEqual((observed['mode'], observed['uid'], observed['gid']), (mode, 0, 0))
            image = work / 'journal.img'; metadata_work = work / 'metadata'; metadata_work.mkdir()
            subprocess.run(['mke2fs', '-q', '-t', 'ext4', '-b', '1024', '-I', '256',
                            '-O', 'none,has_journal,extents,filetype,metadata_csum', '-J', 'size=4',
                            '-E', 'lazy_itable_init=0,lazy_journal_init=0', '-m', '0', '-d', str(root),
                            str(image), '32M'], check=True, capture_output=True)
            result = journal.normalize(Path(shutil.which('debugfs')), image, root, metadata_work)
            for name, mode in (('/var', 0o40755), ('/var/log', 0o40700),
                               ('/var/log/system.log', 0o100600), ('/var/log/system.prev', 0o100600),
                               ('/etc/hosts', 0o100644), ('/bin/resolved', 0o100755), ('/bin/resolvectl', 0o100755)):
                row = result['applied_inode_metadata'][name]
                self.assertEqual((row['mode'], row['uid'], row['gid']), (mode, 0, 0))
            checked = subprocess.run(['e2fsck', '-fn', str(image)], capture_output=True)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            # Maintenance profile remains independently usable without logd.
            maintenance = work / 'maintenance'
            subprocess.run([sys.executable, str(ROOT / 'tools/stage_rootfs.py'),
                            '--apps-dir', str(apps), '--out', str(maintenance)],
                           check=True, capture_output=True)
            self.assertNotIn('/bin/logd', (maintenance / 'etc/services.conf').read_text())
            self.assertFalse((maintenance / 'var/log/system.log').exists())

    def test_unsafe_logging_paths_refused_by_both_policies(self):
        with tempfile.TemporaryDirectory(prefix='ok-log-unsafe-') as temporary:
            work = Path(temporary); root, _ = self.fixture(work)
            image = work / 'bootstrap.img'
            subprocess.run(['mke2fs', '-q', '-t', 'ext4', '-b', '4096', '-I', '256',
                            '-O', 'none,extent,filetype,sparse_super,large_file',
                            '-E', 'lazy_itable_init=0', '-m', '0', '-d', str(root), str(image), '32M'],
                           check=True, capture_output=True)
            raw = image.read_bytes()
            current = root / 'var/log/system.log'; current.unlink(); current.symlink_to('/etc/accounts.db')
            with self.assertRaises(ValueError): journal.inventory(root)
            with self.assertRaises(ValueError): bootstrap.normalize_bootstrap_root(raw, root)
            current.unlink(); current.write_bytes(bytes(8193))
            with self.assertRaises(ValueError): journal.inventory(root)
            with self.assertRaises(ValueError): bootstrap.normalize_bootstrap_root(raw, root)
            current.unlink(); (root / 'var/log/system.prev').unlink(); (root / 'var/log').rmdir()
            (root / 'var/log').symlink_to('/tmp', target_is_directory=True)
            with self.assertRaises(ValueError): journal.inventory(root)
            with self.assertRaises(ValueError): bootstrap.normalize_bootstrap_root(raw, root)


if __name__ == '__main__':
    unittest.main()

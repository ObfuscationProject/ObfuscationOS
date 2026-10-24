"""Host packaging policy checks; no compiler, kernel or user process execution."""
from pathlib import Path
import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

SOURCE = Path(__file__).resolve().parents[2] / 'tools/journalled_rootfs_policy.py'
spec = importlib.util.spec_from_file_location('journalled_bootstrap_policy', SOURCE)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class JournalledInventoryTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory) / 'root'
        (root / 'etc').mkdir(parents=True)
        (root / 'etc/services.conf').write_bytes(b'Trusted English bootstrap service\n')
        (root / 'etc/accounts.db').write_bytes(b'OKACCOUNTS 1\nstate unconfigured\n')
        (root / 'etc/accounts.db').chmod(0o7777)
        (root / 'root').mkdir()
        (root / 'root').chmod(0o2777)
        (root / 'home').mkdir()
        (root / 'home/note').write_bytes(b'Root bootstrap English note\n')
        (root / 'tmp').mkdir()
        return root

    def test_trusted_root_bootstrap_matches_nonjournalled_home_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = policy.inventory(self.fixture(directory))
            self.assertEqual(selected['/etc'], {'mode': 0o40755, 'uid': 0, 'gid': 0})
            self.assertEqual(selected['/etc/services.conf'], {'mode': 0o100644, 'uid': 0, 'gid': 0})
            self.assertEqual(selected['/home'], {'mode': 0o40700, 'uid': 0, 'gid': 0})
            self.assertEqual(selected['/home/note']['uid'], 0)
            self.assertEqual(selected['/tmp']['mode'], 0o41777)
            self.assertEqual(selected['/root'], {'mode': 0o40700, 'uid': 0, 'gid': 0})
            self.assertEqual(selected['/etc/accounts.db'], {'mode': 0o100600, 'uid': 0, 'gid': 0})

    def test_command_delimiters_and_trusted_directory_symlink_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            (root / 'bad;command').write_bytes(b'no')
            with self.assertRaises(ValueError):
                policy.inventory(root)
            (root / 'bad;command').unlink()
            (root / 'etc/services.conf').unlink()
            (root / 'etc/accounts.db').unlink()
            (root / 'etc').rmdir()
            (root / 'etc').symlink_to('home', target_is_directory=True)
            with self.assertRaises(ValueError):
                policy.inventory(root)

    def test_unsafe_debugfs_work_operand_is_refused_before_backend_use(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            for name in ('work space', 'work;command'):
                work = Path(directory) / name
                work.mkdir()
                # Nonexistent tools make a premature backend call fail with
                # FileNotFoundError instead of the required policy refusal.
                with self.assertRaisesRegex(ValueError, 'safe debugfs work directory'):
                    policy.normalize(Path('/not-a-debugfs-tool'), Path('/not-an-image'), root, work)


@unittest.skipUnless(all(shutil.which(tool) for tool in ('mke2fs', 'debugfs', 'e2fsck')), 'ext4 fixture tools unavailable')
class JournalledChecksumPackagingTests(unittest.TestCase):
    fixture = JournalledInventoryTests.fixture
    def make_image(self, work, root):
        image = work / 'rootfs.img'
        subprocess.run(['mke2fs', '-q', '-t', 'ext4', '-b', '1024', '-I', '256',
                        '-O', 'none,has_journal,extents,filetype,metadata_csum', '-J', 'size=4',
                        '-E', 'lazy_itable_init=0,lazy_journal_init=0', '-m', '0', '-d', str(root),
                        str(image), '32M'], check=True, capture_output=True)
        return image

    def test_actual_literal_symlinks_and_inode_identity_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            root = self.fixture(directory)
            targets = {'relative': 'note', 'absolute': '/home/note', 'dangling': '../missing',
                       'long': '../' + 'a' * 76}
            for name, target in targets.items():
                (root / 'home' / name).symlink_to(target)
            image = self.make_image(work, root)
            debugfs = Path(shutil.which('debugfs')).resolve()
            before = {name: policy.metadata(debugfs, image, name)['inode']
                      for name in policy.inventory(root)}
            result = policy.normalize(debugfs, image, root, work)
            self.assertTrue(result['inode_identities_preserved'])
            self.assertTrue(result['literal_symlink_targets_preserved'])
            self.assertEqual(result['literal_symlink_count'], 4)
            self.assertEqual(before, {name: row['inode'] for name, row in result['applied_inode_metadata'].items()})
            for name, target in targets.items():
                number = before['/home/' + name]
                self.assertEqual(policy.literal_symlink_bytes(image, number), target.encode())
            check = subprocess.run(['e2fsck', '-fn', str(image)], capture_output=True)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)

    def test_symlink_staging_mismatch_is_refused_before_metadata_write(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            root = self.fixture(directory)
            link = root / 'home/link'
            link.symlink_to('note')
            image = self.make_image(work, root)
            unchanged = image.read_bytes()
            link.unlink()
            link.symlink_to('../missing')
            with self.assertRaisesRegex(ValueError, 'symlink target differs from staging'):
                policy.normalize(Path(shutil.which('debugfs')).resolve(), image, root, work)
            self.assertEqual(image.read_bytes(), unchanged)
            self.assertFalse((work / 'bootstrap-metadata.debugfs').exists())

    def test_inode_replacement_is_refused_after_metadata_write(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            root = self.fixture(directory)
            image = self.make_image(work, root)
            debugfs = Path(shutil.which('debugfs')).resolve()
            original = policy.metadata
            count = len(policy.inventory(root))
            calls = 0

            def observed(tool, volume, name):
                nonlocal calls
                value = original(tool, volume, name)
                calls += 1
                # Simulate namespace replacement between the two observations.
                if calls > count and name == '/home/note':
                    value['inode'] += 1
                return value

            with mock.patch.object(policy, 'metadata', side_effect=observed):
                with self.assertRaisesRegex(ValueError, 'inode identity changed'):
                    policy.normalize(debugfs, image, root, work)
            self.assertFalse(any(work.glob('metadata-file-*')))

    def test_actual_one_kib_checksum_metadata_preserves_file_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            root = self.fixture(directory)
            image = work / 'rootfs.img'
            subprocess.run(['mke2fs', '-q', '-t', 'ext4', '-b', '1024', '-I', '256',
                            '-O', 'none,has_journal,extents,filetype,metadata_csum', '-J', 'size=4',
                            '-E', 'lazy_itable_init=0,lazy_journal_init=0', '-m', '0', '-d', str(root),
                            str(image), '32M'], check=True, capture_output=True)
            before = {'/etc/services.conf': (root / 'etc/services.conf').read_bytes(),
                      '/home/note': (root / 'home/note').read_bytes(),
                      '/etc/accounts.db': (root / 'etc/accounts.db').read_bytes()}
            record = policy.normalize(Path(shutil.which('debugfs')).resolve(), image, root, work)
            self.assertTrue(record['regular_file_bytes_preserved'])
            self.assertEqual(record['applied_inode_metadata']['/etc/services.conf']['uid'], 0)
            self.assertEqual(record['applied_inode_metadata']['/home']['uid'], 0)
            self.assertEqual(record['applied_inode_metadata']['/root']['mode'], 0o40700)
            self.assertEqual(record['applied_inode_metadata']['/etc/accounts.db']['mode'], 0o100600)
            check = subprocess.run(['e2fsck', '-fn', str(image)], capture_output=True)
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            for name, expected in before.items():
                saved = work / ('verify-' + str(record['applied_inode_metadata'][name]['inode']))
                subprocess.run(['debugfs', '-R', 'dump ' + name + ' ' + str(saved), str(image)],
                               check=True, capture_output=True)
                self.assertEqual(saved.read_bytes(), expected)


if __name__ == '__main__':
    unittest.main()

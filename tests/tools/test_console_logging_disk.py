"""Hosted real-ext4 product admission; synthetic sidecars do not claim activation."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import console_login_disk as disk
import mkext4_journalled as journal


class ConsoleLoggingDiskTests(unittest.TestCase):
    def root(self, work):
        root = work / 'root'
        root.mkdir(mode=0o755)
        root.chmod(0o755)
        for name, mode in (('bin', 0o755), ('etc', 0o755), ('root', 0o700),
                           ('var', 0o755), ('var/log', 0o700)):
            path = root / name
            path.mkdir(mode=mode)
            path.chmod(mode)
        for name in disk.PRODUCTS:
            path = root / name[1:]
            path.write_bytes(disk.SERVICES if name == '/etc/services.conf' else
                             ('nonexecutable-hosted-fixture:' + name).encode())
            path.chmod(0o644 if name == '/etc/services.conf' else 0o755)
        (root / 'var/log/system.log').write_bytes(disk.CHECKPOINT0)
        (root / 'var/log/system.log').chmod(0o600)
        (root / 'etc/accounts.db').write_bytes(b'hosted account fixture\n')
        (root / 'etc/accounts.db').chmod(0o600)
        (root / 'etc/hosts').write_bytes(disk.HOSTS_SEED)
        (root / 'etc/hosts').chmod(0o644)
        return root

    def run_debugfs(self, image, command):
        result = subprocess.run([shutil.which('debugfs'), '-w', '-R', command, str(image)],
                                check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertNotIn(b'not found', result.stderr)

    def replace_log(self, work, image, name, data):
        source = work / 'replacement-log'
        source.write_bytes(data)
        self.run_debugfs(image, 'rm ' + name)
        self.run_debugfs(image, 'write ' + str(source) + ' ' + name)
        for field, value in (('uid', '0'), ('gid', '0'), ('mode', '0100600')):
            self.run_debugfs(image, 'set_inode_field ' + name + ' ' + field + ' ' + value)

    @staticmethod
    def framed(prefix):
        checksum = 2166136261
        for byte in prefix:
            checksum = ((checksum ^ byte) * 16777619) & 0xffffffff
        return prefix + (' #%08x\n' % checksum).encode()

    def image(self, work, root, console_product=None):
        image = work / 'root.img'
        with image.open('wb') as stream:
            stream.truncate(16 * 1024 * 1024)
        subprocess.run([shutil.which('mke2fs'), '-q', '-F', '-t', 'ext4', '-b', '1024',
                        '-d', str(root), str(image)], check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
        products = disk.PRODUCTS if console_product is None else console_product['files']
        paths = ('/', '/bin', '/etc', '/root', '/var', '/var/log', '/var/log/system.log',
                 '/etc/accounts.db', '/etc/hosts', *products)
        for name in paths:
            for field in ('uid', 'gid'):
                self.run_debugfs(image, 'set_inode_field ' + name + ' ' + field + ' 0')
        log = image.with_name(image.name + '.activation.log')
        log.write_text('synthetic hosted admission fixture; no Linux activation performed\n')
        image.with_name(image.name + '.manifest.json').write_text(json.dumps(dict(
            schema=1, profile='linux-activated-clean-1k-jbd2-crc32c-v3-normalized-head',
            console_login=disk.product(root) if console_product is None else console_product,
            activation_log_sha256=disk.sha(log),
            test_fixture=True)))
        return image

    def test_exact_product_binds_daemon_client_and_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(Path(directory))
            selected = disk.product(root)
            self.assertEqual(selected['profile'], 'ordinary-native-console-login-logging-time-mount-resolver-v1')
            self.assertEqual(set(selected['files']), set(disk.PRODUCTS))
            self.assertEqual(selected['files']['/bin/logd'], hashlib.sha256((root / 'bin/logd').read_bytes()).hexdigest())
            for name in ('timed', 'timectl', 'mountctl', 'resolved', 'resolvectl'):
                self.assertEqual(selected['files']['/bin/' + name],
                                 hashlib.sha256((root / 'bin' / name).read_bytes()).hexdigest())
            self.assertEqual(selected['initial_logging_checkpoint'],
                             dict(path='/var/log/system.log', sha256=hashlib.sha256(disk.CHECKPOINT0).hexdigest()))
            self.assertNotIn('/etc/hosts', selected['files'])
            self.assertEqual(selected['mutable_configuration']['hosts']['max_bytes'], 4096)
            (root / 'etc/services.conf').write_bytes(disk.SERVICES.replace(b'service logd notify /bin/logd - 0 0\n', b''))
            with self.assertRaisesRegex(ValueError, 'configuration differs'):
                disk.product(root)

    def test_missing_or_redirected_time_or_inventory_product_refuses_before_activation(self):
        for name in ('timed', 'timectl', 'mountctl', 'resolved', 'resolvectl'):
            for redirect in (False, True):
                with self.subTest(name=name, redirect=redirect), tempfile.TemporaryDirectory() as directory:
                    work = Path(directory)
                    root = self.root(work)
                    (root / 'bin' / name).unlink()
                    if redirect:
                        (root / 'bin' / name).symlink_to('logger')
                    argv = ['journal', '--root', str(root), '--out', str(work / 'disk.img'),
                            '--console-login', '--linux-image', str(work / 'unused'),
                            '--linux-image-sha256', '0' * 64]
                    with patch.object(sys, 'argv', argv), patch.object(journal, 'require') as external:
                        with self.assertRaisesRegex(ValueError, 'regular non-symlink'):
                            journal.main()
                        external.assert_not_called()

    def test_missing_or_redirected_daemon_refuses_before_activation(self):
        for redirect in (False, True):
            with self.subTest(redirect=redirect), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                root = self.root(work)
                (root / 'bin/logd').unlink()
                if redirect:
                    (root / 'bin/logd').symlink_to('logger')
                argv = ['journal', '--root', str(root), '--out', str(work / 'disk.img'),
                        '--console-login', '--linux-image', str(work / 'unused'),
                        '--linux-image-sha256', '0' * 64]
                with patch.object(sys, 'argv', argv), patch.object(journal, 'require') as external:
                    with self.assertRaisesRegex(ValueError, 'regular non-symlink'):
                        journal.main()
                    external.assert_not_called()

    def test_missing_redirected_or_changed_checkpoint_refuses_before_activation(self):
        for kind in ('missing', 'redirected', 'changed'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                root = self.root(work)
                checkpoint = root / 'var/log/system.log'
                checkpoint.unlink()
                if kind == 'redirected':
                    checkpoint.symlink_to('../../etc/accounts.db')
                if kind == 'changed':
                    checkpoint.write_bytes(disk.CHECKPOINT0.replace(b'0000000000000000', b'0000000000000001'))
                argv = ['journal', '--root', str(root), '--out', str(work / 'disk.img'),
                        '--console-login', '--linux-image', str(work / 'unused'),
                        '--linux-image-sha256', '0' * 64]
                with patch.object(sys, 'argv', argv), patch.object(journal, 'require') as external:
                    with self.assertRaisesRegex(ValueError, 'checkpoint differs' if kind == 'changed' else 'regular non-symlink'):
                        journal.main()
                    external.assert_not_called()

    @unittest.skipUnless(shutil.which('debugfs') and shutil.which('mke2fs'), 'ext4 tools required')
    def test_real_image_admits_both_products_and_refuses_metadata_or_byte_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            root = self.root(work)
            original = self.image(work, root)
            debugfs = Path(shutil.which('debugfs'))
            before = disk.sha(original)
            disk.initial_seed(original, debugfs)
            self.assertEqual(disk.admit(original, root, debugfs), disk.product(root))
            self.assertEqual(disk.sha(original), before)
            for name, field, value in (('/bin/logd', 'mode', '0100644'),
                                       ('/bin/logger', 'uid', '1000'),
                                       ('/bin/timed', 'mode', '0100644'),
                                       ('/bin/timed', 'uid', '1000'),
                                       ('/bin/timed', 'links_count', '2'),
                                       ('/bin/timectl', 'gid', '1000'),
                                       ('/bin/timectl', 'mode', '0120755'),
                                       ('/bin/timectl', 'links_count', '2'),
                                       ('/bin/mountctl', 'mode', '0100644'),
                                       ('/bin/mountctl', 'uid', '1000'),
                                       ('/bin/mountctl', 'gid', '1000'),
                                       ('/bin/mountctl', 'links_count', '2'),
                                       ('/bin/mountctl', 'mode', '0120755'),
                                       ('/bin/resolved', 'uid', '1000'),
                                       ('/bin/resolved', 'mode', '0100644'),
                                       ('/bin/resolvectl', 'gid', '1000'),
                                       ('/bin/resolvectl', 'links_count', '2'),
                                       ('/etc/hosts', 'uid', '1000'),
                                       ('/etc/hosts', 'gid', '1000'),
                                       ('/etc/hosts', 'mode', '0100664'),
                                       ('/etc/hosts', 'mode', '0120644'),
                                       ('/etc/hosts', 'links_count', '2'),
                                       ('/etc/hosts', 'size', '4097'),
                                       ('/var/log/system.log', 'mode', '0100644'),
                                       ('/var/log/system.log', 'uid', '1000'),
                                       ('/var/log/system.log', 'gid', '1000'),
                                       ('/var/log/system.log', 'links_count', '2'),
                                       ('/var/log/system.log', 'mode', '0120600'),
                                       ('/var/log/system.log', 'size', '8193'),
                                       ('/var/log', 'mode', '040755'),
                                       ('/var', 'gid', '1000')):
                with self.subTest(name=name, field=field):
                    image = work / 'mutated.img'
                    shutil.copy2(original, image)
                    for suffix in ('.activation.log', '.manifest.json'):
                        shutil.copy2(original.with_name(original.name + suffix), image.with_name(image.name + suffix))
                    self.run_debugfs(image, 'set_inode_field ' + name + ' ' + field + ' ' + value)
                    mutation = disk.sha(image)
                    with self.assertRaisesRegex(ValueError, 'metadata differs'):
                        disk.admit(image, root, debugfs)
                    self.assertEqual(disk.sha(image), mutation)
            image = work / 'changed-product.img'
            shutil.copy2(original, image)
            for suffix in ('.activation.log', '.manifest.json'):
                shutil.copy2(original.with_name(original.name + suffix), image.with_name(image.name + suffix))
            self.replace_log(work, image, '/bin/logger', b'different persisted client bytes')
            mutation = disk.sha(image)
            with self.assertRaisesRegex(ValueError, 'product differs from the selected build'):
                disk.admit(image, root, debugfs)
            self.assertEqual(disk.sha(image), mutation)
            (root / 'bin/logger').write_bytes(b'different selected client bytes')
            with self.assertRaisesRegex(ValueError, 'matching complete activation/product evidence'):
                disk.admit(original, root, debugfs)

    @unittest.skipUnless(shutil.which('debugfs') and shutil.which('mke2fs'), 'ext4 tools required')
    def test_time_or_inventory_binary_byte_drift_refuses_without_rewriting_the_disk(self):
        for name in ('timed', 'timectl', 'mountctl', 'resolved', 'resolvectl'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                root = self.root(work)
                image = self.image(work, root)
                self.replace_log(work, image, '/bin/' + name, b'changed time product bytes')
                self.run_debugfs(image, 'set_inode_field /bin/' + name + ' mode 0100755')
                before = disk.sha(image)
                with self.assertRaisesRegex(ValueError, 'product differs from the selected build'):
                    disk.admit(image, root, Path(shutil.which('debugfs')))
                self.assertEqual(disk.sha(image), before)

    @unittest.skipUnless(shutil.which('debugfs') and shutil.which('mke2fs'), 'ext4 tools required')
    def test_prior_time_product_refuses_without_upgrading_enrollment(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            root = self.root(work)
            prior = disk.product(root)
            prior['profile'] = 'ordinary-native-console-login-logging-time-v1'
            del prior['files']['/bin/mountctl']
            (root / 'bin/mountctl').unlink()
            (root / 'etc/accounts.db').write_bytes(b'opaque enrolled account bytes\n')
            image = self.image(work, root, prior)
            (root / 'bin/mountctl').write_bytes(b'new inventory executable fixture')
            protected = (image, image.with_name(image.name + '.manifest.json'),
                         image.with_name(image.name + '.activation.log'), root / 'etc/accounts.db')
            before = {path: disk.sha(path) for path in protected}
            with patch.object(disk.subprocess, 'run') as external:
                with self.assertRaisesRegex(ValueError, 'matching complete activation/product evidence'):
                    disk.admit(image, root, Path(shutil.which('debugfs')))
                external.assert_not_called()
            self.assertEqual({path: disk.sha(path) for path in protected}, before)

    @unittest.skipUnless(shutil.which('debugfs') and shutil.which('mke2fs'), 'ext4 tools required')
    def test_old_enrolled_profile_is_refused_without_upgrade_or_account_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            root = self.root(work)
            legacy = disk.product(root)
            legacy['profile'] = 'ordinary-native-console-login-logging-v2'
            for name in ('timed', 'timectl', 'mountctl'):
                del legacy['files']['/bin/' + name]
                (root / 'bin' / name).unlink()
            old_services = disk.SERVICES.replace(b'service timed notify /bin/timed - 0 0\n', b'')
            (root / 'etc/services.conf').write_bytes(old_services)
            legacy['files']['/etc/services.conf'] = hashlib.sha256(old_services).hexdigest()
            (root / 'etc/accounts.db').write_bytes(b'opaque existing enrolled account bytes\n')
            image = self.image(work, root, legacy)
            for name in ('timed', 'timectl', 'mountctl'):
                path = root / 'bin' / name
                path.write_bytes(('nonexecutable-hosted-fixture:/bin/' + name).encode())
                path.chmod(0o755)
            (root / 'etc/services.conf').write_bytes(disk.SERVICES)
            protected = (image, image.with_name(image.name + '.manifest.json'),
                         image.with_name(image.name + '.activation.log'))
            before = {path: disk.sha(path) for path in protected}
            # An obsolete product is refused before inspecting or modifying the
            # persisted image. Existing enrollment is never an upgrade input.
            with patch.object(disk.subprocess, 'run') as external:
                with self.assertRaisesRegex(ValueError, 'matching complete activation/product evidence'):
                    disk.admit(image, root, Path(shutil.which('debugfs')))
                external.assert_not_called()
            self.assertEqual({path: disk.sha(path) for path in protected}, before)

    def test_hosts_snapshot_refuses_descriptor_metadata_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(Path(directory)); actual = disk.os.fstat; calls = 0
            def changed(descriptor):
                nonlocal calls
                metadata = actual(descriptor); calls += 1
                if calls != 2:
                    return metadata
                fields = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink', 'st_size',
                          'st_mtime_ns', 'st_ctime_ns')
                values = {key: getattr(metadata, key) for key in fields}
                values['st_size'] += 1
                return SimpleNamespace(**values)
            with patch.object(disk.os, 'fstat', side_effect=changed):
                with self.assertRaisesRegex(ValueError, 'changed while reading'):
                    disk.hosts_snapshot(root / 'etc/hosts')

    def test_mutable_staged_hosts_does_not_change_immutable_product_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(Path(directory)); selected = disk.product(root)
            (root / 'etc/hosts').write_bytes(b'192.0.2.1 example.test alias.test\n')
            self.assertEqual(disk.product(root), selected)
            self.assertNotIn('/etc/hosts', selected['files'])
            for mode in (0o666, 0o600, 0o755, 0o2644):
                (root / 'etc/hosts').chmod(mode)
                with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, 'hosts packaging metadata'):
                    disk.product(root)
            (root / 'etc/hosts').chmod(0o644)
            (root / 'etc/hosts').write_bytes(b'x' * 4097)
            with self.assertRaisesRegex(ValueError, 'hosts packaging metadata'):
                disk.product(root)

    @unittest.skipUnless(shutil.which('debugfs') and shutil.which('mke2fs'), 'ext4 tools required')
    def test_mutable_persisted_hosts_edits_reuse_without_executable_rehash_or_disk_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory); root = self.root(work); image = self.image(work, root)
            selected = disk.product(root); debugfs = Path(shutil.which('debugfs'))
            self.replace_log(work, image, '/etc/hosts', b'192.0.2.1 example.test alias.test\n')
            self.run_debugfs(image, 'set_inode_field /etc/hosts mode 0100644')
            before = disk.sha(image)
            self.assertEqual(disk.admit(image, root, debugfs), selected)
            self.assertEqual(disk.sha(image), before)
            self.run_debugfs(image, 'set_inode_field /etc/hosts size 4097')
            before = disk.sha(image)
            with self.assertRaisesRegex(ValueError, 'hosts metadata differs'):
                disk.admit(image, root, debugfs)
            self.assertEqual(disk.sha(image), before)

    @unittest.skipUnless(shutil.which('debugfs') and shutil.which('mke2fs'), 'ext4 tools required')
    def test_prior_mount_profile_refuses_before_disk_inspection_or_account_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory); root = self.root(work); prior = disk.product(root)
            prior['profile'] = 'ordinary-native-console-login-logging-time-mount-v1'
            del prior['mutable_configuration']
            for name in ('resolved', 'resolvectl'):
                del prior['files']['/bin/' + name]
            old_services = disk.SERVICES.replace(b'service resolved notify /bin/resolved - 0 0\n', b'')
            prior['files']['/etc/services.conf'] = hashlib.sha256(old_services).hexdigest()
            image = self.image(work, root, prior)
            protected = (image, image.with_name(image.name + '.manifest.json'),
                         image.with_name(image.name + '.activation.log'), root / 'etc/accounts.db')
            before = {path: disk.sha(path) for path in protected}
            with patch.object(disk.subprocess, 'run') as external:
                with self.assertRaisesRegex(ValueError, 'matching complete activation/product evidence'):
                    disk.admit(image, root, Path(shutil.which('debugfs')))
                external.assert_not_called()
            self.assertEqual({path: disk.sha(path) for path in protected}, before)

    @unittest.skipUnless(shutil.which('debugfs') and shutil.which('mke2fs'), 'ext4 tools required')
    def test_mutable_live_logs_preserve_console_reuse_and_daemon_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            root = self.root(work)
            image = self.image(work, root)
            debugfs = Path(shutil.which('debugfs'))
            selected = disk.product(root)
            checkpoint = self.framed(b'OKLB1 000000000000000d')
            record = self.framed(b'OKLR1 000000000000000e 0000000000003039 00000049 00000000 00000000 001 78')
            for data in (checkpoint + record, checkpoint + record[:20], b'preserved corrupt log\n'):
                with self.subTest(data=data):
                    self.replace_log(work, image, '/var/log/system.log', data)
                    before = disk.sha(image)
                    self.assertEqual(disk.admit(image, root, debugfs), selected)
                    self.assertEqual(disk.sha(image), before)
                    with self.assertRaisesRegex(ValueError, 'initial logging checkpoint differs'):
                        disk.initial_seed(image, debugfs)
                    self.assertEqual(disk.sha(image), before)
            self.run_debugfs(image, 'rm /var/log/system.log')
            # Missing current is a daemon recovery state; console admission
            # does not recreate it or rewrite an existing account disk.
            self.assertEqual(disk.admit(image, root, debugfs), selected)
            source = work / 'archive'
            source.write_bytes(checkpoint + record)
            self.run_debugfs(image, 'write ' + str(source) + ' /var/log/system.prev')
            self.run_debugfs(image, 'set_inode_field /var/log/system.prev mode 0100600')
            self.assertEqual(disk.admit(image, root, debugfs), selected)
            self.run_debugfs(image, 'set_inode_field /var/log/system.prev mode 0100644')
            with self.assertRaisesRegex(ValueError, 'metadata differs'):
                disk.admit(image, root, debugfs)


if __name__ == '__main__':
    unittest.main()

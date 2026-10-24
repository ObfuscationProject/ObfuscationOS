"""Hosted packaging/admission controls; no native login execution evidence."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import stage_rootfs as stage
import mkext4_journalled as journal


class NativeConsoleProfileTests(unittest.TestCase):
    def project(self, work):
        project = work / 'project'
        (project / 'config').mkdir(parents=True)
        for name in ('services.conf', 'services-login.conf', 'hosts'):
            (project / 'config' / name).write_bytes((ROOT / 'config' / name).read_bytes())
            (project / 'config' / name).chmod(0o644)
        module = project / 'modules/system-gui/system-gui.okmod'
        module.parent.mkdir(parents=True)
        module.write_bytes(b'module fixture')
        apps = work / 'apps'
        apps.mkdir()
        for name in (*stage.APPS, 'login'):
            (apps / (name + '.elf')).write_bytes(name.encode())
        return project, apps

    def run_stage(self, project, apps, out, *extra):
        with patch.object(stage, '__file__', str(project / 'tools/stage_rootfs.py')), \
             patch.object(sys, 'argv', ['stage_rootfs', '--apps-dir', str(apps), '--out', str(out), *extra]):
            return stage.main()

    def test_selected_profile_stages_ordinary_login_and_exact_native_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            project, apps = self.project(work)
            for selected in (False, True):
                out = work / ('login' if selected else 'maintenance')
                self.assertEqual(self.run_stage(project, apps, out, *(['--console-login'] if selected else [])), 0)
                self.assertEqual((out / 'bin/login').exists(), selected)
                for name in ('timed', 'timectl', 'mountctl', 'resolved', 'resolvectl'):
                    self.assertEqual((out / 'bin' / name).read_bytes(), name.encode())
                    self.assertEqual((out / 'bin' / name).stat().st_mode & 0o7777, 0o755)
                if selected:
                    self.assertEqual((out / 'bin/login').read_bytes(), b'login')
                    self.assertEqual((out / 'bin/login').stat().st_mode & 0o7777, 0o755)
                manifest = 'services-login.conf' if selected else 'services.conf'
                self.assertEqual((out / 'etc/services.conf').read_bytes(), (project / 'config' / manifest).read_bytes())
                self.assertEqual(b'service timed notify /bin/timed - 0 0\n' in
                                 (out / 'etc/services.conf').read_bytes(), selected)
                self.assertEqual((out / 'etc/accounts.db').read_bytes(), stage.ACCOUNT_DATABASE_SEED)
                self.assertEqual((out / 'etc/accounts.db').stat().st_mode & 0o7777, 0o600)
                self.assertEqual((out / 'etc/hosts').read_bytes(), b'127.0.0.1 localhost\n')
                self.assertEqual((out / 'etc/hosts').stat().st_mode & 0o7777, 0o644)
                self.assertEqual((out / 'root').stat().st_mode & 0o7777, 0o700)
                self.assertFalse((out / 'bin/oksh-real').exists())

    def test_missing_login_or_linux_pid1_selection_preserves_previous_output(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            project, apps = self.project(work)
            out = work / 'out'
            out.mkdir()
            (out / 'preserved').write_bytes(b'previous root')
            for option, pin in (('--managed-init-build', '--managed-init-manifest-sha256'),
                                ('--service-graph-build', '--service-graph-manifest-sha256')):
                with self.assertRaises(SystemExit):
                    self.run_stage(project, apps, out, '--console-login', option, str(work / 'external'), pin, '0' * 64)
            (apps / 'login.elf').unlink()
            with self.assertRaises(SystemExit):
                self.run_stage(project, apps, out, '--console-login')
            self.assertEqual((out / 'preserved').read_bytes(), b'previous root')

    def test_missing_time_products_preserve_previous_output(self):
        for name in ('timed', 'timectl', 'resolved', 'resolvectl'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                project, apps = self.project(work)
                out = work / 'out'; out.mkdir()
                (out / 'preserved').write_bytes(b'previous root')
                (apps / (name + '.elf')).unlink()
                with self.assertRaisesRegex(SystemExit, 'missing app'):
                    self.run_stage(project, apps, out, '--console-login')
                self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()},
                                 {'preserved': b'previous root'})

    def test_console_service_drift_refuses_before_previous_output_mutation(self):
        for mutation in ('missing', 'simple', 'unprivileged', 'reordered'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                project, apps = self.project(work)
                configuration = project / 'config/services-login.conf'
                original = configuration.read_bytes()
                row = b'service timed notify /bin/timed - 0 0\n'
                changed = {
                    'missing': original.replace(row, b''),
                    'simple': original.replace(row, row.replace(b'notify', b'simple')),
                    'unprivileged': original.replace(row, row.replace(b'0 0', b'1000 1000')),
                    'reordered': original.replace(row, b'').replace(b'OK_SERVICE_MANIFEST 2\n',
                        b'OK_SERVICE_MANIFEST 2\n' + row),
                }[mutation]
                configuration.write_bytes(changed)
                out = work / 'out'; out.mkdir()
                (out / 'preserved').write_bytes(b'previous root')
                with self.assertRaisesRegex(SystemExit, 'exact selected service configuration'):
                    self.run_stage(project, apps, out, '--console-login')
                self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()},
                                 {'preserved': b'previous root'})

    def test_unsafe_hosts_seed_refuses_before_previous_output_mutation(self):
        for kind in ('missing', 'symlink', 'parent-symlink', 'hardlink', 'writable', 'oversized', 'directory'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                project, apps = self.project(work)
                seed = project / 'config/hosts'
                if kind in ('missing', 'symlink', 'hardlink', 'directory'):
                    seed.unlink()
                if kind == 'symlink':
                    seed.symlink_to('services.conf')
                elif kind == 'parent-symlink':
                    (project / 'config').rename(project / 'actual-config')
                    (project / 'config').symlink_to('actual-config', target_is_directory=True)
                elif kind == 'hardlink':
                    seed.hardlink_to(project / 'config/services.conf')
                elif kind == 'writable':
                    seed.chmod(0o666)
                elif kind == 'oversized':
                    seed.write_bytes(b'x' * 4097)
                elif kind == 'directory':
                    seed.mkdir()
                out = work / 'out'; out.mkdir(); (out / 'preserved').write_bytes(b'previous root')
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.run_stage(project, apps, out, '--console-login')
                self.assertEqual({p.name: p.read_bytes() for p in out.iterdir()}, {'preserved': b'previous root'})

    def test_journal_output_and_sidecar_collisions_refuse_before_activation(self):
        for suffix, symlink in (('', False), ('', True), ('.activation.log', False),
                                ('.manifest.json', False), ('.manifest.json', True)):
            with self.subTest(suffix=suffix, symlink=symlink), tempfile.TemporaryDirectory() as directory:
                work = Path(directory)
                root = work / 'root'
                root.mkdir()
                original = work / 'original'
                original.write_bytes(b'account disk bytes must survive')
                out = work / 'root.img'
                collision = out.with_name(out.name + suffix)
                if symlink:
                    collision.symlink_to(original)
                else:
                    collision.write_bytes(original.read_bytes())
                argv = ['mkext4_journalled', '--root', str(root), '--out', str(out),
                        '--linux-image', str(work / 'unused-linux'), '--linux-image-sha256', '0' * 64]
                with patch.object(sys, 'argv', argv), patch.object(journal, 'require') as external:
                    with self.assertRaises(SystemExit):
                        journal.main()
                    external.assert_not_called()
                self.assertEqual(original.read_bytes(), b'account disk bytes must survive')
                self.assertEqual(collision.read_bytes(), original.read_bytes())


if __name__ == '__main__':
    unittest.main()

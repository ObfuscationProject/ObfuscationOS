"""Hosted service configuration and staging controls; no target execution."""
from pathlib import Path
import os
import hashlib
import json
import shutil
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from service_manifest_config import parse, snapshot, BYTE_LIMIT
import stage_rootfs
import service_graph_build
from test_managed_init_elf import static_elf

DEFAULT = b'OK_SERVICE_MANIFEST 1\nservice console simple /bin/oksh -\n'


class ServiceManifestConfigTests(unittest.TestCase):
    def staging_fixture(self, root):
        """Powerless ELF metadata fixture: production staging/admission, no executable run."""
        project = root / 'project'
        source = Path(__file__).resolve().parents[2]
        for name in (*service_graph_build.SOURCES, 'tests/musl/bootstrap.ld',
                     'tools/seal_service_graph_build.py', 'modules/system-gui/system-gui.okmod'):
            destination = project / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, destination)
        config = project / 'config/services.conf'; config.parent.mkdir()
        config.write_bytes(DEFAULT); config.chmod(0o644)
        (project / 'config/hosts').write_bytes(b'127.0.0.1 localhost\n')
        (project / 'config/hosts').chmod(0o644)
        build = root / 'build'; build.mkdir()
        elf = build / 'bootstrap.elf'; elf.write_bytes(static_elf('x86_64'))
        original = dict(schema_version=1, status='built-not-executed', executed=False,
            architecture='x86_64', source_mode='debug', mode='debug',
            probe_sha256=service_graph_build.sha(project / service_graph_build.SOURCES[0]),
            linker_script_sha256=service_graph_build.sha(project / 'tests/musl/bootstrap.ld'),
            elf_sha256=service_graph_build.sha(elf),
            elf=stage_rootfs.inspect_managed_init_elf(elf.read_bytes(), 'x86_64'))
        unsealed = build / 'unsealed-manifest.json'; unsealed.write_text(json.dumps(original))
        sealed = dict(original, service_graph_profile=service_graph_build.PROFILE,
            service_manifest_sha256=hashlib.sha256(DEFAULT).hexdigest(),
            original_manifest_sha256=service_graph_build.sha(unsealed),
            service_graph_sealer_sha256=service_graph_build.sha(project / 'tools/seal_service_graph_build.py'),
            project_source_dependencies={name: service_graph_build.sha(project / name) for name in service_graph_build.SOURCES},
            service_graph_sysroot_dependencies={}, project_dependency_command=['metadata-model', '-M'])
        (build / 'manifest.json').write_text(json.dumps(sealed))
        apps = root / 'apps'; apps.mkdir()
        for name in stage_rootfs.APPS: (apps / (name + '.elf')).write_bytes(name.encode())
        output = root / 'output'; output.mkdir(); (output / 'existing').write_bytes(b'keep')
        argv = ['stage_rootfs', '--apps-dir', str(apps), '--out', str(output), '--arch', 'x86_64',
            '--service-graph-build', str(build), '--service-graph-manifest-sha256', service_graph_build.sha(build / 'manifest.json')]
        return project, config, output, argv

    def test_single_admitted_snapshot_is_staged_after_source_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            project, config, output, argv = self.staging_fixture(Path(directory))
            actual_admit = service_graph_build.admit
            replacement = DEFAULT.replace(b'/bin/oksh', b'/bin/hello')
            admitted = []
            def replace_after_admit(build, expected, arch, selected_project, *, configuration):
                selected = actual_admit(build, expected, arch, selected_project, configuration=configuration)
                admitted.append(configuration)
                config.write_bytes(replacement)
                return selected
            with patch.object(stage_rootfs, '__file__', str(project / 'tools/stage_rootfs.py')), \
                 patch.object(stage_rootfs, 'service_config_snapshot', wraps=snapshot) as selected, \
                 patch.object(service_graph_build, 'snapshot', side_effect=AssertionError('admission must not reread config')), \
                 patch.object(service_graph_build, 'admit', side_effect=replace_after_admit), \
                 patch.object(sys, 'argv', argv):
                self.assertEqual(stage_rootfs.main(), 0)
                self.assertEqual(selected.call_count, 1)
            self.assertEqual(admitted, [DEFAULT])
            self.assertEqual(config.read_bytes(), replacement)
            self.assertEqual((output / 'etc/services.conf').read_bytes(), DEFAULT)

    def test_snapshot_seal_mismatch_refuses_before_existing_output_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            project, config, output, argv = self.staging_fixture(Path(directory))
            config.write_bytes(DEFAULT.replace(b'/bin/oksh', b'/bin/hello'))
            with patch.object(stage_rootfs, '__file__', str(project / 'tools/stage_rootfs.py')), \
                 patch.object(stage_rootfs, 'service_config_snapshot', wraps=snapshot) as selected, \
                 patch.object(service_graph_build, 'snapshot', side_effect=AssertionError('admission must not reread config')), \
                 patch.object(sys, 'argv', argv), self.assertRaises(SystemExit):
                stage_rootfs.main()
            self.assertEqual(selected.call_count, 1)
            self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, {'existing': b'keep'})

    def test_forward_dependencies_and_boundary_document(self):
        records = parse(b'OK_SERVICE_MANIFEST 1\n# ASCII comment\nservice leaf notify /leaf left,right\n'
                        b'service left simple /left root\nservice right oneshot /right root\nservice root simple /root -\n')
        self.assertEqual(records[0]['dependencies'], 6)
        self.assertEqual(records[1]['dependencies'], 8)
        self.assertTrue(all((record['uid'], record['gid']) == (0, 0) for record in records))
        maximum = b'OK_SERVICE_MANIFEST 1\n' + b''.join(
            f'service n{number} simple /app -\n'.encode() for number in range(8))
        self.assertEqual(len(parse(maximum)), 8)
        maximum += b'#' + b'x' * (BYTE_LIMIT - len(maximum) - 2) + b'\n'
        self.assertEqual(len(maximum), BYTE_LIMIT)
        self.assertEqual(len(parse(maximum)), 8)
        with self.assertRaises(ValueError): parse(maximum[:-1] + b'x\n')

    def test_versioned_permanent_identities(self):
        records = parse(b'OK_SERVICE_MANIFEST 2\n# Explicit service identities\n'
                        b'service worker notify /worker root 1001 2002\n'
                        b'service root oneshot /setup - 0 0\n'
                        b'service boundary simple /boundary root 4294967294 4294967294\n')
        self.assertEqual([(r['uid'], r['gid']) for r in records],
                         [(1001, 2002), (0, 0), (4294967294, 4294967294)])
        self.assertEqual(records[0]['dependencies'], 2)
        for value in ('', '00', '01', '-1', '+1', '0x1', '1x', '4294967295', '4294967296', '999999999999999999999'):
            for uid, gid in ((value, '0'), ('0', value)):
                payload = f'OK_SERVICE_MANIFEST 2\nservice worker simple /worker - {uid} {gid}\n'.encode()
                with self.subTest(uid=uid, gid=gid), self.assertRaises(ValueError): parse(payload)
        for payload in (DEFAULT + b'service other simple /other - 1 1\n',
                        b'OK_SERVICE_MANIFEST 2\nservice worker simple /worker - 0 0 extra\n',
                        b'OK_SERVICE_MANIFEST 3\nservice worker simple /worker - 0 0\n'):
            with self.subTest(payload=payload), self.assertRaises(ValueError): parse(payload)

    def test_malformed_and_unknown_configuration(self):
        bad = [b'', b'OK_SERVICE_MANIFEST 2\n' + DEFAULT.split(b'\n', 1)[1],
               b'OK_SERVICE_MANIFEST 1\n', DEFAULT[:-1], DEFAULT.replace(b' simple ', b' future '),
               DEFAULT.replace(b'service ', b'unknown '), DEFAULT.replace(b' -\n', b' - extra\n'),
               DEFAULT.replace(b'service ', b'service  '), DEFAULT.replace(b'/bin/oksh', b'relative'),
               DEFAULT.replace(b'console', b'-'), DEFAULT.replace(b' -\n', b' console\n'),
               DEFAULT.replace(b' -\n', b' missing\n'), DEFAULT.replace(b'\n', b'\r\n'),
               DEFAULT + b'#forbidden\tcomment\n', DEFAULT + b'unknown policy\n',
               DEFAULT + DEFAULT.split(b'\n', 1)[1],
               b'OK_SERVICE_MANIFEST 1\nservice a simple /a b,b\nservice b simple /b -\n',
               b'OK_SERVICE_MANIFEST 1\nservice a simple /a b,\nservice b simple /b -\n',
               b'OK_SERVICE_MANIFEST 1\nservice a simple /a b\nservice b simple /b a\n',
               b'OK_SERVICE_MANIFEST 1\n' + b''.join(f'service n{i} simple /a -\n'.encode() for i in range(9))]
        for index in range(len(DEFAULT)):
            bad.extend((DEFAULT[:index] + b'\0' + DEFAULT[index + 1:], DEFAULT[:index] + b'\xff' + DEFAULT[index + 1:]))
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(ValueError): parse(payload)

    def test_snapshot_file_limits_and_unsafe_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'config'
            source.write_bytes(DEFAULT); source.chmod(0o644)
            self.assertEqual(snapshot(source), DEFAULT)
            source.chmod(0o664)
            with self.assertRaises(ValueError): snapshot(source)
            source.chmod(0o644)
            alias = Path(directory) / 'alias'; alias.symlink_to(source)
            with self.assertRaises(OSError): snapshot(alias)
            fifo = Path(directory) / 'fifo'; os.mkfifo(fifo)
            with self.assertRaises(ValueError): snapshot(fifo)
            with self.assertRaises(ValueError): snapshot(Path(directory))
            source.write_bytes(b'x' * (BYTE_LIMIT + 1))
            with self.assertRaises(ValueError): snapshot(source)
            source.write_bytes(b'bad\n')
            with self.assertRaises(ValueError): snapshot(source)
            source.unlink()
            with self.assertRaises(OSError): snapshot(source)

    def test_snapshot_short_read_eintr_and_metadata_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'config'; source.write_bytes(DEFAULT); source.chmod(0o644)
            actual_read = os.read
            reads = 0
            def short_read(fd, size):
                nonlocal reads
                reads += 1
                if reads == 1: raise InterruptedError()
                return actual_read(fd, min(size, 2))
            with patch('service_manifest_config.os.read', side_effect=short_read):
                self.assertEqual(snapshot(source), DEFAULT)
            actual_stat = os.fstat
            calls = 0
            def changed(fd):
                nonlocal calls
                result = actual_stat(fd); calls += 1
                if calls == 2:
                    values = list(result); values[6] += 1
                    return os.stat_result(values)
                return result
            with patch('service_manifest_config.os.fstat', side_effect=changed), self.assertRaises(ValueError): snapshot(source)

    def test_staging_preflight_preserves_existing_output_and_uses_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); apps = root / 'apps'; apps.mkdir()
            for app in stage_rootfs.APPS: (apps / (app + '.elf')).write_bytes(app.encode())
            output = root / 'staged'; output.mkdir(); (output / 'existing').write_bytes(b'keep')
            argv = ['stage_rootfs', '--apps-dir', str(apps), '--out', str(output)]
            for failure in (ValueError('invalid'), FileNotFoundError('missing')):
                with patch.object(sys, 'argv', argv), patch.object(stage_rootfs, 'service_config_snapshot', side_effect=failure), self.assertRaises(type(failure)):
                    stage_rootfs.main()
                self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, {'existing': b'keep'})
            with patch.object(sys, 'argv', argv), patch.object(stage_rootfs, 'service_config_snapshot', return_value=DEFAULT) as selected:
                self.assertEqual(stage_rootfs.main(), 0)
                self.assertEqual(selected.call_count, 1)
            self.assertEqual((output / 'etc/services.conf').read_bytes(), DEFAULT)
            self.assertEqual(stat.S_IMODE((output / 'etc/services.conf').stat().st_mode), 0o644)
            self.assertEqual(stat.S_IMODE((output / 'etc').stat().st_mode), 0o755)


if __name__ == '__main__': unittest.main()

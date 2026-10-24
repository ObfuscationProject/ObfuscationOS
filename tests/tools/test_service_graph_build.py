"""Production graph admission models; these tests do not compile or execute ELF."""
from pathlib import Path
import copy
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from service_graph_build import admit, sha, PROFILE, SOURCES
from stage_rootfs import inspect_managed_init_elf
from test_managed_init_elf import static_elf

PROJECT = Path(__file__).resolve().parents[2]


class ServiceGraphBuildAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.build = Path(self.temporary.name)
        payload = static_elf('x86_64')
        (self.build / 'bootstrap.elf').write_bytes(payload)
        self.original = dict(schema_version=1, status='built-not-executed', executed=False,
            architecture='x86_64', source_mode='debug', mode='debug',
            probe_sha256=sha(PROJECT / 'apps/init/service_manager.c'),
            linker_script_sha256=sha(PROJECT / 'tests/musl/bootstrap.ld'),
            elf_sha256=sha(self.build / 'bootstrap.elf'),
            elf=inspect_managed_init_elf(payload, 'x86_64'))
        (self.build / 'unsealed-manifest.json').write_text(json.dumps(self.original))
        self.record = dict(self.original,
            service_graph_profile=PROFILE,
            service_manifest_sha256=sha(PROJECT / 'config/services.conf'),
            original_manifest_sha256=sha(self.build / 'unsealed-manifest.json'),
            service_graph_sealer_sha256=sha(PROJECT / 'tools/seal_service_graph_build.py'),
            project_source_dependencies={name: sha(PROJECT / name) for name in SOURCES},
            service_graph_sysroot_dependencies={}, project_dependency_command=['compiler', '-M'])

    def seal(self, record):
        path = self.build / 'manifest.json'
        path.write_text(json.dumps(record))
        return sha(path)

    def test_explicit_production_profile(self):
        pin = self.seal(self.record)
        self.assertEqual(admit(self.build, pin, 'x86_64', PROJECT), self.build / 'bootstrap.elf')
        with self.assertRaises(ValueError): admit(self.build, '0' * 64, 'x86_64', PROJECT)
        with self.assertRaises(ValueError): admit(self.build, pin, 'i386', PROJECT)

    def test_explicit_snapshot_is_immutable_parsed_and_bound_to_seal(self):
        payload = (PROJECT / 'config/services.conf').read_bytes()
        pin = self.seal(self.record)
        self.assertEqual(admit(self.build, pin, 'x86_64', PROJECT, configuration=payload), self.build / 'bootstrap.elf')
        for changed in (payload.replace(b'/bin/oksh', b'/bin/hello'), b'bad\n', bytearray(payload), 'not bytes'):
            with self.subTest(payload=changed), self.assertRaises(ValueError):
                admit(self.build, pin, 'x86_64', PROJECT, configuration=changed)

    def test_rehashed_test_source_and_changed_contract_are_rejected(self):
        mutations = [('status', 'passed'), ('executed', True), ('architecture', 'rv64'),
                     ('source_mode', 'release'), ('mode', 'release'),
                     ('service_graph_profile', 'test-mode'),
                     ('service_manifest_sha256', '0' * 64),
                     ('service_graph_profile', 'bounded-dependency-notify-v1'),
                     ('probe_sha256', sha(PROJECT / 'tests/musl/service_graph_init.c')),
                     ('original_manifest_sha256', '0' * 64),
                     ('service_graph_sealer_sha256', '0' * 64),
                     ('linker_script_sha256', '0' * 64), ('elf_sha256', '0' * 64)]
        for key, value in mutations:
            record = copy.deepcopy(self.record); record[key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                admit(self.build, self.seal(record), 'x86_64', PROJECT)

    def test_source_dependency_omission_or_extension_is_rejected(self):
        for name in list(self.record['project_source_dependencies']) + ['tests/musl/service_graph_init.c']:
            record = copy.deepcopy(self.record)
            if name in record['project_source_dependencies']: del record['project_source_dependencies'][name]
            else: record['project_source_dependencies'][name] = sha(PROJECT / name)
            with self.subTest(name=name), self.assertRaises(ValueError):
                admit(self.build, self.seal(record), 'x86_64', PROJECT)

    def test_sealer_must_preserve_original_build(self):
        record = copy.deepcopy(self.record)
        record['elf']['machine'] = 183
        with self.assertRaisesRegex(ValueError, 'original build'):
            admit(self.build, self.seal(record), 'x86_64', PROJECT)
        record = copy.deepcopy(self.record)
        record['unreviewed_extension'] = True
        with self.assertRaisesRegex(ValueError, 'original build'):
            admit(self.build, self.seal(record), 'x86_64', PROJECT)


if __name__ == '__main__': unittest.main()

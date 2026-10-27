"""Exact metadata capability admission on both sides; no code or guest loading."""
from pathlib import Path
import hashlib
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import kernel_sdk as consumer
import test_kernel_sdk as fixtures
import kernel_checkout

producer = kernel_checkout.load_producer('native_metadata_sdk_producer')


@kernel_checkout.requires_checkout
class NativeMetadataSdkTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.KernelSdkTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.sdk = self.fixture.sdk
        self.profile = self.sdk / 'include' / consumer.NATIVE_METADATA_PROFILE_HEADER
        self.uapi = self.sdk / 'include/ok/uapi/syscall.h'
        self.good_profile = self.profile.read_text()
        self.good_uapi = self.uapi.read_text()

    def rehash(self, path):
        self.fixture.manifest['files'][str(path.relative_to(self.sdk))] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.fixture.save()

    def refused(self):
        for validate in (producer.validate_native_metadata_profile, consumer.validate_native_metadata_profile):
            with self.assertRaises(ValueError):
                validate(self.sdk / 'include')
        with self.assertRaises(ValueError):
            consumer.validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_exact_profile_and_uapi_admitted_on_both_sides(self):
        for validate in (producer.validate_native_metadata_profile, consumer.validate_native_metadata_profile):
            validate(self.sdk / 'include')
        self.assertEqual(consumer.validate_sdk(self.sdk, 'x86_64', 'debug')['abi_version'], 75)
        self.assertEqual(consumer.NATIVE_METADATA_DEFINES, producer.NATIVE_METADATA_DEFINES)
        self.assertEqual(consumer.NATIVE_METADATA_HEADERS, producer.NATIVE_METADATA_HEADERS)

    def test_manifest_requires_exact_profile_and_all_hashed_dependencies(self):
        for value in (None, '', 1, 'checked-mode-root-owner-u32-v2'):
            self.fixture.manifest['native_metadata_profile'] = value
            self.fixture.save()
            with self.subTest(profile=value), self.assertRaises(ValueError):
                consumer.validate_sdk(self.sdk, 'x86_64', 'debug')
        self.fixture.manifest['native_metadata_profile'] = consumer.NATIVE_METADATA_PROFILE
        for header in consumer.NATIVE_METADATA_HEADERS:
            name = 'include/' + header
            digest = self.fixture.manifest['files'].pop(name)
            self.fixture.save()
            with self.subTest(header=header), self.assertRaises(ValueError):
                consumer.validate_sdk(self.sdk, 'x86_64', 'debug')
            self.fixture.manifest['files'][name] = digest

    def test_rehashed_profile_decoys_wrong_abi_and_versions_refused(self):
        good = self.good_profile
        for value in (good + good, '#if 0\n' + good + '#endif\n', '/*\n' + good + '*/\n',
                      'const char *decoy = R"(\n' + good + ')";\n',
                      '#define native_metadata_module_abi 75\n' + good,
                      good.replace('module_abi = 75', 'module_abi = 69'),
                      good.replace('module_abi = 75', 'module_abi = 76'),
                      good.replace('version = 1', 'version = 2'),
                      good.replace('checked-mode-root-owner-u32-v1', 'unchecked-v1'),
                      good.replace('#pragma once', '#pragma once\n#define u32 unsigned')):
            self.profile.write_text(value)
            self.rehash(self.profile)
            with self.subTest(profile=value):
                self.refused()

    def test_every_rehashed_scalar_definition_requires_one_real_unconditional_macro(self):
        for name, value in consumer.NATIVE_METADATA_DEFINES.items():
            line = '#define ' + name + ' ' + value + '\n'
            self.assertIn(line, self.good_uapi)
            for replacement in ('', '#define ' + name + ' 0\n', line + line,
                                '#define ' + name + '(value) ' + value + '\n',
                                '#if 0\n' + line + '#endif\n', '/* ' + line + ' */\n',
                                '// hidden\\\n' + line):
                self.uapi.write_text(self.good_uapi.replace(line, replacement))
                self.rehash(self.uapi)
                with self.subTest(macro=name, replacement=replacement):
                    self.refused()
        for old in (11, 12, 13, 14, 15, 17):
            self.uapi.write_text(self.good_uapi.replace('MINOR 16', f'MINOR {old}'))
            self.rehash(self.uapi)
            with self.subTest(minor=old):
                self.refused()

    def test_each_unhashed_or_absent_dependency_refused(self):
        for name in consumer.NATIVE_METADATA_HEADERS:
            path = self.sdk / 'include' / name
            data = path.read_bytes()
            path.unlink()
            with self.subTest(header=name):
                self.refused()
            path.write_bytes(data)


if __name__ == '__main__':
    unittest.main()

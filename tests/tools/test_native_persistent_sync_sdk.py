"""Independent strong-sync capability admission and rehashed deception tests."""
from pathlib import Path
import hashlib
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from kernel_sdk import validate_native_persistent_sync_profile, validate_sdk
import test_kernel_sdk as sdk_fixture
import kernel_checkout
from test_kernel_sdk import PERSISTENT_SYNC_HEADER, PERSISTENT_SYNC_DEFINITIONS, UAPI_HEADER


def producer():
    module = kernel_checkout.load_producer('storage_sdk_exporter')
    return module.validate_native_persistent_sync_profile if module else None


class PersistentSyncSdkTests(unittest.TestCase):
    def setUp(self):
        self.fixture = sdk_fixture.KernelSdkTests(methodName='test_all_ten_profile_contracts')
        self.fixture.setUp()
        self.sdk = self.fixture.sdk
        self.profile = self.sdk / 'include/ok/fs/persistent_sync_profile.hpp'
        self.uapi = self.sdk / 'include/ok/uapi/syscall.h'
        self.exporter = producer()

    def tearDown(self):
        self.fixture.tearDown()
        self.fixture.doCleanups()

    def rehash(self, path, content):
        path.write_text(content)
        self.fixture.manifest['files'][path.relative_to(self.sdk).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.fixture.save()

    def reject(self, path, content):
        self.rehash(path, content)
        for validator in (self.exporter, validate_native_persistent_sync_profile):
            with self.subTest(content=content, validator=validator.__module__), self.assertRaises(ValueError):
                validator(self.sdk / 'include')
        with self.subTest(content=content), self.assertRaises(ValueError):
            validate_sdk(self.sdk, 'x86_64', 'debug')

    @kernel_checkout.requires_checkout
    def test_canonical_producer_consumer_and_full_sdk(self):
        self.exporter(self.sdk / 'include')
        validate_native_persistent_sync_profile(self.sdk / 'include')
        manifest = validate_sdk(self.sdk, 'x86_64', 'debug')
        self.assertEqual(manifest['native_persistent_sync_profile'],
                         'retained-linked-mounted-ordered-journal-device-flush-v1')
        self.assertEqual(manifest['abi_version'], 76)

    def test_manifest_and_required_header_admission(self):
        for value in (None, '', 'ordinary-fsync-v1', 1, True):
            self.fixture.manifest['native_persistent_sync_profile'] = value
            self.fixture.save()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'persistent sync profile'):
                validate_sdk(self.sdk, 'x86_64', 'debug')
        self.fixture.manifest['native_persistent_sync_profile'] = 'retained-linked-mounted-ordered-journal-device-flush-v1'
        self.fixture.manifest['files'].pop('include/ok/fs/persistent_sync_profile.hpp')
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, 'missing artifacts'):
            validate_sdk(self.sdk, 'x86_64', 'debug')

    @kernel_checkout.requires_checkout
    def test_rehashed_profile_cannot_impersonate_persistent_contract(self):
        source = PERSISTENT_SYNC_HEADER
        attacks = [source.replace('device-flush-v1', 'ordinary-fsync-v1'),
                   source.replace('device-flush-v1', 'device-flush-v1/*changed*/'),
                   '#if 0\n' + source + '#endif\n', '/*\n' + source + '*/\n',
                   source + '#define native_persistent_sync_version 0\n',
                   source.replace('version = 1', 'version = 2'),
                   source.replace('version = 1', 'version = 0/**/1'),
                   source.replace('version = 1', 'version = \\\n1')]
        for separator in ('\u2028', '\u2029', '\x85', '\v', '\f', '\x1c'):
            attacks.append(source.replace('\n', separator))
        for line in source.splitlines(keepends=True):
            if 'constexpr' in line:
                attacks.extend((source.replace(line, ''), source.replace(line, line + line)))
        for attack in attacks:
            self.reject(self.profile, attack)

    @kernel_checkout.requires_checkout
    def test_rehashed_uapi_cannot_hide_or_redefine_persistent_operation(self):
        for name, value in PERSISTENT_SYNC_DEFINITIONS:
            line = '#define ' + name + ' ' + value + '\n'
            for content in (UAPI_HEADER.replace(line, ''),
                UAPI_HEADER.replace(line, '#if 0\n' + line + '#endif\n'),
                UAPI_HEADER.replace(line, '#define ' + name + ' 0\n'),
                UAPI_HEADER.replace('#endif', line + '#endif'),
                UAPI_HEADER.replace(line, '/*\n' + line + '*/\n'),
                UAPI_HEADER.replace(line, '#define ' + name + '(fd) ' + value + '\n')):
                self.reject(self.uapi, content)
        for content in (UAPI_HEADER.replace('1031ULL', '10/**/31ULL'),
                        UAPI_HEADER.replace('\n', '\u2028'), UAPI_HEADER.replace('\n', '\v')):
            self.reject(self.uapi, content)


if __name__ == '__main__':
    unittest.main()

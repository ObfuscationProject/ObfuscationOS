"""Independent producer and hashed consumer admission for the scalar power UAPI."""
from pathlib import Path
import hashlib
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from kernel_sdk import validate_native_power_profile, validate_sdk
import test_kernel_sdk as fixture
import kernel_checkout
from test_kernel_sdk import POWER_HEADER, POWER_DEFINITIONS, UAPI_HEADER


class NativePowerSdkTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.KernelSdkTests(methodName='test_all_ten_profile_contracts')
        self.fixture.setUp()
        self.sdk = self.fixture.sdk
        self.profile = self.sdk / 'include/ok/user/native_power_profile.hpp'
        self.uapi = self.sdk / 'include/ok/uapi/syscall.h'
        self.producer = kernel_checkout.load_producer('power_sdk_producer')

    def tearDown(self):
        self.fixture.tearDown()
        self.fixture.doCleanups()

    def rehash(self, path, content):
        path.write_text(content)
        self.fixture.manifest['files'][path.relative_to(self.sdk).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.fixture.save()

    def reject(self, path, content):
        self.rehash(path, content)
        for validator in (self.producer.validate_native_power_profile, validate_native_power_profile):
            with self.subTest(content=content, validator=validator.__module__), self.assertRaises(ValueError):
                validator(self.sdk / 'include')
        with self.assertRaises(ValueError):
            validate_sdk(self.sdk, 'x86_64', 'debug')

    @kernel_checkout.requires_checkout
    def test_canonical_contract_keeps_all_ten_architectures(self):
        self.producer.validate_native_power_profile(self.sdk / 'include')
        validate_native_power_profile(self.sdk / 'include')
        self.assertEqual(validate_sdk(self.sdk, 'x86_64', 'debug')['native_power_profile'],
                         'original-init-scalar-prepare-queued-commit-v1')
        self.fixture.test_all_ten_profile_contracts()

    def test_manifest_and_required_hashed_contract(self):
        for value in (None, '', True, 1, 'halt-supported-everywhere-v1'):
            self.fixture.manifest['native_power_profile'] = value
            self.fixture.save()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'native power profile'):
                validate_sdk(self.sdk, 'x86_64', 'debug')
        self.fixture.manifest['native_power_profile'] = 'original-init-scalar-prepare-queued-commit-v1'
        self.fixture.manifest['files'].pop('include/ok/user/native_power_profile.hpp')
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, 'missing artifacts'):
            validate_sdk(self.sdk, 'x86_64', 'debug')

    @kernel_checkout.requires_checkout
    def test_wire_definitions_cannot_be_rehashed_into_another_contract(self):
        for name, value in POWER_DEFINITIONS:
            line = '#define ' + name + ' ' + value + '\n'
            for content in (UAPI_HEADER.replace(line, ''),
                UAPI_HEADER.replace(line, '#define ' + name + ' 0\n'),
                UAPI_HEADER.replace('#endif', line + '#endif'),
                UAPI_HEADER.replace(line, '#if 0\n' + line + '#endif\n'),
                UAPI_HEADER.replace(line, '/*\n' + line + '*/\n'),
                UAPI_HEADER.replace(line, '#define ' + name + '(word) ' + value + '\n')):
                self.reject(self.uapi, content)
        for content in (UAPI_HEADER.replace('MINOR 16', 'MINOR 9'),
                        UAPI_HEADER.replace('MINOR 16', 'MINOR 17'),
                        UAPI_HEADER.replace('\n', '\u2028'),
                        UAPI_HEADER.replace('1032ULL', '10/**/32ULL')):
            self.reject(self.uapi, content)

    @kernel_checkout.requires_checkout
    def test_profile_cannot_claim_a_different_boundary(self):
        attacks = [POWER_HEADER.replace('queued-commit-v1', 'direct-power-v1'),
                   '#if 0\n' + POWER_HEADER + '#endif\n',
                   '/*\n' + POWER_HEADER + '*/\n',
                   POWER_HEADER.replace('version = 1', 'version = 2'),
                   POWER_HEADER.replace('0x3fffffff', '0x7fffffff'),
                   POWER_HEADER.replace('version = 1', 'version = 0/**/1')]
        for line in POWER_HEADER.splitlines(keepends=True):
            if 'constexpr' in line:
                attacks.extend((POWER_HEADER.replace(line, ''), POWER_HEADER.replace(line, line + line)))
        for content in attacks:
            self.reject(self.profile, content)


if __name__ == '__main__':
    unittest.main()

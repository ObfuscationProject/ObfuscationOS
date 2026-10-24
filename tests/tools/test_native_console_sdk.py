"""Independent console authority contract and fully rehashed SDK deception checks."""
from pathlib import Path
import hashlib
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from kernel_sdk import validate_native_console_input_profile, validate_sdk
import test_kernel_sdk as sdk_fixture
from test_kernel_sdk import CONSOLE_INPUT_HEADER, CONSOLE_INPUT_DEFINITIONS, UAPI_HEADER


def producer():
    spec = importlib.util.spec_from_file_location('console_sdk_exporter', ROOT.parent / 'ObfuscationKernel/tools/export_sdk.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_native_console_input_profile


def profile_attacks():
    source = CONSOLE_INPUT_HEADER
    yield source.replace('0x3fffffff', '0x3f/**/ffffff')
    yield source.replace('noecho-v1', 'noecho-v1/*changed*/')
    yield '#if 0\n' + source + '#endif\n'
    yield '/*\n' + source + '*/\n'
    yield source + '#define native_console_epoch_limit 0\n'
    for separator in ('\u2028', '\u2029', '\x85', '\v', '\f', '\x1c'):
        yield source.replace('\n', separator)
    for line in source.splitlines(keepends=True):
        if 'constexpr' in line:
            yield source.replace(line, '')
            yield source.replace(line, line + line)


def uapi_attacks():
    for name, value in CONSOLE_INPUT_DEFINITIONS:
        line = '#define ' + name + ' ' + value + '\n'
        yield UAPI_HEADER.replace(line, '')
        yield UAPI_HEADER.replace(line, '#if 0\n' + line + '#endif\n')
        yield UAPI_HEADER.replace(line, '#define ' + name + ' 0\n')
        yield UAPI_HEADER.replace('#endif', line + '#endif')
        yield UAPI_HEADER.replace(line, '/*\n' + line + '*/\n')
    yield UAPI_HEADER.replace('0x3fffffffU', '0x3f/**/ffffffU')
    yield UAPI_HEADER.replace('1028ULL', '10/**/28ULL')
    yield UAPI_HEADER.replace('\n', '\u2028')
    yield UAPI_HEADER.replace('\n', '\v')


class ConsoleSdkTests(unittest.TestCase):
    def setUp(self):
        self.fixture = sdk_fixture.KernelSdkTests(methodName='test_all_ten_profile_contracts')
        self.fixture.setUp()
        self.sdk = self.fixture.sdk
        self.profile = self.sdk / 'include/ok/sched/console_input_profile.hpp'
        self.uapi = self.sdk / 'include/ok/uapi/syscall.h'
        self.exporter = producer()

    def tearDown(self):
        self.fixture.tearDown()
        self.fixture.doCleanups()

    def write_rehashed(self, path, content):
        path.write_text(content)
        self.fixture.manifest['files'][path.relative_to(self.sdk).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.fixture.save()

    def test_independent_canonical_producer_consumer_and_full_sdk(self):
        self.exporter(self.sdk / 'include')
        validate_native_console_input_profile(self.sdk / 'include')
        self.assertEqual(validate_sdk(self.sdk, 'x86_64', 'debug')['native_console_input_profile'],
                         'pid1-issued-epoch-fork-exec-leader-revoke-noecho-v1')

    def test_missing_or_wrong_manifest_capability(self):
        for value in (None, '', 'root-readable-v1', 1):
            self.fixture.manifest['native_console_input_profile'] = value
            self.fixture.save()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'console input profile'):
                validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_rehashed_profile_cannot_impersonate_authority(self):
        for source in profile_attacks():
            self.write_rehashed(self.profile, source)
            for validate in (self.exporter, validate_native_console_input_profile):
                with self.subTest(source=source, validator=validate.__module__), self.assertRaises(ValueError):
                    validate(self.sdk / 'include')
            with self.subTest(source=source), self.assertRaises(ValueError):
                validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_rehashed_uapi_cannot_hide_or_redefine_lease_calls(self):
        for source in uapi_attacks():
            self.write_rehashed(self.uapi, source)
            for validate in (self.exporter, validate_native_console_input_profile):
                with self.subTest(source=source, validator=validate.__module__), self.assertRaises(ValueError):
                    validate(self.sdk / 'include')
            with self.subTest(source=source), self.assertRaises(ValueError):
                validate_sdk(self.sdk, 'x86_64', 'debug')


if __name__ == '__main__':
    unittest.main()

"""Terminal and job-control SDK admission (UAPI 0.17); these checks run no terminal or signal."""
from pathlib import Path
import hashlib
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import kernel_sdk as consumer
import test_kernel_sdk as fixtures
import kernel_checkout

producer = kernel_checkout.load_producer('native_tty_sdk_producer')

# (manifest key, profile constant, profile header, header list, validator, diagnostic)
CONTRACTS = (
    ('native_tty_profile', consumer.NATIVE_TTY_PROFILE, consumer.NATIVE_TTY_PROFILE_HEADER,
     consumer.NATIVE_TTY_HEADERS, 'validate_native_tty_profile', 'native TTY'),
    ('native_job_control_profile', consumer.NATIVE_JOB_CONTROL_PROFILE, consumer.NATIVE_JOB_CONTROL_PROFILE_HEADER,
     consumer.NATIVE_JOB_CONTROL_HEADERS, 'validate_native_job_control_profile', 'native job control'),
)


class NativeTtySdkTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.KernelSdkTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.sdk = self.fixture.sdk
        self.include = self.sdk / 'include'

    def rehash(self, path):
        self.fixture.manifest['files'][path.relative_to(self.sdk).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.fixture.save()

    def refused(self, validator):
        validators = [getattr(consumer, validator)]
        if producer:
            validators.append(getattr(producer, validator))
        for validate in validators:
            with self.assertRaises(ValueError):
                validate(self.include)
        with self.assertRaises(ValueError):
            consumer.validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_fixture_and_manifest_profiles_are_exact(self):
        manifest = consumer.validate_sdk(self.sdk, 'x86_64', 'debug')
        self.assertEqual(manifest['native_tty_profile'], 'bootcpu-ntty-template-console-pts8-devfs-ptmx-tty-console-v1')
        self.assertEqual(manifest['native_job_control_profile'],
                         'bootcpu-overlay-stop-cont-wuntraced-wcontinued-pgrp-wait-nocldstop-owed-kernel-v1')
        for key, profile, header, _, validator, label in CONTRACTS:
            getattr(consumer, validator)(self.include)
            for value in (None, '', False, 1, [], profile + '-smp'):
                if value is None:
                    self.fixture.manifest.pop(key)
                else:
                    self.fixture.manifest[key] = value
                self.fixture.save()
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, label + ' profile'):
                    consumer.validate_sdk(self.sdk, 'x86_64', 'debug')
            self.fixture.manifest[key] = profile
            self.fixture.save()
        consumer.validate_sdk(self.sdk, 'x86_64', 'debug')

    @kernel_checkout.requires_checkout
    def test_producer_and_checked_in_headers_agree(self):
        for name in ('NATIVE_TTY_PROFILE', 'NATIVE_TTY_HEADERS', 'NATIVE_TTY_DEFINES', 'NATIVE_TERMIOS_DEFINES',
                     'NATIVE_TERMIOS_RECORDS', 'NATIVE_JOB_CONTROL_PROFILE', 'NATIVE_JOB_CONTROL_HEADERS',
                     'NATIVE_JOB_CONTROL_DEFINES', 'NATIVE_JOB_CONTROL_RECORDS'):
            self.assertEqual(getattr(consumer, name), getattr(producer, name), name)
        for _, _, header, _, validator, _ in CONTRACTS:
            self.assertEqual((self.include / header).read_text(), (kernel_checkout.INCLUDE / header).read_text())
            getattr(consumer, validator)(kernel_checkout.INCLUDE)
            getattr(producer, validator)(self.include)

    def test_every_dependency_is_required_and_hashed(self):
        for _, _, _, headers, validator, label in CONTRACTS:
            for name in headers:
                key = 'include/' + name
                digest = self.fixture.manifest['files'].pop(key)
                self.fixture.save()
                with self.subTest(unhashed=name), self.assertRaisesRegex(ValueError, 'missing artifacts'):
                    consumer.validate_sdk(self.sdk, 'x86_64', 'debug')
                self.fixture.manifest['files'][key] = digest
                self.fixture.save()
                path = self.sdk / key
                data = path.read_bytes()
                path.unlink()
                with self.subTest(absent=name):
                    self.refused(validator)
                path.write_bytes(data)

    def test_marker_decoys_and_every_typed_field_are_refused(self):
        for _, profile, header, _, validator, _ in CONTRACTS:
            path = self.include / header
            good = path.read_text()
            attacks = [good + good, '/*\n' + good + '*/\n', '#if 0\n' + good + '#endif\n',
                       good.replace('module_abi = 81', 'module_abi = 80'),
                       good.replace('module_abi = 81', 'module_abi = 82'),
                       good.replace(profile, profile.replace('-v1', '-v2')),
                       good.replace('\n', ' '), good.replace('#pragma once', '#pragma once\\\n')]
            for name, value in re.findall(r'inline constexpr u32 (\w+) = (\d+);', good):
                attacks.append(good.replace(name + ' = ' + value + ';', name + ' = ' + str(int(value) ^ 1) + ';'))
            for line in good.splitlines(keepends=True):
                attacks.extend((good.replace(line, ''), good + line))
            for text in attacks:
                self.assertNotEqual(text, good)
                path.write_text(text)
                self.rehash(path)
                with self.subTest(header=header, text=text[-120:]):
                    self.refused(validator)
            path.write_text(good)
            self.rehash(path)
        consumer.validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_uapi_definitions_and_records_are_exact_and_unconditional(self):
        cases = (('ok/uapi/syscall.h', consumer.NATIVE_TTY_DEFINES, 'validate_native_tty_profile'),
                 ('ok/uapi/termios.h', consumer.NATIVE_TERMIOS_DEFINES, 'validate_native_tty_profile'),
                 ('ok/uapi/syscall.h', {'OK_NATIVE_JOB_CONTROL_VERSION': '1'}, 'validate_native_job_control_profile'),
                 ('ok/uapi/job_control.h', consumer.NATIVE_JOB_CONTROL_DEFINES, 'validate_native_job_control_profile'))
        for relative, defines, validator in cases:
            path = self.include / relative
            good = path.read_text()
            for name, value in defines.items():
                line = '#define ' + name + ' ' + value + '\n'
                self.assertIn(line, good)
                for replacement in ('', '#define ' + name + ' 0\n', line + line, '/* ' + line + ' */\n',
                                    '#define ' + name + '(x) ' + value + '\n', '#if 0\n' + line + '#endif\n',
                                    line + '#undef ' + name + '\n'):
                    if replacement == line:
                        continue
                    path.write_text(good.replace(line, replacement))
                    self.rehash(path)
                    with self.subTest(header=relative, name=name, replacement=replacement):
                        self.refused(validator)
            path.write_text(good)
            self.rehash(path)
        for relative, old, new, validator in (
                ('ok/uapi/termios.h', 'uint8_t c_cc[OK_NCCS];', 'uint8_t c_cc[32];', 'validate_native_tty_profile'),
                ('ok/uapi/termios.h', 'uint16_t ws_col;', 'uint32_t ws_col;', 'validate_native_tty_profile'),
                ('ok/uapi/termios.h', '#ifdef __cplusplus', '#if 1', 'validate_native_tty_profile'),
                ('ok/uapi/job_control.h', 'uint64_t mask;', 'uint32_t mask;', 'validate_native_job_control_profile'),
                ('ok/uapi/job_control.h', '#endif\n', 'struct ok_sigaction { uint64_t handler; };\n#endif\n',
                 'validate_native_job_control_profile')):
            path = self.include / relative
            good = path.read_text()
            self.assertIn(old, good)
            path.write_text(good.replace(old, new))
            self.rehash(path)
            with self.subTest(header=relative, mutation=new):
                self.refused(validator)
            path.write_text(good)
            self.rehash(path)
        consumer.validate_sdk(self.sdk, 'x86_64', 'debug')


if __name__ == '__main__':
    unittest.main()

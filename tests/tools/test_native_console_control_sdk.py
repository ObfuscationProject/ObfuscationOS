"""Bounded console-control SDK admission; no guest or hardware execution."""
from pathlib import Path
import argparse
import hashlib
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import kernel_sdk as consumer
import test_kernel_sdk as fixtures
import kernel_checkout

producer = kernel_checkout.load_producer('console_control_sdk_producer')


@kernel_checkout.requires_checkout
class NativeConsoleControlSdkTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.KernelSdkTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.sdk = self.fixture.sdk
        self.header = self.sdk / 'include' / consumer.NATIVE_CONSOLE_CONTROL_PROFILE_HEADER
        self.uapi = self.sdk / 'include/ok/uapi/syscall.h'
        self.good = self.header.read_text()
        self.good_uapi = self.uapi.read_text()

    def rehash(self, path):
        key = path.relative_to(self.sdk).as_posix()
        self.fixture.manifest['files'][key] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.fixture.save()

    def refused(self):
        for validate in (producer.validate_native_console_control_profile,
                         consumer.validate_native_console_control_profile):
            with self.assertRaises(ValueError):
                validate(self.sdk / 'include')
        with self.assertRaises(ValueError):
            consumer.validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_exact_contract_and_all_ten_architectures(self):
        self.assertEqual(consumer.NATIVE_CONSOLE_CONTROL_PROFILE,
                         'bootcpu-lease-epoch-explicit-session-foreground-eio-pid32-ioctl-v1')
        self.assertEqual(consumer.NATIVE_CONSOLE_CONTROL_PROFILE, producer.NATIVE_CONSOLE_CONTROL_PROFILE)
        self.assertEqual(consumer.NATIVE_CONSOLE_CONTROL_HEADERS, producer.NATIVE_CONSOLE_CONTROL_HEADERS)
        self.assertEqual(consumer.NATIVE_CONSOLE_CONTROL_DEFINES, producer.NATIVE_CONSOLE_CONTROL_DEFINES)
        for validate in (producer.validate_native_console_control_profile,
                         consumer.validate_native_console_control_profile):
            validate(self.sdk / 'include')
            validate(kernel_checkout.INCLUDE)
        self.assertEqual(self.good, (kernel_checkout.INCLUDE /
                                    consumer.NATIVE_CONSOLE_CONTROL_PROFILE_HEADER).read_text())
        self.assertEqual(consumer.validate_sdk(self.sdk, 'x86_64', 'debug')['abi_version'], 74)
        self.fixture.test_all_ten_profile_contracts()

    def test_manifest_requires_explicit_console_capability(self):
        for value in (None, '', False, 1, [], 'full-posix-terminal-v1'):
            self.fixture.manifest['native_console_control_profile'] = value
            self.fixture.save()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'native console control profile'):
                consumer.validate_sdk(self.sdk, 'x86_64', 'debug')
        self.fixture.manifest.pop('native_console_control_profile')
        self.fixture.save()
        with self.assertRaisesRegex(ValueError, 'native console control profile'):
            consumer.validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_every_dependency_is_required_and_hashed(self):
        for name in consumer.NATIVE_CONSOLE_CONTROL_HEADERS:
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
                self.refused()
            path.write_bytes(data)

    def test_profile_decoys_and_every_typed_field_are_refused(self):
        attacks = [self.good + self.good, '/*\n' + self.good + '*/\n',
                   '#if 0\n' + self.good + '#endif\n',
                   'const char *example = R"(\n' + self.good + ')";\n',
                   '#define native_console_control_module_abi 74\n' + self.good,
                   self.good.replace('module_abi = 74', 'module_abi = 72'),
                   self.good.replace('module_abi = 74', 'module_abi = 75'),
                   self.good.replace('ioctl-v1', 'ioctl-v2'),
                   self.good.replace('\n', '\u2028'),
                   self.good.replace('#pragma once', '#pragma once\\\n')]
        for name, value in re.findall(r'inline constexpr u32 (\w+) = (\d+);', self.good):
            attacks.append(self.good.replace(name + ' = ' + value, name + ' = ' + str(int(value) + 1)))
        for line in self.good.splitlines(keepends=True):
            attacks.extend((self.good.replace(line, ''), self.good + line))
        for text in attacks:
            self.assertNotEqual(text, self.good)
            self.header.write_text(text)
            self.rehash(self.header)
            with self.subTest(text=text):
                self.refused()

    def test_console_constants_require_one_unconditional_literal(self):
        for name, value in consumer.NATIVE_CONSOLE_CONTROL_DEFINES.items():
            line = '#define ' + name + ' ' + value + '\n'
            self.assertIn(line, self.good_uapi)
            for replacement in ('', '#define ' + name + ' 0\n', line + line,
                                '#define ' + name + '(arg) ' + value + '\n',
                                '#if 0\n' + line + '#endif\n', '/* ' + line + ' */\n',
                                '// hidden\\\n' + line):
                self.uapi.write_text(self.good_uapi.replace(line, replacement))
                self.rehash(self.uapi)
                with self.subTest(name=name, replacement=replacement):
                    self.refused()

    def test_old_future_and_mixed_cohorts_are_refused(self):
        module = self.sdk / 'include/ok/core/module.hpp'
        good_module = module.read_text()
        for abi in (72, 73, 75):
            module.write_text(good_module.replace('= 74;', '= ' + str(abi) + ';'))
            self.rehash(module)
            with self.subTest(abi=abi):
                self.refused()
        module.write_text(good_module)
        self.rehash(module)
        for minor in (14, 15, 17):
            self.uapi.write_text(self.good_uapi.replace('MINOR 16', 'MINOR ' + str(minor)))
            self.rehash(self.uapi)
            with self.subTest(minor=minor):
                self.refused()
        self.uapi.write_text(self.good_uapi)
        self.rehash(self.uapi)
        for path, old, new in ((self.sdk / 'include/ok/user/native_sessions_profile.hpp',
                               'native_sessions_controlling_tty = 1', 'native_sessions_controlling_tty = 0'),
                              (self.sdk / 'include/ok/user/native_group_signal_profile.hpp',
                               'native_group_signal_controlling_tty = 1', 'native_group_signal_controlling_tty = 0')):
            good = path.read_text()
            path.write_text(good.replace(old, new))
            self.rehash(path)
            with self.subTest(mixed=str(path)):
                self.refused()
            path.write_text(good)
            self.rehash(path)

    def test_refusal_cannot_replace_existing_export(self):
        scheduler = self.sdk / 'include/ok/sched/scheduler.hpp'
        scheduler.write_text('user_init_pid = 1; create_init_process(); user_adoption_target();')
        output = self.fixture.root / 'prior-export'
        output.mkdir()
        marker = output / 'retained'
        marker.write_bytes(b'prior SDK')
        args = argparse.Namespace(headers=self.sdk / 'include', output=output, mode='debug',
                                  arch='x86_64', define=['OK_NATIVE_SIGNAL_RUNTIME'], asflag=[], cxxflag=[])
        for attack in (self.good.replace('module_abi = 74', 'module_abi = 72'),
                       self.good.replace('pty = 0', 'pty = 1')):
            self.header.write_text(attack)
            with self.subTest(attack=attack), self.assertRaisesRegex(ValueError, 'native console control profile'):
                producer.export(args)
            self.assertEqual(list(output.iterdir()), [marker])
            self.assertEqual(marker.read_bytes(), b'prior SDK')
            self.assertFalse(any(path.name.startswith('.kernel-sdk-') for path in self.fixture.root.iterdir()))


if __name__ == '__main__':
    unittest.main()

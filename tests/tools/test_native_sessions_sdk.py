"""Session capability admission controls; no process or terminal execution."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import kernel_sdk as consumer
import test_kernel_sdk as fixtures

spec = importlib.util.spec_from_file_location('native_sessions_sdk_producer',
                                             ROOT.parent / 'ObfuscationKernel/tools/export_sdk.py')
producer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(producer)


class NativeSessionsSdkTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.KernelSdkTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.sdk = self.fixture.sdk
        self.profile = self.sdk / 'include' / consumer.NATIVE_SESSIONS_PROFILE_HEADER
        self.uapi = self.sdk / 'include/ok/uapi/syscall.h'
        self.good_profile = self.profile.read_text()
        self.good_uapi = self.uapi.read_text()

    def rehash(self, path):
        name = path.relative_to(self.sdk).as_posix()
        self.fixture.manifest['files'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.fixture.save()

    def refused(self):
        for validate in (producer.validate_native_sessions_profile, consumer.validate_native_sessions_profile):
            with self.assertRaises(ValueError):
                validate(self.sdk / 'include')
        with self.assertRaises(ValueError):
            consumer.validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_exact_contract_and_all_ten_architectures(self):
        for validate in (producer.validate_native_sessions_profile, consumer.validate_native_sessions_profile):
            validate(self.sdk / 'include')
        self.assertEqual(consumer.NATIVE_SESSIONS_DEFINES, producer.NATIVE_SESSIONS_DEFINES)
        self.assertEqual(consumer.NATIVE_SESSIONS_HEADERS, producer.NATIVE_SESSIONS_HEADERS)
        self.assertEqual(consumer.NATIVE_SESSIONS_PROFILE, 'bootcpu-serialized-process-group-session-console-lifecycle-v3')
        self.assertEqual(consumer.validate_sdk(self.sdk, 'x86_64', 'debug')['abi_version'], 74)
        self.fixture.test_all_ten_profile_contracts()

    def test_manifest_capability_is_required(self):
        for value in (None, '', True, 1, 'full-posix-session-v1'):
            self.fixture.manifest['native_sessions_profile'] = value
            self.fixture.save()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'native sessions profile'):
                consumer.validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_every_dependency_must_be_hashed_and_present(self):
        for header in consumer.NATIVE_SESSIONS_HEADERS:
            name = 'include/' + header
            digest = self.fixture.manifest['files'].pop(name)
            self.fixture.save()
            with self.subTest(unhashed=header), self.assertRaisesRegex(ValueError, 'missing artifacts'):
                consumer.validate_sdk(self.sdk, 'x86_64', 'debug')
            self.fixture.manifest['files'][name] = digest
            self.fixture.save()
            path = self.sdk / name
            data = path.read_bytes()
            path.unlink()
            with self.subTest(absent=header):
                self.refused()
            path.write_bytes(data)

    def test_marker_decoys_old_future_and_expanded_scope_are_refused(self):
        good = self.good_profile
        attacks = [good + good, '#if 0\n' + good + '#endif\n', '/*\n' + good + '*/\n',
                   'const char *decoy = R"(\n' + good + ')";\n',
                   '#define native_sessions_module_abi 74\n' + good,
                   good.replace('module_abi = 74', 'module_abi = 72'),
                   good.replace('module_abi = 74', 'module_abi = 75'),
                   good.replace('pid_bits = 32', 'pid_bits = 64'),
                   good.replace('process_capacity = 64', 'process_capacity = 128'),
                   good.replace('lifecycle-v3', 'lifecycle-v4'),
                   good + 'inline constexpr u32 native_sessions_group_signals = 0;\n',
                   good.replace('native_sessions_version = 3', 'native_sessions_version = 2'),
                   good.replace('native_sessions_version = 3', 'native_sessions_version = 4'),
                   good.replace('\n', '\u2028')]
        for name in ('fork_inherits', 'exec_preserves', 'reparent_preserves', 'controlling_tty'):
            attacks.append(good.replace(name + ' = 1', name + ' = 0'))
        for name in ('pty', 'job_control'):
            attacks.append(good.replace('native_sessions_' + name + ' = 0',
                                        'native_sessions_' + name + ' = 1'))
        for line in good.splitlines(keepends=True):
            attacks.extend((good.replace(line, ''), good + line))
        for value in attacks:
            self.profile.write_text(value)
            self.rehash(self.profile)
            with self.subTest(marker=value):
                self.refused()

    def test_scalar_definitions_require_one_unconditional_macro(self):
        for name, value in consumer.NATIVE_SESSIONS_DEFINES.items():
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
        for minor in (12, 13, 14, 15, 17):
            self.uapi.write_text(self.good_uapi.replace('MINOR 16', f'MINOR {minor}'))
            self.rehash(self.uapi)
            with self.subTest(minor=minor):
                self.refused()

    def test_wrong_session_contract_cannot_replace_existing_export(self):
        scheduler = self.sdk / 'include/ok/sched/scheduler.hpp'
        scheduler.write_text('user_init_pid = 1; create_init_process(); user_adoption_target();')
        output = self.fixture.root / 'published'
        output.mkdir()
        retained = output / 'prior-sdk'
        retained.write_bytes(b'preserved SDK')
        args = argparse.Namespace(headers=self.sdk / 'include', output=output, mode='debug',
                                  arch='x86_64', define=['OK_NATIVE_SIGNAL_RUNTIME'], asflag=[], cxxflag=[])
        for value in (self.good_profile.replace('module_abi = 74', 'module_abi = 70'),
                      self.good_profile.replace('pty = 0', 'pty = 1')):
            self.profile.write_text(value)
            with self.subTest(profile=value), self.assertRaisesRegex(ValueError, 'native sessions profile'):
                producer.export(args)
            self.assertEqual(list(output.iterdir()), [retained])
            self.assertEqual(retained.read_bytes(), b'preserved SDK')
            self.assertFalse(any(path.name.startswith('.kernel-sdk-') for path in self.fixture.root.iterdir()))


if __name__ == '__main__':
    unittest.main()

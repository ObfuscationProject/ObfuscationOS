"""Bounded group-signal SDK admission; these checks do not execute signals."""
from pathlib import Path
import argparse
import hashlib
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import kernel_sdk as consumer
import test_kernel_sdk as fixtures
import kernel_checkout

producer = kernel_checkout.load_producer('group_signal_sdk_producer')


@kernel_checkout.requires_checkout
class NativeGroupSignalSdkTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.KernelSdkTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.sdk = self.fixture.sdk
        self.header = self.sdk / 'include' / consumer.NATIVE_GROUP_SIGNAL_PROFILE_HEADER
        self.good = self.header.read_text()

    def rehash(self, path):
        self.fixture.manifest['files'][path.relative_to(self.sdk).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.fixture.save()

    def refused(self):
        for validate in (producer.validate_native_group_signal_profile, consumer.validate_native_group_signal_profile):
            with self.assertRaises(ValueError):
                validate(self.sdk / 'include')
        with self.assertRaises(ValueError):
            consumer.validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_exact_bounded_contract_and_ten_architectures(self):
        expected = 'bootcpu-signed32-current-negative-pgid-probe-term-kill-deferred-partial-v2'
        self.assertEqual(consumer.NATIVE_GROUP_SIGNAL_PROFILE, expected)
        self.assertEqual(producer.NATIVE_GROUP_SIGNAL_PROFILE, expected)
        self.assertEqual(consumer.NATIVE_GROUP_SIGNAL_HEADERS, producer.NATIVE_GROUP_SIGNAL_HEADERS)
        for validate in (producer.validate_native_group_signal_profile, consumer.validate_native_group_signal_profile):
            validate(self.sdk / 'include')
        self.assertEqual(consumer.validate_sdk(self.sdk, 'x86_64', 'debug')['abi_version'], 75)
        self.fixture.test_all_ten_profile_contracts()

    def test_manifest_requires_explicit_bounded_profile(self):
        for value in (None, '', False, 1, [], 'full-job-control-v1'):
            self.fixture.manifest['native_group_signal_profile'] = value
            self.fixture.save()
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'native group signal profile'):
                consumer.validate_sdk(self.sdk, 'x86_64', 'debug')

    def test_dependencies_are_required_and_hashed(self):
        for name in consumer.NATIVE_GROUP_SIGNAL_HEADERS:
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

    def test_marker_decoys_and_expanded_scope_are_refused(self):
        attacks = [self.good + self.good, '/*\n' + self.good + '*/\n',
                   '#if 0\n' + self.good + '#endif\n',
                   'const char *example = R"(\n' + self.good + ')";\n',
                   '#define native_group_signal_module_abi 75\n' + self.good,
                   self.good.replace('module_abi = 75', 'module_abi = 72'),
                   self.good.replace('module_abi = 75', 'module_abi = 76'),
                   self.good.replace('native_group_signal_version = 2', 'native_group_signal_version = 1'),
                   self.good.replace('native_group_signal_version = 2', 'native_group_signal_version = 3'),
                   self.good.replace('pid_bits = 32', 'pid_bits = 64'),
                   self.good.replace('process_capacity = 64', 'process_capacity = 128'),
                   self.good.replace('term = 15', 'term = 1'),
                   self.good.replace('kill = 9', 'kill = 19'),
                   self.good.replace('\n', '\u2028')]
        for name in ('current_group', 'negative_group', 'probe', 'deferred_fatal', 'partial_success', 'controlling_tty'):
            attacks.append(self.good.replace('native_group_signal_' + name + ' = 1',
                                              'native_group_signal_' + name + ' = 0'))
        for name in ('broadcast', 'stop_continue', 'job_control', 'smp'):
            attacks.append(self.good.replace('native_group_signal_' + name + ' = 0',
                                              'native_group_signal_' + name + ' = 1'))
        for line in self.good.splitlines(keepends=True):
            attacks.extend((self.good.replace(line, ''), self.good + line))
        for text in attacks:
            self.header.write_text(text)
            self.rehash(self.header)
            with self.subTest(text=text):
                self.refused()

    def test_refusal_preserves_existing_sdk(self):
        scheduler = self.sdk / 'include/ok/sched/scheduler.hpp'
        scheduler.write_text('user_init_pid = 1; create_init_process(); user_adoption_target();')
        output = self.fixture.root / 'prior-export'
        output.mkdir()
        marker = output / 'retained'
        marker.write_bytes(b'prior SDK')
        self.header.write_text(self.good.replace('broadcast = 0', 'broadcast = 1'))
        args = argparse.Namespace(headers=self.sdk / 'include', output=output, mode='debug',
                                  arch='x86_64', define=['OK_NATIVE_SIGNAL_RUNTIME'], asflag=[], cxxflag=[])
        with self.assertRaisesRegex(ValueError, 'native group signal profile'):
            producer.export(args)
        self.assertEqual(list(output.iterdir()), [marker])
        self.assertEqual(marker.read_bytes(), b'prior SDK')
        self.assertFalse(any(path.name.startswith('.kernel-sdk-') for path in self.fixture.root.iterdir()))


if __name__ == '__main__':
    unittest.main()

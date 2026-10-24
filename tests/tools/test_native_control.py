"""Hosted native control policy and transport controls; no guest execution."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NativeControlTests(unittest.TestCase):
    def test_control_enabled_supervisor_ordering_and_failure_containment(self):
        with tempfile.TemporaryDirectory(prefix='native-control-actor-') as temporary:
            binary = Path(temporary) / 'actor'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=undefined', '-fno-omit-frame-pointer',
                            str(ROOT / 'tests/native_control_supervisor_tests.c'), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, timeout=8, check=True)
            self.assertIn(b'failure containment controls passed', result.stdout)

    def test_actual_server_and_client_with_syscall_faults(self):
        sdk = Path(os.environ.get('OK_TEST_KERNEL_SDK',
                   ROOT.parent / 'ObfuscationKernel/build/sdk/x86_64/debug'))
        self.assertTrue((sdk / 'include/ok/uapi/syscall.h').is_file(),
                        'Set OK_TEST_KERNEL_SDK to an explicit exported SDK')
        with tempfile.TemporaryDirectory(prefix='native-control-hosted-') as temporary:
            binary = Path(temporary) / 'control'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=undefined', '-fno-omit-frame-pointer',
                            '-I', str(ROOT / 'lib/okcrt/include'), '-I', str(sdk / 'include'),
                            '-idirafter', str(ROOT / 'sdk/include'),
                            str(ROOT / 'tests/native_control_tests.c'), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, timeout=8, check=True)
            self.assertIn(b'controls passed', result.stdout)


if __name__ == '__main__':
    unittest.main()

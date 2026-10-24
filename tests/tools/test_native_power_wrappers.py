"""Hosted actual okcrt marshalling, admitted by an explicit exported SDK."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from kernel_sdk import validate_sdk


class NativePowerWrapperTests(unittest.TestCase):
    def test_actual_syscall6_marshalling_and_errno_with_explicit_sdk(self):
        self.assertIn('OK_TEST_KERNEL_SDK', os.environ, 'Set OK_TEST_KERNEL_SDK to the explicit exported SDK')
        sdk = Path(os.environ['OK_TEST_KERNEL_SDK']).resolve()
        manifest = validate_sdk(sdk, 'x86_64', 'debug')
        self.assertEqual(manifest['native_power_profile'], 'original-init-scalar-prepare-queued-commit-v1')
        with tempfile.TemporaryDirectory(prefix='native-power-wrapper-') as directory:
            binary = Path(directory) / 'wrapper'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=undefined', '-fno-sanitize-recover=all',
                '-I', str(ROOT / 'sdk/include'), '-I', str(ROOT / 'lib/okcrt/include'),
                '-I', str(sdk / 'include'), str(ROOT / 'lib/okcrt/src/power.c'),
                str(ROOT / 'lib/okcrt/src/errno.c'), str(ROOT / 'tests/native_power_wrapper_tests.c'),
                '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=8)


if __name__ == '__main__':
    unittest.main()

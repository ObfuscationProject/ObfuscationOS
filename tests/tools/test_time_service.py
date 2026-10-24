"""Hosted actual-code time service checks; never native execution evidence."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class TimeServiceImplementationTests(unittest.TestCase):
    def test_actual_code_with_syscall_faults(self):
        sdk = Path(os.environ['OK_TEST_KERNEL_SDK']).resolve()
        self.assertTrue((sdk / 'manifest.json').is_file())
        with tempfile.TemporaryDirectory(prefix='ok-time-code-') as temporary:
            binary = Path(temporary) / 'time-service'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                            '-fno-pie', '-no-pie', '-I', str(ROOT / 'lib/okcrt/include'),
                            '-I', str(sdk / 'include'), '-idirafter', str(ROOT / 'sdk/include'),
                            str(ROOT / 'tests/time_service_tests.c'), '-o', str(binary)], check=True)
            # LeakSanitizer cannot operate under this host's ptrace execution.
            # Every seam fixture checks its complete descriptor ledger instead.
            environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=0')
            result = subprocess.run([str(binary)], capture_output=True,
                                    env=environment, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(b'actual-code fault controls passed', result.stdout)


if __name__ == '__main__':
    unittest.main()

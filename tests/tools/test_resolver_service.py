"""Hosted actual-source resolver controls, distinct from native execution."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ResolverServiceImplementationTests(unittest.TestCase):
    def test_actual_code_with_syscall_faults(self):
        sdk = Path(os.environ['OK_TEST_KERNEL_SDK']).resolve()
        self.assertTrue((sdk / 'manifest.json').is_file())
        with tempfile.TemporaryDirectory(prefix='ok-resolver-code-') as temporary:
            binary = Path(temporary) / 'resolver-service'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                            '-fno-pie', '-no-pie', '-I', str(ROOT / 'lib/okcrt/include'),
                            '-I', str(sdk / 'include'), '-idirafter', str(ROOT / 'sdk/include'),
                            str(ROOT / 'tests/resolver_service_tests.c'), '-o', str(binary)], check=True)
            # LeakSanitizer cannot operate under this host's ptrace execution;
            # every syscall-seam fixture checks its full descriptor ledger.
            result = subprocess.run([str(binary)], capture_output=True,
                                    env=dict(os.environ, ASAN_OPTIONS='detect_leaks=0'), timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(b'actual-code fault controls passed (10 groups)', result.stdout)


if __name__ == '__main__':
    unittest.main()

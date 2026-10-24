"""Hosted native halt/reboot protocol and actor controls; no target execution."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NativeHaltTests(unittest.TestCase):
    def compile_and_run(self, source, marker, socket_headers=False):
        flags = ['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                 '-fsanitize=undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
        if socket_headers:
            sdk = Path(os.environ.get('OK_TEST_KERNEL_SDK',
                       ROOT.parent / 'ObfuscationKernel/build/sdk/x86_64/debug'))
            self.assertTrue((sdk / 'include/ok/uapi/syscall.h').is_file(),
                            'Set OK_TEST_KERNEL_SDK to an explicit exported SDK')
            flags += ['-I', str(ROOT / 'lib/okcrt/include'), '-I', str(sdk / 'include'),
                      '-idirafter', str(ROOT / 'sdk/include')]
        with tempfile.TemporaryDirectory(prefix='native-halt-hosted-') as temporary:
            binary = Path(temporary) / 'controls'
            subprocess.run([*flags, str(ROOT / 'tests' / source), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, timeout=8, check=True)
            self.assertIn(marker, result.stdout)

    def test_actual_control_prepare_refusal_and_exact_token(self):
        self.compile_and_run('native_halt_control_tests.c', b'exact token and CLI controls passed', True)

    def test_pid1_shutdown_ordering_and_terminal_failure(self):
        self.compile_and_run('native_halt_supervisor_tests.c', b'terminal hold controls passed')


if __name__ == '__main__':
    unittest.main()

"""Hosted quiescence policy and syscall-fault controls, without target execution."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NativeQuiesceTests(unittest.TestCase):
    def compile_and_run(self, unit, marker, socket_headers=False):
        flags = ['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                 '-fsanitize=undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']
        if socket_headers:
            sdk = Path(os.environ.get('OK_TEST_KERNEL_SDK',
                       ROOT.parent / 'ObfuscationKernel/build/sdk/x86_64/debug'))
            self.assertTrue((sdk / 'include/ok/uapi/syscall.h').is_file(),
                            'Set OK_TEST_KERNEL_SDK to an explicit exported SDK')
            flags += ['-I', str(ROOT / 'lib/okcrt/include'), '-I', str(sdk / 'include'),
                      '-idirafter', str(ROOT / 'sdk/include')]
        with tempfile.TemporaryDirectory(prefix='native-quiesce-hosted-') as temporary:
            binary = Path(temporary) / 'control'
            subprocess.run([*flags, str(ROOT / 'tests' / unit), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, timeout=8, check=True)
            self.assertIn(marker, result.stdout)

    def test_actual_server_client_cli_policy_and_framing(self):
        self.compile_and_run('native_quiesce_control_tests.c',
                             b'framing, transport and CLI controls passed', socket_headers=True)

    def test_pid1_dependency_drain_and_fresh_echild(self):
        self.compile_and_run('native_quiesce_supervisor_tests.c',
                             b'deadline and endpoint controls passed')


if __name__ == '__main__':
    unittest.main()

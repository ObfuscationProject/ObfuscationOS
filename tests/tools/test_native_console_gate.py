"""Hosted PID1 console handshake ordering and failure ownership."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ConsoleGateTests(unittest.TestCase):
    def test_claim_before_child_release_and_fail_closed_errors(self):
        with tempfile.TemporaryDirectory(prefix='console-gate-hosted-') as directory:
            binary = Path(directory) / 'gate'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=undefined', '-fno-sanitize-recover=all',
                '-idirafter', str(ROOT / 'sdk/include'),
                str(ROOT / 'tests/native_console_gate_tests.c'), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, check=True, timeout=8)
            self.assertIn(b'ownership and failure controls passed', result.stdout)

    def test_native_console_wrapper_word_and_errno_boundaries(self):
        sdk = Path(os.environ.get('OK_TEST_KERNEL_SDK',
                   ROOT.parent / 'ObfuscationKernel/build/sdk/x86_64/debug'))
        manifest = json.loads((sdk / 'manifest.json').read_text())
        if manifest.get('native_console_input_profile') != 'pid1-issued-epoch-fork-exec-leader-revoke-noecho-v1':
            self.skipTest('Set OK_TEST_KERNEL_SDK to an explicit console-input-capable exported SDK')
        with tempfile.TemporaryDirectory(prefix='console-wrappers-hosted-') as directory:
            binary = Path(directory) / 'wrapper'
            # The wrapper boundary does not establish native guest isolation.
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=undefined', '-fno-sanitize-recover=all',
                '-I', str(ROOT / 'sdk/include'), '-I', str(ROOT / 'lib/okcrt/include'),
                '-I', str(sdk / 'include'),
                str(ROOT / 'lib/okcrt/src/console.c'),
                str(ROOT / 'tests/native_console_wrapper_tests.c'), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=8)


if __name__ == '__main__':
    unittest.main()

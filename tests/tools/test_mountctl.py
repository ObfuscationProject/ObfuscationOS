"""Hosted actual CLI controls; requires an explicit exported inventory SDK."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from kernel_sdk import validate_sdk


class MountctlImplementationTests(unittest.TestCase):
    def test_actual_cli_with_inventory_and_output_faults(self):
        sdk = Path(os.environ['OK_TEST_KERNEL_SDK']).resolve()
        manifest = json.loads((sdk / 'manifest.json').read_text())
        validate_sdk(sdk, manifest['arch'], manifest['mode'])
        self.assertEqual(manifest['native_mount_info_profile'],
                         'global-nine-slot-read-only-derived-generation-v1')
        with tempfile.TemporaryDirectory(prefix='ok-mountctl-code-') as temporary:
            binary = Path(temporary) / 'mountctl'
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie',
                '-I', str(sdk / 'include'), '-idirafter', str(ROOT / 'sdk/include'),
                str(ROOT / 'tests/mountctl_tests.c'), '-o', str(binary)], check=True)
            environment = dict(os.environ, ASAN_OPTIONS='detect_leaks=0:halt_on_error=1',
                               UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            result = subprocess.run([str(binary)], capture_output=True, env=environment, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(b'mountctl actual-code controls passed', result.stdout)


if __name__ == '__main__':
    unittest.main()

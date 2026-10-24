"""Hosted native libc marshalling/error boundary, separate from guest execution."""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class CredentialWrappers(unittest.TestCase):
    def test_high_unsigned_ids_and_fallible_transition_results(self):
        sdk = Path(os.environ.get('OK_TEST_KERNEL_SDK',
                   ROOT.parent / 'ObfuscationKernel/build/sdk/x86_64/debug'))
        with tempfile.TemporaryDirectory(prefix='native-credential-wrappers-') as temporary:
            binary = Path(temporary) / 'wrapper'
            # Rename SDK definitions so sanitizer/libc never resolve to the mocks.
            names = re.findall(r'^(?:static\s+)?\w+[ \t*]+(\w+)\([^;\n]*\)\n\{',
                               (ROOT / 'lib/okcrt/src/syscalls.c').read_text(), re.MULTILINE)
            rename = ['-D' + name + '=ok_test_' + name for name in names]
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                *rename, '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
                '-fsanitize=undefined', '-fno-omit-frame-pointer',
                '-I', str(ROOT / 'sdk/include'), '-I', str(ROOT / 'lib/okcrt/include'),
                '-I', str(sdk / 'include'), str(ROOT / 'lib/okcrt/src/syscalls.c'),
                str(ROOT / 'tests/native_credential_wrapper_tests.c'), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=8)


if __name__ == '__main__':
    unittest.main()

"""Hosted native terminal wrappers against an explicit exported Kernel SDK.

Syscall mocks verify argument/result boundaries; guest execution is separate.
"""
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class TerminalWrappers(unittest.TestCase):
    def test_typed_requests_pointer_arguments_scalar_arguments_and_errno(self):
        sdk = Path(os.environ.get('OK_TEST_KERNEL_SDK',
                   ROOT.parent / 'ObfuscationKernel/build/sdk/x86_64/debug'))
        self.assertTrue((sdk / 'include/ok/uapi/syscall.h').is_file(),
                        'terminal wrapper test requires an explicit exported Kernel SDK')
        with tempfile.TemporaryDirectory(prefix='native-terminal-wrappers-') as temporary:
            binary = Path(temporary) / 'wrapper'
            names = re.findall(r'^(?:static\s+)?\w+[ \t*]+(\w+)\([^;\n]*\)\n\{',
                               (ROOT / 'lib/okcrt/src/syscalls.c').read_text(), re.MULTILINE)
            rename = ['-D' + name + '=ok_test_' + name for name in names]
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                *rename, '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
                '-fsanitize=undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                '-I', str(ROOT / 'sdk/include'), '-I', str(ROOT / 'lib/okcrt/include'),
                '-I', str(sdk / 'include'), str(ROOT / 'lib/okcrt/src/syscalls.c'),
                str(ROOT / 'tests/native_terminal_wrapper_tests.c'), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=8)


if __name__ == '__main__':
    unittest.main()

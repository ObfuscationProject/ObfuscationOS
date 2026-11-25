"""Hosted native terminal wrappers against an explicit exported Kernel SDK.

Syscall mocks verify argument/result boundaries; guest execution is separate.
The wrappers run once as an LP64 host model (64-bit profiles) and once as an
ILP32 host model (32-bit profiles), since the argument word is a C long.
"""
from functools import lru_cache
from pathlib import Path
import os
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (ROOT / 'lib/okcrt/src/syscalls.c', ROOT / 'lib/okcrt/src/termios.c')
TEST = ROOT / 'tests/native_terminal_wrapper_tests.c'
SANITIZE = ['-fsanitize=undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer']


def sdk_path():
    return Path(os.environ.get('OK_TEST_KERNEL_SDK',
                ROOT.parent / 'ObfuscationKernel/build/sdk/x86_64/debug'))


@lru_cache(maxsize=None)
def host_builds_ilp32():
    """Whether the host compiler links and runs a sanitized -m32 program."""
    with tempfile.TemporaryDirectory(prefix='native-terminal-probe-') as temporary:
        source = Path(temporary) / 'probe.c'
        binary = Path(temporary) / 'probe'
        source.write_text('int main(void) { return sizeof(long) == 4 ? 0 : 1; }\n')
        try:
            subprocess.run(['cc', '-m32', *SANITIZE, str(source), '-o', str(binary)],
                           check=True, capture_output=True, timeout=60)
            return subprocess.run([str(binary)], timeout=8).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False


class TerminalWrappers(unittest.TestCase):
    def run_wrappers(self, width, flags=()):
        sdk = sdk_path()
        self.assertTrue((sdk / 'include/ok/uapi/syscall.h').is_file(),
                        'terminal wrapper test requires an explicit exported Kernel SDK')
        with tempfile.TemporaryDirectory(prefix='native-terminal-wrappers-') as temporary:
            binary = Path(temporary) / 'wrapper'
            # Rename the okcrt definitions so libc and the sanitizer runtime
            # never resolve to them.
            names = [name for source in SOURCES for name in
                     re.findall(r'^(?:static\s+)?\w+[ \t*]+(\w+)\([^;\n]*\)\n\{',
                                source.read_text(), re.MULTILINE)]
            rename = ['-D' + name + '=ok_test_' + name for name in names]
            subprocess.run(['cc', *flags, '-std=c11', '-Wall', '-Wextra', '-Werror',
                *rename, '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections', *SANITIZE,
                '-I', str(ROOT / 'sdk/include'), '-I', str(ROOT / 'lib/okcrt/include'),
                '-I', str(sdk / 'include'), *map(str, SOURCES), str(TEST), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=8)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, '')
        self.assertRegex(result.stdout, r'\ANATIVE_TERMINAL_WRAPPER_PASS long_bits=%d cases=[1-9][0-9]* '
                                        r'host_mock_only=1\n\Z' % width)

    def test_typed_requests_pointer_arguments_scalar_arguments_and_errno_lp64(self):
        self.run_wrappers(64)

    @unittest.skipUnless(host_builds_ilp32(), 'host compiler cannot build an ILP32 sanitized program (gcc-multilib)')
    def test_typed_requests_pointer_arguments_scalar_arguments_and_errno_ilp32(self):
        self.run_wrappers(32, ['-m32'])


if __name__ == '__main__':
    unittest.main()

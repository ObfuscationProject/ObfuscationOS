"""Hosted raw PTY syscall wrapper with an explicit validated exported SDK.

The actual okcrt implementation calls mocks; no guest or hardware is exercised.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from kernel_sdk import validate_sdk


class NativePtyWrapperTests(unittest.TestCase):
    def test_pair_arguments_reserved_words_and_errno(self):
        self.assertIn('OK_TEST_KERNEL_SDK', os.environ, 'Set the explicit exported Kernel SDK path')
        sdk = Path(os.environ['OK_TEST_KERNEL_SDK']).resolve(strict=True)
        mode = os.environ.get('OK_TEST_KERNEL_MODE', 'debug')
        self.assertIn(mode, ('debug', 'release'))
        manifest = validate_sdk(sdk, 'x86_64', mode)
        self.assertEqual(manifest['native_pty_profile'], 'bootcpu-native-raw-pair-ofd-waits-drain-eof-eio-v1')
        with tempfile.TemporaryDirectory(prefix='native-pty-wrappers-') as directory:
            project = Path(directory)
            # Keep hosted libc/sanitizer headers while compiling the actual
            # public PTY header and syscall declarations without substitutes.
            include = project / 'include/ok'
            include.mkdir(parents=True)
            for source in (ROOT / 'sdk/include/ok/pty.h', ROOT / 'lib/okcrt/include/ok/syscall.h'):
                shutil.copy2(source, include / source.name)
                self.assertEqual(source.read_bytes(), (include / source.name).read_bytes())
            quoted = lambda value: json.dumps(str(value))
            lines = [
                'set_project("native_pty_wrappers_hosted")', 'set_languages("c11")',
                'target("wrapper")', 'set_kind("binary")', 'set_targetdir("products")',
                'add_includedirs(' + ','.join(quoted(p) for p in (project / 'include', sdk / 'include')) + ')',
                'add_cflags("-Wall","-Wextra","-Werror","-fsanitize=undefined",'
                '"-fno-sanitize-recover=all",{force=true})',
                'add_ldflags("-fsanitize=undefined",{force=true})',
                'add_files(' + ','.join(quoted(p) for p in
                    (ROOT / 'lib/okcrt/src/pty.c', ROOT / 'tests/native_pty_wrapper_tests.c')) + ')',
                'target_end()',
            ]
            (project / 'xmake.lua').write_text('\n'.join(lines) + '\n')
            env = dict(os.environ, XMAKE_ROOT='y', XMAKE_GLOBALDIR=str(project / 'global'),
                       XMAKE_TMPDIR=str(project / 'tmp'))
            for name in ('CPATH', 'CPLUS_INCLUDE_PATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH',
                         'GCC_EXEC_PREFIX', 'COMPILER_PATH'):
                env.pop(name, None)
            for command in (
                ['xmake', 'f', '-P', str(project), '-c', '-y', '-m', 'release', '--ccache=n'],
                ['xmake', 'build', '-P', str(project), '-y', '-j2'],
                [str(project / 'products/wrapper')],
            ):
                subprocess.run(command, cwd=project, env=env, check=True, timeout=90)


if __name__ == '__main__':
    unittest.main()

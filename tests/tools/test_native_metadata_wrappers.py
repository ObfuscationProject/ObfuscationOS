"""Hosted actual okcrt metadata marshalling with an explicitly admitted SDK."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from kernel_sdk import validate_sdk


class NativeMetadataWrapperTests(unittest.TestCase):
    def test_actual_syscall6_marshalling_reserved_words_and_errno(self):
        self.assertIn('OK_TEST_KERNEL_SDK', os.environ, 'Set OK_TEST_KERNEL_SDK to the explicit exported SDK')
        sdk = Path(os.environ['OK_TEST_KERNEL_SDK']).resolve()
        manifest = validate_sdk(sdk, 'x86_64', 'debug')
        self.assertEqual(manifest['native_metadata_profile'], 'checked-mode-root-owner-u32-v1')
        with tempfile.TemporaryDirectory(prefix='native-metadata-wrapper-') as directory:
            project = Path(directory)
            quoted = lambda path: json.dumps(str(path))
            # Rename all public wrappers in the compiled translation unit so
            # sanitizer/libc references cannot retain unrelated okcrt sections.
            source = (ROOT / 'lib/okcrt/src/syscalls.c').read_text()
            import re
            functions = re.findall(r'^\w[\w \t*]*?\b([A-Za-z_]\w*)\([^;]*?\)\s*\{', source, re.MULTILINE)
            replacements = {name: 'metadata_test_' + name for name in functions}
            self.assertTrue({'chmod', 'fchownat', 'mmap', 'write'}.issubset(replacements))
            lines = ['set_project("native_metadata_wrappers_hosted")', 'set_languages("c11")',
                'target("wrapper")', 'set_kind("binary")',
                'add_includedirs(' + ','.join(quoted(p) for p in
                    (ROOT / 'sdk/include', ROOT / 'lib/okcrt/include', sdk / 'include')) + ')',
                'add_cflags("-Wall","-Wextra","-Werror","-fvisibility=hidden","-ffunction-sections","-fdata-sections",'
                '"-fsanitize=undefined","-fno-sanitize-recover=all",{force=true})',
                'add_defines(' + ','.join(json.dumps(k + '=' + v) for k,v in replacements.items()) + ')',
                'add_ldflags("-Wl,--gc-sections","-fsanitize=undefined",{force=true})',
                'add_files(' + ','.join(quoted(p) for p in
                    (ROOT / 'lib/okcrt/src/syscalls.c', ROOT / 'lib/okcrt/src/errno.c',
                     ROOT / 'tests/native_metadata_wrapper_tests.c')) + ')', 'target_end()']
            (project / 'xmake.lua').write_text('\n'.join(lines) + '\n')
            env = dict(os.environ, XMAKE_ROOT='y', XMAKE_GLOBALDIR=str(project / 'global'))
            for command in (['xmake', 'f', '-P', str(project), '-c', '-y', '-m', 'release', '--ccache=n'],
                            ['xmake', 'build', '-P', str(project), '-y', '-j2'],
                            [str(project / 'build/linux/x86_64/release/wrapper')]):
                subprocess.run(command, cwd=project, env=env, check=True, timeout=90)


if __name__ == '__main__':
    unittest.main()

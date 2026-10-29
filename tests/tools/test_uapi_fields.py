"""Layout parser tests independent of an installed Kernel SDK."""
import sys
import os
import subprocess
import tempfile
import unittest
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from check_uapi import struct_fields, parse_defines, validate_directives, EXPECTED_DEFINES, EXPECTED_FIELDS
from kernel_sdk import validate_sdk
import kernel_checkout


class UapiFieldsTests(unittest.TestCase):
    def test_commented_version_cannot_replace_compiled_version(self):
        source = ('#define OK_UAPI_VERSION_MINOR 10 /* actual version */\n'
                  '/*\n#define OK_UAPI_VERSION_MINOR 11\n*/')
        self.assertEqual(parse_defines(source), {'OK_UAPI_VERSION_MINOR': 10})

    def test_duplicate_numeric_directive_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, 'duplicate UAPI symbol'):
            parse_defines('#define OK_UAPI_VERSION_MINOR 11\n#define OK_UAPI_VERSION_MINOR 11\n')

    def test_expected_constant_requires_one_whole_numeric_replacement(self):
        for value in ('11 + 1', '11+1', '11 extra', 'OTHER', '', '11UULL', '11.0',
                      '(11) + 1', '(11)+(1)', '((11) + 1)', '(11))', '((11)', '()'):
            with self.subTest(value=value), self.assertRaisesRegex(SystemExit, 'unsupported UAPI value'):
                parse_defines('#define OK_UAPI_VERSION_MINOR ' + value + '\n')
        with self.assertRaisesRegex(SystemExit, 'unsupported UAPI value'):
            parse_defines('#define OK_UAPI_VERSION_MINOR() 11\n')

    def test_malformed_and_function_like_duplicates_cannot_hide(self):
        for duplicate in ('#define OK_UAPI_VERSION_MINOR() 11', '#define OK_UAPI_VERSION_MINOR OTHER',
                          '#define OK_UAPI_VERSION_MINOR', '# define OK_UAPI_VERSION_MINOR 16'):
            with self.subTest(duplicate=duplicate), self.assertRaisesRegex(SystemExit, 'duplicate UAPI symbol'):
                parse_defines('#define OK_UAPI_VERSION_MINOR 11\n' + duplicate + '\n')
        with self.assertRaisesRegex(SystemExit, 'unsupported UAPI value'):
            parse_defines('#define OK_UAPI_VERSION_MINOR OTHER\n#define OK_UAPI_VERSION_MINOR 11\n')

    def test_numeric_utilities_and_unrelated_function_macros_remain_usable(self):
        self.assertEqual(parse_defines('#define FIRST 0x10u\n#define SECOND 017LL\n#define THIRD -12\n'
                                       '#define OK_CMSG_LEN(length) (sizeof(int) + (length))\n'),
                         {'FIRST': 16, 'SECOND': 15, 'THIRD': -12})
        self.assertEqual(parse_defines('#define OK_AT_FDCWD (-100)\n'
                                       '#define OK_UAPI_VERSION_MINOR (( 11U ))\n'),
                         {'OK_AT_FDCWD': -100, 'OK_UAPI_VERSION_MINOR': 11})

    @kernel_checkout.requires_checkout
    def test_checked_in_kernel_uapi_header_is_accepted(self):
        include = kernel_checkout.INCLUDE
        header = include / 'ok/uapi/syscall.h'
        self.assertTrue(header.is_file())
        values = parse_defines(header.read_text())
        self.assertEqual(values['OK_UAPI_VERSION_MINOR'], 16)
        self.assertEqual(values['OK_NATIVE_SESSIONS_VERSION'], 3)
        self.assertEqual(values['OK_NATIVE_CONSOLE_CONTROL_VERSION'], 1)
        self.assertEqual(values['OK_TIOCGSID'], 0x5429)
        result = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'tools/check_uapi.py'),
                                 '--include', str(include)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless('OK_TEST_KERNEL_SDK' in os.environ, 'explicit exported SDK required')
    def test_real_exported_uapi_header_is_accepted(self):
        sdk = Path(os.environ['OK_TEST_KERNEL_SDK']).resolve()
        self.assertTrue((sdk / 'manifest.json').is_file())
        mode = os.environ.get('OK_TEST_KERNEL_MODE', 'debug')
        self.assertIn(mode, ('debug', 'release'))
        manifest = validate_sdk(sdk, os.environ.get('OK_TEST_KERNEL_ARCH', 'x86_64'), mode)
        self.assertEqual(manifest['abi_version'], 77)
        self.assertEqual(manifest['native_pty_profile'], 'bootcpu-native-raw-pair-ofd-waits-drain-eof-eio-v1')
        values = parse_defines((sdk / 'include/ok/uapi/syscall.h').read_text())
        self.assertEqual(values['OK_AT_FDCWD'], -100)
        self.assertEqual([values['OK_UAPI_VERSION_' + component] for component in ('MAJOR', 'MINOR', 'PATCH')],
                         [0, 16, 0])
        self.assertEqual([values[name] for name in ('OK_SYS_PTY_PAIR', 'OK_NATIVE_PTY_PAIR_VERSION',
                         'OK_NATIVE_PTY_NONBLOCK', 'OK_NATIVE_PTY_CLOEXEC')], [1035, 1, 0x0800, 0x080000])
        result = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'tools/check_uapi.py'),
                                 '--include', str(sdk / 'include')], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @kernel_checkout.requires_checkout
    def test_raw_pty_constants_reject_missing_wrong_and_deceptive_declarations(self):
        expected = {
            'OK_SYS_PTY_PAIR': 1035,
            'OK_NATIVE_PTY_PAIR_VERSION': 1,
            'OK_NATIVE_PTY_NONBLOCK': 0x0800,
            'OK_NATIVE_PTY_CLOEXEC': 0x080000,
        }
        self.assertEqual({name: EXPECTED_DEFINES[name] for name in expected}, expected)
        good = (kernel_checkout.INCLUDE / 'ok/uapi/syscall.h').read_text()
        with tempfile.TemporaryDirectory(prefix='ok-uapi-pty-admission-') as directory:
            include = Path(directory)
            header = include / 'ok/uapi/syscall.h'; header.parent.mkdir(parents=True)
            command = [sys.executable, '-I', '-B', str(ROOT / 'tools/check_uapi.py'), '--include', str(include)]
            header.write_text(good)
            accepted = subprocess.run(command, capture_output=True)
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            for name, value in expected.items():
                declaration = re.findall(r'^#define ' + name + r'[^\n]*\n', good, re.M)
                self.assertEqual(len(declaration), 1, name)
                line = declaration[0]
                replacements = {
                    'missing': '',
                    'wrong': '#define ' + name + ' ' + str(value + 1) + '\n',
                    'comment-only': '/* ' + line.rstrip() + ' */\n',
                    'expression': '#define ' + name + ' ' + str(value) + ' + 0\n',
                    'function-like': '#define ' + name + '() ' + str(value) + '\n',
                    'duplicate': line + line,
                }
                for label, replacement in replacements.items():
                    source = good.replace(line, replacement)
                    self.assertNotEqual(source, good, (name, label))
                    header.write_text(source)
                    rejected = subprocess.run(command, capture_output=True)
                    with self.subTest(symbol=name, case=label):
                        self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                        self.assertNotIn(b'[uapi] checked', rejected.stdout)

    def test_only_main_requires_the_complete_canonical_guard(self):
        with self.assertRaisesRegex(SystemExit, 'include guard'):
            validate_directives('#define OK_UAPI_VERSION_MINOR 11\n')
        validate_directives('#ifndef OK_UAPI_SYSCALL_H\n#define OK_UAPI_SYSCALL_H\n'
                            '#include <stdint.h>\n#define OK_CMSG_LEN(length) (sizeof(int) + (length))\n#endif\n')

    def test_main_checks_complete_header_and_refuses_preprocessor_deception(self):
        # Construct only the checker's required declarations as a valid seed.
        # Independent mutations below exercise admission grammar, not the
        # correctness of the ABI constants or target compilation.
        good = '#ifndef OK_UAPI_SYSCALL_H\n#define OK_UAPI_SYSCALL_H\n#include <stdint.h>\n'
        good += ''.join('#define ' + name + ' ' + str(value) + '\n'
                        for name, value in EXPECTED_DEFINES.items())
        good += ''.join('struct ' + name + '\n{\n' +
                        ''.join('    ' + kind + ' ' + field + ';\n' for kind, field in fields) + '};\n'
                        for name, fields in EXPECTED_FIELDS.items())
        good += '#endif\n'
        cases = {
            'numeric-prefix-expression': good.replace('#define OK_UAPI_VERSION_MINOR 16',
                                                      '#define OK_UAPI_VERSION_MINOR 16 + 1'),
            'conditional-definition': good.replace('#define OK_UAPI_VERSION_MINOR 16',
                '#if 0\n#define OK_UAPI_VERSION_MINOR 16\n#endif'),
            'undef-after-definition': good.replace('#define OK_UAPI_VERSION_MINOR 16',
                '#define OK_UAPI_VERSION_MINOR 16\n#undef OK_UAPI_VERSION_MINOR'),
            'spaced-redefinition': good.replace('#define OK_UAPI_VERSION_MINOR 16',
                '#define OK_UAPI_VERSION_MINOR 16\n# define OK_UAPI_VERSION_MINOR 10'),
            'function-like-duplicate': good.replace('#define OK_UAPI_VERSION_MINOR 16',
                '#define OK_UAPI_VERSION_MINOR 16\n#define OK_UAPI_VERSION_MINOR() 13'),
            'malformed-duplicate': good.replace('#define OK_UAPI_VERSION_MINOR 16',
                '#define OK_UAPI_VERSION_MINOR 16\n#define OK_UAPI_VERSION_MINOR OTHER'),
            'comment-decoy': good.replace('#define OK_UAPI_VERSION_MINOR 16',
                '#define OK_UAPI_VERSION_MINOR 10 /* actual */\n/*\n#define OK_UAPI_VERSION_MINOR 16\n*/'),
            'conditional-record': good.replace('struct ok_mount_info', '#if 0\nstruct ok_mount_info', 1),
            'type-shadow': good.replace('#endif', '#define uint32_t uint16_t\n#endif'),
            'pragma-pack': good.replace('#endif', '#pragma pack(1)\n#endif'),
        }
        with tempfile.TemporaryDirectory(prefix='ok-uapi-admission-') as directory:
            include = Path(directory)
            header = include / 'ok/uapi/syscall.h'; header.parent.mkdir(parents=True)
            command = [sys.executable, '-I', '-B', str(ROOT / 'tools/check_uapi.py'), '--include', str(include)]
            header.write_text(good)
            accepted = subprocess.run(command, capture_output=True)
            self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)
            for label, source in cases.items():
                self.assertNotEqual(source, good, label)
                header.write_text(source)
                rejected = subprocess.run(command, capture_output=True)
                with self.subTest(label=label):
                    self.assertNotEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
                    self.assertNotIn(b'[uapi] checked', rejected.stdout)

    def test_commented_record_is_not_a_layout(self):
        with self.assertRaisesRegex(SystemExit, 'missing UAPI layout'):
            struct_fields('/* struct info { uint32_t value; }; */', 'info')

    def test_nested_stat_record(self):
        text = "struct ok_stat_v2 {\n struct ok_stat basic;\n uint64_t inode;\n};"
        self.assertEqual(struct_fields(text, "ok_stat_v2"),
                         [("struct ok_stat", "basic"), ("uint64_t", "inode")])

    def test_reordered_or_extra_field_remains_visible(self):
        text = "struct ok_stat_v2 {\n uint64_t inode;\n struct ok_stat basic;\n uint32_t extra;\n};"
        self.assertEqual(struct_fields(text, "ok_stat_v2"),
                         [("uint64_t", "inode"), ("struct ok_stat", "basic"), ("uint32_t", "extra")])

    def test_missing_record_is_rejected(self):
        with self.assertRaisesRegex(SystemExit, "missing UAPI layout"):
            struct_fields("struct ok_stat {};", "ok_stat_v2")

    def test_fixed_array_remains_visible(self):
        text = "struct ok_stat_v2 {\n struct ok_stat basic;\n uint64_t inode;\n uint8_t extra[4];\n};"
        self.assertEqual(struct_fields(text, "ok_stat_v2"),
                         [("struct ok_stat", "basic"), ("uint64_t", "inode"), ("uint8_t", "extra[4]")])

    def test_named_array_bound_remains_visible(self):
        self.assertEqual(struct_fields("struct info {\n char path[ PATH_BYTES ];\n};", "info"),
                         [("char", "path[PATH_BYTES]")])

    def test_noncanonical_array_declarations_are_rejected(self):
        for field in ("char path[];", "char path[0];", "char path[-1];", "char path[2 + 2];",
                      "char path[4][2];", "char *path;", "char path[4], extra;", "char path[4] = {0};"):
            with self.subTest(field=field), self.assertRaisesRegex(SystemExit, "unsupported UAPI field"):
                struct_fields("struct info {\n " + field + "\n};", "info")


if __name__ == "__main__":
    unittest.main()

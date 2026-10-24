"""Verify pinned source admission without fetching or executing third-party code."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
import struct
import tarfile
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from musl_source import PORTS, VERSION, extract_archive, inspect_archive, source_pin, inspect_elf, validate_build_path
from musl_source import PPC_CLANG_SHA256, PPC_CLANG_TARGET, ppc_frontend, build_static, digest
from build_musl_probe import admit_musl_build


class MuslSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archive = self.root / "source.tar.gz"

    def fixture(self, extra=None):
        files = [(f"musl-{VERSION}/arch/{port}/syscall_arch.h", b"source") for port in PORTS.values()]
        if extra:
            files.append(extra)
        with tarfile.open(self.archive, "w:gz") as archive:
            for name, content in files:
                member = tarfile.TarInfo(name)
                if content is None:
                    member.type = tarfile.SYMTYPE
                    member.linkname = "/etc/hostname"
                    archive.addfile(member)
                else:
                    member.size = len(content)
                    archive.addfile(member, io.BytesIO(content))
        return {"version": VERSION, "url": "https://example.invalid/test-fixture",
                "archive_sha256": hashlib.sha256(self.archive.read_bytes()).hexdigest(), "audited_files": []}

    def test_selected_pin_is_concrete_and_not_signature_claim(self):
        pin = source_pin()
        self.assertEqual(pin["version"], VERSION)
        self.assertEqual(pin["archive_sha256"], "a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4")
        self.assertEqual(len(PORTS), 10)

    def test_build_paths_reject_shell_and_make_syntax(self):
        validate_build_path(Path("/tmp/toolchain-14.2.0_abi+1"))
        for character in (";", "&", "|", "<", ">", "(", ")", "$", "`", "#", "\\", " ", "\n", "\t", "'", '"', "%", "*", "?", "=", ":"):
            with self.subTest(character=repr(character)), self.assertRaisesRegex(ValueError, "absolute path"):
                validate_build_path(Path("/tmp/tool" + character + "chain"))
        with self.assertRaisesRegex(ValueError, "absolute path"):
            validate_build_path(Path("relative/path"))

    def test_reject_wrong_archive_before_tar_parsing(self):
        self.archive.write_bytes(b"not the pinned source")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            inspect_archive(self.archive)

    def test_preserve_all_ports_without_native_claim(self):
        with patch("musl_source.source_pin", return_value=self.fixture()):
            result = inspect_archive(self.archive)
            self.assertFalse(result["native_execution"])
            self.assertFalse(result["signature_verified"])
            self.assertEqual(result["ports_present"], PORTS)
            directory = extract_archive(self.archive, self.root / "extracted")
            self.assertEqual((directory / "arch/powerpc/syscall_arch.h").read_bytes(), b"source")

    def test_reject_traversal_absolute_path_symlink_and_duplicate(self):
        entries = [(f"musl-{VERSION}/../outside", b"unsafe"), ("/absolute", b"unsafe"),
                   (f"musl-{VERSION}/symlink", None), (f"musl-{VERSION}/arch/i386/syscall_arch.h", b"duplicate")]
        for extra in entries:
            with self.subTest(extra=extra), patch("musl_source.source_pin", return_value=self.fixture(extra)):
                with self.assertRaisesRegex(ValueError, "unsafe or duplicate"):
                    inspect_archive(self.archive)

    def test_elf_architecture_and_static_admission(self):
        data = bytearray(120)
        data[:7] = b"\x7fELF\x02\x01\x01"
        struct.pack_into("<HH", data, 16, 2, 62)
        struct.pack_into("<Q", data, 32, 64)
        struct.pack_into("<HH", data, 54, 56, 1)
        struct.pack_into("<I", data, 64, 1)
        file = self.root / "probe.elf"
        file.write_bytes(data)
        self.assertFalse(inspect_elf(file, "x86_64")["executed"])
        with self.assertRaisesRegex(ValueError, "class/endian/version"):
            inspect_elf(file, "mips64")
        struct.pack_into("<I", data, 64, 3)
        file.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "no PT_INTERP"):
            inspect_elf(file, "x86_64")
        file.write_bytes(data[:80])
        with self.assertRaisesRegex(ValueError, "program headers"):
            inspect_elf(file, "x86_64")

    def test_reject_modified_audited_file(self):
        pin = self.fixture()
        pin["audited_files"] = [{"path": "arch/i386/syscall_arch.h", "sha256": "0" * 64}]
        with patch("musl_source.source_pin", return_value=pin), self.assertRaisesRegex(ValueError, "audited source checksum"):
            inspect_archive(self.archive)

    def frontend_fixture(self):
        compiler = self.root / 'clang'
        compiler.write_bytes(b'isolated test frontend')
        macros = '\n'.join('#define ' + name + ' ' + value for name, value in {
            '__SIZEOF_POINTER__': '4', '__SIZEOF_LONG_DOUBLE__': '8',
            '__BYTE_ORDER__': '__ORDER_BIG_ENDIAN__', '__powerpc__': '1',
            '__linux__': '1', '__clang_major__': '18'}.items())
        return compiler, ['Ubuntu clang version 18.1.3 (1ubuntu1)\n', PPC_CLANG_TARGET + '\n', macros]

    def test_ppc_frontend_is_explicit_pinned_and_effectively_linux(self):
        compiler, replies = self.frontend_fixture()
        self.assertIsNone(ppc_frontend('ppc', None))
        with self.assertRaisesRegex(ValueError, 'requires explicit'):
            ppc_frontend('ppc', None, required=True)
        with self.assertRaisesRegex(ValueError, 'only supported'):
            ppc_frontend('x86_64', compiler)
        with self.assertRaisesRegex(ValueError, 'SHA-256 pin'):
            ppc_frontend('ppc', compiler)
        with patch('musl_source.digest', return_value=PPC_CLANG_SHA256), \
                patch('musl_source.subprocess.check_output', side_effect=replies) as query:
            result = ppc_frontend('ppc', compiler)
        self.assertEqual(result['sha256'], PPC_CLANG_SHA256)
        self.assertEqual(result['target'], PPC_CLANG_TARGET)
        for call in query.call_args_list[1:]:
            self.assertIn('--target=powerpc-linux-musl', call.args[0])
            self.assertIn('-msoft-float', call.args[0])
            self.assertIn('-mlong-double-64', call.args[0])

    def test_ppc_frontend_rejects_wrong_version_target_and_abi(self):
        compiler, original = self.frontend_fixture()
        for index, replacement in [(0, 'clang version 19.0.0\n'), (1, 'powerpc-eabi\n'),
                                   (2, original[2].replace('__SIZEOF_POINTER__ 4', '__SIZEOF_POINTER__ 8')),
                                   (2, original[2].replace('__ORDER_BIG_ENDIAN__', '__ORDER_LITTLE_ENDIAN__')),
                                   (2, original[2].replace('__SIZEOF_LONG_DOUBLE__ 8', '__SIZEOF_LONG_DOUBLE__ 16'))]:
            replies = list(original)
            replies[index] = replacement
            with self.subTest(index=index, replacement=replacement), \
                    patch('musl_source.digest', return_value=PPC_CLANG_SHA256), \
                    patch('musl_source.subprocess.check_output', side_effect=replies), \
                    self.assertRaisesRegex(ValueError, 'mismatch'):
                ppc_frontend('ppc', compiler)

    def build_manifest_fixture(self):
        record = {'schema_version': 1, 'version': VERSION, 'architecture': 'ppc', 'mode': 'debug',
                  'archive_sha256': source_pin()['archive_sha256'], 'status': 'built-not-executed',
                  'native_execution': False, 'files': {}}
        for relative in ('sysroot/usr/lib/crt1.o', 'sysroot/usr/lib/crti.o', 'sysroot/usr/lib/crtn.o',
                         'sysroot/usr/lib/libc.a', 'sysroot/usr/include/unistd.h',
                         'sysroot/usr/include/errno.h', 'sysroot/usr/include/time.h'):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(relative.encode())
            record['files'][relative] = digest(path)
        (self.root / 'manifest.json').write_text(json.dumps(record))
        return record

    def test_probe_source_requires_successful_matching_version_mode(self):
        record = self.build_manifest_fixture()
        self.assertEqual(admit_musl_build(self.root, 'ppc')['mode'], 'debug')
        for key, invalid in [('status', 'build-failed'), ('status', 'building'), ('version', '1.2.4'),
                             ('version', None), ('mode', None), ('mode', 'checked'), ('schema_version', 2),
                             ('architecture', 'mips'), ('native_execution', True), ('archive_sha256', '0' * 64)]:
            changed = {**record, key: invalid}
            (self.root / 'manifest.json').write_text(json.dumps(changed))
            before = (self.root / 'manifest.json').read_bytes()
            with self.subTest(key=key, invalid=invalid), self.assertRaises(ValueError):
                admit_musl_build(self.root, 'ppc')
            self.assertEqual((self.root / 'manifest.json').read_bytes(), before)

    def test_probe_source_rejects_missing_modified_and_escaping_artifacts(self):
        record = self.build_manifest_fixture()
        library = self.root / 'sysroot/usr/lib/libc.a'
        original = library.read_bytes()
        library.write_bytes(b'modified')
        with self.assertRaisesRegex(ValueError, 'artifact mismatch'):
            admit_musl_build(self.root, 'ppc')
        library.unlink()
        outside = self.root.parent / (self.root.name + '-outside')
        outside.write_bytes(original)
        self.addCleanup(outside.unlink)
        library.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'artifact mismatch'):
            admit_musl_build(self.root, 'ppc')
        del record['files']['sysroot/usr/lib/libc.a']
        (self.root / 'manifest.json').write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError, 'lacks audited'):
            admit_musl_build(self.root, 'ppc')

    def test_static_ppc_uses_clang_application_object_with_gcc_libc_and_linker(self):
        compiler, _ = self.frontend_fixture()
        bindir = self.root / 'toolchain/bin'
        bindir.mkdir(parents=True)
        for tool in ('gcc', 'ar', 'ranlib', 'readelf', 'as', 'ld'):
            (bindir / ('powerpc-eabi-' + tool)).write_bytes(tool.encode())
        runtime = self.root / 'libgcc.a'
        runtime.write_bytes(b'runtime')
        self.archive.write_bytes(b'admitted fixture')
        frontend = {'path': str(compiler), 'sha256': PPC_CLANG_SHA256,
                    'flags': ['--target=powerpc-linux-musl', '-mcpu=8548', '-msoft-float', '-mlong-double-64']}
        inspection = {'schema_version': 1, 'version': VERSION, 'native_execution': False}
        calls = []

        def extract(_archive, directory):
            source = directory / ('musl-' + VERSION)
            source.mkdir(parents=True)
            (source / 'COPYRIGHT').write_text('fixture license')
            return source

        def execute(command, **kwargs):
            command = list(map(str, command))
            calls.append(command)
            if command[:2] == ['make', 'install']:
                stage = Path(command[2].removeprefix('DESTDIR='))
                (stage / 'usr/lib').mkdir(parents=True)
                (stage / 'usr/include').mkdir(parents=True)
                for name in ('crt1.o', 'crti.o', 'crtn.o', 'libc.a'):
                    (stage / 'usr/lib' / name).write_bytes(name.encode())
            if '-o' in command:
                Path(command[command.index('-o') + 1]).write_bytes(b'isolated output')
            return SimpleNamespace(returncode=0)

        args = SimpleNamespace(archive=self.archive, arch='ppc', mode='debug', jobs=1,
                               out=self.root / 'built', toolchain=bindir.parent, ppc_clang=compiler)
        with patch('musl_source.inspect_archive', return_value=inspection), \
                patch('musl_source.extract_archive', side_effect=extract), \
                patch('musl_source.ppc_frontend', return_value=frontend), \
                patch('musl_source.inspect_elf', return_value={'executed': False}), \
                patch('musl_source.subprocess.check_output', side_effect=['powerpc-eabi\n', '14.2.0\n', str(runtime)]), \
                patch('musl_source.subprocess.run', side_effect=execute):
            result = build_static(args)
        self.assertEqual(result['status'], 'built-not-executed')
        self.assertFalse(result['native_execution'])
        self.assertIn('-O2', result['cflags'])
        self.assertNotIn('-O0', result['cflags'])
        self.assertIn('-g', result['cflags'])
        self.assertIn('CC=' + str(bindir / 'powerpc-eabi-gcc'), calls[0])
        compile_call = next(command for command in calls if command[0] == str(compiler))
        self.assertIn('--target=powerpc-linux-musl', compile_call)
        link_call = next(command for command in calls if '-static' in command)
        self.assertEqual(link_call[0], str(bindir / 'powerpc-eabi-gcc'))
        self.assertTrue(any(value.endswith('/probe.o') for value in link_call))
        self.assertFalse(any(value.endswith('/probe.c') for value in link_call))
        self.assertEqual(result['probe_compiler']['sha256'], PPC_CLANG_SHA256)
        self.assertEqual(result['tool_sha256']['ld'], digest(bindir / 'powerpc-eabi-ld'))
        self.assertIn('probe.c', result['files'])
        self.assertIn('probe.o', result['files'])


if __name__ == "__main__":
    unittest.main()

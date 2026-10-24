"""Independent ELF byte fixtures for shared-musl artifact admission."""
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from build_shared_musl import ELF_FLAGS, PROFILES, admit_runtimes, inspect_loader


def fixture(arch):
    cls, order, machine = PROFILES[arch]
    endian = '<' if order == 1 else '>'
    word = 4 if cls == 1 else 8
    header, phsize = (52, 32) if cls == 1 else (64, 56)
    data = bytearray(1024)
    data[:7] = b'\x7fELF' + bytes((cls, order, 1))
    struct.pack_into(endian + 'HHI', data, 16, 3, machine, 1)
    struct.pack_into(endian + 'I', data, 36 if cls == 1 else 48, ELF_FLAGS[arch])
    if cls == 1:
        struct.pack_into(endian + 'II', data, 24, 0x10100, header)
        struct.pack_into(endian + 'HHH', data, 40, header, phsize, 3)
        struct.pack_into(endian + 'IIIIIIII', data, header, 1, 0, 0x10000, 0, 1024, 1024, 5, 4096)
        struct.pack_into(endian + 'IIIIIIII', data, header + phsize, 2, 512, 0x10200, 0, 12 * word, 12 * word, 4, word)
        struct.pack_into(endian + 'IIIIIIII', data, header + 2 * phsize, 0x6474e551, 0, 0, 0, 0, 0, 6, word)
    else:
        struct.pack_into(endian + 'QQ', data, 24, 0x10100, header)
        struct.pack_into(endian + 'HHH', data, 52, header, phsize, 3)
        struct.pack_into(endian + 'IIQQQQQQ', data, header, 1, 5, 0, 0x10000, 0, 1024, 1024, 4096)
        struct.pack_into(endian + 'IIQQQQQQ', data, header + phsize, 2, 4, 512, 0x10200, 0, 12 * word, 12 * word, word)
        struct.pack_into(endian + 'IIQQQQQQ', data, header + 2 * phsize, 0x6474e551, 6, 0, 0, 0, 0, 0, word)
    tags = [(5, 0x10000 + 700), (6, 0x10000 + 768), (10, 8), (11, 16 if cls == 1 else 24), (14, 0), (0, 0)]
    for index, pair in enumerate(tags):
        struct.pack_into(endian + ('II' if cls == 1 else 'QQ'), data, 512 + index * word * 2, *pair)
    data[700:708] = b'libc.so\0'
    if arch in ('mips', 'mips64'):
        struct.pack_into(endian + 'H', data, 44 if cls == 1 else 56, 4)
        isa, register = (32, 1) if cls == 1 else (64, 2)
        struct.pack_into('>HBBBBBBIIII', data, 900, 0, isa, 2, register, register, 0, 1, 0, 0, 1, 0)
        if cls == 1:
            struct.pack_into('>IIIIIIII', data, header + 3 * phsize, 0x70000003, 900, 0x10384, 0, 24, 24, 4, 8)
        else:
            struct.pack_into('>IIQQQQQQ', data, header + 3 * phsize, 0x70000003, 4, 900, 0x10384, 0, 24, 24, 8)
    return data


class SharedMuslRuntimeSelectionTests(unittest.TestCase):
    def args(self, arch, **overrides):
        values = dict(arch=arch, mode='release', pic_runtime_build=None,
                      pic_runtime_manifest_sha256=None, softfp_build=None,
                      softfp_manifest_sha256=None, gcc_pic_runtime_build=None,
                      gcc_pic_runtime_manifest_sha256=None, ppc_pic_runtime_build=None,
                      ppc_pic_runtime_manifest_sha256=None)
        values.update(overrides)
        return types.SimpleNamespace(**values)

    def test_required_runtime_pairs_and_wrong_profile_reject_before_import(self):
        for arch in ('mips', 'mips64', 'rv32', 'rv64', 'loongarch64', 'ppc'):
            with self.subTest(arch=arch), self.assertRaises(ValueError):
                admit_runtimes(self.args(arch), Path('/unselected/compiler'))
        for selector in ('pic_runtime', 'softfp', 'gcc_pic_runtime', 'ppc_pic_runtime'):
            for values in ({selector + '_build': Path('/unselected/runtime')},
                           {selector + '_manifest_sha256': 'a' * 64},
                           {selector + '_build': Path('/unselected/runtime'),
                            selector + '_manifest_sha256': 'a' * 64}):
                with self.subTest(selector=selector, values=values), self.assertRaises(ValueError):
                    admit_runtimes(self.args('x86_64', **values), Path('/unselected/compiler'))

    def test_all_ten_dispatch_exact_compiler_mode_and_inventory(self):
        selectors = {'mips': ['pic_runtime'], 'mips64': ['pic_runtime', 'softfp'],
                     'rv32': ['gcc_pic_runtime'], 'rv64': ['gcc_pic_runtime'],
                     'loongarch64': ['gcc_pic_runtime'], 'ppc': ['ppc_pic_runtime']}
        modules = {'pic_runtime': 'mips_pic_runtime', 'softfp': 'mips64_softfp',
                   'gcc_pic_runtime': 'gcc_pic_runtime', 'ppc_pic_runtime': 'ppc_pic_runtime'}
        kinds = {'pic_runtime': 'pic-libgcc', 'softfp': 'binary128',
                 'gcc_pic_runtime': 'gcc-pic', 'ppc_pic_runtime': 'ppc-pic'}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            compiler = root / 'explicit-compiler'
            overrides, calls, installed = {}, [], {}
            for selector, module_name in modules.items():
                directory = root / selector
                directory.mkdir()
                archive = directory / 'libgcc.a'
                archive.write_bytes(selector.encode())
                (directory / 'manifest.json').write_bytes(b'{}')
                expected = str(len(overrides) % 10) * 64
                overrides[selector] = {selector + '_build': directory,
                                       selector + '_manifest_sha256': expected}
                module = types.ModuleType(module_name)
                def admit(directory, expected, arch, mode, selected_compiler, selector=selector):
                    calls.append((selector, directory, expected, arch, mode, selected_compiler))
                    return directory / 'libgcc.a', {}
                module.admit = admit
                installed[module_name] = module
            with patch.dict(sys.modules, installed):
                for arch in PROFILES:
                    calls.clear()
                    requested = selectors.get(arch, [])
                    options = {key: value for selector in requested
                               for key, value in overrides[selector].items()}
                    result = admit_runtimes(self.args(arch, **options), compiler)
                    self.assertEqual([item['kind'] for item in result], [kinds[s] for s in requested])
                    self.assertEqual([item[0] for item in calls], requested)
                    for selector, directory, expected, called_arch, mode, selected in calls:
                        self.assertEqual((directory, expected),
                                         (overrides[selector][selector + '_build'],
                                          overrides[selector][selector + '_manifest_sha256']))
                        self.assertEqual((called_arch, mode, selected), (arch, 'release', compiler))
                    for item in result:
                        self.assertEqual(set(item['files']), {'libgcc.a', 'manifest.json'})
                        self.assertEqual(item['files']['libgcc.a'], item['sha256'])


class SharedMuslElfTests(unittest.TestCase):
    def test_all_ten_explicit_profiles(self):
        self.assertEqual(len(PROFILES), 10)
        for arch, (cls, order, machine) in PROFILES.items():
            with self.subTest(arch=arch):
                result = inspect_loader(fixture(arch), arch)
                self.assertEqual(result['machine'], machine)
                self.assertEqual(result['type'], 'ET_DYN')
                self.assertFalse(result['executed'])

    def test_rejects_corrupt_identity_and_loads(self):
        for arch, (cls, order, _) in PROFILES.items():
            endian = '<' if order == 1 else '>'
            header = 52 if cls == 1 else 64
            phsize = 32 if cls == 1 else 56
            wordfmt = 'I' if cls == 1 else 'Q'
            data = fixture(arch)
            cases = []
            for name, offset, fmt, value in [
                ('static-executable', 16, 'H', 2), ('wrong-machine', 18, 'H', 0),
                ('bad-version', 20, 'I', 0),
                ('wrong-abi-flags', 36 if cls == 1 else 48, 'I', ELF_FLAGS[arch] ^ 1),
                ('no-executable-entry', 24, wordfmt, 0),
                ('interpreter', header, 'I', 3),
                ('writable-executable', header + (24 if cls == 1 else 4), 'I', 7),
                ('executable-stack', header + 2 * phsize + (24 if cls == 1 else 4), 'I', 7),
                ('missing-stack', header + 2 * phsize, 'I', 0),
                ('load-file-overrun', header + (16 if cls == 1 else 32), wordfmt, 2048),
                ('load-address-overflow', header + (8 if cls == 1 else 16), wordfmt, (1 << (32 if cls == 1 else 64)) - 512),
                ('external-dso-dependency', 512, wordfmt, 1),
                ('text-relocations', 512, wordfmt, 22),
                ('bad-symbol-address', 512 + (8 if cls == 1 else 16) + (4 if cls == 1 else 8), wordfmt, 0),
                ('unterminated-soname', 512 + (8 if cls == 1 else 16) * 2 + (4 if cls == 1 else 8), wordfmt, 7),
            ]:
                changed = bytearray(data)
                struct.pack_into(endian + fmt, changed, offset, value)
                cases.append((name, changed))
            cases.extend([('truncated-header', data[:31]), ('truncated-data', data[:707])])
            for name, changed in cases:
                with self.subTest(arch=arch, case=name), self.assertRaises(ValueError):
                    inspect_loader(changed, arch)

    def test_file_only_riscv_attributes_and_word_boundary(self):
        for arch in ('rv32', 'rv64'):
            cls = PROFILES[arch][0]
            header, phsize, word = (52, 32, 4) if cls == 1 else (64, 56, 8)
            data = fixture(arch)
            struct.pack_into('<H', data, 44 if cls == 1 else 56, 4)
            if cls == 1:
                struct.pack_into('<IIIIIIII', data, header + 3 * phsize,
                                 0x70000003, 900, 0, 0, 16, 0, 4, 1)
            else:
                struct.pack_into('<IIQQQQQQ', data, header + 3 * phsize,
                                 0x70000003, 4, 900, 0, 0, 16, 0, 1)
            inspect_loader(data, arch)
            # A mapped one-past endpoint cannot be represented in target words.
            struct.pack_into('<' + ('I' if cls == 1 else 'Q'), data,
                             header + (8 if cls == 1 else 16), (1 << (word * 8)) - 1024)
            with self.assertRaisesRegex(ValueError, 'mapped segment extent'):
                inspect_loader(data, arch)

    def test_mips_rejects_missing_duplicate_and_incompatible_fp_records(self):
        for arch in ('mips', 'mips64'):
            cls = PROFILES[arch][0]
            header, phsize = (52, 32) if cls == 1 else (64, 56)
            original = fixture(arch)
            variants = []
            for name, at, fmt, value in [
                ('missing', header + 3 * phsize, 'I', 0),
                ('soft-float', 907, 'B', 3),
                ('unsupported-isa', 902, 'B', 3),
                ('different-registers', 904, 'B', 0),
                ('nan2008-extension', 912, 'I', 1),
                ('unknown-abi-flags', 920, 'I', 1),
            ]:
                changed = bytearray(original)
                struct.pack_into('>' + fmt, changed, at, value)
                variants.append((name, changed))
            duplicate = bytearray(original)
            struct.pack_into('>H', duplicate, 44 if cls == 1 else 56, 5)
            duplicate[header + 4 * phsize:header + 5 * phsize] = original[header + 3 * phsize:header + 4 * phsize]
            variants.append(('duplicate', duplicate))
            for name, changed in variants:
                with self.subTest(arch=arch, case=name), self.assertRaises(ValueError):
                    inspect_loader(changed, arch)

    def test_load_aliases_and_indirect_library_dependencies(self):
        for arch, (cls, order, _) in PROFILES.items():
            endian = '<' if order == 1 else '>'
            header, phsize, word = (52, 32, 4) if cls == 1 else (64, 56, 8)
            original = fixture(arch)
            # Put a second file range over the first range's entry/dynamic bytes.
            # Both segments are individually within bounds; their joint map is
            # ambiguous regardless of which program-header order is selected.
            count_offset = 44 if cls == 1 else 56
            count = struct.unpack_from(endian + 'H', original, count_offset)[0]
            overlapping = bytearray(original)
            struct.pack_into(endian + 'H', overlapping, count_offset, count + 1)
            if cls == 1:
                struct.pack_into(endian + 'IIIIIIII', overlapping, header + count * phsize,
                                 1, 512, 0x10000, 0, 512, 512, 4, 1)
            else:
                struct.pack_into(endian + 'IIQQQQQQ', overlapping, header + count * phsize,
                                 1, 4, 512, 0x10000, 0, 512, 512, 1)
            with self.subTest(arch=arch, case='overlap'), self.assertRaisesRegex(ValueError, 'overlap'):
                inspect_loader(overlapping, arch)
            for tag in (0x7fffffff, 0x7ffffffd, 0x6ffffefc, 0x6ffffefb):
                dependent = bytearray(original)
                # Extend the mapped dynamic table to insert a filter/audit tag.
                struct.pack_into(endian + ('I' if cls == 1 else 'Q'), dependent,
                                 header + phsize + (16 if cls == 1 else 32), 14 * word)
                struct.pack_into(endian + ('I' if cls == 1 else 'Q'), dependent,
                                 header + phsize + (20 if cls == 1 else 40), 14 * word)
                fmt = endian + ('II' if cls == 1 else 'QQ')
                struct.pack_into(fmt, dependent, 512 + 10 * word, tag, 0)
                struct.pack_into(fmt, dependent, 512 + 12 * word, 0, 0)
                with self.subTest(arch=arch, tag=tag), self.assertRaisesRegex(ValueError, 'another shared library'):
                    inspect_loader(dependent, arch)


if __name__ == '__main__':
    unittest.main()

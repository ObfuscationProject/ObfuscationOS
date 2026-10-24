"""Compiler-runtime admission models; these tests do not execute target instructions."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import mips64_softfp as softfp


def object_bytes():
    data = bytearray(256)
    data[:9] = b'\x7fELF\x02\x02\x01\x00\x00'
    struct.pack_into('>HHI', data, 16, 1, 8, 1)
    struct.pack_into('>Q', data, 40, 64)
    struct.pack_into('>I', data, 48, 0x80000007)
    struct.pack_into('>HHH', data, 58, 64, 2, 1)
    names = b'\0.shstrtab\0.MIPS.abiflags\0'
    struct.pack_into('>IIQQQQIIQQ', data, 64, 11, 0x7000002a, 0, 0, 224, 24, 0, 0, 8, 24)
    struct.pack_into('>IIQQQQIIQQ', data, 128, 1, 3, 0, 0, 192, len(names), 0, 0, 1, 0)
    data[192:192+len(names)] = names
    struct.pack_into('>HBBBBBBIIII', data, 224, 0, 64, 2, 2, 2, 0, 1, 0, 0, 1, 0)
    return data


def archive_bytes(pin, objects):
    def member(name, data):
        header = f'{name:<16}{0:<12}{0:<6}{0:<6}{644:<8}{len(data):<10}`\n'.encode()
        return header + data + (b'\n' if len(data) & 1 else b'')
    names = softfp.expected_symbols(pin)
    strings = b''.join(n.encode() + b'\0' for n in names)
    strings += b'\0' if len(strings) & 1 else b''
    position = 8 + 60 + 4 + 4 * len(names) + len(strings)
    offsets, members = {}, []
    for name in pin['functions']:
        offsets['__' + name] = position
        entry = member(name + '.o/', objects[name])
        members.append(entry); position += len(entry)
    offsets.update(__netf2=offsets['__eqtf2'], __lttf2=offsets['__letf2'], __gttf2=offsets['__getf2'])
    index = struct.pack('>I', len(names)) + b''.join(struct.pack('>I', offsets[n]) for n in names) + strings
    return b'!<arch>\n' + member('/', index) + b''.join(members)


class ObjectAbiTests(unittest.TestCase):
    def test_reject_wrong_abi_and_corrupt_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'object.o'
            data = object_bytes()
            p.write_bytes(data)
            self.assertEqual(softfp.inspect_object(p)['profile'], softfp.PROFILE)
            for index, value in ((4, 1), (5, 1), (18, 1), (48, 0x70), (51, 0x27),
                                 (58, 1), (63, 9), (226, 32), (228, 1), (229, 1), (231, 0)):
                with self.subTest(index=index):
                    bad = bytearray(data); bad[index] = value; p.write_bytes(bad)
                    with self.assertRaises(ValueError): softfp.inspect_object(p)
            p.write_bytes(data[:230])
            with self.assertRaises(ValueError): softfp.inspect_object(p)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / 'build'; self.out.mkdir()
        self.compiler = self.root / 'compiler'; self.compiler.write_bytes(b'compiler model')
        self.pinfile = self.root / 'pin.json'
        self.pin = {'version': '14.3.0', 'archive_sha256': 'a' * 64,
                    'functions': ['addtf3', 'eqtf2', 'letf2', 'getf2'],
                    'files': {'COPYING3': hashlib.sha256(b'license').hexdigest()}}
        self.pinfile.write_text(json.dumps(self.pin))
        self.patch = patch.object(softfp, 'PIN', self.pinfile)
        self.patch.start(); self.addCleanup(self.patch.stop)
        objects = {n: object_bytes() for n in self.pin['functions']}
        data = {softfp.LIBRARY: archive_bytes(self.pin, objects), 'source-pin.json': self.pinfile.read_bytes(),
                'symbols-defined.log': b'defined model', 'symbols-undefined.log': b'',
                'elf-attributes.log': b'attributes model', 'source/COPYING3': b'license',
                'sysroot/usr/share/licenses/gcc-soft-fp/COPYING3': b'license',
                'objects/addtf3.o': object_bytes()}
        data.update({'objects/' + n + '.o': value for n, value in objects.items()})
        for name, contents in data.items():
            p = self.out / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(contents)
        self.record = dict(schema_version=1, architecture='mips64', mode='debug',
            profile=softfp.PROFILE, status='built-not-executed', executed=False,
            source_pin_sha256=softfp.digest(self.pinfile), source_archive_sha256='a' * 64,
            source_version='14.3.0', library=softfp.LIBRARY, compiler_sha256=softfp.digest(self.compiler),
            abi_macros=softfp.ABI_MACROS, symbols=softfp.expected_symbols(self.pin), undefined_symbols=[],
            object_abi={n: softfp.inspect_object(self.out / ('objects/' + n + '.o')) for n in objects},
            archive_members=sorted(n + '.o' for n in objects),
            files={name: softfp.digest(self.out / name) for name in data})

    def admit(self, record=None, **kwargs):
        path = self.out / 'manifest.json'; path.write_text(json.dumps(record or self.record))
        args = dict(manifest_sha256=softfp.digest(path), arch='mips64', mode='debug', compiler=self.compiler)
        args.update(kwargs)
        return softfp.admit(self.out, **args)

    def test_explicit_complete_model_admitted(self):
        self.assertEqual(self.admit()[0], self.out / softfp.LIBRARY)

    def test_wrong_contract(self):
        changes = {'schema_version': 2, 'architecture': 'rv64', 'mode': 'release', 'profile': 'soft-float',
                   'status': 'build-failed', 'executed': True, 'source_pin_sha256': 'f'*64,
                   'source_archive_sha256': '0'*64, 'source_version': '14.2.0',
                   'compiler_sha256': 'f'*64, 'library': '../lib.a', 'abi_macros': {},
                   'symbols': [], 'undefined_symbols': ['__addtf3'], 'object_abi': {}}
        for key, value in changes.items():
            with self.subTest(field=key):
                record = copy.deepcopy(self.record); record[key] = value
                with self.assertRaises(ValueError): self.admit(record)
        for kwargs in ({'manifest_sha256': '0'*64}, {'arch': 'ppc'}, {'mode': 'release'}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError): self.admit(**kwargs)

    def test_missing_audited_object(self):
        del self.record['files']['objects/addtf3.o']
        with self.assertRaisesRegex(ValueError, 'incomplete'): self.admit()

    def test_extra_and_modified_files(self):
        extra = self.out / 'extra.o'; extra.write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'inventory differs'): self.admit()
        extra.unlink()
        (self.out / softfp.LIBRARY).write_bytes(b'changed archive')
        with self.assertRaisesRegex(ValueError, 'checksum'): self.admit()

    def test_outside_symlink(self):
        target = self.out / softfp.LIBRARY; target.unlink(); target.symlink_to(self.compiler)
        self.record['files'][softfp.LIBRARY] = softfp.digest(self.compiler)
        with self.assertRaisesRegex(ValueError, 'escapes'): self.admit()

    def test_forged_upstream_source(self):
        path = self.out / 'source/COPYING3'; path.write_bytes(b'changed license')
        self.record['files']['source/COPYING3'] = softfp.digest(path)
        with self.assertRaisesRegex(ValueError, 'upstream source'): self.admit()

    def test_forged_source_pin(self):
        path = self.out / 'source-pin.json'; path.write_bytes(b'changed pin')
        self.record['files']['source-pin.json'] = softfp.digest(path)
        with self.assertRaisesRegex(ValueError, 'source pin mismatch'): self.admit()

    def test_archive_bytes_and_index_must_match_objects(self):
        target = self.out / softfp.LIBRARY
        original = target.read_bytes()
        bad_index = bytearray(original); bad_index[72:76] = b'\0' * 4
        bad_member = bytearray(original); bad_member[-17] ^= 1
        for data in (b'!<arch>\n', original[:-10], original + original[8:], bad_index, bad_member):
            with self.subTest(size=len(data)):
                target.write_bytes(data)
                self.record['files'][softfp.LIBRARY] = softfp.digest(target)
                with self.assertRaises(ValueError): self.admit()

    def test_reject_unsafe_names(self):
        for name in ('../x', '/x', 'a/../x', 'a\\x', './x'):
            with self.subTest(name=name), self.assertRaises(ValueError): softfp.member_path(self.out, name)


if __name__ == '__main__':
    unittest.main()

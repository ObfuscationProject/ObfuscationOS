"""Independently authored synthetic collector controls; no guest execution evidence.

The frames/stacks helpers below reuse the signal collector's public fixture format.
Use CREDENTIALS_REVIEW_OS_ROOT only when running from an isolated review directory.
"""
from pathlib import Path
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(os.environ.get('CREDENTIALS_REVIEW_OS_ROOT', Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests/tools'))
import native_credentials_evidence as evidence
from test_native_signal_delivery_x86_64 import frames, stacks, IMAGE

ARCHES = ('i386', 'x86_64', 'arm32', 'aarch64', 'rv32', 'rv64', 'loongarch64', 'mips', 'mips64', 'ppc')

def fixture(arch):
    marker, _, command, _ = evidence.probe_spec(arch, 'credentials')
    child = evidence.CHILD.replace(b'{arch}', arch.encode())
    output = command + b'\n' + IMAGE + IMAGE + child + b'\n' + marker + b'\n'
    parts = [
        b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n' +
        frames(0, 0) + stacks(0, 0, 0, peak=0) + frames(40, 0) + stacks(7, 5, 100) + b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n' + frames(100, 60) + stacks(10, 8, 200) + b'oksh> ',
        output + frames(200, 160) + stacks(14, 12, 300) + b'oksh> ',
        output + frames(300, 260) + stacks(18, 16, 400) + b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n' + frames(400, 360) + stacks(20, 18, 500) + b'oksh> ',
    ]
    if arch in ('loongarch64', 'mips', 'mips64'):
        parts = [p.replace(b'source=firmware', b'source=linker') for p in parts]
    return parts

def validate(parts, arch):
    ends = [sum(map(len, parts[:i])) for i in range(1, 5)]
    return evidence.validate_execution(b''.join(parts), *ends, ends[-1], arch)

class CredentialEvidence(unittest.TestCase):
    def test_all_ten_positive_two_run_contract(self):
        for arch in ARCHES:
            with self.subTest(arch=arch):
                result = validate(fixture(arch), arch)
                self.assertEqual((result['runs'], result['sdk_abi'], result['minimum_leases_per_run']), (2, 31, 4))
                self.assertEqual(result['image_publications_per_run'], 2)
                self.assertFalse(result['per_thread_credentials'])
                self.assertFalse(result['physical'])
                self.assertEqual(result['entry_stacks']['commands'][1]['reservations'], 4)
                self.assertEqual(result['entry_stacks']['commands'][2]['releases'], 4)
                crlf = [p.replace(b'\n', b'\r\n') for p in fixture(arch)]
                self.assertEqual(validate(crlf, arch)['runs'], 2)

    def test_required_credential_checks_are_explicit_and_nonzero(self):
        required = (b'reversible=1 permanent_child=1 fork=1 failed_exec=1 saved_exec=1 '
                    b'file_permissions=1 failure_atomic=1 thread_gate=2 high_uid=4')
        for arch in ARCHES:
            expected = b'CREDENTIALS_PASS ' + arch.encode() + b' ' + required
            self.assertEqual(evidence.probe_spec(arch, 'credentials')[0], expected)
            good = fixture(arch)
            self.assertEqual(validate(good, arch)['high_unsigned_ids'], 4)
            for index in (2, 3):
                for field in required.split():
                    parts = good.copy()
                    parts[index] = parts[index].replace(field, field.split(b'=')[0] + b'=0')
                    with self.subTest(arch=arch, run=index, field=field), self.assertRaises(ValueError):
                        validate(parts, arch)

    def test_ordered_unique_exec_markers_and_images(self):
        for arch in ARCHES:
            good = fixture(arch)
            marker, _, _, _ = evidence.probe_spec(arch, 'credentials')
            child = evidence.CHILD.replace(b'{arch}', arch.encode())
            image = IMAGE.replace(b'firmware', b'linker') if arch in ('loongarch64', 'mips', 'mips64') else IMAGE
            for index in (2, 3):
                mutations = {
                    'missing-child': good[index].replace(child+b'\n', b''),
                    'missing-parent': good[index].replace(marker+b'\n', b''),
                    'duplicate-child': good[index].replace(child, child+b'\n'+child),
                    'duplicate-parent': good[index].replace(marker, marker+b'\n'+marker),
                    'one-image': good[index].replace(image, b'', 1),
                    'three-images': good[index].replace(image, image+image, 1),
                    'child-before-exec': good[index].replace(image+image+child+b'\n', image+child+b'\n'+image),
                    'parent-before-child': good[index].replace(child+b'\n'+marker, marker+b'\n'+child),
                    'wrong-arch': good[index].replace(child, child.replace(arch.encode(), b'not-an-arch', 1)),
                    'wrong-source': good[index].replace(b'source=linker' if b'source=linker' in image else b'source=firmware', b'source=wrong'),
                    'unexpected-output': good[index].replace(child, b'injected command\n'+child),
                    'incomplete-line': good[index].replace(marker+b'\n', marker),
                }
                for label, changed in mutations.items():
                    parts = good.copy(); parts[index] = changed
                    with self.subTest(arch=arch, run=index, attack=label), self.assertRaises(ValueError): validate(parts, arch)
            for index in (0, 1, 4):
                parts=good.copy();parts[index]=child+b'\n'+parts[index]
                with self.subTest(arch=arch, outside=index), self.assertRaises(ValueError): validate(parts, arch)

    def test_lease_frame_fault_and_failure_controls(self):
        for arch in ARCHES:
            good=fixture(arch)
            for index in (2,3):
                mutations={
                    'short-lease': good[index].replace(b'reservations=14 releases=12', b'reservations=13 releases=11') if index==2 else good[index].replace(b'reservations=18 releases=16', b'reservations=17 releases=15'),
                    'fault': good[index].replace(b'faults=0', b'faults=1').replace(b'syscalls=300', b'syscalls=299').replace(b'syscalls=400', b'syscalls=399'),
                    'leak': good[index].replace(b'leased=2', b'leased=3'),
                    'quarantine': good[index].replace(b'quarantine=0', b'quarantine=1'),
                    'objects': good[index].replace(b'objects=0', b'objects=1'),
                    'failed': good[index].replace(b'oksh> ', b'CREDENTIALS_FAIL code=17\noksh> '),
                    'failed-drain': good[index].replace(b'oksh> ', b'CREDENTIALS_FAIL code=17'),
                    'contained-fault': good[index].replace(b'oksh> ', b'OK_NATIVE scope=hardware fault=contained\noksh> '),
                }
                for label,changed in mutations.items():
                    parts=good.copy();parts[index]=changed
                    with self.subTest(arch=arch, run=index, attack=label), self.assertRaises(ValueError): validate(parts,arch)
            # Accounting must follow success; all counters still have otherwise valid content.
            parts=good.copy();lines=parts[2].splitlines(keepends=True);marker=next(x for x in lines if x.startswith(b'CREDENTIALS_PASS '));lines.remove(marker);lines.insert(-1,marker);parts[2]=b''.join(lines)
            with self.subTest(arch=arch, attack='late-marker'), self.assertRaises(ValueError):validate(parts,arch)
            parts=good.copy();parts[4]+=b'junk after prompt\n'
            with self.subTest(arch=arch, attack='trailing-junk'), self.assertRaises(ValueError):validate(parts,arch)

    def test_failure_prefix_drains_complete_line(self):
        self.assertIsNone(evidence.failure_line(b'boot\n'))
        self.assertFalse(evidence.incomplete_failure_line(b'boot\n'))
        for suffix in (b'', b' code=', b' code=17', b' code=17\r'):
            serial=b'boot\nCREDENTIALS_FAIL'+suffix
            self.assertTrue(evidence.incomplete_failure_line(serial))
            self.assertIn('saved-ID assertion failed', evidence.failure_line(serial))
        for newline in (b'\n',b'\r\n'):
            serial=b'boot\nCREDENTIALS_FAIL code=17'+newline+b'after'
            self.assertFalse(evidence.incomplete_failure_line(serial))
            self.assertIn('code=17', evidence.failure_line(serial))
            self.assertNotIn('after', evidence.failure_line(serial))

    def test_mismatched_sdk_rejected_even_if_common_validator_accepts(self):
        # Isolates the credential-specific ABI gate. Common SDK internals are purposefully mocked, not claimed tested.
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);compiler=root/'g++';compiler.write_bytes(b'synthetic compiler')
            for abi in (28,29,30,31,32):
                manifest={'files':{},'abi_version':abi,'compiler':{'family':'gcc'}}
                path=root/'manifest.json';path.write_text(json.dumps(manifest))
                digest=hashlib.sha256(path.read_bytes()).hexdigest();cc=hashlib.sha256(compiler.read_bytes()).hexdigest()
                with patch.object(evidence,'validate_sdk',return_value=manifest):
                    if abi==31:self.assertEqual(evidence.admit_sdk(root,digest,'x86_64','debug',compiler,cc)['abi_version'],31)
                    else:
                        with self.assertRaisesRegex(ValueError,'SDK31'):evidence.admit_sdk(root,digest,'x86_64','debug',compiler,cc)
                with self.assertRaises(ValueError):evidence.admit_sdk(root,digest,'x86_64','release',compiler,cc)
                with self.assertRaises(ValueError):evidence.admit_sdk(root,'0'*64,'x86_64','debug',compiler,cc)

if __name__=='__main__':unittest.main()

"""PPC32 collector fixtures are parser tests, never kernel execution evidence."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import native_signal_delivery_x86_64_evidence as evidence
import qualify_native_signal_delivery_x86_64 as qualifier
from test_native_signal_delivery_x86_64 import fixture, validate, IMAGE


KINDS = ('pthread', 'altstack', 'altstack-exec', 'bad-sp')
OTHER_ARCHES = ('i386', 'x86_64', 'aarch64', 'arm32', 'rv32', 'rv64', 'loongarch64', 'mips', 'mips64')


class PpcCommonEvidence(unittest.TestCase):
    def test_two_runs_exact_marker_command_counts_and_leases(self):
        for kind, minimum, image_count in (('pthread', 2, 1), ('altstack', 5, 1),
                                          ('altstack-exec', 6, 2), ('bad-sp', 3, 1)):
            with self.subTest(kind=kind):
                parts = fixture(kind, arch='ppc')
                result = validate(parts, kind, 'ppc')
                self.assertEqual(result['runs'], 2)
                self.assertEqual(result['minimum_leases_per_run'], minimum)
                self.assertEqual(result['entry_stacks']['cpu'], 0)
                self.assertFalse(result['production_signal_support'])
                self.assertFalse(result['entry_stacks']['smp'])
                marker, _, command, _ = evidence.probe_spec('ppc', kind)
                source, rootfs_name, command_line = qualifier.probe_layout('ppc', kind)
                self.assertEqual(command.decode(), command_line)
                self.assertEqual(rootfs_name, command_line.removeprefix('/bin/').split()[0])
                self.assertTrue((Path(__file__).resolve().parents[2] / 'tests/musl' / (source + '.c')).is_file())
                for index in (2, 3):
                    self.assertEqual(parts[index].count(IMAGE), image_count)
                    self.assertEqual(parts[index].count(marker), 1)
                if kind.startswith('altstack'):
                    self.assertEqual(result['successful_exec'], 'passed' if kind.endswith('exec') else 'not-run')

    def test_wrong_architecture_and_unsupported_other_kinds_rejected(self):
        for kind in KINDS:
            parts = fixture(kind, arch='ppc')
            for arch in OTHER_ARCHES:
                with self.subTest(kind=kind, arch=arch), self.assertRaises(ValueError):
                    validate(parts, kind, arch)
            for arch in OTHER_ARCHES:
                with self.subTest(kind=kind, incoming=arch), self.assertRaises(ValueError):
                    validate(fixture(kind, arch=arch), kind, 'ppc')
        for kind in ('raw', 'riscv-raw', 'riscv-map', 'riscv-entry',
                     'mips64-raw', 'mips64-map', 'mips-raw', 'mips-map', 'loongarch-raw',
                     'loongarch-map', 'arm32-raw', 'i386-raw', 'i386-entry'):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                qualifier.probe_layout('ppc', kind)

    def test_missing_duplicate_partial_cross_kind_or_wrong_field(self):
        for kind in KINDS:
            original = fixture(kind, arch='ppc')
            marker, prefix, command, _ = evidence.probe_spec('ppc', kind)
            for index in (2, 3):
                for replacement in (b'', marker + b'\n' + marker, marker[:-1],
                                    marker.replace(b' ppc ', b' mips64 '),
                                    marker.replace(marker.split()[2], marker.split()[2].split(b'=')[0] + b'=0', 1)):
                    parts = original.copy(); parts[index] = parts[index].replace(marker, replacement)
                    with self.subTest(kind=kind, span=index, value=replacement), self.assertRaises(ValueError):
                        validate(parts, kind, 'ppc')
                for wrong in (b'SIGNAL_BAD_SP_FAIL code=103 handler=209',
                              b'ALTSTACK_FAIL code=107 handler=207',
                              b'PTHREAD_SIGNALS_FAIL code=102 bad=1',
                              b'OK_NATIVE signal=deferred reason=unsupported', b'command failed exit=1'):
                    parts = original.copy(); parts[index] = parts[index].replace(marker, wrong)
                    with self.subTest(kind=kind, span=index, wrong=wrong), self.assertRaises(ValueError):
                        validate(parts, kind, 'ppc')
                parts = original.copy(); parts[index] = parts[index].replace(command, b'/bin/wrong-ppc-probe', 1)
                with self.assertRaises(ValueError): validate(parts, kind, 'ppc')

    def test_image_and_check_count_order_and_unique_exec(self):
        for kind in KINDS:
            original = fixture(kind, arch='ppc')
            for index in (2, 3):
                for replacement in (b'', IMAGE + IMAGE, IMAGE.replace(b'firmware', b'linker')):
                    parts = original.copy(); parts[index] = parts[index].replace(IMAGE, replacement, 1)
                    with self.subTest(kind=kind, span=index, image=replacement), self.assertRaises(ValueError):
                        validate(parts, kind, 'ppc')
                if kind in evidence.PPC_CHECK_COUNTS:
                    count = (b'SIGNAL_BAD_SP_CHECKS count=' if kind=='bad-sp' else b'ALTSTACK_CHECKS count=') + evidence.PPC_CHECK_COUNTS[kind]
                    for replacement in (b'', count+b'\n'+count, count[:-1]+b'0'):
                        parts = original.copy(); parts[index] = parts[index].replace(count, replacement)
                        with self.assertRaises(ValueError): validate(parts, kind, 'ppc')
            if kind == 'altstack-exec':
                child = evidence.ALTSTACK_EXEC.replace(b'x86_64', b'ppc')
                for index in (2, 3):
                    for replacement in (b'', child+b'\n'+child, child.replace(b'autodisarm_disabled', b'disabled')):
                        parts = original.copy(); parts[index] = parts[index].replace(child, replacement)
                        with self.assertRaises(ValueError): validate(parts, kind, 'ppc')
                    parts = original.copy(); parts[index] = parts[index].replace(IMAGE+child, child+b'\n'+IMAGE.rstrip(b'\n'))
                    with self.assertRaises(ValueError): validate(parts, kind, 'ppc')

    def test_dynamic_boundaries_and_success_outside_commands(self):
        for kind in KINDS:
            original = fixture(kind, arch='ppc')
            original[0] = b'variable boot diagnostic\n' + original[0]
            self.assertEqual(validate(original, kind, 'ppc')['runs'], 2)
            marker = evidence.probe_spec('ppc', kind)[0]
            for index in (0, 1, 4):
                parts = original.copy(); parts[index] = marker+b'\n'+parts[index]
                with self.assertRaises(ValueError): validate(parts, kind, 'ppc')
            bounds = [sum(map(len, original[:i])) for i in range(1, 5)]
            for index in range(4):
                broken = bounds.copy(); broken[index] -= 1
                with self.assertRaises(ValueError):
                    evidence.validate_execution(b''.join(original), *broken, bounds[-1], 'ppc', kind)
            parts = original.copy(); parts[3] = b'oksh> '
            with self.assertRaises(ValueError): validate(parts, kind, 'ppc')

    def test_fault_and_retirement_accounting_not_just_markers(self):
        for kind in KINDS:
            original = fixture(kind, arch='ppc')
            for index in (2, 3):
                for old, new in ((b'cpu=0', b'cpu=1'), (b'smp=0', b'smp=1'),
                                 (b'active=0', b'active=1'), (b'quarantine=0', b'quarantine=1'),
                                 (b'objects=0', b'objects=1'), (b'faults=0', b'faults=1'),
                                 (b'leased=2', b'leased=3'), (b'capacity=128', b'capacity=64')):
                    parts = original.copy(); parts[index] = parts[index].replace(old, new)
                    with self.subTest(kind=kind, span=index, old=old), self.assertRaises(ValueError):
                        validate(parts, kind, 'ppc')
                for prefix in (b'OK_NATIVE_FRAMES ', b'OK_ENTRY_STACKS '):
                    parts = original.copy();parts[index] = b'\n'.join(line for line in parts[index].split(b'\n') if not line.startswith(prefix))
                    with self.assertRaises(ValueError): validate(parts, kind, 'ppc')
            minimum = evidence.probe_spec('ppc', kind)[3]
            with self.assertRaises(ValueError): validate(fixture(kind, leases=minimum-1, arch='ppc'), kind, 'ppc')

    def test_failure_fragments_preserve_complete_diagnostic(self):
        for prefix in (b'PTHREAD_SIGNALS_FAIL', b'ALTSTACK_FAIL', b'SIGNAL_BAD_SP_FAIL'):
            line = prefix + b' code=107 handler=207 errno=-22\r\n'
            for split in range(1, len(line)):
                serial = b'prior output\n' + line[:split]
                if split >= len(prefix):
                    self.assertIsNotNone(evidence.failure_line(serial))
                    self.assertTrue(evidence.incomplete_failure_line(serial))
                serial += line[split:]
                self.assertFalse(evidence.incomplete_failure_line(serial))
                self.assertIsNotNone(evidence.failure_line(serial))
                self.assertTrue(serial.endswith(line))
                parts = fixture('pthread', arch='ppc'); parts[2] = serial + parts[2]
                with self.assertRaises(ValueError): validate(parts, 'pthread', 'ppc')

    def test_sdk_debug_only_and_n64_options_unchanged(self):
        manifest = {'abi_version': 31, 'compiler': {'family': 'gcc'}}
        with patch.object(evidence, 'admit_common_sdk', return_value=manifest) as admit:
            self.assertEqual(evidence.admit_sdk(None, None, 'ppc', 'debug', None, None), manifest)
            with self.assertRaises(ValueError): evidence.admit_sdk(None, None, 'ppc', 'release', None, None)
            self.assertEqual(admit.call_count, 1)
        qualifier.validate_runtime_options('ppc', None, None)
        qualifier.validate_runtime_options('mips64', Path('/explicit/runtime'), '1'*64)
        for arch, runtime, digest in (('ppc', Path('/runtime'), '1'*64),
                                       ('mips64', None, None), ('mips64', Path('/runtime'), None)):
            with self.assertRaises(ValueError): qualifier.validate_runtime_options(arch, runtime, digest)

    def test_private_qemu_cpu_and_recipe_rejection(self):
        qemu, image, disk = Path('/explicit/qemu-system-ppc'), Path('/explicit/kernel-input.bin'), Path('/explicit/rootfs.ext4.img')
        command = qualifier.delivery_qemu_command(qemu, 'ppc', image, disk)
        self.assertEqual(command[-6:], ['-cpu', 'e500v2_v22', '-smp', '1', '-accel', 'tcg,thread=single'])
        self.assertEqual(command.count('-cpu'), 1)
        self.assertEqual(command.count('-smp'), 1)
        original = qualifier.command_for(qemu, 'ppc', image, disk, 'none')
        for wrong in (original+['-cpu','e500mc'], original+['-smp','2'],
                      [x.replace('ppce500','malta') for x in original],
                      [x.replace(str(disk),'/wrong/disk') for x in original]):
            with patch.object(qualifier, 'command_for', return_value=wrong), self.assertRaises(ValueError):
                qualifier.delivery_qemu_command(qemu, 'ppc', image, disk)
        for arch in OTHER_ARCHES:
            self.assertEqual(qualifier.delivery_qemu_command(qemu, arch, image, disk),
                             qualifier.command_for(qemu, arch, image, disk, 'none'))


if __name__ == '__main__':
    unittest.main()

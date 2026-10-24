"""PPC aggregate collector parser controls; these never execute guest code."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import native_signal_delivery_x86_64_evidence as evidence
import qualify_native_signal_delivery_x86_64 as qualifier
from test_native_signal_delivery_x86_64 import ppc_fixture, validate, IMAGE

KINDS = ('ppc-raw', 'ppc-map')
OTHER_ARCHES = ('i386', 'x86_64', 'aarch64', 'arm32', 'rv32', 'rv64', 'loongarch64', 'mips', 'mips64')
CHILD = b'SIGNAL_MAP_EXEC_CHILD_PASS ppc fresh=1 restorer=1'
COUNT = b'SIGNAL_MAP_CHECKS count=26'
FAULT = evidence.CONTAINED_FAULT


class PpcRawMappingEvidence(unittest.TestCase):
    def rejected(self, parts, kind):
        with self.assertRaises(ValueError):
            validate(parts, kind, 'ppc')

    def test_exact_aggregate_contracts_and_source_layout(self):
        for kind, leases, images in (('ppc-raw', 25, 1), ('ppc-map', 3, 2)):
            with self.subTest(kind=kind):
                parts = ppc_fixture(kind)
                result = validate(parts, kind, 'ppc')
                self.assertEqual(result['runs'], 2)
                self.assertEqual(result['minimum_leases_per_run'], leases)
                self.assertEqual(result['image_publications_per_run'], images)
                self.assertTrue(result['experimental'])
                self.assertFalse(result['production_signal_support'])
                self.assertFalse(result['entry_stacks']['smp'])
                self.assertEqual(result['entry_stacks']['cpu'], 0)
                marker, _, command, _ = evidence.probe_spec('ppc', kind)
                source, installed, invocation = qualifier.probe_layout('ppc', kind)
                self.assertEqual(invocation, command.decode())
                self.assertEqual('/bin/' + installed, invocation)
                self.assertTrue((Path(__file__).resolve().parents[2] / 'tests/musl' / (source + '.c')).is_file())
                for span in (2, 3):
                    self.assertEqual(parts[span].count(marker), 1)
                    self.assertEqual(parts[span].count(IMAGE), images)
                if kind == 'ppc-raw':
                    self.assertEqual(result['handlers'], 22)
                    self.assertEqual(result['state_cases'], 10)
                    self.assertEqual(result['fatal_children'], 24)
                    self.assertEqual(result['corrupt_return_children'], 23)
                    self.assertEqual(result['highest_signal_children'], 1)
                    for unsupported in ('fp', 'edited_fp', 'fcsr', 'sigfpe_before_resume', 'coalescing', 'resethand', 'alternate_stack'):
                        self.assertNotIn(unsupported, result)
                    for supported in ('legacy', 'realtime', 'nesting', 'nodefer_nesting', 'states', 'relocated_context', 'full_spe', 'masks', 'fatal_return', 'restorer_ignored'):
                        self.assertEqual(result[supported], 'passed')
                else:
                    self.assertFalse(result['rt_only'])
                    self.assertEqual(result['check_count'], 26)
                    self.assertEqual(result['entry_stacks']['first']['faults'], 1)
                    self.assertEqual(result['entry_stacks']['second']['faults'], 2)

    def test_every_aggregate_field_is_required_and_exact(self):
        for kind in KINDS:
            original = ppc_fixture(kind)
            marker = evidence.probe_spec('ppc', kind)[0]
            for span in (2, 3):
                for field in marker.split()[2:]:
                    key, value = field.split(b'=')
                    wrong = key + b'=' + str(int(value) + 1).encode()
                    parts = original.copy(); parts[span] = parts[span].replace(field, wrong, 1)
                    with self.subTest(kind=kind, span=span, field=field):
                        self.rejected(parts, kind)
                for replacement in (b'', marker+b'\n'+marker, marker[:-1], marker+b' extra=1',
                                    marker.replace(b' ppc ', b' mips64 ')):
                    parts = original.copy(); parts[span] = parts[span].replace(marker, replacement)
                    with self.subTest(kind=kind, span=span, replacement=replacement):
                        self.rejected(parts, kind)

    def test_single_case_spoof_failure_and_extra_output_never_aggregate(self):
        for kind in KINDS:
            original = ppc_fixture(kind)
            marker = evidence.probe_spec('ppc', kind)[0]
            for span in (2, 3):
                for wrong in (b'SIGNAL_PPC_CASE_PASS core0', b'SIGNAL_PPC_CASE_PASS highest',
                              b'SIGNAL_PPC_DIAGNOSTIC_PASS', b'SIGNAL_PPC_FAIL code=299 mode=10 rt=1',
                              b'SIGNAL_MAP_FAIL code=113 checks=14 calls=1 bad=0',
                              b'command failed exit=1', b'OK_NATIVE signal=deferred reason=unsupported'):
                    for replacement in (wrong, wrong+b'\n'+marker, marker+b'\n'+wrong):
                        parts = original.copy(); parts[span] = parts[span].replace(marker, replacement)
                        with self.subTest(kind=kind, span=span, wrong=wrong):
                            self.rejected(parts, kind)

    def test_failure_fragments_are_drained_and_never_accepted(self):
        for prefix in (b'SIGNAL_PPC_FAIL', b'SIGNAL_MAP_FAIL'):
            line = prefix + b' code=219 mode=12 rt=1\r\n'
            for split in range(len(prefix), len(line)):
                partial = b'prior diagnostic\n' + line[:split]
                self.assertTrue(evidence.incomplete_failure_line(partial))
                self.assertIsNotNone(evidence.failure_line(partial))
                self.assertFalse(evidence.incomplete_failure_line(partial + line[split:]))
                for kind in KINDS:
                    parts = ppc_fixture(kind)
                    parts[2] = parts[2].replace(b'oksh> ', line[:split]+b'oksh> ')
                    self.rejected(parts, kind)
            self.assertIn('PPC32', evidence.failure_line(b'SIGNAL_PPC_FAIL code=219\n'))

    def test_mapping_exec_fault_and_count_order_is_exact(self):
        original = ppc_fixture('ppc-map')
        marker = evidence.PPC_MAP_MARKER
        sequence = FAULT+b'\n'+IMAGE+CHILD+b'\n'+marker+b'\n'+COUNT
        wrong_sequences = (
            IMAGE+CHILD+b'\n'+marker+b'\n'+COUNT,
            FAULT+b'\n'+FAULT+b'\n'+IMAGE+CHILD+b'\n'+marker+b'\n'+COUNT,
            IMAGE+FAULT+b'\n'+CHILD+b'\n'+marker+b'\n'+COUNT,
            FAULT+b'\n'+CHILD+b'\n'+IMAGE+marker+b'\n'+COUNT,
            FAULT+b'\n'+IMAGE+marker+b'\n'+CHILD+b'\n'+COUNT,
            FAULT+b'\n'+IMAGE+CHILD+b'\n'+COUNT+b'\n'+marker,
        )
        for span in (2, 3):
            self.assertIn(sequence, original[span])
            for replacement in wrong_sequences:
                parts = original.copy(); parts[span] = parts[span].replace(sequence, replacement)
                self.rejected(parts, 'ppc-map')
            for record in (CHILD, COUNT):
                for replacement in (b'', record+b'\n'+record, record[:-1], record.replace(b'26', b'25')):
                    if replacement == record:
                        continue
                    parts = original.copy(); parts[span] = parts[span].replace(record, replacement)
                    self.rejected(parts, 'ppc-map')
            for old, new in ((b'faults=1', b'faults=0'), (b'faults=2', b'faults=1')):
                if old in original[span]:
                    parts = original.copy(); parts[span] = parts[span].replace(old, new)
                    self.rejected(parts, 'ppc-map')

    def test_image_provenance_count_and_placement(self):
        for kind in KINDS:
            original = ppc_fixture(kind)
            marker = evidence.probe_spec('ppc', kind)[0]
            for span in (2, 3):
                for position in range(original[span].count(IMAGE)):
                    start = original[span].find(IMAGE)
                    if position:
                        start = original[span].find(IMAGE, start+len(IMAGE))
                    for replacement in (b'', IMAGE+IMAGE, IMAGE.replace(b'firmware', b'linker')):
                        parts = original.copy()
                        parts[span] = parts[span][:start]+replacement+parts[span][start+len(IMAGE):]
                        self.rejected(parts, kind)
                parts = original.copy(); parts[span] = parts[span].replace(IMAGE, b'', 1).replace(marker, marker+b'\n'+IMAGE.rstrip())
                self.rejected(parts, kind)

    def test_boundaries_missing_second_run_and_outside_success(self):
        for kind in KINDS:
            original = ppc_fixture(kind)
            original[0] = b'arbitrary earlier boot bytes\n'+original[0]
            self.assertEqual(validate(original, kind, 'ppc')['runs'], 2)
            marker, _, command, _ = evidence.probe_spec('ppc', kind)
            outside_records = (marker, b'SIGNAL_PPC_CASE_PASS highest')
            if kind == 'ppc-map':
                outside_records += (CHILD, COUNT)
            for index in (0, 1, 4):
                for extra in outside_records:
                    parts = original.copy(); parts[index] = extra+b'\n'+parts[index]
                    self.rejected(parts, kind)
            for index in (2, 3):
                parts = original.copy(); parts[index] = b'oksh> '
                self.rejected(parts, kind)
                parts = original.copy(); parts[index] = parts[index].replace(command, command+b' highest', 1)
                self.rejected(parts, kind)
            bounds = [sum(map(len, original[:i])) for i in range(1, 5)]
            for index in range(4):
                wrong = bounds.copy(); wrong[index] -= 1
                with self.assertRaises(ValueError):
                    evidence.validate_execution(b''.join(original), *wrong, bounds[-1], 'ppc', kind)

    def test_fresh_leases_retirement_and_serialized_cpu(self):
        for kind in KINDS:
            minimum = evidence.probe_spec('ppc', kind)[3]
            self.rejected(ppc_fixture(kind, leases=minimum-1), kind)
            original = ppc_fixture(kind)
            for span in (2, 3):
                for old, new in ((b'cpu=0', b'cpu=1'), (b'smp=0', b'smp=1'),
                                 (b'active=0', b'active=1'), (b'quarantine=0', b'quarantine=1'),
                                 (b'objects=0', b'objects=1'), (b'leased=2', b'leased=3'),
                                 (b'capacity=128', b'capacity=64')):
                    parts = original.copy(); parts[span] = parts[span].replace(old, new)
                    self.rejected(parts, kind)
                for prefix in (b'OK_NATIVE_FRAMES ', b'OK_ENTRY_STACKS '):
                    parts = original.copy()
                    parts[span] = b'\n'.join(line for line in parts[span].split(b'\n') if not line.startswith(prefix))
                    self.rejected(parts, kind)
            if kind == 'ppc-raw':
                for span in (2, 3):
                    parts = original.copy(); parts[span] = parts[span].replace(evidence.PPC_RAW_MARKER, FAULT+b'\n'+evidence.PPC_RAW_MARKER)
                    self.rejected(parts, kind)

    def test_wrong_profiles_cross_kind_and_no_generic_ppc_raw(self):
        for kind in KINDS:
            original = ppc_fixture(kind)
            for arch in OTHER_ARCHES:
                with self.assertRaises(ValueError): qualifier.probe_layout(arch, kind)
                with self.assertRaises(ValueError): validate(original, kind, arch)
            for wrong_kind in ('raw', 'pthread', 'altstack', 'bad-sp', *KINDS):
                if wrong_kind != kind:
                    self.rejected(original, wrong_kind)

    def test_cli_choices_accept_distinct_kinds_and_keep_n64_contract(self):
        required = ['run', '--arch', 'ppc', '--mode', 'debug']
        for name in ('kernel-sdk', 'toolchain', 'qemu', 'musl-build', 'source-inventory', 'output'):
            required += ['--'+name, '/explicit/'+name]
        for name in ('sdk-manifest-sha256', 'compiler-sha256', 'qemu-sha256', 'musl-manifest-sha256', 'source-inventory-sha256'):
            required += ['--'+name, '1'*64]
        for kind in KINDS:
            with patch.object(sys, 'argv', ['qualifier', *required, '--probe', kind]), patch.object(qualifier, 'run') as run:
                qualifier.main()
                self.assertEqual(run.call_args.args[0].probe, kind)
            qualifier.validate_runtime_options('ppc', None, None)
            with self.assertRaises(ValueError): qualifier.validate_runtime_options('ppc', Path('/runtime'), '1'*64)
        qualifier.validate_runtime_options('mips64', Path('/runtime'), '1'*64)
        with self.assertRaises(ValueError): qualifier.validate_runtime_options('mips64', None, None)


if __name__ == '__main__':
    unittest.main()

"""Synthetic fixture admission controls; these do not execute signal handlers."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import native_signal_delivery_x86_64_evidence as evidence

IMAGE = b'OK_NATIVE_IMAGE personality=linux source=firmware pages=37 physical_first=0x0000000002988000 physical_last=0x00000000029ac000 owner=retained\n'


def stacks(reservations, releases, activations, *, peak=4):
    return (f'OK_ENTRY_STACKS version=1 scope=actual-user cpu=0 capacity=128 usable_bytes=65536 '
            f'backing_bytes=9437184 leased={reservations-releases} active=0 quarantine=0 peak={peak} '
            f'reservations={reservations} releases={releases} activations={activations} syscalls={activations} '
            'timers=0 faults=0 rejected=0 guards=mapped-canaries smp=0\n').encode()


def frames(allocations, releases):
    used = allocations-releases
    return (f'OK_NATIVE_FRAMES version=2 source=firmware used={used} total=1024 allocations={allocations} '
            f'releases={releases} pinned=0 user={used} objects=0 free={1024-used} pending=0 reserve=10 '
            'user_limit=1014\n').encode()


def fixture(kind='raw', leases=None, arch='x86_64'):
    marker, _, command, minimum = evidence.PROBES[kind]
    marker = marker.replace(b'x86_64', arch.encode())
    command = command.replace(b'x86-64', b'la64' if arch == 'loongarch64' else arch.replace('_', '-').encode())
    n = minimum if leases is None else leases
    success = marker + b'\n'
    if kind == 'bad-sp':
        success += b'SIGNAL_BAD_SP_CHECKS count=18\n'
    if kind.startswith('altstack'):
        success += b'ALTSTACK_CHECKS count=' + (b'37' if kind == 'altstack-exec' else b'35') + b'\n'
        if kind == 'altstack-exec':
            success = IMAGE + evidence.ALTSTACK_EXEC.replace(b'x86_64', arch.encode()) + b'\n' + success
    success = IMAGE + success
    parts = [
        b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n' +
        frames(0, 0) + stacks(0, 0, 0, peak=0) + frames(40, 0) + stacks(7, 5, 100) + b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n' + frames(100, 60) + stacks(10, 8, 200) + b'oksh> ',
        command + b'\n' + success + frames(200, 160) + stacks(10+n, 8+n, 300) + b'oksh> ',
        command + b'\n' + success + frames(300, 260) + stacks(10+2*n, 8+2*n, 400) + b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n' + frames(400, 360) + stacks(12+2*n, 10+2*n, 500) + b'oksh> ',
    ]
    return [part.replace(b'source=firmware', b'source=linker') for part in parts] if arch in ('loongarch64', 'mips', 'mips64') else parts


def validate(parts, kind='raw', arch='x86_64'):
    boundaries = [sum(map(len, parts[:i])) for i in range(1, 5)]
    return evidence.validate_execution(b''.join(parts), *boundaries, boundaries[-1], arch, kind)


def ppc_fixture(kind, leases=None):
    marker, _, command, minimum = evidence.probe_spec('ppc', kind)
    parts = fixture('pthread', leases=minimum if leases is None else leases, arch='ppc')
    output = marker
    if kind == 'ppc-map':
        output = (evidence.CONTAINED_FAULT + b'\n' + IMAGE +
                  evidence.MAP_EXEC.replace(b'x86_64', b'ppc') + b'\n' + marker +
                  b'\nSIGNAL_MAP_CHECKS count=26')
    for index in (2, 3):
        parts[index] = parts[index].replace(evidence.PTHREAD_MARKER.replace(b'x86_64', b'ppc'), output)
        parts[index] = parts[index].replace(b'native-pthread-signals-ppc', command)
    if kind == 'ppc-map':
        for index, faults in ((2, 1), (3, 2), (4, 2)):
            parts[index] = parts[index].replace(b'faults=0', f'faults={faults}'.encode())
            parts[index] = parts[index].replace(f'syscalls={(index+1)*100}'.encode(),
                                                f'syscalls={(index+1)*100-faults}'.encode())
    return parts


def riscv_fixture(kind, arch='rv64'):
    marker, _, command, leases = evidence.probe_spec(arch, kind)
    marker = marker.replace(b'x86_64', arch.encode())
    command = command.replace(b'x86-64', arch.encode())
    parts = fixture('pthread', leases=leases, arch=arch)
    old_marker = evidence.PTHREAD_MARKER.replace(b'x86_64', arch.encode())
    old_command = evidence.PROBES['pthread'][2].replace(b'x86-64', arch.encode())
    output = marker
    if kind == 'riscv-map':
        output = (evidence.CONTAINED_FAULT + b'\n' + IMAGE +
                  evidence.MAP_EXEC.replace(b'x86_64', arch.encode()) + b'\n' + marker +
                  b'\nSIGNAL_MAP_CHECKS count=25')
    for index in (2, 3):
        parts[index] = parts[index].replace(old_marker, output).replace(old_command, command)
    if kind == 'riscv-map':
        for index, faults in ((2, 1), (3, 2), (4, 2)):
            parts[index] = parts[index].replace(b'faults=0', f'faults={faults}'.encode())
            parts[index] = parts[index].replace(f'syscalls={(index+1)*100}'.encode(),
                                                f'syscalls={(index+1)*100-faults}'.encode())
    return parts




def loongarch_raw_fixture():
    parts = fixture('pthread', leases=7, arch='loongarch64')
    for index in (2, 3):
        parts[index] = parts[index].replace(evidence.PTHREAD_MARKER.replace(b'x86_64', b'loongarch64'), evidence.LOONGARCH64_MARKER).replace(b'native-pthread-signals-la64', b'native-signal-delivery-la64')
    return parts


class LoongarchRawEvidence(unittest.TestCase):
    def test_exact_raw_signal_execution_and_controls(self):
        original = loongarch_raw_fixture()
        result = validate(original, 'loongarch-raw', 'loongarch64')
        self.assertEqual(result['minimum_leases_per_run'], 7)
        self.assertEqual(result['fcsr_writeback'], 'passed')
        for index in (2, 3):
            for field in (b'handlers=20', b'edited_fp=2', b'f32=1', b'fcc8=1', b'pending_fcsr=2',
                          b'fcsr_writeback=2', b'sigfpe_before_resume=2', b'si_kernel=1',
                          b'forced_default=2', b'preserved_payload=1'):
                broken = original.copy(); broken[index] = broken[index].replace(field, field.split(b'=')[0]+b'=0')
                with self.subTest(index=index, field=field), self.assertRaises(ValueError):
                    validate(broken, 'loongarch-raw', 'loongarch64')
            broken = original.copy(); broken[index] = broken[index].replace(evidence.LOONGARCH64_MARKER, b'SIGNAL_LOONGARCH64_FAIL code=122 handler=00 mode=20')
            with self.assertRaises(ValueError): validate(broken, 'loongarch-raw', 'loongarch64')
        for kind in ('pthread', 'loongarch-map', 'riscv-raw'):
            with self.assertRaises(ValueError): validate(original, kind, 'loongarch64')


def loongarch_mapping_fixture():
    parts = fixture('pthread', leases=3, arch='loongarch64')
    image = IMAGE.replace(b'source=firmware', b'source=linker')
    old_marker = evidence.PTHREAD_MARKER.replace(b'x86_64', b'loongarch64')
    output = (evidence.CONTAINED_FAULT + b'\n' + image +
        evidence.MAP_EXEC.replace(b'x86_64', b'loongarch64') + b'\n' +
        evidence.MAP_MARKER.replace(b'x86_64', b'loongarch64') + b'\nSIGNAL_MAP_CHECKS count=25')
    for index in (2, 3):
        parts[index] = parts[index].replace(old_marker, output).replace(b'native-pthread-signals-la64', b'/bin/native-signal-mapping-la64')
    for index, faults in ((2, 1), (3, 2), (4, 2)):
        parts[index] = parts[index].replace(b'faults=0', f'faults={faults}'.encode())
        parts[index] = parts[index].replace(f'syscalls={(index+1)*100}'.encode(), f'syscalls={(index+1)*100-faults}'.encode())
    return parts


class LoongarchMappingEvidence(unittest.TestCase):
    def test_exact_mapping_execution_and_controls(self):
        original = loongarch_mapping_fixture()
        self.assertEqual(validate(original, 'loongarch-map', 'loongarch64')['protected'], 'passed')
        for index in (2, 3):
            for old, new in ((b'SIGNAL_MAP_CHECKS count=25', b'SIGNAL_MAP_CHECKS count=24'),
                             (evidence.CONTAINED_FAULT+b'\n', b''),
                             (b'SIGNAL_MAP_EXEC_CHILD_PASS', b'SIGNAL_MAP_EXEC_CHILD_FAIL'),
                             (b'/bin/native-signal-mapping-la64', b'/bin/native-signal-mapping-loongarch64'),
                             (b'faults=', b'invalid=')):
                parts = original.copy(); parts[index] = parts[index].replace(old, new)
                with self.subTest(index=index, old=old), self.assertRaises(ValueError):
                    validate(parts, 'loongarch-map', 'loongarch64')
        for kind in ('pthread', 'riscv-map'):
            with self.assertRaises(ValueError): validate(original, kind, 'loongarch64')




def mips_raw_fixture():
    parts = fixture('pthread', leases=12, arch='mips')
    for index in (2, 3):
        parts[index] = parts[index].replace(evidence.PTHREAD_MARKER.replace(b'x86_64', b'mips'), evidence.MIPS_MARKER).replace(b'native-pthread-signals-mips', b'native-signal-mips')
    return parts


class MipsRawEvidence(unittest.TestCase):
    def test_exact_raw_signal_marker_and_failed_controls(self):
        original = mips_raw_fixture()
        result = validate(original, 'mips-raw', 'mips')
        self.assertEqual(result['minimum_leases_per_run'], 12)
        for key in ('gpr', 'fpr16', 'hilo', 'fcsr', 'tls', 'highest_fatal', 'fcsr_writeback'):
            self.assertEqual(result[key], 'passed')
        for span in (2, 3):
            for field in evidence.MIPS_MARKER.split()[2:]:
                changed = original.copy();changed[span] = changed[span].replace(field, field.split(b'=')[0]+b'=0')
                with self.subTest(span=span, field=field), self.assertRaises(ValueError):
                    validate(changed, 'mips-raw', 'mips')
            for wrong in (b'SIGNAL_MIPS_FAIL code=102 handler=08 mode=00 rt=0',
                          b'SIGNAL_MIPS_DIAGNOSTIC_PASS', b'SIGNAL_MIPS_CASE_PASS core0'):
                changed=original.copy();changed[span]=changed[span].replace(evidence.MIPS_MARKER, wrong)
                with self.assertRaises(ValueError): validate(changed, 'mips-raw', 'mips')
        for kind in ('pthread', 'raw', 'riscv-raw', 'mips-map'):
            with self.assertRaises(ValueError): validate(original, kind, 'mips')
        for arch in ('x86_64', 'mips64', 'ppc', 'loongarch64'):
            with self.assertRaises(ValueError): validate(original, 'mips-raw', arch)


def mips_mapping_fixture():
    return [part.replace(b'loongarch64', b'mips').replace(b'la64', b'mips')
            for part in loongarch_mapping_fixture()]


def mips64_raw_fixture(leases=22):
    parts = fixture('pthread', leases=leases, arch='mips64')
    for index in (2, 3):
        parts[index] = parts[index].replace(
            evidence.PTHREAD_MARKER.replace(b'x86_64', b'mips64'), evidence.MIPS64_MARKER
        ).replace(b'native-pthread-signals-mips64', b'/bin/native-signal-mips64')
    return parts


def mips64_mapping_fixture():
    parts = [part.replace(b'mips', b'mips64') for part in mips_mapping_fixture()]
    old = evidence.MAP_MARKER.replace(b'x86_64', b'mips64')
    return [part.replace(old, evidence.MIPS64_MAP_MARKER).replace(
        b'SIGNAL_MAP_CHECKS count=25', b'SIGNAL_MAP_CHECKS count=26') for part in parts]


class MipsMappingEvidence(unittest.TestCase):
    def test_mapping_lifetime_and_strict_command_controls(self):
        original = mips_mapping_fixture()
        result = validate(original, 'mips-map', 'mips')
        self.assertEqual(result['minimum_leases_per_run'], 3)
        self.assertEqual(result['protected'], 'passed')
        for span in (2, 3):
            for old, new in ((b'protected=8', b'protected=7'),
                             (b'SIGNAL_MAP_CHECKS count=25', b'SIGNAL_MAP_CHECKS count=24'),
                             (b'SIGNAL_MAP_EXEC_CHILD_PASS', b'SIGNAL_MAP_EXEC_CHILD_FAIL'),
                             (evidence.CONTAINED_FAULT+b'\n', b''),
                             (b'/bin/native-signal-mapping-mips', b'native-signal-mapping-mips')):
                changed = original.copy(); changed[span] = changed[span].replace(old, new)
                with self.subTest(span=span, old=old), self.assertRaises(ValueError):
                    validate(changed, 'mips-map', 'mips')
        for arch in ('mips64', 'loongarch64', 'rv32', 'rv64', 'x86_64'):
            with self.assertRaises(ValueError): validate(original, 'mips-map', arch)
        for kind in ('pthread', 'loongarch-map', 'riscv-map'):
            with self.assertRaises(ValueError): validate(original, kind, 'mips')

class RiscvSignalEvidence(unittest.TestCase):
    def test_raw_and_mapping_profile_specific_acceptance(self):
        for arch in ('rv32', 'rv64'):
            for kind in evidence.RISCV_PROBES:
                parts = riscv_fixture(kind, arch)
                result = validate(parts, kind, arch)
                self.assertEqual(result['runs'], 2)
                self.assertEqual(result['minimum_leases_per_run'], 5 if kind == 'riscv-entry' else 3)
                if kind == 'riscv-raw': self.assertEqual(result['tp'], 'passed')
                elif kind == 'riscv-map': self.assertEqual(result['protected'], 'passed')
                else: self.assertEqual(result['frame_boundary'], 'passed')
                for other in ('x86_64', 'aarch64', 'rv64' if arch == 'rv32' else 'rv32'):
                    with self.assertRaises(ValueError): validate(parts, kind, other)
                for other in ('pthread', 'riscv-map' if kind == 'riscv-raw' else 'riscv-raw'):
                    with self.assertRaises(ValueError): validate(parts, other, arch)
                for index in (2, 3):
                    broken = parts.copy(); broken[index] = broken[index].replace(IMAGE, b'', 1)
                    with self.assertRaises(ValueError): validate(broken, kind, arch)

    def test_no_unreported_faults_for_any_probe(self):
        for arch in ('rv32', 'rv64', 'x86_64', 'aarch64'):
            kinds = ('riscv-entry', 'riscv-raw', 'pthread') if arch.startswith('rv') else ('raw', 'pthread')
            for kind in kinds:
                for start in (1, 2, 3, 4):
                    parts = riscv_fixture(kind, arch) if kind.startswith('riscv') else fixture(kind, arch=arch)
                    for index in range(start, 5):
                        parts[index] = parts[index].replace(b'faults=0', b'faults=1')
                        old = (index+1)*100
                        parts[index] = parts[index].replace(f'activations={old}'.encode(), f'activations={old+1}'.encode())
                    with self.subTest(arch=arch,kind=kind,start=start), self.assertRaises(ValueError):
                        validate(parts, kind, arch)

    def test_mapping_exec_checks_and_fault_order(self):
        for arch in ('rv32', 'rv64'):
            marker = evidence.MAP_MARKER.replace(b'x86_64', arch.encode())+b'\n'
            child = evidence.MAP_EXEC.replace(b'x86_64', arch.encode())+b'\n'
            fault = evidence.CONTAINED_FAULT+b'\n'
            count = b'SIGNAL_MAP_CHECKS count=25\n'
            for index in (2, 3):
                for item in (marker, child, fault, count):
                    for replacement in (b'', item+item, item.replace(b'PASS', b'FAIL').replace(b'25',b'24').replace(b'contained',b'unknown')):
                        parts = riscv_fixture('riscv-map', arch)
                        if replacement == item: continue
                        parts[index] = parts[index].replace(item, replacement)
                        with self.assertRaises(ValueError): validate(parts, 'riscv-map', arch)
                for item in (child, fault, IMAGE):
                    parts = riscv_fixture('riscv-map', arch)
                    parts[index] = parts[index].replace(item, b'', 1).replace(marker, marker+item)
                    with self.assertRaises(ValueError): validate(parts, 'riscv-map', arch)
                parts = riscv_fixture('riscv-map', arch)
                parts[index] = parts[index].replace(count,b'').replace(marker,count+marker)
                with self.assertRaises(ValueError): validate(parts,'riscv-map',arch)
            for index in (0,1,4):
                for item in (child,count):
                    parts = riscv_fixture('riscv-map', arch); parts[index]=item+parts[index]
                    with self.assertRaises(ValueError): validate(parts,'riscv-map',arch)


class SignalDeliveryEvidence(unittest.TestCase):
    def test_i386_altstack_and_bad_sp_admission(self):
        for kind in ('altstack', 'altstack-exec', 'bad-sp'):
            parts = fixture(kind, arch='i386')
            self.assertEqual(validate(parts, kind, 'i386')['runs'], 2)
            for other in ('x86_64', 'aarch64', 'rv32', 'rv64'):
                with self.assertRaises(ValueError): validate(parts, kind, other)
            for index in (2, 3):
                broken = parts.copy(); broken[index] = broken[index].replace(IMAGE, b'', 1)
                with self.assertRaises(ValueError): validate(broken, kind, 'i386')

    def test_i386_legacy_rt_and_pthread_admission(self):
        for kind in ('i386-raw', 'i386-entry', 'pthread'):
            parts = riscv_fixture(kind, 'i386')
            result = validate(parts, kind, 'i386')
            self.assertEqual(result['runs'], 2)
            self.assertEqual(result['minimum_leases_per_run'], 5 if kind == 'i386-raw' else 9 if kind == 'i386-entry' else 2)
            if kind == 'i386-raw':
                self.assertEqual(result['legacy'], 'passed')
                self.assertEqual(result['edited_fp'], 'passed')
            marker, _, _, _ = evidence.probe_spec('i386', kind)
            marker = marker.replace(b'x86_64', b'i386')
            for index in (2, 3):
                for item in (marker, IMAGE):
                    for replacement in (b'', item+item, item[:-1]):
                        broken = parts.copy(); broken[index] = broken[index].replace(item, replacement)
                        with self.assertRaises(ValueError): validate(broken, kind, 'i386')
            for start in (1, 2, 3, 4):
                broken = parts.copy()
                for index in range(start, 5):
                    broken[index] = broken[index].replace(b'faults=0', b'faults=1')
                    old = (index+1)*100
                    broken[index] = broken[index].replace(f'activations={old}'.encode(), f'activations={old+1}'.encode())
                with self.assertRaises(ValueError): validate(broken, kind, 'i386')
            for arch in ('x86_64', 'aarch64', 'rv32', 'rv64', 'arm32', 'mips', 'mips64', 'ppc', 'loongarch64'):
                with self.assertRaises(ValueError): validate(parts, kind, arch)
            for index in range(5):
                broken = parts.copy(); broken[index] = b'SIGNAL_I386_FAIL code=102\n'+broken[index]
                with self.assertRaises(ValueError): validate(broken, kind, 'i386')

    def test_explicit_probe_kinds(self):
        for kind in evidence.PROBES:
            with self.subTest(kind=kind):
                result = validate(fixture(kind), kind)
                self.assertEqual(result['runs'], 2)
                self.assertEqual(result['kind'], kind)
                self.assertTrue(result['experimental'])
                self.assertFalse(result['production_signal_support'])
                self.assertFalse(result['entry_stacks']['smp'])
                self.assertEqual(result['minimum_leases_per_run'], {'raw':3,'pthread':2,'altstack':5,'altstack-exec':6,'bad-sp':3}[kind])

    def test_aarch64_markers_are_profile_specific(self):
        for kind in evidence.PROBES:
            self.assertEqual(validate(fixture(kind, arch='aarch64'), kind, 'aarch64')['runs'], 2)
            with self.assertRaises(ValueError): validate(fixture(kind), kind, 'aarch64')
            with self.assertRaises(ValueError): validate(fixture(kind, arch='aarch64'), kind, 'x86_64')

    def test_riscv_admission_is_probe_specific(self):
        for arch in ('rv32', 'rv64'):
            self.assertEqual(validate(fixture('pthread', arch=arch), 'pthread', arch)['runs'], 2)
            for kind in ('pthread', 'altstack', 'altstack-exec', 'bad-sp'):
                self.assertEqual(validate(fixture(kind, arch=arch), kind, arch)['runs'], 2)
            with self.assertRaises(ValueError): validate(fixture('raw', arch=arch), 'raw', arch)
            for other in ('x86_64', 'aarch64', 'rv32' if arch == 'rv64' else 'rv64'):
                with self.assertRaises(ValueError): validate(fixture('pthread', arch=arch), 'pthread', other)

    def test_kind_cannot_substitute_other_probe(self):
        with self.assertRaises(ValueError): validate(fixture(), 'pthread')
        with self.assertRaises(ValueError): validate(fixture('pthread'))
        with self.assertRaises(ValueError): validate(fixture(), 'unknown')

    def test_other_architectures_are_not_execution_claims(self):
        for arch in ('i386', 'mips64', 'ppc', 'unknown'):
            with self.subTest(arch=arch), self.assertRaises(ValueError): validate(fixture(), arch=arch)

    def test_missing_duplicate_partial_or_cross_kind_marker(self):
        for kind, (marker, _, _, _) in evidence.PROBES.items():
            for replacement in (b'', marker+marker, marker[:-1], evidence.PTHREAD_MARKER if kind == 'raw' else evidence.MARKER):
                parts = fixture(kind); parts[2] = parts[2].replace(marker, replacement)
                with self.subTest(kind=kind, value=replacement), self.assertRaises(ValueError): validate(parts, kind)

    def test_failed_assertion_anywhere(self):
        for prefix in (b'SIGNAL_DELIVERY_FAIL', b'PTHREAD_SIGNALS_FAIL', b'ALTSTACK_FAIL', b'SIGNAL_BAD_SP_FAIL', b'OK_TEST_FAIL'):
            for i in range(5):
                parts = fixture(); parts[i] = prefix+b' code=102 handler=0\n'+parts[i]
                with self.subTest(prefix=prefix, span=i), self.assertRaises(ValueError): validate(parts)

    def test_success_cannot_be_outside_command(self):
        for i in (0, 1, 4):
            parts = fixture(); parts[i] = evidence.MARKER+b'\n'+parts[i]
            with self.subTest(span=i), self.assertRaises(ValueError): validate(parts)

    def test_altstack_requires_its_own_checks_and_exec_child(self):
        for arch in ('x86_64', 'aarch64'):
            for kind in ('altstack', 'altstack-exec'):
                self.assertEqual(validate(fixture(kind, arch=arch), kind, arch)['successful_exec'],
                                 'passed' if kind == 'altstack-exec' else 'not-run')
                for replace in (b'', b'ALTSTACK_CHECKS count=999\n', b'ALTSTACK_CHECKS count=35\nALTSTACK_CHECKS count=37\n'):
                    parts = fixture(kind, arch=arch)
                    count = b'ALTSTACK_CHECKS count=' + (b'37' if kind == 'altstack-exec' else b'35') + b'\n'
                    parts[2] = parts[2].replace(count, replace)
                    with self.assertRaises(ValueError): validate(parts, kind, arch)
            for target in ('altstack', 'raw', 'pthread'):
                with self.assertRaises(ValueError): validate(fixture('altstack-exec', arch=arch), target, arch)
            child = evidence.ALTSTACK_EXEC.replace(b'x86_64', arch.encode()) + b'\n'
            for replacement in (b'', child+child, child.replace(arch.encode(), b'unknown')):
                parts = fixture('altstack-exec', arch=arch); parts[2] = parts[2].replace(child, replacement)
                with self.assertRaises(ValueError): validate(parts, 'altstack-exec', arch)
            parts = fixture('altstack-exec', arch=arch)
            parts[2] = parts[2].replace(child, b'').replace(b'ALTSTACK_CHECKS', child+b'ALTSTACK_CHECKS')
            with self.assertRaises(ValueError): validate(parts, 'altstack-exec', arch)
            for index in (0,1,4):
                parts = fixture('altstack-exec', arch=arch); parts[index] = child+parts[index]
                with self.assertRaises(ValueError): validate(parts, 'altstack-exec', arch)

    def test_minimum_leases_are_kind_specific(self):
        for kind in evidence.PROBES:
            minimum = evidence.PROBES[kind][3]
            with self.subTest(kind=kind), self.assertRaises(ValueError): validate(fixture(kind, minimum-1), kind)

    def test_altstack_fault_children_require_matching_capture_counters(self):
        for kind in ('altstack', 'altstack-exec', 'bad-sp'):
            for count in (1, 2):
                parts = fixture(kind)
                for index in (2, 3):
                    parts[index] = parts[index].replace(IMAGE, IMAGE+(evidence.CONTAINED_FAULT+b'\n')*count, 1)
                parts[2] = parts[2].replace(b'faults=0', f'faults={count}'.encode())
                parts[3] = parts[3].replace(b'faults=0', f'faults={2*count}'.encode())
                parts[4] = parts[4].replace(b'faults=0', f'faults={2*count}'.encode())
                parts[2] = parts[2].replace(b'syscalls=300', f'syscalls={300-count}'.encode())
                parts[3] = parts[3].replace(b'syscalls=400', f'syscalls={400-2*count}'.encode())
                parts[4] = parts[4].replace(b'syscalls=500', f'syscalls={500-2*count}'.encode())
                self.assertEqual(validate(parts, kind)['runs'], 2)
                late = parts.copy()
                marker = evidence.PROBES[kind][0] + b'\n'
                late[2] = late[2].replace(evidence.CONTAINED_FAULT+b'\n', b'').replace(marker, marker+(evidence.CONTAINED_FAULT+b'\n')*count)
                with self.assertRaises(ValueError): validate(late, kind)
                parts[2] = parts[2].replace(evidence.CONTAINED_FAULT+b'\n', b'', 1)
                with self.assertRaises(ValueError): validate(parts, kind)
            for count in (1, 3):
                parts = fixture(kind); parts[2] = parts[2].replace(b'\n', b'\n'+(evidence.CONTAINED_FAULT+b'\n')*count, 1)
                with self.assertRaises(ValueError): validate(parts, kind)
        parts = fixture(); parts[2] = evidence.CONTAINED_FAULT+b'\n'+parts[2]
        with self.assertRaises(ValueError): validate(parts)

    def test_probe_image_admission_is_required_unique_and_ordered(self):
        for kind in evidence.PROBES:
            for index in (2, 3):
                for replacement in (b'', IMAGE+IMAGE, IMAGE.replace(b'linux', b'native'), IMAGE[:-2]+b'\n'):
                    parts = fixture(kind); parts[index] = parts[index].replace(IMAGE, replacement, 1)
                    with self.subTest(kind=kind, span=index, replacement=replacement), self.assertRaises(ValueError):
                        validate(parts, kind)
                parts = fixture(kind)
                marker = evidence.PROBES[kind][0] + b'\n'
                parts[index] = parts[index].replace(IMAGE, b'').replace(marker, marker+IMAGE*(2 if kind == 'altstack-exec' else 1))
                with self.assertRaises(ValueError): validate(parts, kind)
        child = evidence.ALTSTACK_EXEC + b'\n'
        for count in (1, 2):
            parts = fixture('altstack-exec')
            parts[2] = parts[2].replace(IMAGE, b'', count).replace(child, child+IMAGE*count)
            with self.assertRaises(ValueError): validate(parts, 'altstack-exec')

    def test_bad_sp_completion_is_ordered_and_unique(self):
        count = b'SIGNAL_BAD_SP_CHECKS count=18\n'
        for arch in ('x86_64', 'aarch64'):
            for replacement in (b'', count+count, count.replace(b'18', b'17')):
                parts = fixture('bad-sp', arch=arch); parts[2] = parts[2].replace(count, replacement)
                with self.assertRaises(ValueError): validate(parts, 'bad-sp', arch)
            parts = fixture('bad-sp', arch=arch)
            parts[2] = parts[2].replace(count,b'').replace(b'SIGNAL_BAD_SP_PASS',count+b'SIGNAL_BAD_SP_PASS')
            with self.assertRaises(ValueError): validate(parts,'bad-sp',arch)
            for index in (0,1,4):
                parts = fixture('bad-sp', arch=arch); parts[index] = count+parts[index]
                with self.assertRaises(ValueError): validate(parts,'bad-sp',arch)
            for kind in ('raw','pthread','altstack','altstack-exec'):
                with self.assertRaises(ValueError): validate(fixture('bad-sp',arch=arch),kind,arch)

    def test_retirement_must_follow_success(self):
        for kind in evidence.PROBES:
            marker = evidence.PROBES[kind][0]
            parts = fixture(kind); parts[2] = parts[2].replace(marker+b'\n', b'').replace(b'oksh> ', marker+b'\noksh> ')
            with self.subTest(kind=kind), self.assertRaises(ValueError): validate(parts, kind)

    def test_frames_and_leases_return_to_baseline(self):
        for old, new in ((b'used=40', b'used=41'), (b'objects=0', b'objects=1'),
                         (b'leased=2', b'leased=3'), (b'active=0', b'active=1')):
            parts = fixture(); parts[3] = parts[3].replace(old, new)
            with self.subTest(field=old), self.assertRaises(ValueError): validate(parts)

    def test_boundary_integrity_and_final_tail(self):
        parts = fixture(); serial = b''.join(parts)
        boundaries = [sum(map(len, parts[:i])) for i in range(1, 5)]
        for value in (0, True, boundaries[1]-1, boundaries[2]+1):
            changed = boundaries.copy(); changed[1] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                evidence.validate_execution(serial, *changed, boundaries[-1], 'x86_64')
        parts[-1] += b'UNEXPECTED\n'
        with self.assertRaises(ValueError): validate(parts)

    def test_exact_sdk_shape(self):
        with patch.object(evidence, 'admit_common_sdk', return_value={'abi_version':31, 'compiler':{'family':'gcc'}}):
            self.assertEqual(evidence.admit_sdk(None, None, 'x86_64', 'debug', None, None)['abi_version'],31)
            self.assertEqual(evidence.admit_sdk(None,None,'aarch64','debug',None,None)['abi_version'],31)
            with self.assertRaises(ValueError): evidence.admit_sdk(None,None,'x86_64','release',None,None)
        for manifest in ({'abi_version':28,'compiler':{'family':'gcc'}}, {'abi_version':29,'compiler':{'family':'gcc'}}, {'abi_version':30,'compiler':{'family':'gcc'}}, {'abi_version':32,'compiler':{'family':'gcc'}}, {'abi_version':31,'compiler':{'family':'clang'}}):
            with patch.object(evidence, 'admit_common_sdk', return_value=manifest), self.assertRaises(ValueError):
                evidence.admit_sdk(None,None,'x86_64','debug',None,None)


class SignalImageSourceTests(unittest.TestCase):
    # Explicit supported pairs keep a missing profile from silently reducing
    # these controls. This fixture matrix does not claim target execution.
    PROFILES = {
        'ppc': ('ppc-raw', 'ppc-map', 'pthread', 'altstack', 'altstack-exec', 'bad-sp'),
        'mips': ('mips-raw', 'mips-map', 'pthread', 'altstack', 'altstack-exec', 'bad-sp'),
        'mips64': ('mips64-raw', 'mips64-map', 'pthread', 'altstack', 'altstack-exec', 'bad-sp'),
        'loongarch64': ('pthread', 'altstack', 'altstack-exec', 'bad-sp', 'loongarch-map', 'loongarch-raw'),
        'i386': ('i386-raw', 'i386-entry', 'pthread', 'altstack', 'altstack-exec', 'bad-sp'),
        'x86_64': ('raw', 'pthread', 'altstack', 'altstack-exec', 'bad-sp'),
        'aarch64': ('raw', 'pthread', 'altstack', 'altstack-exec', 'bad-sp'),
        'arm32': ('arm32-raw', 'pthread', 'altstack', 'altstack-exec', 'bad-sp'),
        'rv32': ('riscv-raw', 'riscv-entry', 'riscv-map', 'pthread', 'altstack', 'altstack-exec', 'bad-sp'),
        'rv64': ('riscv-raw', 'riscv-entry', 'riscv-map', 'pthread', 'altstack', 'altstack-exec', 'bad-sp'),
    }

    @staticmethod
    def parts(arch, kind):
        if arch == 'ppc' and kind in ('ppc-raw', 'ppc-map'): return ppc_fixture(kind)
        if kind == 'mips64-raw': return mips64_raw_fixture()
        if kind == 'mips64-map': return mips64_mapping_fixture()
        return (mips_raw_fixture() if kind == 'mips-raw' else mips_mapping_fixture() if kind == 'mips-map' else loongarch_raw_fixture() if kind == 'loongarch-raw' else loongarch_mapping_fixture() if kind == 'loongarch-map' else fixture(kind, arch=arch) if kind in evidence.PROBES
                else riscv_fixture(kind, arch))

    def test_loongarch_short_command_is_exact(self):
        parts = fixture('pthread', arch='loongarch64')
        self.assertEqual(validate(parts, 'pthread', 'loongarch64')['runs'], 2)
        for index in (2, 3):
            broken = parts.copy()
            broken[index] = broken[index].replace(b'native-pthread-signals-la64', b'native-pthread-signals-loongarch64')
            with self.subTest(span=index), self.assertRaises(ValueError):
                validate(broken, 'pthread', 'loongarch64')

    def test_loongarch_scope_excludes_unported_raw_probes(self):
        for kind in ('raw', 'riscv-raw', 'riscv-map', 'riscv-entry', 'arm32-raw', 'i386-raw'):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                evidence.probe_spec('loongarch64', kind)

    def test_correct_source_for_all_supported_profiles(self):
        for arch, kinds in self.PROFILES.items():
            for kind in kinds:
                with self.subTest(arch=arch, kind=kind):
                    self.assertEqual(validate(self.parts(arch, kind), kind, arch)['runs'], 2)

    def test_wrong_source_in_each_run_and_each_exec_image(self):
        for arch, kinds in self.PROFILES.items():
            for kind in kinds:
                original = self.parts(arch, kind)
                for span in (2, 3):
                    expected = IMAGE.replace(b'source=firmware', b'source=linker') if arch in ('loongarch64', 'mips', 'mips64') else IMAGE
                    wrong = IMAGE if arch in ('loongarch64', 'mips', 'mips64') else IMAGE.replace(b'source=firmware', b'source=linker')
                    pieces = original[span].split(expected)
                    self.assertEqual(len(pieces) - 1, 2 if kind in ('altstack-exec', 'riscv-map', 'loongarch-map', 'mips-map', 'mips64-map', 'ppc-map') else 1)
                    for image_index in range(len(pieces) - 1):
                        broken = original.copy()
                        broken[span] = (expected.join(pieces[:image_index+1]) + wrong +
                            expected.join(pieces[image_index+1:]))
                        with self.subTest(arch=arch, kind=kind, span=span, image=image_index):
                            with self.assertRaisesRegex(ValueError, 'Linux image source'):
                                validate(broken, kind, arch)



class Arm32SignalAdmissionTests(unittest.TestCase):
    def test_arm32_pthread_actual_arch_marker(self):
        result = validate(fixture('pthread', arch='arm32'), 'pthread', 'arm32')
        self.assertEqual(result['runs'], 2)
        parts = fixture('pthread', arch='arm32')
        parts[2] = parts[2].replace(b'PTHREAD_SIGNALS_PASS arm32', b'PTHREAD_SIGNALS_PASS aarch64')
        with self.assertRaises(ValueError): validate(parts, 'pthread', 'arm32')

    def test_unported_arm32_guest_kinds_are_not_admitted(self):
        for kind in ('raw', 'i386-raw', 'riscv-raw', 'i386-entry', 'riscv-entry', 'riscv-map'):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                evidence.probe_spec('arm32', kind)


class Arm32RawEvidenceTests(unittest.TestCase):
    def test_strict_raw_and_profile_identity(self):
        parts = riscv_fixture('arm32-raw', 'arm32')
        result = validate(parts, 'arm32-raw', 'arm32')
        self.assertEqual(result['minimum_leases_per_run'], 5)
        for key in ('legacy','realtime','arm_thumb','d32','fpscr','edited_fp','restorers'):
            self.assertEqual(result[key], 'passed')
        for arch in ('i386','x86_64','aarch64','rv32','rv64','mips','mips64','ppc','loongarch64'):
            with self.subTest(arch=arch), self.assertRaises(ValueError): validate(parts, 'arm32-raw', arch)
        for index in (2,3):
            for item in (evidence.ARM32_MARKER,IMAGE):
                for replacement in (b'', item+item, item[:-1]):
                    broken=parts.copy();broken[index]=broken[index].replace(item,replacement)
                    with self.assertRaises(ValueError): validate(broken,'arm32-raw','arm32')
        for index in range(5):
            broken=parts.copy();broken[index]=b'SIGNAL_ARM32_FAIL code=103 handler=03\n'+broken[index]
            with self.assertRaises(ValueError): validate(broken,'arm32-raw','arm32')


class Arm32AltstackEvidenceTests(unittest.TestCase):
    def test_arm32_altstack_bad_sp_and_exec(self):
        for kind in ('altstack','altstack-exec','bad-sp'):
            parts=fixture(kind,arch='arm32')
            self.assertEqual(validate(parts,kind,'arm32')['runs'],2)
            for index in (2,3):
                broken=parts.copy();broken[index]=broken[index].replace(IMAGE,b'',1)
                with self.assertRaises(ValueError): validate(broken,kind,'arm32')
            for arch in ('i386','x86_64','aarch64','rv32','rv64'):
                with self.assertRaises(ValueError): validate(parts,kind,arch)


class MipsO32SignalAdmissionTests(unittest.TestCase):
    def test_common_probes_keep_architecture_and_source(self):
        for kind in ('pthread', 'altstack', 'altstack-exec', 'bad-sp'):
            original = fixture(kind, arch='mips')
            self.assertEqual(validate(original, kind, 'mips')['runs'], 2)
            for arch in ('i386', 'x86_64', 'aarch64', 'arm32', 'rv32', 'rv64', 'loongarch64', 'mips64', 'ppc'):
                with self.subTest(kind=kind, arch=arch), self.assertRaises(ValueError):
                    validate(original, kind, arch)

    def test_raw_and_other_abi_probes_remain_unavailable(self):
        for kind in ('raw', 'i386-raw', 'i386-entry', 'arm32-raw', 'riscv-raw', 'riscv-entry', 'riscv-map', 'loongarch-raw', 'loongarch-map'):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                evidence.probe_spec('mips', kind)
        for arch in ('ppc',):
            for kind in ('raw', 'riscv-raw', 'riscv-map'):
                with self.subTest(arch=arch, kind=kind), self.assertRaises(ValueError):
                    evidence.probe_spec(arch, kind)




class FragmentedSignalDiagnostics(unittest.TestCase):
    def test_all_recognized_signal_failures_are_drained_through_newline(self):
        for prefix in evidence.SIGNAL_FAILURE_PREFIXES:
            full = prefix + b' code=117 handler=23 mode=21 rt=1\r\n'
            for end in range(len(prefix), len(full)):
                with self.subTest(prefix=prefix, end=end):
                    partial = b'previous complete output\n' + full[:end]
                    self.assertIsNotNone(evidence.failure_line(partial))
                    self.assertTrue(evidence.incomplete_failure_line(partial))
            self.assertFalse(evidence.incomplete_failure_line(full))
            self.assertFalse(evidence.incomplete_failure_line(full + b'later bytes'))
        self.assertFalse(evidence.incomplete_failure_line(b'SIGNAL_MIPS_PASS mips\n'))


class Mips64CommonEvidence(unittest.TestCase):
    def test_n64_common_profiles_and_architecture_rejection(self):
        for kind in ('pthread', 'altstack', 'altstack-exec', 'bad-sp'):
            original = fixture(kind, arch='mips64')
            self.assertEqual(validate(original, kind, 'mips64')['runs'], 2)
            for arch in ('i386', 'x86_64', 'aarch64', 'arm32', 'rv32', 'rv64', 'loongarch64', 'mips', 'ppc'):
                with self.subTest(kind=kind, arch=arch), self.assertRaises(ValueError):
                    validate(original, kind, arch)
            for index in (2, 3):
                broken = original.copy()
                broken[index] = broken[index].replace(b'source=linker', b'source=firmware', 1)
                with self.assertRaises(ValueError): validate(broken, kind, 'mips64')
                broken = original.copy()
                broken[index] = broken[index].replace(b'PASS mips64', b'FAIL mips64')
                with self.assertRaises(ValueError): validate(broken, kind, 'mips64')

    def test_unimplemented_raw_profiles_stay_unavailable(self):
        for kind in ('raw', 'mips-raw', 'mips-map', 'loongarch-raw', 'loongarch-map',
                     'i386-entry', 'i386-raw', 'arm32-raw', 'riscv-raw', 'riscv-map', 'riscv-entry'):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                evidence.probe_spec('mips64', kind)

    def test_runtime_options_are_explicit_and_profile_specific(self):
        from qualify_native_signal_delivery_x86_64 import validate_runtime_options
        validate_runtime_options('mips64', Path('/explicit/runtime'), '1' * 64)
        validate_runtime_options('mips', None, None)
        for arch, build, digest in (('mips64', None, None), ('mips64', Path('/runtime'), None),
                                    ('mips64', None, '1' * 64), ('mips', Path('/runtime'), '1' * 64)):
            with self.subTest(arch=arch, build=build, digest=digest), self.assertRaises(ValueError):
                validate_runtime_options(arch, build, digest)


class Mips64RawEvidence(unittest.TestCase):
    def test_exact_rt_only_contract(self):
        result = validate(mips64_raw_fixture(), 'mips64-raw', 'mips64')
        self.assertEqual(result['runs'], 2)
        self.assertTrue(result['rt_only'])
        self.assertFalse(result['production_signal_support'])
        self.assertNotIn('legacy', result)
        self.assertEqual(result['minimum_leases_per_run'], 22)
        self.assertEqual(result['corrupt_return_children'], 16)
        self.assertEqual(result['forced_default_children'], 4)
        self.assertEqual(result['highest_signal_children'], 1)
        self.assertEqual(result['image_publications_per_run'], 1)
        for key in ('plain_rt', 'siginfo_rt', 'gpr', 'fpr32', 'hilo', 'fcsr', 'tls',
                    'edited_fp', 'restorers', 'high_mask', 'pending_fcsr', 'fcsr_writeback',
                    'sigfpe_before_resume', 'si_kernel', 'forced_default',
                    'preserved_payload', 'highest_fatal'):
            self.assertEqual(result[key], 'passed')

    def test_each_raw_count_and_flag_is_required_in_each_run(self):
        original = mips64_raw_fixture()
        for index in (2, 3):
            for field in evidence.MIPS64_MARKER.split()[2:]:
                for value in (b'0', b'999'):
                    parts = original.copy()
                    parts[index] = parts[index].replace(field, field.split(b'=')[0] + b'=' + value)
                    with self.subTest(index=index, field=field, value=value), self.assertRaises(ValueError):
                        validate(parts, 'mips64-raw', 'mips64')

    def test_per_case_reference_diagnostic_and_legacy_are_not_aggregate_success(self):
        original = mips64_raw_fixture()
        for index in (2, 3):
            for replacement in (b'SIGNAL_MIPS64_CASE_PASS core0',
                                b'SIGNAL_MIPS64_DIAGNOSTIC_PASS', evidence.MIPS_MARKER,
                                evidence.MIPS64_MARKER.replace(b'plain_rt=1', b'legacy=1'),
                                evidence.MIPS64_MARKER.replace(b'fpr32=4', b'fpr16=4')):
                parts = original.copy(); parts[index] = parts[index].replace(evidence.MIPS64_MARKER, replacement)
                with self.subTest(index=index, replacement=replacement), self.assertRaises(ValueError):
                    validate(parts, 'mips64-raw', 'mips64')

    def test_raw_marker_image_and_command_are_unique_exact_and_complete(self):
        original = mips64_raw_fixture()
        image = IMAGE.replace(b'source=firmware', b'source=linker')
        for index in (2, 3):
            for item in (evidence.MIPS64_MARKER + b'\n', image):
                for replacement in (b'', item + item, item[:-1], item[:-1] + b' trailing\n'):
                    parts = original.copy(); parts[index] = parts[index].replace(item, replacement)
                    with self.subTest(index=index, item=item, replacement=replacement), self.assertRaises(ValueError):
                        validate(parts, 'mips64-raw', 'mips64')
            for command in (b'native-signal-mips64', b'/bin/native-signal-mips', b'/bin/native-signal-delivery-mips64'):
                parts = original.copy(); parts[index] = parts[index].replace(b'/bin/native-signal-mips64', command)
                with self.assertRaises(ValueError): validate(parts, 'mips64-raw', 'mips64')

    def test_raw_requires_twenty_two_fresh_leases_and_retirement_each_run(self):
        with self.assertRaises(ValueError): validate(mips64_raw_fixture(21), 'mips64-raw', 'mips64')
        original = mips64_raw_fixture()
        parts = original.copy()
        parts[3] = parts[3].replace(b'reservations=54 releases=52', b'reservations=53 releases=51')
        with self.assertRaises(ValueError): validate(parts, 'mips64-raw', 'mips64')
        for index in (2, 3):
            for old, new in ((b'leased=2', b'leased=3'), (b'objects=0', b'objects=1'),
                             (b'active=0', b'active=1'), (b'quarantine=0', b'quarantine=1')):
                parts = original.copy(); parts[index] = parts[index].replace(old, new)
                with self.assertRaises(ValueError): validate(parts, 'mips64-raw', 'mips64')

    def test_failure_anywhere_and_success_outside_probe_are_rejected(self):
        original = mips64_raw_fixture()
        for index in range(5):
            parts = original.copy(); parts[index] = b'SIGNAL_MIPS64_FAIL code=117\n' + parts[index]
            with self.assertRaises(ValueError): validate(parts, 'mips64-raw', 'mips64')
        for index in (0, 1, 4):
            parts = original.copy(); parts[index] = evidence.MIPS64_MARKER + b'\n' + parts[index]
            with self.assertRaises(ValueError): validate(parts, 'mips64-raw', 'mips64')


class Mips64MappingEvidence(unittest.TestCase):
    def test_exact_mapping_contract(self):
        result = validate(mips64_mapping_fixture(), 'mips64-map', 'mips64')
        self.assertEqual(result['runs'], 2)
        self.assertEqual(result['minimum_leases_per_run'], 3)
        self.assertEqual(result['image_publications_per_run'], 2)
        self.assertEqual(result['check_count'], 26)
        self.assertTrue(result['rt_only'])
        for key in ('plain', 'siginfo', 'protected', 'hint', 'adjacent', 'fork', 'successful_exec', 'write_fault'):
            self.assertEqual(result[key], 'passed')

    def test_mapping_counts_flags_markers_and_absolute_command(self):
        original = mips64_mapping_fixture()
        child = evidence.MAP_EXEC.replace(b'x86_64', b'mips64')
        changes = [(field, field.split(b'=')[0] + b'=0') for field in evidence.MIPS64_MAP_MARKER.split()[2:]]
        changes += [(b'SIGNAL_MAP_CHECKS count=26', b'SIGNAL_MAP_CHECKS count=25'),
                    (child, b''), (child, child + b'\n' + child),
                    (evidence.CONTAINED_FAULT + b'\n', b''),
                    (b'/bin/native-signal-mapping-mips64', b'native-signal-mapping-mips64'),
                    (b'faults=', b'invalid=')]
        for index in (2, 3):
            for old, new in changes:
                parts = original.copy(); parts[index] = parts[index].replace(old, new)
                with self.subTest(index=index, old=old), self.assertRaises(ValueError):
                    validate(parts, 'mips64-map', 'mips64')

    def test_mapping_images_and_completion_order(self):
        original = mips64_mapping_fixture()
        image = IMAGE.replace(b'source=firmware', b'source=linker')
        child = evidence.MAP_EXEC.replace(b'x86_64', b'mips64') + b'\n'
        marker = evidence.MIPS64_MAP_MARKER + b'\n'
        for index in (2, 3):
            for replacement in (b'', image + image):
                parts = original.copy(); parts[index] = parts[index].replace(image, replacement, 1)
                with self.assertRaises(ValueError): validate(parts, 'mips64-map', 'mips64')
            for old, new in ((image + child, child + image),
                             (child + marker, marker + child),
                             (marker + b'SIGNAL_MAP_CHECKS count=26\n', b'SIGNAL_MAP_CHECKS count=26\n' + marker),
                             (evidence.CONTAINED_FAULT + b'\n' + image, image + evidence.CONTAINED_FAULT + b'\n')):
                parts = original.copy(); self.assertIn(old, parts[index]); parts[index] = parts[index].replace(old, new)
                with self.assertRaises(ValueError): validate(parts, 'mips64-map', 'mips64')

    def test_mapping_requires_three_fresh_leases_and_bound_subtest_outputs(self):
        original = mips64_mapping_fixture()
        for index, old, new in ((2, b'reservations=13 releases=11', b'reservations=12 releases=10'),
                                (3, b'reservations=16 releases=14', b'reservations=15 releases=13')):
            parts = original.copy(); self.assertIn(old, parts[index]); parts[index] = parts[index].replace(old, new)
            with self.assertRaises(ValueError): validate(parts, 'mips64-map', 'mips64')
        for index in (0, 1, 4):
            for line in (evidence.MIPS64_MAP_MARKER, b'SIGNAL_MAP_CHECKS count=26',
                         evidence.MAP_EXEC.replace(b'x86_64', b'mips64')):
                parts = original.copy(); parts[index] = line + b'\n' + parts[index]
                with self.assertRaises(ValueError): validate(parts, 'mips64-map', 'mips64')


class Mips64ConsumerAdmission(unittest.TestCase):
    def test_raw_and_mapping_reject_other_architectures_and_probe_kinds(self):
        for kind, original in (('mips64-raw', mips64_raw_fixture()), ('mips64-map', mips64_mapping_fixture())):
            for arch in ('i386', 'x86_64', 'aarch64', 'arm32', 'rv32', 'rv64', 'loongarch64', 'mips', 'ppc'):
                with self.subTest(kind=kind, arch=arch), self.assertRaises(ValueError):
                    validate(original, kind, arch)
            for other in ('pthread', 'raw', 'mips-raw', 'mips-map', 'mips64-raw', 'mips64-map'):
                if kind != other:
                    with self.subTest(kind=kind, other=other), self.assertRaises(ValueError):
                        validate(original, other, 'mips64')

    def test_collector_paths_and_all_existing_command_contracts(self):
        from qualify_native_signal_delivery_x86_64 import probe_layout
        for kind, source, command in (
                ('mips64-raw', 'native_signal_delivery_mips64', 'native-signal-mips64'),
                ('mips64-map', 'native_signal_mapping_mips64', 'native-signal-mapping-mips64')):
            self.assertEqual(probe_layout('mips64', kind), (source, command, '/bin/' + command))
            self.assertTrue((Path(__file__).resolve().parents[1] / 'musl' / (source + '.c')).is_file())
        for arch, kinds in SignalImageSourceTests.PROFILES.items():
            for kind in kinds:
                expected = evidence.probe_spec(arch, kind)[2].replace(
                    b'x86-64', b'la64' if arch == 'loongarch64' else arch.replace('_', '-').encode())
                self.assertEqual(probe_layout(arch, kind)[2].encode(), expected)
        for arch in ('i386', 'x86_64', 'aarch64', 'arm32', 'rv32', 'rv64', 'loongarch64', 'mips', 'ppc'):
            for kind in ('mips64-raw', 'mips64-map'):
                with self.assertRaises(ValueError): probe_layout(arch, kind)

    def test_n64_sdk_private_debug_scope_is_preserved(self):
        manifest = {'abi_version': 31, 'compiler': {'family': 'gcc'}}
        with patch.object(evidence, 'admit_common_sdk', return_value=manifest):
            self.assertEqual(evidence.admit_sdk(None, None, 'mips64', 'debug', None, None), manifest)
            with self.assertRaises(ValueError): evidence.admit_sdk(None, None, 'mips64', 'release', None, None)


if __name__ == '__main__':
    unittest.main()

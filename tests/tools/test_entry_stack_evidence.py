"""Synthetic corruption controls; these tests do not execute privileged code."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from entry_stack_evidence import decode_stacks, validate_execution
from native_threads_evidence import MARKER
from object_pressure_evidence import ARCH_TRIPLES


def stack(reservations, releases, activations, syscalls, *, peak=4, timers=0, faults=0, rejected=0):
    return (f'OK_ENTRY_STACKS version=1 scope=actual-user cpu=0 capacity=128 usable_bytes=65536 '
            f'backing_bytes=9437184 leased={reservations-releases} active=0 quarantine=0 peak={peak} '
            f'reservations={reservations} releases={releases} activations={activations} syscalls={syscalls} '
            f'timers={timers} faults={faults} rejected={rejected} guards=mapped-canaries smp=0\n').encode()


EMPTY = stack(0, 0, 0, 0, peak=0)
BOOT = stack(7, 6, 90, 90)
BASE = stack(10, 8, 140, 140)
PEER = stack(29, 26, 420, 419, timers=1)
FIRST = stack(29, 27, 470, 469, timers=1)
SECOND = stack(48, 46, 800, 799, timers=1)
FINAL = stack(50, 48, 850, 849, timers=1)


def frames(allocations, releases, source):
    used = allocations - releases
    return (f'OK_NATIVE_FRAMES version=2 source={source} used={used} total=1024 allocations={allocations} '
            f'releases={releases} pinned=0 user={used} objects=0 free={1024-used} pending=0 reserve=10 '
            f'user_limit=1014\n').encode()


def spans(source='firmware', timer=True):
    parts = [
        b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw\nOK_SYSTEM_GUI boot=complete\n' +
        frames(0, 0, source) + EMPTY + b'hello from ObfuscationOS userland\n' + frames(19, 0, source) + BOOT + b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n' + frames(100, 60, source) + BASE + b'oksh> ',
        b'native-threads\n' + PEER + MARKER + b'\n' + frames(200, 160, source) + FIRST + b'oksh> ',
        b'native-threads\n' + MARKER + b'\n' + frames(300, 260, source) + SECOND + b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n' + frames(400, 360, source) + FINAL + b'oksh> ',
    ]
    if not timer:
        # One unobserved activation is permitted; no mandatory timer/fault quota.
        parts = [part.replace(b'timers=1', b'timers=0') for part in parts]
    return parts


def validate(parts, arch='x86_64'):
    boundaries = [sum(map(len, parts[:index])) for index in range(1, 5)]
    return validate_execution(b''.join(parts), *boundaries, boundaries[-1], arch)


class EntryStackEvidence(unittest.TestCase):
    def test_all_ten_profiles_and_stable_shell_leases(self):
        for arch in ARCH_TRIPLES:
            with self.subTest(arch=arch):
                source = 'linker' if arch in ('mips', 'mips64', 'loongarch64') else 'firmware'
                result = validate(spans(source), arch)
                self.assertEqual(result['runs'], 2)
                evidence = result['entry_stacks']
                self.assertEqual(evidence['records'], 7)
                self.assertEqual(evidence['baseline']['leased'], 2)
                self.assertEqual(evidence['final']['leased'], 2)
                self.assertEqual(evidence['commands'][1]['reservations'], 19)
                self.assertEqual(evidence['commands'][1]['releases'], 19)
                self.assertEqual(evidence['minimum_probe_reservations'], 16)
                self.assertFalse(evidence['smp'])

    def test_timer_fault_not_required_and_synthetic_rejection_allowed(self):
        self.assertEqual(validate(spans(timer=False))['entry_stacks']['final']['timers'], 0)
        parts = spans()
        parts[3] = parts[3].replace(SECOND, stack(48, 46, 810, 799, timers=1, rejected=10))
        parts[4] = parts[4].replace(FINAL, stack(50, 48, 860, 849, timers=1, rejected=10))
        self.assertEqual(validate(parts)['entry_stacks']['final']['rejected'], 10)

    def test_complete_record_and_fixed_contract(self):
        mutations = [
            BASE.rstrip(b'\n'), b'prefix ' + BASE, BASE.replace(b'active=0', b'active=0 active=0'),
            BASE.replace(b'version=1', b'version=2'), BASE.replace(b'scope=actual-user', b'scope=model'),
            BASE.replace(b'cpu=0', b'cpu=1'), BASE.replace(b'capacity=128', b'capacity=127'),
            BASE.replace(b'usable_bytes=65536', b'usable_bytes=4096'),
            BASE.replace(b'backing_bytes=9437184', b'backing_bytes=8388608'),
            BASE.replace(b'guards=mapped-canaries', b'guards=unmapped'), BASE.replace(b'smp=0', b'smp=1'),
            BASE.replace(b'leased=2', b'leased=02'), BASE.replace(b'leased=2', b'leased=-1'),
            BASE.replace(b'rejected=0', b'rejected=18446744073709551616'),
            BASE.replace(b' active=0 quarantine=0', b' quarantine=0 active=0'),
            BASE.replace(b' smp=0', b' extra=0 smp=0'), BASE.replace(b' faults=0', b''),
        ]
        for replacement in mutations:
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                decode_stacks(replacement)
        self.assertEqual(decode_stacks(BASE.replace(b'\n', b'\r\n'))[0]['leased'], 2)

    def test_accounting_corruption(self):
        for old, new in ((b'active=0', b'active=1'), (b'quarantine=0', b'quarantine=1'),
                         (b'leased=2', b'leased=3'), (b'peak=4', b'peak=1'),
                         (b'peak=4', b'peak=129'), (b'releases=8', b'releases=11'),
                         (b'activations=140', b'activations=139'), (b'rejected=0', b'rejected=1')):
            with self.subTest(new=new), self.assertRaises(ValueError):
                decode_stacks(BASE.replace(old, new))
        with self.assertRaises(ValueError):
            decode_stacks(stack(3, 1, 0, 0, peak=4))
        with self.assertRaises(ValueError):
            decode_stacks(stack(3, 3, 0, 0, peak=0))
        with self.assertRaises(ValueError):
            decode_stacks(stack(0, 0, 1, 1, peak=0))

    def test_duplicates_backward_and_unsupported_counter_increases(self):
        for serial in (EMPTY + EMPTY, BASE + BASE, BASE + BOOT,
                       BASE + stack(10, 8, 141, 140, peak=5),
                       # New captures cannot consume slack from an older snapshot.
                       stack(10, 8, 200, 140) + stack(10, 8, 201, 142),
                       stack(10, 8, 200, 140, rejected=3) + stack(10, 8, 201, 141, rejected=2),
                       BASE + stack(11, 9, 141, 141, peak=3)):
            with self.subTest(serial=serial), self.assertRaises(ValueError):
                decode_stacks(serial)

    def test_empty_boot_and_each_command_have_their_own_records(self):
        parts = spans(); parts[0] = parts[0].replace(EMPTY, b'')
        with self.assertRaises(ValueError): validate(parts)
        for index in range(5):
            parts = spans()
            parts[index] = b''.join(line for line in parts[index].splitlines(keepends=True)
                                    if b'OK_ENTRY_STACKS' not in line)
            with self.subTest(index=index), self.assertRaises(ValueError): validate(parts)
        parts = spans()
        parts[2] = parts[2].replace(PEER, b'').replace(FIRST, b'')
        parts[3] = PEER + FIRST + parts[3]
        with self.assertRaises(ValueError): validate(parts)
        for index, last in ((1, BASE), (2, FIRST), (3, SECOND), (4, FINAL)):
            parts = spans(); parts[index] = last + parts[index].replace(last, b'')
            if index == 2:
                parts[index] = parts[index].replace(PEER, b'')
            with self.subTest(index=index), self.assertRaises(ValueError): validate(parts)

    def test_leaked_or_missing_shell_lease(self):
        parts = spans(); parts[3] = parts[3].replace(SECOND, stack(48, 45, 800, 799, timers=1))
        with self.assertRaises(ValueError): validate(parts)
        parts = spans()
        for index, old, new in ((1, BASE, stack(10, 10, 140, 140)),
                                (2, FIRST, stack(29, 29, 470, 469, timers=1)),
                                (3, SECOND, stack(48, 48, 800, 799, timers=1)),
                                (4, FINAL, stack(50, 50, 850, 849, timers=1))):
            parts[index] = parts[index].replace(old, new)
        with self.assertRaises(ValueError): validate(parts)

    def test_fresh_command_syscalls_entries_and_sixteen_reuses(self):
        mutations = [stack(25, 23, 470, 469, timers=1),
                     stack(29, 27, 470, 140), stack(29, 27, 140, 140)]
        for replacement in mutations:
            parts = spans(); parts[2] = parts[2].replace(PEER, b'').replace(FIRST, replacement)
            with self.subTest(replacement=replacement), self.assertRaises(ValueError): validate(parts)
        parts = spans(); parts[3] = parts[3].replace(SECOND, stack(44, 42, 800, 799, timers=1))
        with self.assertRaises(ValueError): validate(parts)
        parts = spans(); parts[4] = parts[4].replace(FINAL, stack(48, 46, 850, 849, timers=1))
        with self.assertRaises(ValueError): validate(parts)
        parts = spans(); parts[1] = parts[1].replace(BASE, stack(8, 6, 140, 140))
        with self.assertRaises(ValueError): validate(parts)

    def test_existing_thread_frame_and_boundary_checks_remain_required(self):
        parts = spans(); parts[2] = parts[2].replace(MARKER, b'missing')
        with self.assertRaises(ValueError): validate(parts)
        parts = spans(); parts[2] = parts[2].replace(frames(200, 160, 'firmware'), frames(200, 159, 'firmware'))
        with self.assertRaises(ValueError): validate(parts)
        parts = spans(); data = b''.join(parts)
        boundaries = [sum(map(len, parts[:index])) for index in range(1, 5)]
        for value in (0, True, boundaries[1] - 1):
            changed = boundaries.copy(); changed[1] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_execution(data, *changed, boundaries[-1], 'x86_64')
        parts = spans(); parts[2] = b'OK_TEST_FAIL native-entry-stack=ownership\n' + parts[2]
        with self.assertRaises(ValueError): validate(parts)

    def test_gap_activity_and_final_tail(self):
        parts = spans(); bounds = [sum(map(len, parts[:index])) for index in range(1, 5)]
        gap = stack(49, 47, 810, 809, timers=1) + b'oksh> '
        data = b''.join(parts[:4]) + gap + parts[4]
        with self.assertRaises(ValueError):
            validate_execution(data, *bounds, bounds[-1] + len(gap), 'x86_64')
        parts[-1] += b'qemu-system-x86_64: terminating on signal 15 from pid 5 (/usr/bin/python3)\n'
        self.assertEqual(validate(parts)['entry_stacks']['records'], 7)
        parts[-1] += b'OK_ENTRY_STACKS'
        with self.assertRaises(ValueError): validate(parts)


if __name__ == '__main__':
    unittest.main()

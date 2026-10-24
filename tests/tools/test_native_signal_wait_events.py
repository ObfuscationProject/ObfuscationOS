"""Independent all-ten native wait ledger models; no native or kernel execution.

Fixtures below spell the wire contract independently of the parser and guest
protocol modules. A synthetic pass cannot establish that these events executed.
"""
from pathlib import Path
import copy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import native_signal_wait_events as ledger

ARCHES = ('x86_64', 'i386', 'aarch64', 'arm32', 'rv32', 'rv64', 'loongarch64', 'mips', 'mips64', 'ppc')
TIMED = dict(zip(ARCHES, (128, 177, 137, 177, 421, 137, 137, 4197, 5126, 176)))
SUSPEND = dict(zip(ARCHES, (130, 179, 133, 179, 133, 133, 133, 4199, 5128, 178)))
WORD32 = {'i386', 'arm32', 'rv32', 'mips', 'ppc'}
MAX_ID = 0x3fffffff
MAX_U64 = (1 << 64) - 1
MAX_TIME = (1 << 63) - 1
IDENTITY = 'pid tid epoch wait kind'.split()
INPUTS = 'syscall pc set info timeout sigsetsize wanted0 wanted1 original0 original1 deadline'.split()
ACTIVE = 'active0 active1'.split()
FIELDS = {
    'ARM': IDENTITY + INPUTS + ACTIVE + ['live'],
    'COMPLETE': IDENTITY + 'outcome signal code sender_pid sender_uid info result published staged consumed live deadline now'.split(),
    'REARM': IDENTITY + ['old_wait', 'cause'] + INPUTS + ACTIVE + ['published', 'staged', 'live'],
    'COMMIT': IDENTITY + ['signal', 'published', 'result', 'live_before'],
    'RETIRE': IDENTITY + ['cause', 'published', 'staged', 'live_before'],
}


def bounds(arch):
    return (0x10000000, 0x40000000) if arch in ('aarch64', 'arm32') else (0x40000000, 0x80000000)


def signals(arch):
    return (16, 17, 20) if arch in ('mips', 'mips64') else (10, 12, 28)


def words(*numbers):
    value = sum(1 << (number - 1) for number in set(numbers))
    return value & MAX_U64, value >> 64


def arm(arch, *, kind='timed', finite=True, pid=10, tid=11, epoch=1, wait=1, live=1, signal=None, time64=False):
    low, _ = bounds(arch)
    one, two, _ = signals(arch)
    wanted = words(signal or one) if kind == 'timed' else words(two)
    original = words(one, two, signal or one)
    number = SUSPEND[arch] if kind == 'suspend' else TIMED[arch]
    if time64:
        number = 4421 if arch == 'mips' else 421
    fields = dict(pid=pid, tid=tid, epoch=epoch, wait=wait, kind=kind,
                  syscall=number, pc=low + 0x1040, set=low + 0x2000,
                  info=low + 0x3000 if kind == 'timed' else 0,
                  timeout=low + 0x4000 if kind == 'timed' and finite else 0,
                  sigsetsize=16 if arch in ('mips', 'mips64') else 8,
                  wanted0=wanted[0], wanted1=wanted[1], original0=original[0], original1=original[1],
                  deadline=1000 if kind == 'timed' and finite else 0,
                  active0=wanted[0] if kind == 'suspend' else original[0] & ~wanted[0],
                  active1=wanted[1] if kind == 'suspend' else original[1] & ~wanted[1], live=live)
    return 'ARM', fields


def complete(origin, *, outcome='received', signal=None, code=-6, sender_pid=99, sender_uid=1000, now=900, live=None):
    a = origin[1]
    if signal is None:
        mask = a['wanted0'] | (a['wanted1'] << 64)
        signal = (mask & -mask).bit_length()
    empty = outcome in ('timeout', 'cancelled')
    if empty:
        signal = code = sender_pid = sender_uid = 0
    staged = a['kind'] == 'suspend' and outcome == 'eintr'
    matched = outcome in ('received', 'efault')
    result = signal if outcome == 'received' else -14 if outcome == 'efault' else -11 if outcome == 'timeout' else -4
    return 'COMPLETE', dict({k: a[k] for k in IDENTITY}, outcome=outcome, signal=signal,
                           code=code, sender_pid=sender_pid, sender_uid=sender_uid, info=a['info'], result=result,
                           published=int(not staged), staged=int(staged), consumed=int(matched),
                           live=int(staged) if live is None else live, deadline=a['deadline'], now=now)


def rearm(origin, *, wait=None, cause='ready', staged=0, live=None):
    a = origin[1]
    fields = {k: a[k] for k in IDENTITY + INPUTS + ACTIVE}
    fields.update(wait=a['wait'] + 2 if wait is None else wait, old_wait=a['wait'], cause=cause,
                  published=0, staged=staged, live=a['live'] if live is None else live)
    return 'REARM', fields


def commit(origin, signal, live=1):
    return 'COMMIT', dict({k: origin[1][k] for k in IDENTITY}, signal=signal, published=1, result=-4, live_before=live)


def retire(origin, *, cause='thread', staged=0, live=1):
    return 'RETIRE', dict({k: origin[1][k] for k in IDENTITY}, cause=cause, published=0, staged=staged, live_before=live)


def wire(row):
    if isinstance(row, bytes):
        return row
    event, fields = row
    return ('OK_NATIVE_SIGNAL_WAIT_' + event + ''.join(' ' + key + '=' + str(fields[key]) for key in FIELDS[event])).encode()


def stream(rows):
    return b'\n'.join(wire(row) for row in rows) + b'\n'


def changed(rows, index, **fields):
    result = copy.deepcopy(rows)
    result[index][1].update(fields)
    return result


class NativeSignalWaitLedgerTests(unittest.TestCase):
    def accepted(self, rows, arch):
        result = ledger.native_events(stream(rows), arch)
        expected = [(position, wire(row)) for position, row in enumerate(rows) if not isinstance(row, bytes)]
        self.assertEqual([(row['position'], row['line']) for row in result], expected)
        self.assertTrue(all(isinstance(row['pid'], int) and isinstance(row['event'], str) for row in result))
        return result

    def rejected(self, rows, arch):
        with self.assertRaises(ValueError):
            ledger.native_events(stream(rows), arch)

    def test_all_ten_timed_completion_forms(self):
        for arch in ARCHES:
            for finite in (False, True):
                for outcome in ('received', 'efault', 'cancelled', 'eintr'):
                    with self.subTest(arch=arch, finite=finite, outcome=outcome):
                        a = arm(arch, finite=finite)
                        signal = signals(arch)[2] if outcome == 'eintr' else signals(arch)[0]
                        rows = [b'unrelated guest output', a, b'', complete(a, outcome=outcome, signal=signal)]
                        parsed = self.accepted(rows, arch)
                        self.assertEqual([row['origin_position'] for row in parsed], [1, 1])
            a = arm(arch)
            self.accepted([a, complete(a, outcome='timeout', now=a[1]['deadline'])], arch)
            self.accepted([a, complete(a, now=MAX_U64)], arch)  # A matching occurrence wins elapsed time.
            a[1]['info'] = 0
            self.accepted([a, complete(a)], arch)
            a = arm(arch, finite=False)
            for key in ('wanted0', 'wanted1'):
                a[1][key] = 0
            a[1]['active0'], a[1]['active1'] = a[1]['original0'], a[1]['original1']
            self.accepted([a, complete(a, outcome='cancelled')], arch)

    def test_kernel_siginfo_and_fallback_are_distinct(self):
        for arch in ARCHES:
            a = arm(arch)
            self.accepted([a, complete(a, code=0)], arch)
            with self.subTest(arch=arch, code=128):
                self.accepted([a, complete(a, code=128, sender_pid=0, sender_uid=0)], arch)
            fallback = arm(arch, signal=32)
            self.accepted([fallback, complete(fallback, code=0, sender_pid=0, sender_uid=0)], arch)
            for code, pid, uid in ((128, 99, 0), (128, 0, 1), (1, 99, 1)):
                with self.subTest(arch=arch, bad=(code, pid, uid)):
                    self.rejected([a, complete(a, code=code, sender_pid=pid, sender_uid=uid)], arch)

    def test_all_ten_rearm_preserves_logical_operation(self):
        for arch in ARCHES:
            for kind in ('timed', 'suspend'):
                a = arm(arch, kind=kind)
                r = rearm(a)
                end = complete(r) if kind == 'timed' else retire(r)
                parsed = self.accepted([a, b'legitimate peer syscall', r, end], arch)
                self.assertEqual([row['origin_position'] for row in parsed], [0, 0, 0])
                for field in INPUTS:
                    with self.subTest(arch=arch, kind=kind, field=field):
                        self.rejected(changed([a, r, end], 1, **{field: r[1][field] + 1}), arch)
                for fields in ({'old_wait': 0}, {'old_wait': 2}, {'wait': 1}, {'epoch': 2},
                               {'kind': 'timed' if kind == 'suspend' else 'suspend'}, {'staged': 1}, {'cause': 'delivery'}):
                    with self.subTest(arch=arch, fields=fields):
                        self.rejected(changed([a, r, end], 1, **fields), arch)

    def test_suspend_staging_commit_and_delayed_rearm(self):
        for arch in ARCHES:
            signal = signals(arch)[0]
            a = arm(arch, kind='suspend')
            c = complete(a, outcome='eintr', signal=signal)
            self.accepted([a, c, commit(a, signal)], arch)
            # Pending selection can change before deferred frame publication.
            self.accepted([a, c, commit(a, signals(arch)[2])], arch)
            r = rearm(a, cause='delivery', staged=1)
            rr = rearm(r, staged=1)
            cc = complete(rr, outcome='eintr', signal=signal)
            self.accepted([a, c, r, rr, cc, commit(rr, signal)], arch)
            self.accepted([a, c, r, complete(r, outcome='cancelled')], arch)
            self.accepted([a, c, retire(a, staged=1, cause='group')], arch)
            for index, bad in enumerate(([a, c], [a, commit(a, signal)], [a, c, c, commit(a, signal)],
                                         [a, c, retire(a, staged=0)], [a, c, rearm(a), retire(a)],
                                         [a, c, r, commit(r, signal)])):
                with self.subTest(arch=arch, case=index):
                    self.rejected(bad, arch)
            for forbidden in (9, 23 if arch.startswith('mips') else 19, signals(arch)[1]):
                with self.subTest(arch=arch, signal=forbidden):
                    self.rejected([a, c, commit(a, forbidden)], arch)

    def test_exec_batch_counts_and_cleanup(self):
        for arch in ARCHES:
            a = arm(arch, pid=10, tid=10)
            b = arm(arch, pid=10, tid=11, live=2)
            other = arm(arch, pid=20, tid=20, live=3)
            ra, rb = retire(a, cause='exec', live=3), retire(b, cause='exec', live=3)
            ending = complete(other)
            self.accepted([a, b, other, ra, rb, b'new image for retired process', ending], arch)
            for index, bad in enumerate(([a, b, other, ra, ending],
                                         [a, b, other, ra, b'peer guest line inside atomic batch', rb, ending],
                                         [a, b, other, ra, b'', rb, ending],
                                         [a, b, other, ra, retire(b, cause='exec', live=2), ending],
                                         [a, b, other, ra, retire(other, cause='exec', live=3), rb])):
                with self.subTest(arch=arch, case=index):
                    self.rejected(bad, arch)
            self.accepted([a, b, retire(a, cause='group', live=2), retire(b, cause='group')], arch)

    def test_retirement_resets_exposed_lifetime_not_global_epoch(self):
        for arch in ARCHES:
            for cause in ('exec', 'thread', 'group'):
                a = arm(arch)
                # A replacement lease/TCB may restart tickets and use another slot's epoch.
                with self.subTest(arch=arch, cause=cause):
                    self.accepted([a, retire(a, cause=cause), b'explicit retired image/lease boundary', a, complete(a)], arch)
            a = arm(arch)
            b = arm(arch, epoch=2, wait=2)
            self.accepted([a, complete(a), b, complete(b)], arch)
            # Exec can move a retained TCB to a different entry-stack slot;
            # scheduler generations survive even when the slot epoch decreases.
            earlier = arm(arch, epoch=100, wait=10)
            later = arm(arch, epoch=1, wait=12)
            self.accepted([earlier, complete(earlier), later, complete(later)], arch)
            # Same lease history without retirement cannot reuse a scheduler ticket.
            for epoch, wait in ((1, 1), (2, 1)):
                b = arm(arch, epoch=epoch, wait=wait)
                with self.subTest(arch=arch, epoch=epoch, wait=wait):
                    self.rejected([a, complete(a), b, complete(b)], arch)
            for first, last in ((5, 4), (MAX_U64, 1)):
                a, b = arm(arch, wait=first), arm(arch, epoch=2, wait=last)
                with self.subTest(arch=arch, previous=first, next=last):
                    self.rejected([a, complete(a), b, complete(b)], arch)
            a = arm(arch)
            r = rearm(a, wait=3)
            b = arm(arch, epoch=2, wait=2)
            with self.subTest(arch=arch, previous='rearmed'):
                self.rejected([a, r, complete(r), b, complete(b)], arch)
            a = arm(arch, kind='suspend', wait=3)
            signal = signals(arch)[0]
            with self.subTest(arch=arch, previous='committed'):
                self.rejected([a, complete(a, outcome='eintr', signal=signal), commit(a, signal), b, complete(b)], arch)

    def test_time_abi_and_input_span_boundaries(self):
        for arch in ARCHES:
            forms = (False, True) if arch in ('i386', 'arm32', 'mips', 'ppc') else (False,)
            for time64 in forms:
                a = arm(arch, time64=time64)
                low, high = bounds(arch)
                size = 16 if arch not in WORD32 or time64 or arch == 'rv32' else 8
                a[1]['set'] = high - a[1]['sigsetsize']
                a[1]['timeout'] = high - size
                a[1]['info'] = high - 128
                self.accepted([a, complete(a)], arch)
                for key, value in (('set', high - a[1]['sigsetsize'] + 1), ('set', 0),
                                   ('timeout', high - size + 1), ('timeout', low - 1),
                                   ('syscall', 9999), ('sigsetsize', a[1]['sigsetsize'] + 1),
                                   ('deadline', MAX_TIME + 1)):
                    b = changed([a], 0, **{key: value})[0]
                    with self.subTest(arch=arch, time64=time64, key=key):
                        self.rejected([b, complete(b, now=MAX_U64)], arch)
                b = copy.deepcopy(a)
                b[1]['deadline'] = MAX_TIME
                self.accepted([b, complete(b, outcome='timeout', now=MAX_TIME)], arch)
            if arch == 'rv32':
                a = arm(arch)
                a[1]['syscall'] = 137  # No legacy time32 timedwait on rv32.
                self.rejected([a, complete(a)], arch)

    def test_copyout_is_not_admission_and_checks_full_success_span(self):
        for arch in ARCHES:
            maximum = (1 << (32 if arch in WORD32 else 64)) - 1
            for pointer in (1, bounds(arch)[1] - 1, maximum):
                a = arm(arch)
                a[1]['info'] = pointer
                with self.subTest(arch=arch, pointer=pointer):
                    self.accepted([a, complete(a, outcome='efault')], arch)
                    self.accepted([a, complete(a, outcome='timeout', now=1000)], arch)
                    self.rejected([a, complete(a)], arch)
            a = arm(arch)
            a[1]['info'] = 0
            self.rejected([a, complete(a, outcome='efault')], arch)
            if arch in WORD32:
                a[1]['info'] = 1 << 32
                self.rejected([a, complete(a, outcome='efault')], arch)

    def test_target_instruction_alignment(self):
        for arch in ARCHES:
            a = arm(arch)
            alignment = 1 if arch in ('i386', 'x86_64') else 2 if arch in ('arm32', 'rv32', 'rv64') else 4
            a[1]['pc'] += alignment
            with self.subTest(arch=arch):
                self.accepted([a, complete(a)], arch)
            for bad in (0, bounds(arch)[0] - 1, bounds(arch)[1]):
                b = changed([a], 0, pc=bad)[0]
                self.rejected([b, complete(b)], arch)
            if alignment > 1:
                b = changed([a], 0, pc=a[1]['pc'] + 1)[0]
                self.rejected([b, complete(b)], arch)

    def test_sender_identity_and_owner_widths(self):
        for arch in ARCHES:
            for field in ('pid', 'tid'):
                for value in (0, MAX_ID + 1, MAX_U64):
                    a = arm(arch)
                    a[1][field] = value
                    with self.subTest(arch=arch, field=field, value=value):
                        self.rejected([a, complete(a)], arch)
            a = arm(arch, pid=MAX_ID, tid=MAX_ID)
            self.accepted([a, complete(a, sender_pid=MAX_ID, sender_uid=0xffffffff)], arch)
            for field, value in (('sender_pid', MAX_ID + 1), ('sender_uid', 1 << 32), ('code', -(1 << 31) - 1)):
                with self.subTest(arch=arch, field=field):
                    self.rejected(changed([a, complete(a)], 1, **{field: value}), arch)
            a = arm(arch, pid=10, tid=11)
            b = arm(arch, pid=20, tid=11, live=2)
            self.rejected([a, b, complete(a, live=1), complete(b)], arch)

    def test_masks_and_signal_selection(self):
        for arch in ARCHES:
            a = arm(arch)
            for mask in ('wanted', 'original', 'active'):
                for forbidden in (9, 23 if arch.startswith('mips') else 19):
                    with self.subTest(arch=arch, mask=mask, forbidden=forbidden):
                        self.rejected(changed([a, complete(a)], 0, **{mask+'0': a[1][mask+'0'] | (1 << (forbidden-1))}), arch)
            for field in ('wanted1', 'original1', 'active1'):
                if not arch.startswith('mips'):
                    self.rejected(changed([a, complete(a)], 0, **{field: 1}), arch)
            for signal in (0, 9, 23 if arch.startswith('mips') else 19, 129 if arch.startswith('mips') else 65, signals(arch)[1]):
                self.rejected([a, complete(a, signal=signal)], arch)
            self.rejected([a, complete(a, outcome='eintr', signal=signals(arch)[0])], arch)
            self.rejected([a, complete(a, outcome='eintr', signal=signals(arch)[1])], arch)
            if arch.startswith('mips'):
                high = arm(arch, signal=100)
                self.accepted([high, complete(high, signal=100)], arch)

    def test_completion_ownership_publication_and_timer_priority(self):
        for arch in ARCHES:
            a = arm(arch)
            rows = [a, complete(a)]
            for fields in ({'epoch': 2}, {'wait': 2}, {'pid': 20}, {'tid': 20}, {'info': 0},
                           {'deadline': 999}, {'result': 0}, {'published': 0}, {'staged': 1},
                           {'consumed': 0}, {'live': 1}):
                with self.subTest(arch=arch, fields=fields):
                    self.rejected(changed(rows, 1, **fields), arch)
            for outcome in ('timeout', 'cancelled'):
                c = complete(a, outcome=outcome, now=1000)
                for key in ('signal', 'code', 'sender_pid', 'sender_uid'):
                    self.rejected(changed([a, c], 1, **{key: 1}), arch)
            self.rejected([a, complete(a, outcome='timeout', now=999)], arch)
            for now in (1000, 1001):
                self.rejected([a, complete(a, outcome='eintr', signal=signals(arch)[2], now=now)], arch)
            infinite = arm(arch, finite=False)
            self.rejected([infinite, complete(infinite, outcome='timeout', now=MAX_U64)], arch)

    def test_missing_duplicate_unknown_and_unrelated_records(self):
        for arch in ARCHES:
            a = arm(arch)
            c = complete(a)
            for rows in ([a], [c], [a, a, c], [a, c, c], [a, retire(a), c]):
                self.rejected(rows, arch)
            self.accepted([b'hello world', b'OK_UNRELATED_EVENT result=0', a, c, b'oksh> '], arch)
            for malformed in (wire(a) + b' extra=1', wire(a) + b' pid=10', wire(a) + b' ',
                              wire(a).replace(b' epoch=1', b' epoch=-1'), b'OK_NATIVE_SIGNAL_WAIT_UNKNOWN x=1',
                              b'prefix ' + wire(a), b'OK_NATIVE_SIGNAL_WAIT_'):
                with self.subTest(arch=arch, malformed=malformed):
                    self.rejected([malformed], arch)
            # Every field and record name is required; no ignored partial evidence.
            for token in wire(a).split():
                self.rejected([wire(a).replace(token, b'', 1), c], arch)
            with self.assertRaises(ValueError):
                ledger.native_events(stream([a]) + wire(c), arch)
            self.assertEqual(len(ledger.native_events(stream([a, c]) + b'oksh> ', arch)), 2)
        with self.assertRaises(ValueError):
            ledger.native_events(b'', 'foreign')
        for arch in ARCHES:
            self.assertEqual(ledger.native_events(b'ordinary text\n', arch), [])
            self.assertEqual(ledger.native_events(b'unterminated ordinary prompt> ', arch), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)

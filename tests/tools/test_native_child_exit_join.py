"""Adverse ordering/ownership joins; no guest or kernel execution is performed."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from native_child_exit_guest import guest_events, probe_spec
from native_child_exit_join import validate_join, validate_native_pipeline
from test_native_child_exit_guest import fixture, ARCHES


def exit_line(child, parent, tid, epoch, status=0, notify=0, automatic=0, merged=0):
    code, value = (2, 15) if status == 15 else (1, status >> 8)
    return (f'OK_NATIVE_CHILD_EXIT child={child} parent={parent} parent_tid={tid} parent_epoch={epoch} '
            f'uid=1000 code={code} status={value} wait_code={code} wait_status={value} published=1 '
            f'notify={notify} queued={notify-merged} coalesced={merged} autoreap={automatic}\n').encode()


REAP = b'OK_NATIVE_CHILD_REAP count=1 failed_pid=0 failed_after_erase=0 success=1\n'


def joined_fixture(arch='x86_64'):
    lines = [b'OK_NATIVE_CHILD_WAIT pid=99 tid=99 request=1 wait=1 selector=5 output=4096 format=status outcome=arm result=-11 live=2\n']
    slots = {}
    for line in fixture(arch).splitlines(keepends=True):
        lines.append(line)
        if line.startswith(b'CHILD_EXIT_CASE '):
            row = dict(word.split('=') for word in line.decode().split()[1:])
            case, pid = int(row['case']), int(row['pid'])
            slots = {}
        elif line.startswith(b'CHILD_EXIT_EVENT '):
            row = dict(word.split('=') for word in line.decode().split()[1:])
            slot, child = int(row['a']), int(row['b'])
            if row['op'] == 'SPAWN': slots[slot] = (child, int(row['c']))
            if row['op'] == 'RELEASE' or row['op'] == 'SPAWN' and case == 16 and slot == 1:
                child, status = slots[slot]
                # Explicit12-row oracle, independent of collector branching.
                policy = ((0,0),(0,1),(1,0),(1,1),(0,1),(0,1),(0,1),(0,1),(1,0),(1,1),(1,0),(1,1))
                notify, automatic = policy[case] if case < 12 else (1, 0)
                merged = int(case == 14 or (case, slot) in ((13,1),(16,1)))
                lines.append(exit_line(child,pid,pid,1000+case,status,notify,automatic,merged))
                if automatic: lines.append(REAP)
        elif line.startswith(b'CHILD_EXIT_DONE '):
            lines.append(exit_line(pid,5,5,9))
        elif line.startswith(b'CHILD_EXIT_PASS '):
            lines.append(exit_line(5,99,0,0))
            lines.append(b'OK_NATIVE_CHILD_WAIT pid=99 tid=99 request=1 wait=1 selector=5 output=4096 format=status outcome=complete result=5 live=1\n')
    return b''.join(lines)


def check(span, arch='x86_64'):
    guest_events(span, arch)
    return validate_join(span, arch, probe_spec(arch)[0], 99)


class JoinTests(unittest.TestCase):
    def test_complete_all_profiles(self):
        for arch in ARCHES:
            for crlf in (False, True):
                span = joined_fixture(arch)
                if crlf: span = span.replace(b'\n', b'\r\n')
                result = check(span, arch)
                self.assertEqual(result['completions'],40)
                self.assertEqual(result['automatic_detaches'],8)
                self.assertEqual(result['physical_reaps'],8)
                self.assertEqual(result['coalesced'],3)

    def test_each_completion_must_be_unique_and_match_real_owner(self):
        span = joined_fixture()
        exits = [line for line in span.splitlines(keepends=True) if line.startswith(b'OK_NATIVE_CHILD_EXIT ')]
        for line in exits:
            fields = dict(word.split(b'=') for word in line.split()[1:])
            for bad in (b'', line*2, line.replace(b'uid=1000',b'uid=1001'),
                        line.replace(b'parent_tid='+fields[b'parent_tid'],b'parent_tid=999'),
                        line.replace(b'wait_status='+fields[b'wait_status'],b'wait_status=98')):
                with self.subTest(line=line,bad=bad),self.assertRaises(ValueError):
                    check(span.replace(line,bad,1))

    def test_notification_cannot_precede_child_completion(self):
        span = joined_fixture()
        lines = span.splitlines(keepends=True)
        # Killed case12 has INFO before WAIT, so WAIT-only joins miss this move.
        event = next(line for line in lines if line.startswith(b'OK_NATIVE_CHILD_EXIT child=137 '))
        info = next(line for line in lines if line.startswith(b'CHILD_EXIT_INFO ') and b'case=12 ' in line)
        moved = span.replace(event,b'',1).replace(info,info+event,1)
        with self.assertRaisesRegex(ValueError,'siginfo before completion'): check(moved)
        # Case15's first pending observation proves exit before action changes.
        event = next(line for line in lines if line.startswith(b'OK_NATIVE_CHILD_EXIT child=146 '))
        pending = next(line for line in lines if b'case=15 ' in line and b'op=PENDING a=1 ' in line)
        moved = span.replace(event,b'',1).replace(pending,pending+event,1)
        with self.assertRaisesRegex(ValueError,'pending notification before'): check(moved)

    def test_physical_reap_cannot_be_missing_duplicate_or_early(self):
        span = joined_fixture()
        for bad in (span.replace(REAP,b'',1),span.replace(REAP,REAP*2,1),
                    span.replace(REAP,REAP.replace(b'count=1',b'count=2'),1),
                    REAP+span.replace(REAP,b'',1)):
            with self.assertRaises(ValueError): check(bad)
        subject = exit_line(104,103,103,1001,37<<8,0,1)
        self.assertIn(subject,span)
        with self.assertRaises(ValueError): check(span.replace(subject,subject.replace(b'autoreap=1',b'autoreap=0'),1))

    def test_shell_wait_requires_observed_live_parent_and_completed_main(self):
        span = joined_fixture()
        terminal = next(line for line in span.splitlines(keepends=True)
                        if line.startswith(b'OK_NATIVE_CHILD_WAIT ') and b'outcome=complete' in line)
        initial = exit_line(5,99,0,0)
        mutations = [
            terminal + span.replace(terminal, b'', 1),
            span.replace(initial, initial.replace(b'parent=99', b'parent=0') + REAP),
            span.replace(b'selector=5 ', b'selector=987654 ').replace(b'result=5 ', b'result=987654 '),
            span.replace(terminal, b'', 1),
            span.replace(terminal, terminal * 2, 1),
            span.replace(b'pid=99 tid=99 request=', b'pid=98 tid=98 request='),
        ]
        for bad in mutations:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                check(bad)

    def test_native_pipeline_requires_both_real_shell_owned_successful_waits(self):
        rows = []
        for request, child in ((7,90),(8,91)):
            arm = (f'OK_NATIVE_CHILD_WAIT pid=99 tid=99 request={request} wait={request} '
                   f'selector={child} output=4096 format=status outcome=arm result=-11 live=2\n').encode()
            terminal = arm.replace(b'outcome=arm result=-11 live=2',
                                   f'outcome=complete result={child} live=1'.encode())
            completion = exit_line(child,99,0,0).replace(b'uid=1000',b'uid=0').replace(b'published=1',b'published=0')
            rows.extend((arm, completion, terminal))
        span = b''.join(rows)
        for arch in ARCHES:
            validate_native_pipeline(span, arch, 99)
            for immediate in (span.replace(rows[0],b'').replace(rows[2],b''), rows[1]+rows[4]):
                validate_native_pipeline(immediate, arch, 99, require_two_pairs=False)
                for before, after in ((b'parent=99 ',b'parent=987651 '),
                        (b'uid=0 ',b'uid=1 '),(b'published=0 ',b'published=1 '),
                        (b'wait_status=0 ',b'wait_status=1 ')):
                    with self.assertRaises(ValueError):
                        validate_native_pipeline(immediate.replace(before,after),arch,99,require_two_pairs=False)
            for bad in (span.replace(rows[0],b''),span.replace(rows[1],b''),
                    span.replace(b'tid=99 ',b'tid=12345 '),
                    span.replace(b'outcome=complete result=90',b'outcome=cancelled result=-125')):
                with self.assertRaises(ValueError):
                    validate_native_pipeline(bad,arch,99,require_two_pairs=False)
            mutations = [
                span.replace(rows[2], rows[2].replace(b'outcome=complete result=90', b'outcome=cancelled result=-125')),
                span.replace(b'tid=99 ', b'tid=987650 '),
                span.replace(rows[0],b'').replace(rows[2],b''),
                span.replace(rows[1],b''),
                span.replace(rows[1],rows[1]*2),
                span.replace(b'parent=99 ',b'parent=987651 '),
                span.replace(b'uid=0 ',b'uid=1 '),
                span.replace(b'published=0 ',b'published=1 '),
                span.replace(b'wait_status=0 ',b'wait_status=1 '),
                rows[1]+span.replace(rows[1],b'',1),
            ]
            for bad in mutations:
                with self.subTest(arch=arch, bad=bad), self.assertRaises(ValueError):
                    validate_native_pipeline(bad, arch, 99)


if __name__ == '__main__': unittest.main()

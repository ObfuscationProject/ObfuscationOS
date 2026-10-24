"""Hosted original-stream pressure lifetime controls; no guest execution."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from native_child_exit_events import EXIT_FIELDS, native_events as exit_events
from native_child_exit_pressure_guest import guest_events
from native_child_exit_pressure_join import validate_joins
from native_pipe_io_events import native_events as pipe_events
from test_native_child_exit_pressure_guest import fixture, replace_field
from native_child_exit_guest import ARCHES, expected_info


def exited(pid, status, wave=0, first=True, parent=100, epoch=7, published=True):
    notify = int(wave != 1 and bool(epoch) and published)
    fields = dict(child=pid, parent=parent, parent_tid=parent if epoch else 0,
                  parent_epoch=epoch, uid=1000, code=1, status=status,
                  wait_code=1, wait_status=status, published=int(published),
                  notify=notify, queued=int(notify and first), coalesced=int(notify and not first),
                  autoreap=int(wave != 0 and bool(epoch) and published))
    return b'OK_NATIVE_CHILD_EXIT ' + b' '.join((name + '=' + str(fields[name])).encode() for name in EXIT_FIELDS)


def pipe(pid, live, arch, complete=False, pipe_id=1, ticket=1, stage='arm'):
    output = 0x10010000 if arch in ('arm32', 'aarch64') else 0x40010000
    prefix = 'OK_NATIVE_PIPE_READ_COMPLETE' if complete else 'OK_NATIVE_PIPE_READ_WAIT'
    terminal = 'result=1 outcome=ready pinned=0' if complete else 'stage='+stage
    return (f'{prefix} pid={pid} tid={pid} wait={ticket} request=1 output={output} '
            f'fd=3 description={40+pipe_id} pipe={pipe_id} bytes=1 {terminal} live={live}').encode()


def transcript(arch='x86_64', rollback=False, recovery_blocked=False, per_child_reap=False, rearms=False):
    raw = fixture(arch)
    observed = guest_events(raw, arch)
    after = {}

    def add(position, *rows):
        after.setdefault(position, []).extend(rows)

    for wave in observed['waves']:
        index = wave['wave']
        for live, spawn in enumerate(wave['spawns'], 1):
            add(spawn['position'], pipe(spawn['a'], live, arch, pipe_id=index+1))
            if rearms:
                add(spawn['position'], pipe(spawn['a'], live, arch, pipe_id=index+1, ticket=2, stage='rearm'))
        pids = list(reversed(wave['children']))
        for order, pid in enumerate(pids):
            add(wave['release']['position'], pipe(pid, len(pids)-order-1, arch, True, index+1, ticket=2 if rearms else 1),
                exited(pid, 37, index, order == 0))
            if index and per_child_reap:
                add(wave['release']['position'], b'OK_NATIVE_CHILD_REAP count=1 failed_pid=0 failed_after_erase=0 success=1')
        if index and not per_child_reap:
            add(wave['release']['position'], f'OK_NATIVE_CHILD_REAP count={len(pids)} failed_pid=0 failed_after_erase=0 success=1'.encode())
        if rollback:
            failed = next(row for row in wave['failures'] if row['errno'] == 12)
            add(failed['begin']['position'], exited(50000+index, 127, epoch=0, published=False))
        recovery = wave['recovery']
        if recovery_blocked:
            add(recovery['spawn']['position'], pipe(recovery['pid'], 1, arch, pipe_id=index+4))
            add(recovery['release']['position'], pipe(recovery['pid'], 0, arch, True, index+4))
        add(recovery['release']['position'], exited(recovery['pid'], 39))
    add(observed['success']['position'], exited(observed['pid'], 0, parent=57, epoch=0))
    lines = []
    for position, line in enumerate(raw.splitlines()):
        lines.append(line)
        lines.extend(after.get(position, []))
    return b'\n'.join(lines) + b'\n'


def validate(data, arch='x86_64'):
    return validate_joins(guest_events(data, arch), exit_events(data, arch), pipe_events(data, arch), 57)


class PressureJoinTests(unittest.TestCase):
    def test_rearm_keeps_one_original_owned_read_until_single_completion(self):
        for arch in ARCHES:
            data = transcript(arch, rearms=True)
            self.assertEqual(validate(data, arch)['blocked_pressure_reads'], 12)
            lines = data.splitlines(True)
            at = next(i for i, row in enumerate(lines) if b'stage=rearm' in row)
            for key, value in (('request', 2), ('wait', 1), ('stage', 'arm'), ('fd', 4)):
                changed = lines[:]; changed[at] = replace_field(lines[at], key, value)
                with self.subTest(arch=arch, key=key), self.assertRaises(ValueError):
                    validate(b''.join(changed), arch)

    def test_ten_profiles_blocked_reads_batch_reaps_and_internal_rollback(self):
        for arch in ARCHES:
            for rollback, recovery, batches in ((False, False, False), (True, False, True), (True, True, False)):
                with self.subTest(arch=arch, rollback=rollback, recovery=recovery, per_child=batches):
                    data = transcript(arch, rollback, recovery, batches)
                    got = validate(data, arch)
                    self.assertEqual(got['published_completions'], 16)
                    self.assertEqual(got['rollback_completions'], 3 if rollback else 0)
                    self.assertEqual(got['automatic_physical_reaps'], 9)
                    self.assertEqual(got['blocked_pressure_reads'], 12)
                    self.assertEqual(got['minimum_entry_leases'], 16)
                    self.assertFalse(got['global_process_exhaustion'])
                    self.assertEqual(validate(data.replace(b'\n', b'\r\n'), arch), got)

    def test_published_completions_required_and_all_records_unique(self):
        for arch in ARCHES:
            rows = transcript(arch, True).splitlines(True)
            for position, row in enumerate(rows):
                if not row.startswith(b'OK_NATIVE_CHILD_EXIT '): continue
                removed = b''.join(rows[:position]+rows[position+1:])
                if b'published=0' in row:
                    self.assertEqual(validate(removed, arch)['rollback_completions'], 2)
                else:
                    with self.subTest(arch=arch, position=position), self.assertRaises(ValueError):
                        validate(removed, arch)
                with self.subTest(arch=arch, duplicate=position), self.assertRaises(ValueError):
                    validate(b''.join(rows[:position]+[row,row]+rows[position+1:]), arch)

    def test_owner_cause_policy_epoch_and_safe_reap_are_bound(self):
        for arch in ARCHES:
            rows = transcript(arch).splitlines(True)
            target = next(i for i,r in enumerate(rows) if r.startswith(b'OK_NATIVE_CHILD_EXIT child=103 '))
            for key, value in [('parent', 99), ('parent_tid', 101), ('parent_epoch', 8), ('uid', 1001),
                               ('status', 36), ('wait_status', 38), ('code', 2), ('wait_code', 2),
                               ('published', 0), ('notify', 0), ('queued', 0), ('coalesced', 1), ('autoreap', 1)]:
                changed = rows[:]; changed[target] = replace_field(rows[target], key, value)
                with self.subTest(arch=arch, key=key), self.assertRaises(ValueError):
                    validate(b''.join(changed), arch)
            for position, row in enumerate(rows):
                if row.startswith(b'OK_NATIVE_CHILD_REAP '):
                    for replacement in (b'', replace_field(row, 'count', 1), replace_field(row, 'success', 0)):
                        with self.subTest(arch=arch, reap=position), self.assertRaises(ValueError):
                            validate(b''.join(rows[:position]+[replacement]+rows[position+1:]), arch)

    def test_actual_queued_sender_must_match_complete_guest_payload(self):
        for arch in ARCHES:
            data = transcript(arch)
            observed = guest_events(data, arch)
            row = observed['waves'][0]['notification']
            other = observed['waves'][0]['children'][0]
            line = replace_field(row['line'], 'child', other)
            line = replace_field(line, 'hex', expected_info(arch, 1, other, 1000, 37).hex())
            changed = data.replace(row['line'], line)
            guest_events(changed, arch)
            with self.assertRaisesRegex(ValueError, 'actual queued child'):
                validate(changed, arch)

    def test_failure_window_cannot_hide_published_or_wrong_rollback(self):
        for arch in ARCHES:
            data = transcript(arch, True)
            rows = data.splitlines(True)
            position = next(i for i,r in enumerate(rows) if r.startswith(b'OK_NATIVE_CHILD_EXIT child=50000 '))
            for key, value in [('published', 1), ('parent', 99), ('status', 126), ('wait_status', 126), ('uid', 0)]:
                changed = rows[:]; changed[position] = replace_field(rows[position], key, value)
                with self.subTest(arch=arch, key=key), self.assertRaises(ValueError):
                    validate(b''.join(changed), arch)
            guest = guest_events(data, arch)
            failure = guest['waves'][0]['failures'][1]
            changed = data.replace(failure['end']['line'], replace_field(failure['end']['line'], 'b', 11))
            guest_events(changed, arch)
            with self.assertRaisesRegex(ValueError, 'unqualified rollback'):
                validate(changed, arch)
            row = rows.pop(position)
            rows.insert(0, row)
            with self.assertRaisesRegex(ValueError, 'unobserved or unassigned'):
                validate(b''.join(rows), arch)

    def test_join_requires_actual_blocking_and_original_causal_positions(self):
        # These are typed-view unit mutations, distinct from full-stream checks.
        data = transcript()
        guest, lifecycle, reads = guest_events(data, 'x86_64'), exit_events(data, 'x86_64'), pipe_events(data, 'x86_64')
        pid = guest['waves'][0]['children'][0]
        with self.assertRaisesRegex(ValueError, 'lacks actual blocked read'):
            validate_joins(guest, lifecycle, [row for row in reads if row['pid'] != pid], 57)
        for row in reads:
            if row['pid'] == pid and row['event'] == 'WAIT':
                row['position'] = guest['waves'][0]['release']['position'] + 1
        with self.assertRaisesRegex(ValueError, 'not armed before release'):
            validate_joins(guest, lifecycle, reads, 57)
        reads = pipe_events(data, 'x86_64')
        for row in lifecycle:
            if row.get('child') == pid: row['position'] = guest['waves'][0]['release']['position'] - 1
        with self.assertRaisesRegex(ValueError, 'outside release/wait'):
            validate_joins(guest, lifecycle, reads, 57)


if __name__ == '__main__': unittest.main()

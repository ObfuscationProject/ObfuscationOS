"""Synthetic adversarial reader controls; these do not execute a native guest."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from native_console_lease_evidence import key_hash, validate_console_lease
from qualify_native_console_lease import archive_only_command

KEY = b'abcdef0123456789abcdef0123456789'
DENIED = 'read=EACCES readv=EACCES dup=EACCES poll=ERR_HUP controls=EACCES'


def event(kind, service, pid, generation=1, status=0):
    return (f'NATIVE_PID1 scope=hardware profile=dependency-graph-v1 event={kind} '
            f'service={service} pid={pid} generation={generation} time_ms=1 next_ms=0 errno=0 status={status}')


def sample():
    lines = ['OK_STORAGE source=archive reason=no-supported-device', event('launch', 'guard', 2),
        'NATIVE_CONSOLE_GUARD_START pid=2 parent=1 uid=0 gid=0 epoch=0', event('notify-ready', 'guard', 2),
        event('launch', 'console', 3), 'NATIVE_CONSOLE_LEADER generation=1 pid=3 parent=1 epoch=1',
        event('simple-ready', 'console', 3)]
    roles = ('read', 'readv', 'poll')
    lines += [f'NATIVE_CONSOLE_WAIT kind={role} pid={pid} parent=3 epoch=1' for role, pid in zip(roles, (4, 5, 6))]
    lines += ['NATIVE_CONSOLE_FIRST_EXIT pid=3 epoch=1 read_pid=4 readv_pid=5 poll_pid=6 status=37']
    lines += [f'NATIVE_CONSOLE_REVOKED kind={role} pid={pid} parent=1 epoch=1 initial=' +
              ('ERR_HUP' if role == 'poll' else 'EACCES') for role, pid in zip(roles, (4, 5, 6))]
    lines += [event('reap', 'console', 3, status=37), event('restart', 'console', 0),
        event('launch', 'console', 7, 2), 'NATIVE_CONSOLE_LEADER generation=2 pid=7 parent=1 epoch=2',
        event('simple-ready', 'console', 7, 2), 'NATIVE_CONSOLE_PROMPT generation=2 pid=7 epoch=2 bytes=32',
        'NATIVE_CONSOLE_BUFFERED pid=7 epoch=2 ready=POLLIN',
        'NATIVE_CONSOLE_WINDOW role=guard pid=2 epoch=0 control_epoch=2 ' + DENIED]
    lines += [f'NATIVE_CONSOLE_WINDOW role={role} pid={pid} epoch=1 control_epoch=2 ' + DENIED for role, pid in zip(roles, (4, 5, 6))]
    lines += [f'NATIVE_CONSOLE_READ_PASS pid=7 epoch=2 bytes=32 readv=8 read=24 hash={key_hash(KEY)}']
    lines += [f'NATIVE_CONSOLE_OLD_PASS kind={role} pid={pid} parent=1 epoch=1 attempts=25 ' + DENIED
              for role, pid in zip(roles, (4, 5, 6))]
    lines += ['NATIVE_CONSOLE_GUARD_PASS pid=2 attempts=30 ' + DENIED,
              'NATIVE_CONSOLE_PASS pid=7 epoch=2 guard=live old_children=3 key=exact']
    lines += [event('other-child', 'none', pid, 0, status) for pid, status in ((4, 10496), (5, 10752), (6, 11008))]
    return ('\n'.join(lines) + '\n').encode()


class ConsoleLeaseEvidenceTests(unittest.TestCase):
    def test_complete_causal_records(self):
        record = validate_console_lease(sample().replace(b'\n', b'\r\n'), KEY)
        self.assertEqual(record['epochs'], [1, 2])
        self.assertEqual(record['old_child_pids'], [4, 5, 6])
        self.assertTrue(record['actual_child_reaps'])
        self.assertFalse(record['account_authentication'])
        self.assertFalse(record['model_test'])

    def test_missing_duplicate_malformed_or_unknown_probe_records(self):
        for line in sample().splitlines():
            if b'NATIVE_CONSOLE_' not in line:
                continue
            for changed in (sample().replace(line, b''), sample() + line + b'\n',
                            sample().replace(line, b'banner ' + line)):
                with self.subTest(line=line), self.assertRaises(ValueError):
                    validate_console_lease(changed, KEY)
        with self.assertRaises(ValueError):
            validate_console_lease(sample() + b'NATIVE_CONSOLE_UNKNOWN pass=1\n', KEY)

    def test_identity_authority_epoch_result_and_real_reap_refusals(self):
        mutations = ((b'parent=1 uid=0', b'parent=1 uid=1000'),
            (b'parent=3 epoch=1', b'parent=1 epoch=1'),
            (b'kind=read pid=4', b'kind=read pid=9'), (b'read_pid=4', b'read_pid=3'),
            (b'pid=7 epoch=2', b'pid=7 epoch=1'), (b'parent=1 epoch=2', b'parent=1 epoch=1'),
            (b'initial=EACCES', b'initial=EOF'), (b'poll=ERR_HUP', b'poll=POLLIN'),
            (b'controls=EACCES', b'controls=EINVAL'), (b'attempts=25', b'attempts=1'),
            (b'control_epoch=2', b'control_epoch=1'),
            (b'readv=8 read=24', b'readv=7 read=25'),
            (str(key_hash(KEY)).encode(), b'0'), (b'epoch=2 ready=POLLIN', b'epoch=2 ready=ERR_HUP'),
            (b'status=10496', b'status=41'), (b'status=10752', b'status=10496'),
            (b'event=other-child service=none pid=6', b'event=other-child service=none pid=7'),
            (b'service=none pid=4 generation=0', b'service=none pid=4 generation=1'),
            (b'event=reap service=console pid=3', b'event=reap service=console pid=7'),
            (b'source=archive reason=no-supported-device', b'source=ext4'))
        for before, after in mutations:
            with self.subTest(before=before), self.assertRaises(ValueError):
                validate_console_lease(sample().replace(before, after), KEY)

    def test_missing_duplicate_or_contradictory_pid1_lifecycle(self):
        for line in sample().splitlines():
            if b'NATIVE_PID1 ' not in line:
                continue
            for changed in (sample().replace(line, b''), sample() + line + b'\n',
                            sample().replace(line, line.replace(b'errno=0', b'errno=5'))):
                with self.subTest(line=line), self.assertRaises(ValueError):
                    validate_console_lease(changed, KEY)
        for extra in (event('reap', 'guard', 2), event('launch', 'console', 8, 3),
                      event('restart', 'console', 0, 2)):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_console_lease(sample() + extra.encode() + b'\n', KEY)

    def test_causal_order_rejected(self):
        base = sample().splitlines()
        pairs = ((b'NATIVE_CONSOLE_BUFFERED', b'NATIVE_CONSOLE_READ_PASS'),
                 (b'NATIVE_CONSOLE_FIRST_EXIT', b'NATIVE_CONSOLE_WAIT kind=read '),
                 (b'NATIVE_CONSOLE_WINDOW role=read ', b'NATIVE_CONSOLE_READ_PASS'),
                 (b'NATIVE_CONSOLE_OLD_PASS kind=poll', b'event=other-child service=none pid=6'),
                 (b'NATIVE_CONSOLE_GUARD_PASS', b'NATIVE_CONSOLE_PASS '),
                 (b'event=reap service=console', b'event=launch service=console pid=7'))
        for first, second in pairs:
            changed = list(base)
            a = next(i for i, line in enumerate(changed) if first in line)
            b = next(i for i, line in enumerate(changed) if second in line)
            changed[a], changed[b] = changed[b], changed[a]
            with self.subTest(pair=(first, second)), self.assertRaises(ValueError):
                validate_console_lease(b'\n'.join(changed), KEY)

    def test_raw_or_partial_echo_failures_and_bad_input_refused(self):
        for extra in (KEY, KEY[3:11], b'NATIVE_CONSOLE_FAIL pid=7 code=12', b'Kernel panic', b'event=fatal-hold'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                validate_console_lease(sample() + extra + b'\n', KEY)
        for key in (b'', KEY[:-1], KEY + b'0', KEY.upper(), b'x' * 32):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_console_lease(sample(), key)

    def test_archive_qemu_has_no_distribution_disk(self):
        command = archive_only_command(Path('/usr/bin/qemu-system-x86_64'), 'x86_64', Path('/tmp/kernel.bin'))
        self.assertFalse(any('fsdisk' in arg or 'virtio-blk' in arg or 'rootfs.img' in arg for arg in command))


if __name__ == '__main__':
    unittest.main()

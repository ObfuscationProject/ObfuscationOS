"""Synthetic reader controls; these are not native execution evidence."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from native_archive_permissions_evidence import PASS, validate_archive_permissions


def event(kind, service, pid):
    return (f'NATIVE_PID1 scope=hardware profile=dependency-graph-v1 event={kind} '
            f'service={service} pid={pid} generation=1 time_ms=1 next_ms=0 errno=0 status=0')


def sample():
    return '\n'.join(['OK_STORAGE source=archive reason=no-supported-device',
        event('launch', 'archive', 2),
        'NATIVE_ARCHIVE_METADATA pid=2 parent=1 tmp=01777 sticky=01777 sgid=02777 imported=0755 regular=0444 uid=0 gid=0',
        'NATIVE_ARCHIVE_CREATOR uid=1000 gid=1000 sticky_file_gid=1000 sgid_file_gid=0 sgid_directory_mode=02700',
        'NATIVE_ARCHIVE_REAP child=3 uid=1000 raw_status=0',
        'NATIVE_ARCHIVE_ATTACKER uid=1001 gid=1001 foreign_unlink=EPERM tmp_unlink=EPERM own_unlink=pass',
        'NATIVE_ARCHIVE_REAP child=4 uid=1001 raw_status=0', PASS.decode(),
        event('reap', 'archive', 2), event('oneshot-ready', 'archive', 2),
        event('launch', 'console', 5), 'oksh> ']).encode()


class ArchivePermissionsEvidenceTests(unittest.TestCase):
    def test_complete_causal_records(self):
        record = validate_archive_permissions(sample().replace(b'\n', b'\r\n'))
        self.assertEqual(record['child_pids'], [3, 4])
        self.assertTrue(record['archive_root'])

    def test_wrong_root_metadata_mode_and_result_refused(self):
        for before, after in ((b'source=archive reason=no-supported-device', b'source=ext4'),
                              (b'tmp=01777', b'tmp=0777'), (b'imported=0755', b'imported=02755'),
                              (b'uid=0 gid=0', b'uid=1000 gid=1000'),
                              (b'foreign_unlink=EPERM', b'foreign_unlink=pass'),
                              (b'sgid_file_gid=0', b'sgid_file_gid=1000'),
                              (b'raw_status=0', b'raw_status=256')):
            with self.subTest(before=before), self.assertRaises(ValueError):
                validate_archive_permissions(sample().replace(before, after))

    def test_missing_duplicate_and_malformed_records_refused(self):
        for line in sample().splitlines():
            if b'NATIVE_ARCHIVE_' not in line:
                continue
            for modified in (sample().replace(line, b''), sample() + b'\n' + line,
                             sample().replace(line, b'banner ' + line)):
                with self.subTest(line=line), self.assertRaises(ValueError):
                    validate_archive_permissions(modified)

    def test_identity_and_causal_order_refused(self):
        for before, after in ((b'child=4', b'child=3'), (b'child=3', b'child=2'),
                              (b'NATIVE_ARCHIVE_METADATA pid=2', b'NATIVE_ARCHIVE_METADATA pid=8'),
                              (b'event=reap service=archive pid=2', b'event=reap service=archive pid=7'),
                              (b'event=oneshot-ready service=archive pid=2', b'event=oneshot-ready service=archive pid=7')):
            with self.subTest(before=before), self.assertRaises(ValueError):
                validate_archive_permissions(sample().replace(before, after))
        lines = sample().splitlines()
        for first, second in ((3, 4), (5, 6), (7, 8), (9, 10)):
            changed = list(lines); changed[first], changed[second] = changed[second], changed[first]
            with self.subTest(order=(first, second)), self.assertRaises(ValueError):
                validate_archive_permissions(b'\n'.join(changed))


if __name__ == '__main__':
    unittest.main()

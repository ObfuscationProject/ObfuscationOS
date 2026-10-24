"""Parser model tests; the synthetic byte images are not mountable ext4 proof."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from ext4_timestamp_user_evidence import validate


EVENTS = [
    ('native', 'create', 'native-time', 7),
    ('native', 'write', 'native-time', 6),
    ('native', 'same-truncate', 'native-time', 6),
    ('native', 'link', 'native-time', 4),
    ('native', 'rename', 'native-renamed', 4),
    ('native', 'unlink-alias', 'native-renamed', 4),
    ('native', 'pread', 'native-renamed', 1),
    ('native', 'symlink', 'native-link', 7),
    ('native', 'readlink', 'native-link', 1),
    ('native', 'mkdir', 'native-dir', 7),
    ('musl', 'create', 'musl-time', 7),
    ('musl', 'write', 'musl-time', 6),
    ('musl', 'pwrite', 'musl-time', 6),
    ('musl', 'pread', 'musl-time', 1),
    ('musl', 'read-eof', 'musl-time', 1),
    ('musl', 'create', 'musl-truncate', 7),
    ('musl', 'open-truncate', 'musl-truncate', 6),
    ('musl', 'mkdir', 'musl-dir', 7),
    ('musl', 'getdents', 'musl-dir', 1),
    ('musl', 'getdents-eof', 'musl-dir', 1),
    ('musl', 'readlink', 'fixture-link', 1),
]
MARKERS = [
    'EXT4_TIME_NATIVE_PASS authority=uid1000 clock-set=EPERM automatic-times=enabled',
    'EXT4_TIME_MUSL_PASS authority=uid1000 clock-set=EPERM linux-stat=qualified',
    'EXT4_TIME_USER_CREDENTIALS uid=1000 euid=1000 gid=1000 egid=1000 before-entry=1',
    'EXT4_TIME_USER_STORAGE virtio=1 maintained=1 baseline=retained-fixture clock=administrator-software',
    'EXT4_TIME_USER_FIXTURE_PASS exit=0 actual-native-and-musl=1 uid=1000 linux-stat=qualified',
]
NODES = {'fixture-link': 12, 'native-renamed': 13, 'native-link': 14,
         'native-dir': 15, 'musl-time': 16, 'musl-truncate': 17, 'musl-dir': 18}
STORED_EVENTS = {'native-renamed': (6, 2, 5), 'native-link': (8, 7, 7),
                 'native-dir': (9, 9, 9), 'musl-time': (14, 12, 12),
                 'musl-truncate': (15, 16, 16), 'musl-dir': (19, 17, 17),
                 'fixture-link': (20, None, None)}
BASELINE = (1700000000, 123456789)


def inode_offset(number):
    return 5 * 1024 + (number - 1) * 256


def sample(event):
    return (2208988800, (event + 1) * 1000000 + 25000)


def serial_fixture():
    lines = MARKERS.copy()
    for index, (api, event, name, mask) in enumerate(EVENTS):
        low = (index + 1) * 1000000
        lines.append(f'EXT4_TIME_USER_EVENT api={api} event={event} path=/home/{name} '
                     f'mask={mask} before_s=2208988800 before_n={low} '
                     f'after_s=2208988800 after_n={low + 50000}')
    return '\n'.join(lines) + '\n'


def image_fixture(final):
    """Encode only the superblock, inode and directory fields read by the oracle.

    Allocation bitmaps/checksums are deliberately absent: no filesystem driver,
    fsck, guest, or hardware execution is claimed by these parser unit tests.
    """
    data = bytearray(64 * 1024)
    for offset, value in ((1024, 64), (1044, 1), (1048, 0), (1064, 64), (2056, 5)):
        struct.pack_into('<I', data, offset, value)
    struct.pack_into('<H', data, 1080, 0xef53)
    struct.pack_into('<H', data, 1112, 256)
    next_block = 32

    def put(number, mode, content, times=(BASELINE,) * 3):
        nonlocal next_block
        at = inode_offset(number)
        struct.pack_into('<HHI', data, at, mode, 1000, len(content))
        struct.pack_into('<H', data, at + 24, 1000)
        struct.pack_into('<H', data, at + 128, 16)
        for (seconds, nanos), base, extra in zip(times, (8, 16, 12), (140, 136, 132)):
            struct.pack_into('<I', data, at + base, seconds & 0xffffffff)
            # This fixture uses only positive dates in the years 2023 and 2040.
            struct.pack_into('<I', data, at + extra, (nanos << 2) | int(seconds >= 2**31))
        if mode & 0xf000 == 0xa000:
            data[at + 40:at + 40 + len(content)] = content
        else:
            struct.pack_into('<HHHH', data, at + 40, 0xf30a, bool(content), 4, 0)
            if content:
                struct.pack_into('<IHHI', data, at + 52, 0, 1, 0, next_block)
                data[next_block * 1024:next_block * 1024 + len(content)] = content
                next_block += 1

    def directory(number, parent, entries):
        block = bytearray(1024)
        items = [('.', number), ('..', parent)] + list(entries.items())
        offset = 0
        for index, (name, child) in enumerate(items):
            encoded = name.encode('ascii')
            length = (8 + len(encoded) + 3) & ~3
            if index == len(items) - 1:
                length = 1024 - offset
            struct.pack_into('<IHB', block, offset, child, length, len(encoded))
            block[offset + 8:offset + 8 + len(encoded)] = encoded
            offset += length
        return block

    put(2, 0o40755, directory(2, 2, {'home': 11}))
    put(11, 0o40777, directory(11, 2, NODES if final else {'fixture-link': 12}))
    for name, number in NODES.items():
        if not final and name != 'fixture-link':
            continue
        times = tuple(BASELINE if event is None else sample(event)
                      for event in STORED_EVENTS[name]) if final else (BASELINE,) * 3
        if name in ('fixture-link', 'native-link'):
            put(number, 0o120777, b'musl-time' if name == 'fixture-link' else b'native-renamed', times)
        elif name.endswith('-dir'):
            put(number, 0o40755, directory(number, 11, {}), times)
        else:
            content = {'native-renamed': b'native', 'musl-time': b'abZdef', 'musl-truncate': b''}[name]
            put(number, 0o100600, content, times)
    return bytes(data)


class UserTimestampEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serial = serial_fixture()
        cls.initial = image_fixture(False)
        cls.final = image_fixture(True)

    def reject(self, text=None, image=None, reason=None):
        with self.assertRaisesRegex(ValueError, reason or '.'):
            validate(self.serial if text is None else text, self.initial,
                     self.final if image is None else image)

    def changed(self, name, offset, fmt, value):
        image = bytearray(self.final)
        struct.pack_into(fmt, image, inode_offset(NODES[name]) + offset, value)
        return image

    def test_complete_evidence_and_line_endings(self):
        for text in (self.serial, self.serial.replace('\n', '\r\n')):
            with self.subTest(crlf='\r' in text):
                result = validate(text, self.initial, self.final)
                self.assertEqual(result['event_count'], 21)
                self.assertEqual(set(result['raw_nodes']), set(NODES))
                self.assertEqual(result['uid'], 1000)
                self.assertEqual(result['linux_stat'], 'qualified')
                for name, labels in STORED_EVENTS.items():
                    self.assertEqual(result['raw_nodes'][name]['times'],
                                     [BASELINE if label is None else sample(label) for label in labels])

    def test_each_marker_is_required_exactly_once(self):
        for marker in MARKERS:
            with self.subTest(marker=marker, mutation='missing'):
                self.reject(self.serial.replace(marker, ''))
            with self.subTest(marker=marker, mutation='duplicate'):
                self.reject(self.serial + marker + '\n')
        self.reject(self.serial + 'EXT4_TIME_USER_FIXTURE_FAIL\n')

    def test_sdk20_stat_markers_are_not_sdk21_evidence(self):
        legacy = self.serial.replace('linux-stat=qualified', 'linux-stat=ENOSYS', 1)
        legacy = legacy.replace('linux-stat=qualified', 'linux-stat=disabled', 1)
        self.reject(legacy, reason='missing or failed user fixture marker')

    def test_event_schema_inventory_and_order(self):
        lines = self.serial.splitlines()
        first = lines[len(MARKERS)]
        for replacement in ('', first + '\n' + first, first + ' mask=7', first + ' unknown=1',
                            first.replace('api=native', 'api=other'),
                            first.replace('mask=7', 'mask=6'), first.replace('/home/', '/tmp/')):
            with self.subTest(replacement=replacement):
                self.reject(self.serial.replace(first, replacement))
        lines[len(MARKERS)], lines[len(MARKERS) + 1] = lines[len(MARKERS) + 1], lines[len(MARKERS)]
        self.reject('\n'.join(lines))

    def test_clock_brackets_are_bounded_and_ordered(self):
        for old, new in (('before_n=1000000', 'before_n=1000000000'),
                         ('before_n=1000000', 'before_n=-1'),
                         ('before_n=1000000', 'before_n=1050001'),
                         ('before_s=2208988800', 'before_s=2147483647'),
                         ('after_s=2208988800', 'after_s=2208989101')):
            with self.subTest(new=new):
                self.reject(self.serial.replace(old, new, 1))

    def test_same_event_fields_must_use_exactly_one_sample(self):
        for name in ('native-dir', 'native-link', 'musl-time', 'musl-truncate', 'musl-dir'):
            for delta in (-4, 4):
                at = inode_offset(NODES[name]) + 132
                original = struct.unpack_from('<I', self.final, at)[0]
                with self.subTest(name=name, delta_ns=delta // 4):
                    self.reject(image=self.changed(name, 132, '<I', original + delta),
                                reason='different stored samples for one event')

    def test_different_events_may_use_distinct_samples(self):
        # An access sample differs from the earlier write/create sample.
        atime, mtime, ctime = validate(self.serial, self.initial, self.final)['raw_nodes']['musl-time']['times']
        self.assertNotEqual(atime, mtime)
        self.assertEqual(mtime, ctime)

    def test_selected_and_preserved_fields_are_checked(self):
        self.reject(image=self.changed('native-dir', 8, '<I', 0), reason='outside event bracket')
        self.reject(image=self.changed('native-dir', 140, '<I', (1000000000 << 2) | 1),
                    reason='nanosecond overflow')
        self.reject(image=self.changed('fixture-link', 12, '<I', BASELINE[0] + 1),
                    reason='untouched baseline field changed')

    def test_inode_identity_owner_layout_and_content(self):
        for offset, fmt, value, reason in ((2, '<H', 1001, 'owner mismatch'),
                                           (24, '<H', 1001, 'owner mismatch'),
                                           (120, '<H', 1, 'owner mismatch'),
                                           (122, '<H', 1, 'owner mismatch'),
                                           (128, '<H', 20, 'extra-size mismatch')):
            with self.subTest(offset=offset):
                self.reject(image=self.changed('native-dir', offset, fmt, value), reason=reason)
        self.reject(image=self.changed('native-link', 40, '<B', ord('X')), reason='symlink mismatch')
        self.reject(image=self.changed('musl-time', 4, '<I', 5), reason='final data mismatch')


if __name__ == '__main__':
    unittest.main()

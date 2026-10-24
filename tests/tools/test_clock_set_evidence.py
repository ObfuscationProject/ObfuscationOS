"""Hosted parser rejection tests; synthetic serial is not guest execution evidence."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from clock_set_evidence import setter_forms, validate_clock_set


FORMS = {
    'i386': (4, [(264, 8), (404, 16)]), 'x86_64': (8, [(227, 16)]),
    'aarch64': (8, [(112, 16)]), 'arm32': (4, [(262, 8), (404, 16)]),
    'rv64': (8, [(112, 16)]), 'rv32': (4, [(404, 16)]),
    'loongarch64': (8, [(112, 16)]), 'mips': (4, [(4262, 8), (4404, 16)]),
    'mips64': (8, [(5221, 16)]), 'ppc': (4, [(245, 8), (404, 16)]),
}


def profile_header():
    result = 'enum class Operation : u8 { clock_settime, clock_settime32, clock_settime64, count };\n'
    for arch, (word, forms) in FORMS.items():
        numbers = ['unavailable_number'] * 3
        for number, width in forms:
            index = 1 if width == 8 else 0 if word == 8 else 2
            numbers[index] = str(number) + 'U'
        result += '{"' + arch + '", ' + str(word) + ', false, 0, 0, {}, ErrorConvention::negative, false,\n'
        result += ' {' + ', '.join(numbers) + '},\n {}},\n'
    return result


def serial(arch='x86_64', authority='root'):
    root = authority == 'root'
    uid = 0 if root else 1000
    lines = ['CLOCK_SET_FIXTURE_BEGIN scope=actual-user-mode sdk-only=1',
             f'CLOCK_SET_FIXTURE_CREDENTIALS pid=16 uid={uid} euid={uid} gid={uid} egid={uid} before-user-entry=1']
    word, forms = FORMS[arch]
    for number, width in forms:
        padding = 'none' if width == 8 else 'ignored-high32' if word == 4 else 'full64'
        lines.append(f'CLOCK_SET_RAW_PASS number={number} bytes={width} authority={authority} copies=pass range=pass padding={padding}')
    if not root:
        lines += ['CLOCK_SET_NATIVE_DENIED_PASS authority=real-process errno=EPERM',
                  'CLOCK_SET_MUSL_DENIED_PASS authority=real-process errno=EPERM',
                  'CLOCK_SET_FIXTURE_PASS mode=deny exit=0 actual-native-and-musl=1']
        return '\n'.join(lines) + '\n'
    for kind in range(6):
        begin = 1_000_000_000 + kind * 200_000_000
        api = ('sleep', 'sleep', 'poll', 'select', 'poll', 'select')[kind]
        for index in range(2):
            generation = 3 + kind * 2 + index
            time = begin + 21_000_000 + index * 10_000_000
            detail = f'deadline={begin + 150_000_000} wait_generation={kind + 1}' if api == 'sleep' else 'deadline=private pending-syscall=1'
            lines.append(f'CLOCK_SET_FIXTURE_WAIT_SET api={api} pid=18 tid=24 wall_before={generation} wall_after={generation + 1} monotonic_before={time} monotonic_after={time + 1000} wait_key=0 {detail} held=1')
        lines.append(f'CLOCK_SET_WAIT_PASS kind={kind} parent=18 child={19 + kind} before={begin} first={begin + 20_000_000} last={begin + 32_000_000} after={begin + 150_000_000}')
    for label, sec, nsec in [('time32-date', 1700000001, 123456789), ('forward', 1700000101, 456789123),
                              ('backward', 1700000002, 987654321), ('post2038', 2214176523, 135791113)]:
        wall = sec * 1_000_000_000 + nsec + 21_000_000
        lines.append(f'CLOCK_SET_MUSL_SAMPLE label={label} requested={sec}:{nsec} before=3:0 after=3:1000000 read_before=3:21000000 wall={wall // 1_000_000_000}:{wall % 1_000_000_000} at=3:22000000')
    lines += ['CLOCK_SET_MUSL_EXEC_PASS inherited=software-time',
              'CLOCK_SET_MUSL_PASS setters=pass backwards=pass post2038=pass fork-exec=pass',
              'CLOCK_SET_NATIVE_WAIT pid=18 status=0',
              'CLOCK_SET_NATIVE_PASS setter=pass global-musl-child=pass monotonic=pass',
              'CLOCK_SET_FIXTURE_PASS mode=root exit=0 actual-native-and-musl=1']
    return '\n'.join(lines) + '\n'


class ClockSetEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.sdk = Path(self.temp.name)
        self.header = self.sdk / 'include/ok/abi/linux_profile_data.hpp'
        self.header.parent.mkdir(parents=True)
        self.header.write_text(profile_header())

    def validate(self, text, arch='x86_64', authority='root'):
        return validate_clock_set(text, self.sdk, arch, authority, require_fixture=True,
                                  require_held=authority == 'root')

    def test_ten_profiles_fourteen_forms_and_both_authorities(self):
        count = 0
        for arch, (_, expected) in FORMS.items():
            for authority in ('root', 'denied'):
                with self.subTest(arch=arch, authority=authority):
                    result = self.validate(serial(arch, authority), arch, authority)
                    self.assertEqual(len(result['raw_forms']), len(expected))
                    if authority == 'root':
                        self.assertEqual(result['correlated_held_event_count'], 12)
                        self.assertEqual(len(result['samples']), 4)
            count += len(expected)
        self.assertEqual(count, 14)

    def test_sdk_profile_matrix_cannot_be_narrowed_or_ambiguous(self):
        original = profile_header()
        for bad in (original.replace('"rv32"', '"rv64"'), original.replace('404U', '405'),
                    original.replace('clock_settime64, count', 'clock_settime64, clock_settime64, count')):
            with self.subTest(header=bad[:90]), self.assertRaises(ValueError):
                self.header.write_text(bad)
                setter_forms(self.sdk)

    def test_missing_repeated_and_interleaved_lines(self):
        original = serial()
        lines = original.splitlines(keepends=True)
        for bad in (original[:-1], ''.join(lines[:-1]), original + lines[-1],
                    original.replace('CLOCK_SET_RAW_PASS', 'unexpected CLOCK_SET_RAW_PASS', 1),
                    original.replace('CLOCK_SET_MUSL_SAMPLE label=forward', 'CLOCK_SET_MUSL_SAMPLE label=backward', 1)):
            with self.subTest(tail=bad[-160:]), self.assertRaises(ValueError):
                self.validate(bad)

    def test_raw_width_number_padding_and_credentials(self):
        original = serial()
        for old, new in [('number=227', 'number=228'), ('bytes=16', 'bytes=8'),
                         ('padding=full64', 'padding=ignored-high32'), ('copies=pass', 'copies=fail'),
                         ('euid=0', 'euid=1000'), ('before-user-entry=1', 'before-user-entry=0')]:
            with self.subTest(change=(old, new)), self.assertRaises(ValueError):
                self.validate(original.replace(old, new, 1))

    def test_bracket_oracles_reject_frozen_wall_and_elapsed_errors(self):
        original = serial()
        for old, new in [('wall=1700000001:144456789', 'wall=1700000001:123456789'),
                         ('read_before=3:21000000', 'read_before=3:20999999'),
                         ('after=3:1000000', 'after=3:22000001'),
                         ('at=3:22000000', 'at=3:1000000000'),
                         ('requested=1700000001:123456789', 'requested=1700000000:123456789')]:
            with self.subTest(change=(old, new)), self.assertRaises(ValueError):
                self.validate(original.replace(old, new, 1))

    def test_wait_interval_and_process_correlation(self):
        original = serial()
        for old, new in [('after=1150000000', 'after=1149999999'),
                         ('first=1020000000', 'first=999999999'),
                         ('last=1032000000', 'last=1150000000'),
                         ('parent=18', 'parent=19'), ('child=19', 'child=18'),
                         ('CLOCK_SET_NATIVE_WAIT pid=18', 'CLOCK_SET_NATIVE_WAIT pid=19'),
                         ('api=sleep pid=18', 'api=sleep pid=19'),
                         ('wall_after=4', 'wall_after=5'), ('deadline=1150000000', 'deadline=1021000000'),
                         ('pending-syscall=1', 'pending-syscall=0'), ('held=1', 'held=0')]:
            with self.subTest(change=(old, new)), self.assertRaises(ValueError):
                self.validate(original.replace(old, new, 1))

    def test_duplicate_held_events_do_not_count_as_two_mutations(self):
        lines = serial().splitlines()
        first = next(index for index, line in enumerate(lines) if line.startswith('CLOCK_SET_FIXTURE_WAIT_SET'))
        lines[first + 1] = lines[first]
        with self.assertRaisesRegex(ValueError, 'repeated held mutation'):
            self.validate('\n'.join(lines) + '\n')

    def test_denied_cannot_admit_root_success_or_held_events(self):
        original = serial(authority='denied')
        for bad in (original.replace('authority=denied', 'authority=root'), original +
                    next(line for line in serial().splitlines() if line.startswith('CLOCK_SET_FIXTURE_WAIT_SET')) + '\n'):
            with self.assertRaises(ValueError):
                self.validate(bad, authority='denied')


if __name__ == '__main__':
    unittest.main()

"""Reject stale, incomplete and cross-process clock acceptance evidence."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from realtime_evidence import fixture_seconds, validate_realtime


def serial(arch='arm32', fixture='2040-01-01T00:00:00'):
    seconds = fixture_seconds(fixture)
    positive = arch in ('arm32', 'aarch64', 'rv32', 'rv64')
    lines = []
    for personality, repeats in (('NATIVE', 1), ('MUSL', 2)):
        for _ in range(repeats):
            for role in ('parent', 'fork', 'exec'):
                prefix = 'OK_' + personality + '_REALTIME'
                if positive:
                    lines.append(f'{prefix}_SAMPLE role={role} seconds={seconds + 1} nanoseconds=100 monotonic_seconds=1 monotonic_nanoseconds=100')
                    legacy = 'overflow' if seconds > 2147483647 else 'pass'
                    if personality == 'NATIVE':
                        if arch not in ('arm32', 'rv32'):
                            legacy = 'pass'
                        claim = 'capability=available legacy=' + legacy
                    else:
                        if arch != 'arm32':
                            legacy = 'not-declared'
                        claim = 'capability=available wrappers=pass legacy=' + legacy
                    claim += ' copies=pass sleep=pass'
                else:
                    claim = 'capability=unavailable errors=pass copies=unchanged monotonic=pass'
                lines.append(f'{prefix} role={role} {claim}')
    return ('\n'.join(lines) + '\n').encode()


class RealtimeEvidenceTests(unittest.TestCase):
    def test_independent_epoch_vectors(self):
        for fixture, expected in (('1970-01-01T00:00:00', 0),
                                  ('2024-02-29T12:34:56', 1709210096),
                                  ('2040-01-01T00:00:00', 2208988800)):
            self.assertEqual(fixture_seconds(fixture), expected)

    def test_invalid_fixtures(self):
        for fixture in ('2023-02-29T12:34:56', '1969-12-31T23:59:59',
                        '2024-02-29', '2024-02-29T12:34:56Z', '2107-01-01T00:00:00'):
            with self.subTest(fixture=fixture), self.assertRaises(ValueError):
                fixture_seconds(fixture)

    def test_all_profiles_and_source_dates(self):
        for arch in ('x86_64', 'i386', 'aarch64', 'arm32', 'rv64', 'rv32', 'loongarch64', 'mips', 'mips64', 'ppc'):
            for fixture in ('1970-01-01T00:00:00', '2024-02-29T12:34:56', '2040-01-01T00:00:00'):
                with self.subTest(arch=arch, fixture=fixture):
                    result = validate_realtime(serial(arch, fixture), arch, fixture)
                    self.assertEqual(result['oracle_seconds'], fixture_seconds(fixture))

    def test_missing_duplicate_and_incomplete_roles(self):
        original = serial()
        lines = original.splitlines(keepends=True)
        for invalid in (b''.join(lines[:-1]), original + lines[-1], original[:-1],
                        original.replace(b'role=exec', b'role=fork', 1)):
            with self.subTest(invalid=invalid[-100:]), self.assertRaises(ValueError):
                validate_realtime(invalid, 'arm32', '2040-01-01T00:00:00')

    def test_stale_fixture_bad_layout_and_false_overflow(self):
        original = serial()
        for invalid in (original.replace(b'seconds=2208988801', b'seconds=1709210096', 1),
                        original.replace(b' nanoseconds=100 ', b' nanoseconds=1000000000 ', 1),
                        original.replace(b'legacy=overflow', b'legacy=pass', 1),
                        original.replace(b'monotonic_seconds=1 ', b'monotonic_seconds=31 ', 1)):
            with self.subTest(invalid=invalid[:180]), self.assertRaises(ValueError):
                validate_realtime(invalid, 'arm32', '2040-01-01T00:00:00')

    def test_process_anchor_discontinuity(self):
        changed = serial().replace(b' nanoseconds=100 ', b' nanoseconds=51000101 ', 1)
        with self.assertRaisesRegex(ValueError, 'anchor changed'):
            validate_realtime(changed, 'arm32', '2040-01-01T00:00:00')

    def test_unavailable_source_cannot_publish_samples(self):
        sample = serial().splitlines(keepends=True)[0]
        with self.assertRaises(ValueError):
            validate_realtime(serial('x86_64') + sample, 'x86_64', '2040-01-01T00:00:00')


if __name__ == '__main__':
    unittest.main()

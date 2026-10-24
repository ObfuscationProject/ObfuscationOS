import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from dynamic_startup_observer import (MARKER, RUNNER, MISSING_RUNNER, MISSING_ERROR,
                                      STATIC_MARKER, STATIC_RUNNER, STATIC_NO_ENTROPY,
                                      STATIC_NO_ENTROPY_RUNNER, validate_static_run,
                                      validate_run, validate_complete)


def run(missing=False):
    records = (MISSING_ERROR, MISSING_RUNNER) if missing else (MARKER, RUNNER)
    return b'\r\n'.join((*records, b'oksh> '))


class DynamicStartupObserverTests(unittest.TestCase):
    def test_static_entropy_success_and_rollback(self):
        normal = b'\r\n'.join((STATIC_MARKER, STATIC_RUNNER, b'oksh> '))
        absent = b'\r\n'.join((STATIC_NO_ENTROPY, STATIC_NO_ENTROPY_RUNNER, b'oksh> '))
        self.assertTrue(validate_static_run(normal)['executed'])
        self.assertTrue(validate_static_run(absent, no_entropy=True)['rollback'])
        for transcript in (normal.replace(STATIC_MARKER, b''),
                           absent.replace(STATIC_NO_ENTROPY, b''),
                           normal + STATIC_MARKER):
            with self.assertRaises(ValueError):
                validate_static_run(transcript)

    def test_positive_and_missing_loader(self):
        for missing in (False, True):
            self.assertTrue(validate_run(run(missing), missing_loader=missing)['child_reaped'])

    def test_malformed_success(self):
        good = run()
        for damaged in (good.replace(MARKER, b''), good.replace(MARKER, b'prefix ' + MARKER),
                        good.replace(MARKER, MARKER + b'\r\n' + MARKER),
                        good.replace(RUNNER, b'OK_DYNAMIC_RUNNER child_exit=93 normal=1'),
                        good.replace(MARKER + b'\r\n' + RUNNER, RUNNER + b'\r\n' + MARKER),
                        good.replace(b'\r\n', b'\r'), good[:-1], good + b'\nOK_DYNAMIC_RUNNER',
                        good.replace(b'oksh> ', b'acceptance=FAIL after-pass\noksh> '),
                        good.replace(b'oksh> ', b'OK_TEST_FAIL\noksh> ')):
            with self.subTest(damaged=damaged):
                with self.assertRaises(ValueError):
                    validate_run(damaged)

    def test_missing_loader_requires_errno_and_resumed_child(self):
        for damaged in (run(True).replace(MISSING_ERROR, b''),
                        run(True).replace(MISSING_ERROR, b'OK_DYNAMIC_ROLLBACK errno=13 continued=1'),
                        run(True).replace(MISSING_ERROR, b'prefix ' + MISSING_ERROR), run()):
            with self.assertRaises(ValueError):
                validate_run(damaged, missing_loader=True)

    def test_negative_record_must_be_atomic_and_complete(self):
        for damaged in (run(True).replace(MISSING_ERROR, b'OK_DYNAMIC_ROLLBACK errno=2\ncontinued=1'),
                        run(True).replace(MISSING_ERROR, MISSING_ERROR + b'\n' + MISSING_ERROR)):
            with self.assertRaises(ValueError):
                validate_run(damaged, missing_loader=True)

    def test_two_command_boundaries_and_pipeline(self):
        initial = b'boot\r\noksh> '
        first, second = run(), run()
        pipeline = b'hello from ObfuscationOS userland\r\noksh> '
        serial = initial + first + second + pipeline
        a, b, c = len(initial), len(initial + first), len(initial + first + second)
        self.assertEqual(validate_complete(serial, [(a, b), (b, c)], (c, len(serial)), missing_loader=False)['commands'], 2)
        for boundaries in ([(a, b), (a, b)], [(a, c), (b, c)], [(a + 1, b), (b, c)]):
            with self.assertRaises(ValueError):
                validate_complete(serial, boundaries, (c, len(serial)), missing_loader=False)

    def test_unreviewed_record_between_commands_is_rejected(self):
        initial, first, second = b'boot\noksh> ', run(), run()
        gap = MARKER + b'\noksh> '
        pipeline = b'hello from ObfuscationOS userland\noksh> '
        serial = initial + first + gap + second + pipeline
        a, b = len(initial), len(initial + first)
        c, d = len(initial + first + gap), len(initial + first + gap + second)
        with self.assertRaises(ValueError):
            validate_complete(serial, [(a, b), (c, d)], (d, len(serial)), missing_loader=False)


if __name__ == '__main__':
    unittest.main()

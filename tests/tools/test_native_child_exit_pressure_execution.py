"""A failed observed guest must not be relabeled as an unexecuted build."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from qualify_native_child_exit_pressure import observe_guest_execution
from native_child_exit_pressure_guest import probe_spec
from native_child_exit_guest import ARCHES


class PressureExecutionObservationTests(unittest.TestCase):
    def test_begin_failure_and_pass_are_observations_not_acceptance(self):
        for arch in ARCHES:
            begin = f'CHILD_PRESSURE_BEGIN arch={arch} pid=101 uid=0 cap=128 waves=3 failures=3\n'.encode()
            failure = b'CHILD_PRESSURE_FAIL line=0047 wave=9\n'
            complete = probe_spec(arch)[0] + b'\n'
            for data, expected in ((b'', (0, 0, 0)), (begin, (1, 0, 0)), (failure, (0, 1, 0)),
                                   (begin + failure, (1, 1, 0)), (begin + complete, (1, 0, 1)),
                                   (begin + complete + begin + complete, (2, 0, 2))):
                with self.subTest(arch=arch, expected=expected):
                    observed = observe_guest_execution(data, arch)
                    self.assertEqual(tuple(observed[key] for key in ('guest_begin_markers_observed',
                                     'guest_failure_markers_observed', 'observed_pass_markers')), expected)
                    self.assertEqual(observed['executed'], any(expected))
                    self.assertNotIn('native_execution_accepted', observed)
                    self.assertEqual(observe_guest_execution(data.replace(b'\n', b'\r\n'), arch), observed)

    def test_partial_foreign_and_unrecognized_markers_do_not_establish_execution(self):
        for data in (b'CHILD_PRESSURE_', b'CHILD_PRESSURE_FAIL line=0047 wave=9',
                     b'CHILD_PRESSURE_FAIL line=0047 wave=8\n',
                     b'CHILD_PRESSURE_BEGIN arch=mips pid=101 uid=0 cap=128 waves=3 failures=3\n',
                     b'kernel CHILD_PRESSURE_FAIL line=0047 wave=9\n'):
            self.assertFalse(observe_guest_execution(data, 'x86_64')['executed'])


if __name__ == '__main__': unittest.main()

"""Reject premature termination, incomplete UART records and stale baselines."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from native_terminal_evidence import inspect_terminal

MARKER = b'PID1_NATIVE_PASS pid=1 restarts=2 other=1 shutdown=clean'
FRAME = (b'OK_NATIVE_FRAMES version=2 source=firmware used=0 total=1024 allocations=259 releases=259 '
         b'pinned=0 user=0 objects=0 free=1024 pending=0 reserve=157 user_limit=867 object_quarantine=0\r\n')
STACK = (b'OK_ENTRY_STACKS version=1 scope=actual-user cpu=0 capacity=128 usable_bytes=65536 backing_bytes=9437184 '
         b'leased=0 active=0 quarantine=0 peak=4 reservations=6 releases=6 activations=334 syscalls=286 '
         b'timers=48 faults=0 rejected=0 guards=mapped-canaries smp=0\r\n')


class TerminalEvidenceTests(unittest.TestCase):
    def test_application_pass_alone_is_incomplete(self):
        self.assertIsNone(inspect_terminal(MARKER + b'\r\n', MARKER, 'aarch64'))
        with self.assertRaises(ValueError):
            inspect_terminal(MARKER + b'\r\n', MARKER, 'aarch64', complete=True)

    def test_partial_uart_never_satisfies_completion(self):
        prefix = MARKER + b'\r\n' + FRAME
        for index in range(len(STACK)):
            self.assertIsNone(inspect_terminal(prefix + STACK[:index], MARKER, 'aarch64'))
        self.assertEqual(inspect_terminal(prefix + STACK, MARKER, 'aarch64')['entry_stacks']['leased'], 0)

    def test_truncated_final_record_rejected(self):
        serial = MARKER + b'\r\n' + FRAME[:-30] + b'qemu-system-aarch64: terminating on signal 15\n'
        with self.assertRaises(ValueError):
            inspect_terminal(serial, MARKER, 'aarch64', complete=True)

    def test_pre_marker_empty_baseline_cannot_count(self):
        self.assertIsNone(inspect_terminal(FRAME + STACK + MARKER + b'\r\n', MARKER, 'aarch64'))

    def test_retained_ownership_or_wrong_source_rejected(self):
        for frame in (FRAME.replace(b'used=0', b'used=1'), FRAME.replace(b'source=firmware', b'source=linker')):
            with self.assertRaises(ValueError):
                inspect_terminal(MARKER + b'\r\n' + frame + STACK, MARKER, 'aarch64', complete=True)

    def test_failure_duplicate_or_post_success_truncation_rejected(self):
        serial = MARKER + b'\r\n' + FRAME + STACK
        for damaged in (serial + b'acceptance=FAIL after-pass\n', serial + MARKER + b'\n', serial + FRAME[:-3]):
            with self.assertRaises(ValueError):
                inspect_terminal(damaged, MARKER, 'aarch64', complete=True)
        self.assertFalse(inspect_terminal(serial + b'qemu-system-aarch64: terminating on signal 15\n', MARKER, 'aarch64', complete=True)['guest_shutdown'])


if __name__ == '__main__':
    unittest.main()

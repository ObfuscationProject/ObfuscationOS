"""Observer controls for complete-line PID 1 adoption evidence, not execution."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from native_init_adoption_evidence import PASS, lines_of, validate_execution

TRANSCRIPT = b'''OK_SYSTEM_GUI boot=complete
OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none
OK_NATIVE_FRAMES version=2 source=firmware used=0 total=1024 allocations=10 releases=10 pinned=0 user=0 objects=0 free=1024 pending=0 reserve=38 user_limit=986 object_quarantine=0
OK_ENTRY_STACKS version=1 scope=actual-user cpu=0 capacity=128 usable_bytes=65536 backing_bytes=9437184 leased=0 active=0 quarantine=0 peak=0 reservations=0 releases=0 activations=0 syscalls=0 timers=0 faults=0 rejected=0 guards=mapped-canaries smp=0
OK_NATIVE_IMAGE personality=linux source=firmware pages=24 physical_first=0x0000000002a27000 physical_last=0x0000000002a3e000 owner=retained
OK_NATIVE scope=hardware init=loaded
INIT_ADOPTION_BEGIN pid=1 ppid=0
INIT_ADOPTION_WAIT child=58 status=4352
INIT_ADOPTION_SIGNAL case=live owner=init child=58 status=17
OK_NATIVE_CHILD_WAIT pid=1 tid=1 request=3 wait=3 selector=4294967295 output=2146434524 format=status outcome=arm result=-11 live=1
INIT_ADOPTION_GRANDCHILD case=live pid=59 ppid=1
OK_NATIVE_CHILD_WAIT pid=1 tid=1 request=3 wait=3 selector=4294967295 output=2146434524 format=status outcome=complete result=59 live=0
INIT_ADOPTION_WAIT child=59 status=5888
INIT_ADOPTION_SIGNAL case=live owner=init child=59 status=23
INIT_ADOPTION_CASE case=live service=58 grandchild=59 pass=1
INIT_ADOPTION_SIGNAL case=completed owner=service child=61 status=31
OK_NATIVE_FRAMES version=2 source=firmware used=25 total=1024 allocations=135 releases=110 pinned=0 user=24 objects=1 free=999 pending=0 reserve=38 user_limit=986 object_quarantine=0
OK_ENTRY_STACKS version=1 scope=actual-user cpu=0 capacity=128 usable_bytes=65536 backing_bytes=9437184 leased=1 active=0 quarantine=0 peak=3 reservations=5 releases=4 activations=80 syscalls=76 timers=4 faults=0 rejected=0 guards=mapped-canaries smp=0
INIT_ADOPTION_WAIT child=60 status=4864
INIT_ADOPTION_SIGNAL case=completed owner=init child=60 status=19
INIT_ADOPTION_WAIT child=61 status=7936
INIT_ADOPTION_CASE case=completed service=60 grandchild=61 pass=1
INIT_ADOPTION_PASS live=1 completed=1 wait_any=1 signal=1 drained=1
'''

class NativeInitEvidenceTests(unittest.TestCase):
    def reject(self, data, arch='x86_64', mode='debug'):
        with self.assertRaises(ValueError): validate_execution(data, arch, mode)

    def test_positive_records_are_parser_only(self):
        for data in (TRANSCRIPT, TRANSCRIPT.replace(b'\n', b'\r\n')):
            result = validate_execution(data, 'x86_64', 'debug')
            self.assertTrue(result['parser_replay_only'])
            self.assertFalse(result['native_execution'])
            self.assertNotIn('sdk_abi', result)
            self.assertEqual(validate_execution(data, 'x86_64', 'debug', sdk_abi=34)['sdk_abi'], 34)
            self.assertEqual(result['final_entry_leases'], 1)

    def test_incomplete_tail_cannot_hide_an_extra_record(self):
        for suffix in (PASS, b'INIT_ADOPTION_CASE invalid', b'ignored tail', b'\r'):
            self.reject(TRANSCRIPT + suffix)
        self.reject(TRANSCRIPT[:-1])

    def test_wrapped_or_duplicated_guest_records(self):
        for prefix in (b'wrapper ', b' ', b'\t', b'OK_DISPLAY_TEXT '):
            self.reject(TRANSCRIPT + prefix + PASS + b'\n')
        self.reject(TRANSCRIPT + PASS + b'\n')
        self.reject(TRANSCRIPT.replace(PASS, b'wrapper ' + PASS))

    def test_malformed_missing_reordered_or_reused_guest(self):
        self.reject(TRANSCRIPT.replace(b'child=58 status=4352', b'child=58 status=4353'))
        self.reject(TRANSCRIPT.replace(b'INIT_ADOPTION_WAIT child=58 status=4352\n', b''))
        self.reject(TRANSCRIPT.replace(b'grandchild=61', b'grandchild=59'))
        self.reject(TRANSCRIPT.replace(b'INIT_ADOPTION_GRANDCHILD case=live pid=59 ppid=1',
                                       b'INIT_ADOPTION_GRANDCHILD case=live pid=59 ppid=58'))
        self.reject(TRANSCRIPT.replace(PASS, b'INIT_ADOPTION_PASS invalid'))

    def test_rv32_requires_siginfo_and_release_forbids_diagnostics(self):
        rv32 = TRANSCRIPT.replace(b'format=status', b'format=siginfo')
        validate_execution(rv32, 'rv32', 'debug')
        self.reject(TRANSCRIPT, 'rv32', 'debug')
        self.reject(rv32)
        release = b'\n'.join(line for line in TRANSCRIPT.split(b'\n') if not line.startswith(b'OK_NATIVE_CHILD_WAIT'))
        validate_execution(release, 'x86_64', 'release')
        self.reject(TRANSCRIPT, 'x86_64', 'release')

    def test_failure_markers_and_resource_leaks(self):
        self.reject(TRANSCRIPT + b'INIT_ADOPTION_FAIL after-pass\n')
        self.reject(TRANSCRIPT.replace(b'user=24 objects=1', b'user=24 objects=0'))
        self.reject(TRANSCRIPT.replace(b'leased=1 active=0', b'leased=2 active=0'))
        self.reject(TRANSCRIPT.replace(b'releases=4 activations=80', b'releases=3 activations=80'))

    def test_line_normalization_requires_completed_unambiguous_lines(self):
        self.assertEqual(lines_of(b'a\r\n\n'), [b'a', b''])
        for data in (b'', b'a', b'a\r', b'a\rb\n'):
            with self.assertRaises(ValueError): lines_of(data)

if __name__ == '__main__': unittest.main()

"""Hosted typed-child signal-wait admission; no target execution is performed."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from native_signal_wait_events import native_events
from signal_wait_guest_protocol import ARCHES, TIMED


def fixture(arch, code=1, child=234, uid=1000, signal=None):
    chld = 18 if arch.startswith('mips') else 17
    signal = chld if signal is None else signal
    low = 0x10000000 if arch in ('arm32','aarch64') else 0x40000000
    bits = 1 << (signal-1)
    size = 16 if arch.startswith('mips') else 8
    identity = 'pid=123 tid=123 epoch=11 wait=7 kind=timed'
    arm = (f'OK_NATIVE_SIGNAL_WAIT_ARM {identity} syscall={TIMED[arch]} pc={low+4096} '
           f'set={low+8192} info={low+8448} timeout={low+8704} sigsetsize={size} '
           f'wanted0={bits} wanted1=0 original0={bits} original1=0 deadline=1000 '
           'active0=0 active1=0 live=1\n')
    end = (f'OK_NATIVE_SIGNAL_WAIT_COMPLETE {identity} outcome=received signal={signal} code={code} '
           f'sender_pid={child} sender_uid={uid} info={low+8448} result={signal} '
           'published=1 staged=0 consumed=1 live=0 deadline=1000 now=50\n')
    return (arm+end).encode()


class ChildSignalWaitTests(unittest.TestCase):
    def test_child_codes_require_explicit_campaign_and_target_sigchld(self):
        for arch in ARCHES:
            for code in (1,2):
                for crlf in (False,True):
                    raw=fixture(arch,code)
                    if crlf: raw=raw.replace(b'\n',b'\r\n')
                    rows=native_events(raw,arch,allow_child=True)
                    self.assertEqual(len(rows),2)
                    self.assertEqual(rows[1]['code'],code)
                    self.assertEqual(rows[1]['origin_position'],0)
                    with self.assertRaises(ValueError): native_events(raw,arch)
            for code,child,uid,signal in ((1,0,1000,None),(2,0,1000,None),
                    (1,234,2**32,None),(1,2**30,1000,None),(3,234,1000,None),
                    (1,234,1000,10),(2,234,1000,10)):
                with self.subTest(arch=arch,code=code,child=child,signal=signal),self.assertRaises(ValueError):
                    native_events(fixture(arch,code,child,uid,signal),arch,allow_child=True)

    def test_user_sender_domain_and_owned_mask_checks_remain_intact(self):
        for arch in ARCHES:
            for code in (0,-6):
                self.assertEqual(len(native_events(fixture(arch,code),arch)),2)
            raw=fixture(arch)
            for before,after in ((b'active0=0',b'active0=1'),(b'consumed=1',b'consumed=0'),
                    (b'staged=0',b'staged=1'),(b'live=0',b'live=1'),(b'now=50',b'now=18446744073709551616')):
                with self.subTest(arch=arch,before=before),self.assertRaises(ValueError):
                    native_events(raw.replace(before,after,1),arch,allow_child=True)


if __name__=='__main__': unittest.main()

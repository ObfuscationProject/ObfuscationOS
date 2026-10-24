"""Adversarial protocol controls, separate from native execution."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from native_child_exit_events import parse, native_events, wait_ledger_view, explicit_reap_batches, ARCHES


def completion(**changes):
    fields = dict(child=3, parent=1, parent_tid=2, parent_epoch=5, uid=1001,
                  code=1, status=37, wait_code=1, wait_status=37, published=1,
                  notify=1, queued=1, coalesced=0, autoreap=0)
    fields.update(changes)
    return b'OK_NATIVE_CHILD_EXIT ' + b' '.join(f'{k}={v}'.encode() for k, v in fields.items())


class ProtocolTests(unittest.TestCase):
    def test_all_profiles_typed_causes_and_policy_boundaries(self):
        for arch in ARCHES:
            maximum = 128 if arch.startswith('mips') else 64
            cases = [dict(), dict(notify=0, queued=0), dict(autoreap=1),
                     dict(notify=0, queued=0, autoreap=1), dict(queued=0, coalesced=1),
                     dict(parent=0, parent_tid=0, parent_epoch=0, notify=0, queued=0),
                     dict(parent_tid=0, parent_epoch=0, notify=0, queued=0),
                     dict(published=0, parent_tid=0, parent_epoch=0, notify=0, queued=0),
                     dict(code=1, status=0, wait_status=255),
                     dict(code=2, status=maximum, wait_code=2, wait_status=maximum),
                     dict(status=17, wait_code=2, wait_status=15)]
            for case in cases:
                with self.subTest(arch=arch, case=case):
                    self.assertEqual(parse(completion(**case), arch)['child'], 3)

    def test_identity_cause_policy_and_exact_grammar(self):
        for arch in ARCHES:
            maximum = 128 if arch.startswith('mips') else 64
            invalid = [dict(child=0), dict(parent=3), dict(child=2**32),
                       dict(parent=2**32), dict(parent_tid=2**32), dict(parent_epoch=2**64),
                       dict(uid=2**32), dict(code=0), dict(code=3), dict(status=256),
                       dict(code=2, status=0), dict(code=2, status=maximum+1),
                       dict(wait_code=2, wait_status=0), dict(wait_status=256),
                       dict(published=2), dict(notify=2), dict(autoreap=2),
                       dict(queued=0), dict(coalesced=1), dict(notify=0),
                       dict(parent_tid=0), dict(parent_epoch=0), dict(parent=0),
                       dict(published=0), dict(parent_tid=0, parent_epoch=0)]
            bad_lines = [completion(**case) for case in invalid]
            bad_lines += [b'prefix ' + completion(), completion() + b' extra=0',
                          completion().replace(b'child=3', b'child=-3'),
                          completion().replace(b' uid=1001', b''),
                          completion().replace(b'uid=1001', b'uid=1001 uid=1001')]
            for line in bad_lines:
                with self.subTest(arch=arch, line=line), self.assertRaises(ValueError):
                    parse(line, arch)

    def test_checked_reap_cannot_hide_failure(self):
        for arch in ARCHES:
            valid = b'OK_NATIVE_CHILD_REAP count=2 failed_pid=0 failed_after_erase=0 success=1'
            self.assertEqual(parse(valid, arch)['count'], 2)
            for bad in (valid.replace(b'count=2', b'count=0'),
                        valid.replace(b'failed_pid=0', b'failed_pid=4'),
                        valid.replace(b'failed_after_erase=0', b'failed_after_erase=1'),
                        valid.replace(b'success=1', b'success=0'),
                        valid.replace(b'count=2', b'count=4294967296'),
                        valid.replace(b'success=1', b'success=2')):
                with self.subTest(arch=arch, line=bad), self.assertRaises(ValueError):
                    parse(bad, arch)

    def test_view_preserves_other_records_and_validates_positions(self):
        wait = b'OK_NATIVE_CHILD_WAIT opaque-for-separate-ledger\r\n'
        other = b'OK_NATIVE_OBJECT_PAGES objects=1\r\n'
        span = wait + completion() + b'\r\n' + other
        events = native_events(span, 'x86_64')
        self.assertEqual(wait_ledger_view(span, events), wait + other)
        with self.assertRaises(ValueError):
            native_events(span + completion() + b'\n', 'x86_64')
        with self.assertRaises(ValueError):
            wait_ledger_view(span, events * 2)
        events[0]['position'] = 0
        with self.assertRaises(ValueError):
            wait_ledger_view(span, events)
        with self.assertRaises(ValueError):
            native_events(b'OK_NATIVE_CHILD_EXIT invalid\n', 'x86_64')
        with self.assertRaises(ValueError):
            parse(completion(), 'unknown')

    def test_checked_batches_follow_all_explicit_autoreap_completions(self):
        exit1 = completion(autoreap=1) + b'\n'
        exit2 = completion(child=4, parent=0, parent_tid=0, parent_epoch=0, notify=0, queued=0) + b'\n'
        reap = b'OK_NATIVE_CHILD_REAP count=2 failed_pid=0 failed_after_erase=0 success=1\n'
        for arch in ARCHES:
            rows = native_events(exit1 + exit2 + reap, arch)
            self.assertEqual(explicit_reap_batches(rows)[0]['completed_pids'], [3, 4])
            for bad in (exit1 + exit2, reap + exit1 + exit2,
                        exit1 + reap + exit2, exit1 + exit2 + reap + reap,
                        exit1 + exit2 + reap.replace(b'count=2', b'count=1')):
                with self.subTest(arch=arch, bad=bad), self.assertRaises(ValueError):
                    explicit_reap_batches(native_events(bad, arch))


if __name__ == '__main__':
    unittest.main()

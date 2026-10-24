"""Synthetic EXIT/REAP migration controls; no guest execution is claimed."""
from functools import lru_cache
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests/tools')]
import native_child_lifecycle_evidence as lifecycle
from native_child_exit_events import ARCHES
from test_native_child_events import wait
from test_native_child_exit_events import completion
import test_native_signal_delivery_x86_64 as frames
import test_native_signal_wait as waits
import test_native_process_signals as process
import test_native_directed_signals as directed

REAP = b'OK_NATIVE_CHILD_REAP count=1 failed_pid=0 failed_after_erase=0 success=1\n'


def trace():
    arm = wait(pid=2, tid=2, selector=8, live=2)
    done = wait(pid=2, tid=2, selector=8, outcome='complete', result=8, live=1)
    child = completion(child=8, parent=2, parent_tid=2) + b'\n'
    orphan = completion(child=9, parent=0, parent_tid=0, parent_epoch=0,
                        notify=0, queued=0) + b'\n'
    return arm, child, done, orphan, REAP


def validate(name, parts, arch):
    if name == 'frames':
        return frames.validate(parts, 'pthread', arch)
    return {'waits': waits, 'process': process, 'directed': directed}[name].validate(parts, arch)


@lru_cache(None)
def fixture(name, arch):
    if name == 'frames':
        parts = frames.fixture('pthread', arch=arch)
    elif name == 'directed':
        parts = directed.fixture(arch)
    else:
        parts = {'waits': waits, 'process': process}[name].transcript(arch)
    if name in ('frames', 'directed'):
        parts = [p.replace(b'user=40 objects=0', b'user=39 objects=1') for p in parts]
        parts[0] = parts[0].removesuffix(b'oksh> ') + wait() + b'oksh> '
    for index in range(1, 5):
        arm, child, done, orphan, reap = trace()
        command, body = parts[index].split(b'\n', 1)
        # The lifecycle appears after guest success and before final accounting.
        body = body.replace(b'OK_NATIVE_FRAMES ', child + done + orphan + reap + b'OK_NATIVE_FRAMES ', 1)
        parts[index] = command + b'\n' + arm + body
    return tuple(parts)


class LifecycleAdapterTests(unittest.TestCase):
    def test_all_profiles_preserve_wait_owner_and_typed_lifecycle(self):
        for arch in ARCHES:
            baseline = lifecycle.boot_baseline(wait(), arch, required=True)
            for newline in (b'\n', b'\r\n'):
                with self.subTest(arch=arch, newline=newline):
                    rows = lifecycle.native_events(b''.join(trace()).replace(b'\n', newline), arch, baseline)
                    self.assertEqual(len(rows), 5)
                    self.assertEqual(rows[1]['arm']['selector'], 8)
                    self.assertEqual(rows[-1]['count'], 1)

    def test_causal_join_and_typed_reaper_fail_closed(self):
        arm, child, done, orphan, reap = trace()
        good = b''.join(trace())
        bad = [arm + done + child + orphan + reap, good.replace(child, b''),
               good.replace(child, child + child), good.replace(child, child.replace(b'parent=2', b'parent=7')),
               good.replace(child, child.replace(b'autoreap=0', b'autoreap=1')),
               good.replace(done, done + arm + done), good.replace(arm, b''),
               good.replace(done, done.replace(b'live=1', b'live=0')),
               good.replace(reap, reap.replace(b'success=1', b'success=0')),
               good.replace(reap, reap.replace(b'failed_pid=0', b'failed_pid=9')),
               good.replace(reap, reap.replace(b'failed_after_erase=0', b'failed_after_erase=1')),
               good.replace(reap, reap.replace(b'count=1', b'count=0')),
               good.replace(child, b'prefix ' + child), good.replace(reap, b'prefix ' + reap),
               good.replace(child, child.rstrip() + b' extra=0\n'),
               good + b'OK_NATIVE_CHILD_UNKNOWN count=1\n']
        for arch in ARCHES:
            baseline = lifecycle.boot_baseline(wait(), arch, required=True)
            for mutation in bad:
                with self.subTest(arch=arch, mutation=mutation), self.assertRaises(ValueError):
                    lifecycle.native_events(mutation, arch, baseline)
            # Boot also validates completion identity before deriving its owner.
            with self.subTest(arch=arch, boot=True), self.assertRaises(ValueError):
                lifecycle.boot_baseline(wait() + child.replace(b'code=1', b'code=0'), arch, required=True)

    def test_negative_wait_outcomes_need_no_successful_child(self):
        for arch in ARCHES:
            baseline = lifecycle.boot_baseline(wait(), arch, required=True)
            arm = trace()[0]
            for result in (-3, -10, -14):
                done = wait(pid=2, tid=2, selector=8, outcome='complete', result=result, live=1)
                self.assertEqual(len(lifecycle.native_events(arm + done, arch, baseline)), 2)

    def test_four_complete_consumers_admit_exact_new_lines(self):
        for name in ('frames', 'waits', 'process', 'directed'):
            for arch in ('x86_64', 'ppc'):
                with self.subTest(collector=name, arch=arch):
                    result = validate(name, list(fixture(name, arch)), arch)
                    self.assertEqual(result['runs'], 2)
                    self.assertEqual(result['final']['objects'], 1)

    def test_four_consumers_reject_missing_malformed_and_unowned_records(self):
        arm, child, done, orphan, reap = trace()
        for name in ('frames', 'waits', 'process', 'directed'):
            parts = list(fixture(name, 'x86_64'))
            changes = [parts[1].replace(child, b''), parts[1].replace(child, child + child),
                       parts[1].replace(child, child.replace(b'parent=2', b'parent=7')),
                       parts[1].replace(child + done, done + child),
                       parts[1].replace(reap, reap.replace(b'success=1', b'success=0')),
                       parts[1].replace(reap, b'prefix ' + reap),
                       parts[1].replace(child, b'OK_NATIVE_CHILD_UNKNOWN count=1\n')]
            for mutated in changes:
                changed = parts.copy(); changed[1] = mutated
                with self.subTest(collector=name, mutation=mutated), self.assertRaises(ValueError):
                    validate(name, changed, 'x86_64')


if __name__ == '__main__':
    unittest.main()

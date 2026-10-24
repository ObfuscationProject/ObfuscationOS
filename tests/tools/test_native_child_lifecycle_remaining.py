"""Synthetic lifecycle migration controls for the remaining eleven collectors."""
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
import importlib
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests/tools')]
import native_child_lifecycle_evidence as adapter
import native_child_wait_smoke_evidence as smoke
from native_child_events import PATTERNS as WAIT_PATTERNS
from native_child_exit_events import ARCHES, EXIT, REAP
from test_native_child_events import wait
from test_native_child_exit_events import completion
from test_native_child_consumers import collector as inherited_collector
from test_native_child_lifecycle_consumers import trace
from test_native_signal_delivery_x86_64 import frames, stacks, IMAGE

CONSUMERS = ('child_wait', 'child_wait_smoke', 'pipe_write', 'pipe_vector',
             'pipe_sigpipe', 'pipe_signal', 'pipe_blocking', 'futex_signal',
             'poll_signal', 'poll_temporary_mask', 'poll_mask_exec')


def interrupted(arch):
    signal = 16 if arch.startswith('mips') else 10
    pc = 0x10001000 if arch in ('aarch64', 'arm32') else 0x40001000
    fields = dict(pid=2, tid=2, selector=8, live=2)
    arm = wait(**fields)
    terminal = wait(**dict(fields, live=1, outcome='interrupted', result=-4))
    publication = (f'OK_NATIVE_CHILD_SIGNAL pid=2 tid=2 request=4 wait=4 origin=8 '
                   f'signal={signal} outcome=eintr pc={pc} selector=8 output=1073745920 live=1\n').encode()
    return arm, terminal, publication


def smoke_events():
    lines = []
    for case in range(4):
        pid, child, site, output = 10, 20 + case, 0x40002000, 0x40001000
        restart, any_child = case % 2, case // 2
        selector = 0xffffffff if any_child else child
        request = 2 * case + 1
        def emit(tag, pc, result):
            lines.append((f'CHILD_SMOKE_{tag} case={case} restart={restart} any={any_child} '
                          f'pid={pid} child={child} selector={selector} output={output} pc={pc} result={result}\n').encode())
        fields = dict(pid=pid, tid=pid, request=request, selector=selector, output=output)
        emit('BEGIN', site, 0)
        lines.append(wait(**fields, live=2))
        emit('SEND', site, 0)
        lines.append(wait(**fields, outcome='interrupted', result=0 if restart else -4, live=1))
        lines.append((f'OK_NATIVE_CHILD_SIGNAL pid={pid} tid={pid} request={request} wait={request} origin={request + 100} '
                      f'signal=10 outcome={"restart" if restart else "eintr"} pc={site if restart else site + 2} '
                      f'selector={selector} output={output} live=1\n').encode())
        emit('HANDLE', site if restart else site + 2, 61 if restart else -4)
        if not restart:
            emit('EINTR', site + 2, -4)
        fields['request'] += 1
        lines.append(wait(**fields, live=2))
        emit('RELEASE', site, 0)
        lines.append(completion(child=child, parent=pid, parent_tid=pid,
                                parent_epoch=1, status=0, wait_status=0,
                                notify=0, queued=0) + b'\n')
        lines.append(wait(**fields, outcome='complete', result=child, live=1))
        emit('REAP', site + 2, child)
        emit('CASE_PASS', site + 2, child)
    return b''.join(lines)


def smoke_fixture(arch):
    assert arch == 'x86_64'
    marker, _, command, _ = smoke.probe_spec(arch, 'child-wait-smoke')
    body = command + b'\n' + IMAGE + smoke_events() + marker + b'\n'
    def frame(a, r):
        return frames(a, r).replace(b'user=40 objects=0', b'user=39 objects=1')
    return [b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n' +
            frame(0, 0) + stacks(0, 0, 0, peak=0) + wait() + frame(40, 0) + stacks(7, 5, 100) + b'oksh> ',
            b'hello | cat\nhello from ObfuscationOS userland\n' + frame(100, 60) + stacks(10, 8, 200) + b'oksh> ',
            body + frame(200, 160) + stacks(19, 17, 300) + b'oksh> ',
            body + frame(300, 260) + stacks(28, 26, 400) + b'oksh> ',
            b'hello | cat\nhello from ObfuscationOS userland\n' + frame(400, 360) + stacks(30, 28, 500) + b'oksh> ']


def smoke_validate(parts, arch):
    bounds = [sum(map(len, parts[:i])) for i in range(1, 5)]
    return smoke.validate_execution(b''.join(parts), *bounds, bounds[-1], arch)


def collector(name):
    if name == 'child_wait_smoke':
        return SimpleNamespace(fixture=smoke_fixture, validate=smoke_validate)
    if name == 'poll_mask_exec':
        return inherited_collector(name)
    module = importlib.import_module('test_native_' + name)
    return SimpleNamespace(fixture=getattr(module, 'fixture', None) or module.transcript,
                           validate=module.validate)


@lru_cache(None)
def fixture(name, arch):
    parts = collector(name).fixture(arch)
    if b'OK_NATIVE_CHILD_WAIT' not in parts[0]:
        parts = [p.replace(b'user=40 objects=0', b'user=39 objects=1') for p in parts]
        parts[0] = parts[0].removesuffix(b'oksh> ') + wait() + b'oksh> '
    for index in range(1, 5):
        fields = dict(pid=2, tid=2, request=900 + index, selector=4000000000)
        arm = wait(**fields, live=2)
        done = wait(**fields, outcome='complete', result=4000000000, live=1)
        child = completion(child=4000000000, parent=2, parent_tid=2,
                           status=0, wait_status=0, notify=0, queued=0) + b'\n'
        orphan = completion(child=4000000001, parent=0, parent_tid=0, parent_epoch=0,
                            notify=0, queued=0) + b'\n'
        command, body = parts[index].split(b'\n', 1)
        body = body.replace(b'OK_NATIVE_FRAMES ', arm + child + done + orphan + trace()[-1] + b'OK_NATIVE_FRAMES ', 1)
        parts[index] = command + b'\n' + body
    return tuple(parts)


class RemainingLifecycleTests(unittest.TestCase):
    def test_original_interrupted_publication_adjacency_all_profiles(self):
        for arch in ARCHES:
            arm, terminal, publication = interrupted(arch)
            baseline = adapter.boot_baseline(wait(), arch, required=True)
            options = dict(baseline=baseline, allow_signal=True,
                           signal_numbers=(16, 17) if arch.startswith('mips') else (10, 12),
                           pc_bounds=(0x10000000, 0x40000000) if arch in ('aarch64', 'arm32') else (0x40000000, 0x80000000))
            for separator in (b'', b'\n', b'\r\n'):
                with self.subTest(arch=arch, accepted=separator):
                    self.assertEqual(len(adapter.native_events(arm + terminal + separator + publication, arch, **options)), 3)
            for separator in (trace()[1], trace()[-1], b'unrelated\n'):
                with self.subTest(arch=arch, rejected=separator), self.assertRaises(ValueError):
                    adapter.native_events(arm + terminal + separator + publication, arch, **options)
            for invalid in (publication.replace(b'origin=8', b'origin=0'),
                            publication.replace(b'outcome=eintr', b'outcome=restart'),
                            publication.replace(b'pid=2', b'pid=3')):
                with self.subTest(arch=arch, invalid=invalid), self.assertRaises(ValueError):
                    adapter.native_events(arm + terminal + invalid, arch, **options)

    def test_existing_public_patterns_remain_wait_only(self):
        for name in CONSUMERS:
            evidence = importlib.import_module('native_' + name + '_evidence')
            self.assertEqual(evidence.CHILD_PATTERNS, WAIT_PATTERNS)
            self.assertNotIn(EXIT, evidence.PATTERNS)
            self.assertNotIn(REAP, evidence.PATTERNS)

    def test_all_consumers_two_complete_commands_with_lifecycle(self):
        for name in CONSUMERS:
            for arch in ('x86_64',) if name == 'child_wait_smoke' else ARCHES:
                with self.subTest(consumer=name, arch=arch):
                    result = collector(name).validate(list(fixture(name, arch)), arch)
                    self.assertEqual(result['runs'], 2)
                    self.assertEqual(result['final']['objects'], 1)

    def test_all_consumers_reject_malformed_or_unowned_lifecycle(self):
        for name in CONSUMERS:
            good = list(fixture(name, 'x86_64'))
            span = good[1]
            child = next(l for l in span.splitlines(keepends=True) if l.startswith(b'OK_NATIVE_CHILD_EXIT child=4000000000 '))
            done = next(l for l in span.splitlines(keepends=True) if b'outcome=complete result=4000000000 ' in l)
            mutations = [span.replace(child, b''), span.replace(child, child + child),
                         span.replace(child, child.replace(b'parent=2', b'parent=7')),
                         span.replace(child + done, done + child),
                         span.replace(child, b'prefix ' + child),
                         span.replace(b'success=1', b'success=0'),
                         span.replace(child, b'OK_NATIVE_CHILD_UNKNOWN child=4000000000\n')]
            for changed_span in mutations:
                changed = good.copy(); changed[1] = changed_span
                with self.subTest(consumer=name, mutated=changed_span), self.assertRaises(ValueError):
                    collector(name).validate(changed, 'x86_64')

    def test_smoke_requires_exit_and_unbroken_interrupted_signal_pair(self):
        raw = smoke_events()
        baseline = adapter.boot_baseline(wait(), 'x86_64', required=True)
        self.assertEqual(smoke.validate_cases(raw, 'x86_64', baseline)['cases'], 4)
        child = next(l for l in raw.splitlines(keepends=True) if l.startswith(b'OK_NATIVE_CHILD_EXIT '))
        signal = next(l for l in raw.splitlines(keepends=True) if l.startswith(b'OK_NATIVE_CHILD_SIGNAL '))
        for changed in (raw.replace(child, b'', 1), raw.replace(signal, trace()[-1] + signal, 1)):
            with self.assertRaises(ValueError):
                smoke.validate_cases(changed, 'x86_64', baseline)


if __name__ == '__main__':
    unittest.main()

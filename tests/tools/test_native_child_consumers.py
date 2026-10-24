"""Synthetic integration of validated child records with inherited collectors."""
from pathlib import Path
import importlib
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_native_child_events import wait
from test_native_child_exit_events import completion

COLLECTORS = ('pipe_signal', 'futex_signal', 'poll_signal', 'poll_temporary_mask', 'poll_mask_exec')


def collector(name):
    module = importlib.import_module('test_native_' + name)
    if name != 'poll_mask_exec':
        return module
    from test_native_signal_delivery_x86_64 import frames, stacks
    def fixture(arch):
        command = module.evidence.probe_spec(arch, 'poll-mask-exec')[2]
        output = command + b'\n' + module.synthetic(arch)
        parts = [b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n' + frames(0, 0) + stacks(0, 0, 0, peak=0) + frames(40, 0) + stacks(7, 5, 100) + b'oksh> ',
                 b'hello | cat\nhello from ObfuscationOS userland\n' + frames(100, 60) + stacks(10, 8, 200) + b'oksh> ',
                 output + frames(200, 160) + stacks(19, 17, 300) + b'oksh> ',
                 output + frames(300, 260) + stacks(28, 26, 400) + b'oksh> ',
                 b'hello | cat\nhello from ObfuscationOS userland\n' + frames(400, 360) + stacks(30, 28, 500) + b'oksh> ']
        if arch in ('mips64', 'mips', 'loongarch64'):
            parts = [p.replace(b'source=firmware', b'source=linker') for p in parts]
        return parts
    def validate(parts, arch):
        bounds = [sum(map(len, parts[:i])) for i in range(1, 5)]
        return module.evidence.validate_execution(b''.join(parts), *bounds, bounds[-1], arch)
    return SimpleNamespace(fixture=fixture, validate=validate)


def fixture(module, arch):
    parts = module.fixture(arch)
    # Existing synthetic snapshots have 40 live user pages. Give the retained
    # init wait one owned object page, preserving total/used arithmetic.
    parts = [part.replace(b'user=40 objects=0', b'user=39 objects=1') for part in parts]
    parts[0] = parts[0].removesuffix(b'oksh> ') + wait() + b'oksh> '
    for index in range(1, 5):
        command, body = parts[index].split(b'\n', 1)
        parts[index] = (command + b'\n' + wait(pid=2, tid=2, request=10+index, selector=8, live=2) +
                        body.removesuffix(b'oksh> ') +
                        completion(child=8, parent=2, parent_tid=2, notify=0, queued=0) + b'\n' +
                        wait(pid=2, tid=2, request=10+index, selector=8,
                             outcome='complete', result=8, live=1) + b'oksh> ')
    return parts


class ChildConsumerTests(unittest.TestCase):
    def test_inherited_profiles_with_exact_child_baseline(self):
        for name in COLLECTORS:
            module = collector(name)
            for arch in ('x86_64', 'rv32', 'mips64', 'ppc'):
                with self.subTest(collector=name, arch=arch):
                    result = module.validate(fixture(module, arch), arch)
                    self.assertEqual(result['runs'], 2)
                    self.assertEqual(result['final']['objects'], 1)

    def test_child_records_cannot_be_whitelisted_or_dropped(self):
        for name in COLLECTORS:
            module = collector(name)
            parts = fixture(module, 'x86_64')
            for index in range(1, 5):
                trace = parts[index]
                first = trace.splitlines(keepends=True)[1]
                for replacement in (b'', b'prefix' + first,
                                    first.replace(b'live=2', b'live=1'),
                                    first.replace(b'selector=8', b'selector=9')):
                    changed = parts.copy()
                    changed[index] = trace.replace(first, replacement, 1)
                    with self.subTest(collector=name, index=index, replacement=replacement), self.assertRaises(ValueError):
                        module.validate(changed, 'x86_64')
            for changed in (parts[:1] + [p.replace(b'objects=1', b'objects=0') for p in parts[1:]],
                            [parts[0].replace(wait(), b'')] + parts[1:],
                            parts[:2] + [parts[2].replace(b'result=8', b'result=9')] + parts[3:]):
                with self.subTest(collector=name), self.assertRaises(ValueError):
                    module.validate(changed, 'x86_64')


if __name__ == '__main__':
    unittest.main()

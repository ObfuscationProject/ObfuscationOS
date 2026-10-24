"""Synthetic pipe evidence tests. These do not execute user code or devices."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests/tools'))
import native_pipe_read_evidence as evidence
from test_native_signal_delivery_x86_64 import frames, stacks, IMAGE

ARCHES = ('i386', 'x86_64', 'aarch64', 'arm32', 'rv32', 'rv64', 'loongarch64', 'mips', 'mips64', 'ppc')


def events(arch):
    lines = []
    for form in (0, 1):
        for round_id in range(4):
            for case in range(8):
                pid = 200 + form if case != 7 else 400 + form * 4 + round_id
                tid = 1000 + form * 32 + round_id * 8 + case
                count = 8 if case == 2 else 0 if case == 5 else 1
                waiting = case in (0, 1, 2, 3, 4, 7)
                key = f'arch={arch} form={form} round={round_id} case={case}'
                owner = f' pid={pid} tid={tid}'
                arguments = f' fd=3 buffer=268443648 count={count}'
                identity = f'pid={pid} tid={tid} wait=1 request=1 output=268443648 fd=3 description=1 pipe=2 bytes={count}'
                lines.append(f'PIPE_READ_CASE_BEGIN {key}{owner}{arguments} wait={int(waiting)}')
                lines.append(f'PIPE_READ_ATTEMPT {key}{owner}{arguments}')
                if waiting:
                    lines.append(f'OK_NATIVE_PIPE_READ_WAIT {identity} stage=arm live=1')
                    if case == 7:
                        lines.append(f'PIPE_READ_EXIT_GROUP {key}{owner}')
                        result, outcome = -125, 'cancelled'
                    else:
                        lines += [f'PIPE_READ_MUTATE {key}{owner}', f'PIPE_READ_REPLACEMENT_READY {key}', f'PIPE_READ_ORIGINAL_READY {key}']
                        result, outcome = {0:(1,'ready'), 1:(1,'ready'), 2:(3,'ready'), 3:(0,'eof'), 4:(-14,'efault')}[case]
                    lines.append(f'OK_NATIVE_PIPE_READ_COMPLETE {identity} result={result} outcome={outcome} pinned=0 live=0')
                lines.append(f'PIPE_READ_CASE_PASS {key}')
    return ('\n'.join(lines) + '\n').encode()


def fixture(arch):
    marker, _, command, leases = evidence.probe_spec(arch, 'pipe-read-continuation')
    output = command + b'\n' + IMAGE + events(arch) + marker + b'\n'
    parts = [
        b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n'+frames(0,0)+stacks(0,0,0,peak=0)+frames(40,0)+stacks(7,5,100)+b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n'+frames(100,60)+stacks(10,8,200)+b'oksh> ',
        output+frames(200,160)+stacks(10+leases,8+leases,300)+b'oksh> ',
        output+frames(300,260)+stacks(10+2*leases,8+2*leases,400)+b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n'+frames(400,360)+stacks(12+2*leases,10+2*leases,500)+b'oksh> ',
    ]
    if arch in ('loongarch64', 'mips', 'mips64'):
        parts = [p.replace(b'source=firmware', b'source=linker') for p in parts]
    return parts


def validate(parts, arch):
    ends = [sum(map(len, parts[:i])) for i in range(1, 5)]
    return evidence.validate_execution(b''.join(parts), *ends, ends[-1], arch)


class PipeReadEvidence(unittest.TestCase):
    def test_all_profiles(self):
        for arch in ARCHES:
            for newline in (b'\n', b'\r\n'):
                with self.subTest(arch=arch, newline=newline):
                    result = validate([p.replace(b'\n', newline) for p in fixture(arch)], arch)
                    self.assertEqual(result['observations'], [dict(cases=64, forms=2, rounds=4, waits=48, rearms=0, efault=8, cancellations=8)] * 2)
                    self.assertTrue(result['owned_description_continuation'])
                    self.assertFalse(result['blocked_wait_interruption'])

    def test_owned_case_rejections(self):
        for arch in ARCHES:
            original = fixture(arch)
            for index in (2, 3):
                span = original[index]
                lines = span.splitlines(keepends=True)
                arm = next(line for line in lines if line.startswith(b'OK_NATIVE_PIPE_READ_WAIT'))
                complete = next(line for line in lines if line.startswith(b'OK_NATIVE_PIPE_READ_COMPLETE'))
                mutate = next(line for line in lines if line.startswith(b'PIPE_READ_MUTATE'))
                changed = {
                    'missing-arm': span.replace(arm, b'', 1),
                    'duplicate-arm': span.replace(arm, arm+arm, 1),
                    'missing-complete': span.replace(complete, b'', 1),
                    'duplicate-complete': span.replace(complete, complete+complete, 1),
                    'wrong-output': span.replace(complete, complete.replace(b'output=268443648', b'output=268443649'), 1),
                    'wrong-description': span.replace(complete, complete.replace(b'description=1', b'description=2'), 1),
                    'wrong-pipe': span.replace(complete, complete.replace(b'pipe=2', b'pipe=3'), 1),
                    'wrong-fd': span.replace(complete, complete.replace(b'fd=3', b'fd=4'), 1),
                    'wrong-thread': span.replace(complete, complete.replace(b'tid=1000', b'tid=1001'), 1),
                    'wrong-wait': span.replace(complete, complete.replace(b'wait=1', b'wait=2'), 1),
                    'wrong-request': span.replace(complete, complete.replace(b'request=1', b'request=2'), 1),
                    'pin-leak': span.replace(complete, complete.replace(b'pinned=0', b'pinned=1'), 1),
                    'object-leak': span.replace(complete, complete.replace(b'live=0', b'live=1'), 1),
                    'wrong-result': span.replace(complete, complete.replace(b'result=1', b'result=2'), 1),
                    'early-complete': span.replace(complete, b'', 1).replace(mutate, complete+mutate, 1),
                    'late-arm': span.replace(arm+mutate, mutate+arm, 1),
                    'wrong-case': span.replace(b'case=0 ', b'case=1 ', 1),
                    'wrong-attempt': span.replace(b'count=1\n', b'count=2\n', 1),
                    'bad-line': span.replace(arm, b'junk '+arm, 1),
                    'overflow-generation': span.replace(arm, arm.replace(b'wait=1', b'wait=18446744073709551616'), 1),
                    'failure': span.replace(b'oksh> ', b'PIPE_READ_FAIL code=129\noksh> '),
                    'unexpected-output': span.replace(b'oksh> ', b'junk\noksh> '),
                    'fault': span.replace(b'oksh> ', b'OK_NATIVE scope=hardware fault=contained\noksh> '),
                }
                for name, value in changed.items():
                    with self.subTest(arch=arch, index=index, name=name):
                        self.assertNotEqual(value, span)
                        parts = original.copy(); parts[index] = value
                        with self.assertRaises(ValueError): validate(parts, arch)

    def test_incidental_native_pipeline_and_rearm(self):
        for arch in ARCHES:
            parts = fixture(arch)
            arm = b'OK_NATIVE_PIPE_READ_WAIT pid=50 tid=50 wait=1 request=1 output=268443648 fd=3 description=1 pipe=2 bytes=64 stage=arm live=1\n'
            rearm = arm.replace(b'wait=1', b'wait=2').replace(b'stage=arm', b'stage=rearm')
            complete = arm.replace(b'_WAIT ', b'_COMPLETE ').replace(b'wait=1', b'wait=2').replace(b'stage=arm live=1', b'result=4 outcome=ready pinned=0 live=0')
            for index in (1, 4):
                good = parts.copy(); good[index] = good[index].replace(b'hello from ObfuscationOS userland\n', arm+rearm+complete+b'hello from ObfuscationOS userland\n')
                self.assertEqual(validate(good, arch)['runs'], 2)
                for bad in (rearm+complete, arm+complete, arm+rearm, arm+rearm+complete+complete):
                    broken = parts.copy(); broken[index] = broken[index].replace(b'hello from ObfuscationOS userland\n', bad+b'hello from ObfuscationOS userland\n')
                    with self.subTest(arch=arch, index=index, bad=bad), self.assertRaises(ValueError): validate(broken, arch)
                broken = parts.copy(); broken[index] = broken[index].replace(b'hello from ObfuscationOS userland\n', IMAGE+b'hello from ObfuscationOS userland\n')
                with self.assertRaises(ValueError): validate(broken, arch)

    def test_case_rearm_keeps_initial_request(self):
        for arch in ARCHES:
            parts = fixture(arch)
            arm = next(line for line in parts[2].splitlines(keepends=True) if line.startswith(b'OK_NATIVE_PIPE_READ_WAIT'))
            complete = next(line for line in parts[2].splitlines(keepends=True) if line.startswith(b'OK_NATIVE_PIPE_READ_COMPLETE'))
            rearm = arm.replace(b'wait=1', b'wait=2').replace(b'stage=arm', b'stage=rearm')
            parts[2] = parts[2].replace(complete, rearm+complete.replace(b'wait=1', b'wait=2'), 1)
            self.assertEqual(validate(parts, arch)['observations'][0]['rearms'], 1)
            parts[2] = parts[2].replace(rearm, rearm.replace(b'request=1', b'request=2'))
            with self.assertRaises(ValueError): validate(parts, arch)

    def test_runner_freeze_admission(self):
        from object_pressure_evidence import admit_sources, sha
        with tempfile.TemporaryDirectory() as tmp:
            inventory = Path(tmp)/'source.json'
            run = subprocess.run([sys.executable, '-B', str(ROOT/'tools/qualify_native_pipe_read.py'), 'freeze', '--output', str(inventory)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(run.stdout.strip(), sha(inventory))
            self.assertIn('tools/native_pipe_read_evidence.py', admit_sources(ROOT, inventory, sha(inventory))['files'])

    def test_fragmented_failure(self):
        for suffix in (b'', b' code=', b' code=129\r'):
            self.assertTrue(evidence.incomplete_failure_line(b'PIPE_READ_FAIL'+suffix))
        self.assertFalse(evidence.incomplete_failure_line(b'PIPE_READ_FAIL code=129\n'))
        self.assertIn('code=129', evidence.failure_line(b'PIPE_READ_FAIL code=129\n'))


if __name__ == '__main__':
    unittest.main()

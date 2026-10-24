"""Hermetic parser controls; synthetic records are never native execution."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import native_poll_mask_exec_evidence as evidence

IMAGE = (b'OK_NATIVE_IMAGE personality=linux source=firmware pages=21 '
         b'physical_first=0x0000000002000000 physical_last=0x0000000002014000 owner=retained')


def synthetic(arch):
    lines = [IMAGE]
    signal = 16 if arch.startswith('mips') else 10
    for stage in range(8):
        family, mode = stage // 4, stage % 4
        pid, tid = 100, 100 if mode in (0, 2) else 200 + stage
        executor = tid if mode < 2 else 200 + stage if mode == 2 else pid

        def event(tag, waiting=tid, executing=executor):
            return (f'MASK_EXEC_{tag} stage={stage} family={family} mode={mode} '
                    f'pid={pid} waiter={waiting} executor={executing}').encode()

        lines.append(event('WAIT', executing=executor if mode < 2 else 0))
        number = evidence.MASK_NUMBERS[arch][family][0]
        kind = 'select' if family else 'poll'
        key = f'pid={pid} tid={tid} wait=1'
        lines.append(f'OK_NATIVE_POLL_ARM {key} pc=1073745920 syscall={number} kind={kind} count=0 deadline=1000 live=1'.encode())
        if mode < 2:
            lines.extend([event('SEND'),
                          f'OK_NATIVE_POLL_RETIRE {key} reason=interrupted result=-4 live=0'.encode(),
                          f'OK_NATIVE_POLL_SIGNAL {key} signal={signal} kind={kind} result=eintr deadline=1000 now=1 live=0'.encode(),
                          event('HANDLER')])
        lines.extend([event('FAILED_PRESERVED'), event('COMMIT')])
        if mode >= 2:
            lines.append(f'OK_NATIVE_POLL_RETIRE {key} reason=cancelled result=-4 live=0'.encode())
        lines.extend([IMAGE, event('REPLACED', 0, 0)])
    lines.append(b'MASK_EXEC_PASS replacements=8 failed_exec=8')
    return b'\n'.join(lines) + b'\n'


class MaskExecEvidenceTests(unittest.TestCase):
    def test_all_profiles_and_line_endings(self):
        for arch in evidence.MASK_NUMBERS:
            with self.subTest(arch=arch):
                raw = synthetic(arch)
                result = evidence.validate_cases(raw, arch)
                self.assertEqual(result['replacements'], 8)
                self.assertEqual(result['cancelled_waits'], 4)
                self.assertEqual(evidence.validate_cases(raw.replace(b'\n', b'\r\n'), arch), result)
                self.assertLessEqual(len(evidence.probe_spec(arch, 'poll-mask-exec')[2].rsplit(b'/', 1)[-1]), 31)

    def test_failed_exec_success_is_not_failure(self):
        line = b'MASK_EXEC_FAILED_PRESERVED stage=0 family=0 mode=0 pid=1 waiter=1 executor=1\n'
        self.assertIsNone(evidence.failure_line(line))
        self.assertFalse(evidence.incomplete_failure_line(line))
        self.assertIsNotNone(evidence.failure_line(b'MASK_EXEC_FAIL code=204\n'))
        self.assertTrue(evidence.incomplete_failure_line(b'MASK_EXEC_FAIL code=204'))

    def test_each_lifecycle_event_is_required_and_unique(self):
        raw = synthetic('x86_64')
        for index, line in enumerate(raw.splitlines(keepends=True)[:-1]):
            for replacement in (b'', line + line):
                with self.subTest(index=index, duplicate=bool(replacement)):
                    with self.assertRaises(ValueError):
                        evidence.validate_cases(raw.replace(line, replacement, 1), 'x86_64')

    def test_mask_capable_syscall_required(self):
        for arch, plain_poll in dict(x86_64=7, i386=168, arm32=168, mips=4188, mips64=5007, ppc=167).items():
            raw = synthetic(arch)
            old = str(evidence.MASK_NUMBERS[arch][0][0]).encode()
            with self.subTest(arch=arch), self.assertRaises(ValueError):
                evidence.validate_cases(raw.replace(b'syscall=' + old, b'syscall=' + str(plain_poll).encode(), 1), arch)

    def test_exact_owner_ticket_and_retirement_order(self):
        raw = synthetic('x86_64')
        corruptions = [raw.replace(b'wait=1 reason=interrupted', b'wait=2 reason=interrupted', 1),
                       raw.replace(b'count=0', b'count=1', 1),
                       raw.replace(b'reason=cancelled result=-4', b'reason=cancelled result=0', 1),
                       raw.replace(b'waiter=0 executor=0', b'waiter=100 executor=0', 1),
                       raw.replace(b'deadline=1000 now=1', b'deadline=1000 now=1000', 1)]
        lines = raw.splitlines()
        index = next(i for i, line in enumerate(lines) if b'reason=cancelled' in line)
        lines[index], lines[index + 1] = lines[index + 1], lines[index]
        corruptions.append(b'\n'.join(lines) + b'\n')
        for index, changed in enumerate(corruptions):
            with self.subTest(index=index), self.assertRaises(ValueError):
                evidence.validate_cases(changed, 'x86_64')


if __name__ == '__main__':
    unittest.main()

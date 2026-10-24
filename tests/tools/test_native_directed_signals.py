"""Synthetic directed collector controls, separate from actual guest execution."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests/tools'))
import native_directed_signals_evidence as evidence
from test_native_signal_delivery_x86_64 import frames, stacks, IMAGE

ARCHES = ('i386', 'x86_64', 'arm32', 'aarch64', 'rv32', 'rv64', 'loongarch64', 'mips', 'mips64', 'ppc')


def fixture(arch):
    marker, _, command, _ = evidence.probe_spec(arch, 'directed-signals')
    output = command + b'\n' + IMAGE + marker + b'\n'
    parts = [
        b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\nOK_SYSTEM_GUI boot=complete\n' +
        frames(0, 0) + stacks(0, 0, 0, peak=0) + frames(40, 0) + stacks(7, 5, 100) + b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n' + frames(100, 60) + stacks(10, 8, 200) + b'oksh> ',
        output + frames(200, 160) + stacks(29, 27, 300) + b'oksh> ',
        output + frames(300, 260) + stacks(48, 46, 400) + b'oksh> ',
        b'hello | cat\nhello from ObfuscationOS userland\n' + frames(400, 360) + stacks(50, 48, 500) + b'oksh> ',
    ]
    if arch in ('loongarch64', 'mips', 'mips64'):
        parts = [p.replace(b'source=firmware', b'source=linker') for p in parts]
    return parts


def validate(parts, arch):
    ends = [sum(map(len, parts[:i])) for i in range(1, 5)]
    return evidence.validate_execution(b''.join(parts), *ends, ends[-1], arch)


class DirectedEvidence(unittest.TestCase):
    def test_all_ten_two_completed_commands(self):
        for arch in ARCHES:
            for newline in (b'\n', b'\r\n'):
                with self.subTest(arch=arch, newline=newline):
                    result = validate([p.replace(b'\n', newline) for p in fixture(arch)], arch)
                    self.assertEqual((result['runs'], result['sdk_abi'], result['minimum_leases_per_run']), (2, 31, 19))
                    self.assertEqual(result['image_publications_per_run'], 1)
                    self.assertFalse(result['process_directed_kill'])
                    self.assertFalse(result['blocked_wait_interruption'])
                    self.assertFalse(result['physical'])
                    self.assertEqual(result['entry_stacks']['commands'][1]['reservations'], 19)

    def test_marker_image_and_accounting_mutations(self):
        for arch in ARCHES:
            good = fixture(arch)
            marker, _, command, _ = evidence.probe_spec(arch, 'directed-signals')
            image = IMAGE.replace(b'firmware', b'linker') if arch in ('loongarch64', 'mips', 'mips64') else IMAGE
            for index in (2, 3):
                mutations = {
                    'missing-marker': good[index].replace(marker+b'\n', b''),
                    'duplicate-marker': good[index].replace(marker, marker+b'\n'+marker),
                    'missing-image': good[index].replace(image, b''),
                    'duplicate-image': good[index].replace(image, image+image),
                    'wrong-order': good[index].replace(image+marker+b'\n', marker+b'\n'+image),
                    'wrong-arch': good[index].replace(marker, marker.replace(arch.encode(), b'wrong', 1)),
                    'wrong-command': good[index].replace(command, b'/bin/wrong'),
                    'wrong-source': good[index].replace(b'source=linker', b'source=wrong').replace(b'source=firmware', b'source=wrong'),
                    'incomplete-marker': good[index].replace(marker+b'\n', marker),
                    'unexpected-output': good[index].replace(marker, b'unexpected\n'+marker),
                    'short-lease': good[index].replace(b'reservations=29 releases=27', b'reservations=28 releases=26').replace(b'reservations=48 releases=46', b'reservations=47 releases=45'),
                    'leaked-lease': good[index].replace(b'leased=2', b'leased=3'),
                    'leaked-object': good[index].replace(b'objects=0', b'objects=1'),
                    'quarantine': good[index].replace(b'quarantine=0', b'quarantine=1'),
                    'assertion': good[index].replace(b'oksh> ', b'DIRECTED_SIGNALS_FAIL code=201\noksh> '),
                    'partial-assertion': good[index].replace(b'oksh> ', b'DIRECTED_SIGNALS_FAIL code=201'),
                    'contained-fault': good[index].replace(b'oksh> ', b'OK_NATIVE scope=hardware fault=contained\noksh> '),
                }
                for label, changed in mutations.items():
                    parts = good.copy(); parts[index] = changed
                    with self.subTest(arch=arch, run=index, mutation=label), self.assertRaises(ValueError):
                        validate(parts, arch)
            for index in (0, 1, 4):
                parts = good.copy(); parts[index] = marker+b'\n'+parts[index]
                with self.subTest(arch=arch, outside=index), self.assertRaises(ValueError): validate(parts, arch)
            parts = good.copy(); parts[4] += b'junk after final prompt\n'
            with self.subTest(arch=arch, trailing=True), self.assertRaises(ValueError): validate(parts, arch)

    def test_complete_failure_line(self):
        for suffix in (b'', b' code=', b' code=201\r'):
            self.assertTrue(evidence.incomplete_failure_line(b'DIRECTED_SIGNALS_FAIL'+suffix))
        self.assertFalse(evidence.incomplete_failure_line(b'DIRECTED_SIGNALS_FAIL code=201\n'))
        self.assertIn('code=201', evidence.failure_line(b'DIRECTED_SIGNALS_FAIL code=201\n'))


if __name__ == '__main__':
    unittest.main()

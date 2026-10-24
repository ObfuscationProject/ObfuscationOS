"""Compiler-free ordinary collector controls; no target code or QEMU execution."""
from copy import deepcopy
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
import native_signal_production_evidence as evidence
import qualify_native_signal_production as qualifier
from native_child_exit_guest import ARCHES
from test_native_child_exit_guest import fixture as policy_fixture
from test_native_child_exit_pressure_guest import fixture as pressure_fixture
from test_entry_stack_evidence import stack

COUNTS = dict(positive=0, negative=0, observer=0)


def profile(arch, mode):
    return dict(abi_version=31, arch=arch, mode=mode, native_signal_profile='bounded-bootcpu-v1',
                defines=['OK_NATIVE_SIGNAL_RUNTIME'], cxxflags=[],
                asflags=['-DOK_NATIVE_SIGNAL_RUNTIME'] if arch == 'mips64' else [],
                triple=evidence.ARCH_TRIPLES[arch], compiler=dict(version='14.2.0'))


def transcript(arch, kind, endings=b'\n', terminate=False, guest=None, mode='release', echo=True):
    if guest is None:
        guest = (policy_fixture if kind == 'child-exit-policy' else pressure_fixture)(arch)
    source = 'linker' if arch in ('loongarch64', 'mips', 'mips64') else 'firmware'
    def frames(a, r, empty=False):
        used = a-r
        return (f'OK_NATIVE_FRAMES version=2 source={source} used={used} total=1024 allocations={a} '
                f'releases={r} pinned=0 user={used-int(not empty)} objects={int(not empty)} free={1024-used} '
                'pending=0 reserve=10 user_limit=1014\n').encode()
    def resources(index):
        return frames(10+10*index, 10*index) + stack(3+index*3, 1+index*3, 30+30*index, 30+30*index, peak=3)
    def image(offset):
        return (f'OK_NATIVE_IMAGE personality=linux source={source} pages=2 '
                f'physical_first=0x{offset:016x} physical_last=0x{offset+4096:016x} owner=retained\n').encode()
    if kind == 'child-exit-policy':
        guest = b''.join(row + (image(12288) if b'op=EXEC_FAILED ' in row else b'')
                         for row in guest.splitlines(keepends=True))
    boot = ((b'N64_SIGNAL_PLATFORM_PASS before-cxx=1 fp=fr1\n' if arch == 'mips64' else b'') +
            b'ordinary boot\nOK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\n'
            b'OK_SYSTEM_GUI boot=complete\n' + frames(0, 0, True) + stack(0, 0, 0, 0, peak=0) + resources(0))
    if mode == 'debug':
        boot += b'OK_NATIVE_CHILD_WAIT pid=1 tid=1 request=1 wait=1 selector=2 output=1073745920 format=status outcome=arm result=-11 live=1\n'
    parts = [boot + b'oksh> ']
    for index in range(1, 5):
        probe = index in (2, 3)
        body = ((evidence.probe_spec(arch, kind)[2] if probe else b'hello | cat') + b'\n') if echo else b''
        if mode == 'debug':
            body += (f'OK_NATIVE_CHILD_WAIT pid=2 tid=2 request={index} wait={index} selector=5 output=1073745920 format=status outcome=arm result=-11 live=2\n').encode()
        body += image(4096) + guest if probe else b'hello from ObfuscationOS userland\n'
        if mode == 'debug':
            body += (f'OK_NATIVE_CHILD_WAIT pid=2 tid=2 request={index} wait={index} selector=5 output=1073745920 format=status outcome=complete result=5 live=1\n').encode()
        parts.append(body+resources(index)+b'oksh> ')
    parts = [part.replace(b'\n', endings) for part in parts]
    bounds = [sum(map(len, parts[:i])) for i in range(1, 5)]
    if terminate:
        parts.append(b'qemu-system-test: terminating on signal 15 from pid 123 (/usr/bin/python3.13)\n')
    return b''.join(parts), (*bounds, bounds[-1])


def change_part(data, bounds, index, mutate):
    ends = [0, *bounds[:4], len(data)]
    parts = [data[left:right] for left, right in zip(ends, ends[1:])]
    parts[index] = mutate(parts[index])
    new_bounds = [sum(map(len, parts[:i])) for i in range(1, 5)]
    return b''.join(parts), (*new_bounds, new_bounds[-1])


class ProductionSignalTests(unittest.TestCase):
    def positive(self, data, bounds, arch, kind, mode='release'):
        COUNTS['positive'] += 1
        result = evidence.validate_execution(data, *bounds, arch, kind, mode)
        self.assertFalse(result['native_execution'])
        self.assertTrue(result['parser_replay_only'])
        for key in ('private_diagnostics', 'internal_blocked_waits_verified',
                    'internal_reclaim_ledger_verified', 'fault_injection_verified',
                    'physical', 'smp', 'full_posix_claim'):
            self.assertFalse(result[key])
        return result

    def negative(self, data, bounds, arch, kind, mode='release'):
        COUNTS['negative'] += 1
        with self.assertRaises(ValueError):
            evidence.validate_execution(data, *bounds, arch, kind, mode)

    def test_all_ten_profiles_two_repeated_commands(self):
        for arch in ARCHES:
            for kind in evidence.KINDS:
                for mode in ('debug', 'release'):
                    for endings in (b'\n', b'\r\n'):
                        for terminate in (False, True):
                            data, bounds = transcript(arch, kind, endings, terminate, mode=mode)
                            result = self.positive(data, bounds, arch, kind, mode)
                            self.assertEqual(result['runs'], 2)
                            self.assertEqual(result['mode'], mode)
                            if kind == 'child-exit-policy':
                                self.assertEqual(result['observations'][0]['cases'], 18)
                            else:
                                self.assertEqual(result['observations'][0]['failed_forks_observed'], 9)
                                self.assertEqual(result['observations'][0]['pressure_children_observed'], 12)
                    self.positive(*transcript(arch, kind, mode=mode, echo=False), arch, kind, mode)

    def test_strict_commands_boundaries_and_output(self):
        for arch in ARCHES:
            for kind in evidence.KINDS:
                data, bounds = transcript(arch, kind)
                for index in range(5):
                    for noise in (b'OK_NATIVE_FRAMES forged\n', b'OK_NATIVE_CHILD_EXIT forged\n',
                                  b'CHILD_EXIT_FAIL line=0001 case=99\n', b'CHILD_PRESSURE_FAIL line=0001 wave=9\n',
                                  b'CHILD_EXIT_PASS forged\n', b'CHILD_PRESSURE_PASS forged\n'):
                        self.negative(*change_part(data, bounds, index, lambda p, n=noise: n+p), arch, kind)
                    if index:
                        for mutate in (lambda p: b'unrelated output\n'+p,
                                       lambda p: p.replace(b'\n', b'\r\r\n', 1),
                                       lambda p: p.replace(b'oksh> ', b'oksh> oksh> ', 1),
                                       lambda p: p.replace(b'\n', b'\nhello | cat\n', 1)):
                            self.negative(*change_part(data, bounds, index, mutate), arch, kind)
                for index in range(5):
                    for value in (False, -1, 0, bounds[index]-1, bounds[index]+1, len(data)+1):
                        altered = list(bounds); altered[index] = value
                        self.negative(data, altered, arch, kind)
                for suffix in (b'junk', b'\n', b'oksh> ', b'qemu-system-test: forged\n'):
                    self.negative(data+suffix, bounds, arch, kind)
                for mutate in (lambda p: p.replace(b'boot=complete', b'boot=degraded'),
                               lambda p: p.replace(b'OK_SYSTEM_GUI boot=complete\n', b''),
                               lambda p: p.replace(b'OK_SYSTEM_GUI boot=complete\n', b'OK_SYSTEM_GUI boot=complete\n'*2),
                               lambda p: p.replace(b'mode=rw', b'mode=ro')):
                    self.negative(*change_part(data, bounds, 0, mutate), arch, kind)
                for index in (1, 4):
                    for mutate in (lambda p: p.replace(b'hello from ObfuscationOS userland\n', b''),
                                   lambda p: p.replace(b'hello from ObfuscationOS userland\n', b'hello from ObfuscationOS userland\n'*2)):
                        self.negative(*change_part(data, bounds, index, mutate), arch, kind)

    def test_every_guest_row_and_every_siginfo_byte(self):
        for arch in ARCHES:
            for kind, fixture in zip(evidence.KINDS, (policy_fixture, pressure_fixture)):
                guest = fixture(arch)
                rows = guest.splitlines(keepends=True)
                for index, row in enumerate(rows):
                    for replacement in (b'', row+row):
                        altered = b''.join(rows[:index]) + replacement + b''.join(rows[index+1:])
                        self.negative(*transcript(arch, kind, guest=altered), arch, kind)
                info = next(row for row in rows if b' hex=' in row)
                original = re.search(rb' hex=([0-9a-f]{256})', info)[1]
                payload = bytes.fromhex(original.decode())
                for index in range(128):
                    altered = bytearray(payload); altered[index] ^= 1
                    mutated = guest.replace(info, info.replace(original, altered.hex().encode()), 1)
                    self.negative(*transcript(arch, kind, guest=mutated), arch, kind)

    def test_general_diagnostics_are_validated_without_private_lifetime_claims(self):
        for arch in ARCHES:
            for kind in evidence.KINDS:
                for mode in ('debug', 'release'):
                    data, bounds = transcript(arch, kind, mode=mode)
                    for index in range(1, 5):
                        for prefix in (b'OK_NATIVE_FRAMES ', b'OK_ENTRY_STACKS '):
                            row = next(line for line in data[bounds[index-1]:].splitlines(True) if line.startswith(prefix))
                            for mutation in (lambda part, row=row: part.replace(row, b'', 1),
                                             lambda part, row=row: part.replace(row, b'prefix '+row, 1),
                                             lambda part, row=row: part.replace(row, row.replace(b'used=10 ', b'used=11 ').replace(b'leased=2 ', b'leased=3 '), 1)):
                                self.negative(*change_part(data, bounds, index, mutation), arch, kind, mode)
                    for index in (2, 3):
                        for mutation in (lambda p: p.replace(b'physical_first=0x0000000000001000', b'physical_first=0x0000000000001001', 1),
                                         lambda p: p.replace(b'physical_last=0x0000000000002000', b'physical_last=0x0000000000000000', 1),
                                         lambda p: p.replace(b'pages=2', b'pages=3', 1),
                                         lambda p: p.replace(b'OK_NATIVE_IMAGE ', b'OK_NATIVE_IMAGE_BAD ', 1),
                                         lambda p: b''.join(line for line in p.splitlines(True) if not line.startswith(b'OK_NATIVE_IMAGE '))):
                            self.negative(*change_part(data, bounds, index, mutation), arch, kind, mode)
                    if mode == 'debug':
                        self.negative(data, bounds, arch, kind, 'release')
                        lower = 0x10000000 if arch in ('aarch64', 'arm32') else 0x40000000
                        fields = f'pid=200 tid=200 wait=1 request=1 output={lower+4096} fd=3 description=4 pipe=2 bytes=1'
                        pipe = (f'OK_NATIVE_PIPE_READ_WAIT {fields} stage=arm live=1\n'
                                f'OK_NATIVE_PIPE_READ_COMPLETE {fields} result=1 outcome=ready pinned=0 live=0\n').encode()
                        changed = change_part(data, bounds, 2, lambda p: p.replace(b'OK_NATIVE_IMAGE ', pipe+b'OK_NATIVE_IMAGE ', 1))
                        self.positive(*changed, arch, kind, mode)
                        self.negative(*change_part(*changed, 2, lambda p: p.replace(b'pinned=0', b'pinned=1', 1)), arch, kind, mode)
                        self.negative(*change_part(*changed, 2, lambda p: p.replace(pipe.splitlines(True)[1], b'', 1)), arch, kind, mode)
                        glued = change_part(data, bounds, 1, lambda p: p.replace(
                            b'hello from ObfuscationOS userland\nOK_NATIVE_CHILD_WAIT',
                            b'hello from ObfuscationOS userlandOK_NATIVE_CHILD_WAIT', 1))
                        self.positive(*glued, arch, kind, mode)
                        self.negative(*change_part(*glued, 1, lambda p: p.replace(
                            b'hello from ObfuscationOS userlandOK_NATIVE_CHILD_WAIT',
                            b'hello from other userlandOK_NATIVE_CHILD_WAIT', 1)), arch, kind, mode)
                    else:
                        self.negative(data, bounds, arch, kind, 'debug')

    def test_sdk_profile_and_libc_mode_are_independent(self):
        for arch in ARCHES:
            for mode in ('debug', 'release'):
                manifest = profile(arch, mode)
                self.assertIs(evidence.admit_profile(manifest, arch, mode), manifest)
                COUNTS['positive'] += 1
                libc = dict(mode='debug', compiler=dict(triple=manifest['triple'], version='14.2.0'))
                self.assertEqual(evidence.admit_libc_mode(libc, 'debug', manifest)['kernel_mode'], mode)
                COUNTS['positive'] += 1
                for key, value in (('abi_version', 30), ('arch', 'unknown'), ('mode', 'other'),
                                   ('native_signal_profile', None), ('native_signal_profile', 'private'),
                                   ('defines', []), ('defines', ['OK_NATIVE_SIGNAL_RUNTIME=0']),
                                   ('defines', ['OK_NATIVE_SIGNAL_RUNTIME']*2)):
                    invalid = deepcopy(manifest); invalid[key] = value
                    COUNTS['negative'] += 1
                    with self.assertRaises(ValueError): evidence.admit_profile(invalid, arch, mode)
                for key in ('defines', 'cxxflags', 'asflags'):
                    options = (['OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE', 'OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE=0']
                               if key == 'defines' else ['-DOK_PRIVATE_SIGNAL_DELIVERY_FIXTURE',
                               '-D OK_PRIVATE_SIGNAL_DELIVERY_FIXTURE=0', '-Wp,-DOK_PRIVATE_SIGNAL_DELIVERY_FIXTURE',
                               '-UOK_NATIVE_SIGNAL_RUNTIME', '-Wp,-U,OK_NATIVE_SIGNAL_RUNTIME',
                               '-UOK_ENABLE_TEST_POINTS', '-UOK_PRIVATE_SIGNAL_DELIVERY_FIXTURE'])
                    for option in options:
                        invalid = deepcopy(manifest); invalid[key].append(option)
                        COUNTS['negative'] += 1
                        with self.assertRaises(ValueError): evidence.admit_profile(invalid, arch, mode)
                for option in ('-DOK_NATIVE_SIGNAL_RUNTIME', '-D OK_NATIVE_SIGNAL_RUNTIME=1', '-Wp,-D,OK_NATIVE_SIGNAL_RUNTIME'):
                    invalid = deepcopy(manifest); invalid['cxxflags'].append(option)
                    COUNTS['negative'] += 1
                    with self.assertRaises(ValueError): evidence.admit_profile(invalid, arch, mode)
                for wrong, explicit in ((dict(mode='release', compiler=libc['compiler']), 'debug'),
                                        (libc, 'release'), (dict(mode='debug', compiler={}), 'debug')):
                    COUNTS['negative'] += 1
                    with self.assertRaises(ValueError): evidence.admit_libc_mode(wrong, explicit, manifest)
                invalid = deepcopy(manifest); invalid['asflags'] = [] if arch == 'mips64' else ['-DOK_NATIVE_SIGNAL_RUNTIME']
                COUNTS['negative'] += 1
                with self.assertRaises(ValueError): evidence.admit_profile(invalid, arch, mode)
                ordinary_debug = deepcopy(manifest); ordinary_debug['defines'].append('OK_ENABLE_TEST_POINTS')
                if mode == 'release':
                    COUNTS['negative'] += 1
                    with self.assertRaises(ValueError): evidence.admit_profile(ordinary_debug, arch, mode)
                else:
                    evidence.admit_profile(ordinary_debug, arch, mode); COUNTS['positive'] += 1

    def test_complete_begin_and_fail_preserve_failed_execution(self):
        for arch in ARCHES:
            for kind in evidence.KINDS:
                data, _ = transcript(arch, kind)
                got = evidence.observe_guest_execution(data, arch, kind); COUNTS['observer'] += 1
                self.assertTrue(got['executed'])
                self.assertEqual(got['guest_invocation_starts_observed'], 2)
                self.assertEqual(got['guest_begin_markers_observed'], 36 if kind == 'child-exit-policy' else 2)
                self.assertEqual(got['observed_pass_markers'], 2)
                first = (policy_fixture if kind == 'child-exit-policy' else pressure_fixture)(arch).split(b'\n')[0]
                failure = (b'CHILD_EXIT_FAIL line=0001 case=99' if kind == 'child-exit-policy'
                           else b'CHILD_PRESSURE_FAIL line=0001 wave=9')
                for marker in (first, failure):
                    for ending in (b'', b'\r', b'\n', b'\r\n'):
                        got = evidence.observe_guest_execution(marker+ending, arch, kind); COUNTS['observer'] += 1
                        self.assertEqual(got['executed'], ending.endswith(b'\n'))
                        self.assertNotIn('native_execution_accepted', got)
                for bad in (first.replace(arch.encode(), b'unknown', 1)+b'\n', b'prefix '+first+b'\n', b'CHILD_EXIT_FAIL\n'):
                    self.assertFalse(evidence.observe_guest_execution(bad, arch, kind)['executed']); COUNTS['observer'] += 1
                self.assertIsNotNone(evidence.failure_line(failure))
                self.assertTrue(evidence.incomplete_failure_line(failure))
                self.assertFalse(evidence.incomplete_failure_line(failure+b'\n'))

    def test_probe_selection_and_runtime_options(self):
        for arch in ARCHES:
            for kind, source in zip(evidence.KINDS, ('native_child_exit', 'native_child_exit_pressure')):
                layout = qualifier.probe_layout(arch, kind)
                self.assertEqual(layout[0], source)
                self.assertEqual('/bin/'+layout[1], layout[2])
            if arch == 'mips64':
                with self.assertRaises(ValueError): qualifier.validate_runtime_options(arch, None, None)
                qualifier.validate_runtime_options(arch, Path('/explicit'), 'a'*64)
            else:
                qualifier.validate_runtime_options(arch, None, None)
                with self.assertRaises(ValueError): qualifier.validate_runtime_options(arch, Path('/explicit'), 'a'*64)
        with self.assertRaises(ValueError): evidence.probe_spec('unknown', evidence.KINDS[0])
        with self.assertRaises(ValueError): evidence.probe_spec('x86_64', 'unknown')

    def test_platform_rejection_and_private_early_records_anywhere(self):
        rejected = (b'N64_SIGNAL_PLATFORM_REJECT reason=no-fpu before-cp1=1',
                    b'N64_PRIVATE_EARLY_PASS', b'N64_PRIVATE_EARLY_REJECT reason=no-fpu before-cp1=1',
                    b'N64_PRIVATE_EARLY_UNKNOWN')
        for arch in ARCHES:
            for kind in evidence.KINDS:
                for mode in ('debug', 'release'):
                    data, bounds = transcript(arch, kind, mode=mode)
                    for marker in rejected:
                        for index in range(5):
                            self.negative(*change_part(data, bounds, index, lambda part, marker=marker: marker+b'\n'+part), arch, kind, mode)
        for marker in rejected:
            for ending in (b'', b'\r', b'\n', b'\r\n'):
                self.assertIsNotNone(evidence.failure_line(marker+ending))
                self.assertEqual(evidence.incomplete_failure_line(marker+ending), not ending.endswith(b'\n'))
                self.assertFalse(evidence.observe_guest_execution(marker+ending, 'mips64', 'child-exit-pressure')['executed'])
                COUNTS['observer'] += 1

    def test_unique_mips64_platform_admission_in_boot(self):
        marker = evidence.PLATFORM_PASS + b'\n'
        for arch in ARCHES:
            for kind in evidence.KINDS:
                for mode in ('debug', 'release'):
                    data, bounds = transcript(arch, kind, mode=mode)
                    if arch != 'mips64':
                        for index in range(5):
                            self.negative(*change_part(data, bounds, index,
                                lambda part: marker + part), arch, kind, mode)
                            self.negative(*change_part(data, bounds, index,
                                lambda part: b'prefix ' + marker + part), arch, kind, mode)
                        continue
                    missing, missing_bounds = change_part(data, bounds, 0,
                        lambda part: part.replace(marker, b''))
                    self.negative(missing, missing_bounds, arch, kind, mode)
                    self.negative(*change_part(data, bounds, 0,
                        lambda part: b'prefix ' + marker + part), arch, kind, mode)
                    self.negative(*change_part(data, bounds, 0,
                        lambda part: part.replace(marker, b'').replace(
                            b'OK_SYSTEM_GUI boot=complete\n', b'OK_SYSTEM_GUI boot=complete\n' + marker)),
                        arch, kind, mode)
                    for altered in (marker + marker, b'N64_SIGNAL_PLATFORM_PASS\n',
                                    marker.replace(b'fp=fr1', b'fp=fr0'),
                                    marker.replace(b'before-cxx=1', b'before-cxx=0'),
                                    b'N64_SIGNAL_PLATFORM_UNKNOWN\n'):
                        self.negative(*change_part(data, bounds, 0,
                            lambda part, altered=altered: part.replace(marker, altered)), arch, kind, mode)
                    for index in range(1, 5):
                        self.negative(*change_part(missing, missing_bounds, index,
                            lambda part: marker + part), arch, kind, mode)
                        self.negative(*change_part(data, bounds, index,
                            lambda part: marker + part), arch, kind, mode)


if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        print('HOSTED_ORDINARY_SIGNAL_CONTROLS', COUNTS, flush=True)

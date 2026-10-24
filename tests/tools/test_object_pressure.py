"""Admission refusal and corrupt-serial controls; these are host model tests."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import test_kernel_sdk as sdk_fixture

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from object_pressure_evidence import (admit_sdk, admit_sources, decode_frames,
    decode_pressure, relative_file, sha, source_files, validate_execution)
from qualify_object_pressure import copy_inventory, dependencies, pressure_qemu_command


def frame(used=0, allocations=0, releases=0, objects=0, total=2048, reserve=13, source='firmware'):
    return (f'OK_NATIVE_FRAMES version=2 source={source} used={used} total={total} '
            f'allocations={allocations} releases={releases} pinned=0 user={used-objects} '
            f'objects={objects} free={total-used} pending=0 reserve={reserve} '
            f'user_limit={total-reserve} object_quarantine=0\n').encode()


SUCCESS = b'OK_MUSL_OBJECT_PRESSURE children=4 pages=800 first=256 last=32 poll=pass reclaim=pass reuse=pass\n'


def serial(source='firmware'):
    boot = (b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw\n'
            b'OK_SYSTEM_GUI boot=complete\n' + frame(source=source) +
            b'hello from ObfuscationOS userland\n' + frame(40, 100, 60, source=source) + b'oksh> ')
    baseline = (b'hello from ObfuscationOS userland\n' +
                frame(59, 180, 121, source=source) + frame(40, 180, 140, source=source) + b'oksh> ')
    pressure = (b'object-pressure\n' + frame(889, 1800, 911, 1, source=source) +
                frame(40, 1800, 1760, source=source) + SUCCESS + b'oksh> ')
    native = b'hello | cat\nhello from ObfuscationOS userland\n' + frame(40, 1880, 1840, source=source) + b'oksh> '
    start = len(boot) + len(baseline)
    return boot + baseline + pressure + native, len(boot), start, start + len(pressure)


class EvidenceTests(unittest.TestCase):
    def test_ppc_pressure_uses_measured_reference_cpu(self):
        qemu, image, disk = Path('/qemu-system-ppc'), Path('/kernel.bin'), Path('/rootfs.ext4.img')
        command = pressure_qemu_command(qemu, 'ppc', image, disk)
        self.assertEqual(command[-6:], ['-cpu', 'e500v2_v22', '-smp', '1', '-accel', 'tcg,thread=single'])
        self.assertEqual(command.count('-cpu'), 1)
        original = command[:-6]
        for wrong in (original + ['-cpu', 'e500mc'], original + ['-smp', '2'],
                      [word.replace('ppce500', 'malta') for word in original]):
            with self.subTest(wrong=wrong), patch('qualify_object_pressure.command_for', return_value=wrong):
                with self.assertRaisesRegex(ValueError, 'reference'):
                    pressure_qemu_command(qemu, 'ppc', image, disk)

    def test_dynamic_quota_and_all_ten_sources(self):
        for arch in ('i386', 'x86_64', 'aarch64', 'arm32', 'rv32', 'rv64', 'loongarch64', 'mips', 'mips64', 'ppc'):
            source = 'linker' if arch in ('loongarch64', 'mips', 'mips64') else 'firmware'
            data, baseline, start, end = serial(source)
            result = validate_execution(data, baseline, start, end, end, arch)
            self.assertEqual((result['total'], result['reserve'], result['user_limit']), (2048, 13, 2035))
            self.assertEqual(result['observed_object_pages'], 1)

    def test_crlf_supported(self):
        self.assertEqual(decode_pressure(SUCCESS.replace(b'\n', b'\r\n'))['pages'], 800)
        self.assertEqual(decode_frames(frame().replace(b'\n', b'\r\n'), 'x86_64')[0]['reserve'], 13)

    def test_malformed_frame_records(self):
        sample = frame()
        mutations = ((b'version=2', b'version=1'), (b' pinned=0', b''),
                     (b' source=firmware', b' source=linker'), (b'user=0', b'user=+0'),
                     (b'user=0', b'user=00'), (b'used=0', b'used=-1'),
                     (b'pending=0', b'pending=1'), (b'pinned=0', b'pinned=1'),
                     (b'total=2048', b'total=2049'), (b'free=2048', b'free=2047'),
                     (b'allocations=0', b'allocations=1'), (b'releases=0', b'releases=1'),
                     (b'user_limit=2035', b'user_limit=2048'), (b'reserve=13', b'reserve=0'),
                     (b'user=0', b'user=1'), (b'objects=0', b'objects=1'),
                     (b' object_quarantine=0', b''), (b'object_quarantine=0', b'object_quarantine=1'))
        for old, new in mutations:
            with self.subTest(old=old, new=new), self.assertRaises(ValueError):
                decode_frames(sample.replace(old, new), 'x86_64', require_quarantine=True)
        for data in (sample[:-1], b'prefix ' + sample, sample.rstrip() + b' extra\n',
                     sample.replace(b'allocations=0', b'allocations=18446744073709551616')):
            with self.subTest(data=data), self.assertRaises(ValueError):
                decode_frames(data, 'x86_64')

    def test_legacy_decoder_and_current_execution_accounting(self):
        legacy = frame().replace(b' object_quarantine=0', b'')
        self.assertEqual(decode_frames(legacy, 'x86_64')[0]['object_quarantine'], 0)
        with self.assertRaisesRegex(ValueError, 'missing current'):
            decode_frames(legacy, 'x86_64', require_quarantine=True)
        data, baseline, start, end = serial()
        damaged = data.replace(b'object_quarantine=0', b'object_quarantine=1')
        with self.assertRaises(ValueError):
            validate_execution(damaged, baseline, start, end, end, 'x86_64')

    def test_consistent_capacity_and_monotonic_lifetime(self):
        for following in (frame(total=1024), frame(reserve=14), frame(10, 19, 9), frame(12, 21, 9)):
            with self.subTest(following=following), self.assertRaises(ValueError):
                decode_frames(frame(10, 20, 10) + following, 'x86_64')

    def test_quota_excess_even_if_equations_balance(self):
        for data in (frame(14, 14, 0, 14), frame(2040, 2040, 0)):
            with self.assertRaises(ValueError):
                decode_frames(data, 'x86_64')

    def test_pressure_requires_real_smaller_last_child(self):
        for data in (SUCCESS.replace(b'last=32', b'last=256'), SUCCESS.replace(b'last=32', b'last=0'),
                     SUCCESS.replace(b'pages=800', b'pages=799'), SUCCESS.replace(b'children=4', b'children=12'),
                     SUCCESS.replace(b'children=4', b'children=1'), SUCCESS.replace(b'first=256', b'first=255'),
                     SUCCESS.replace(b'poll=pass', b'poll=fail'), SUCCESS[:-1], SUCCESS * 2, b'prefix ' + SUCCESS):
            with self.subTest(data=data), self.assertRaises(ValueError):
                decode_pressure(data)

    def test_missing_object_use(self):
        data, baseline, start, end = serial()
        data = data.replace(frame(889, 1800, 911, 1), frame(889, 1800, 911, 0))
        with self.assertRaisesRegex(ValueError, 'actual object use'):
            validate_execution(data, baseline, start, end, end, 'x86_64')

    def test_persistent_boot_object_is_a_relative_baseline(self):
        data, baseline, start, end = serial()
        replacements = ((frame(40, 100, 60), frame(40, 100, 60, 1)),
                        (frame(59, 180, 121), frame(59, 180, 121, 1)),
                        (frame(40, 180, 140), frame(40, 180, 140, 1)),
                        (frame(889, 1800, 911, 1), frame(889, 1800, 911, 2)),
                        (frame(40, 1800, 1760), frame(40, 1800, 1760, 1)),
                        (frame(40, 1880, 1840), frame(40, 1880, 1840, 1)))
        for old, new in replacements:
            data = data.replace(old, new)
        result = validate_execution(data, baseline, start, end, end, 'x86_64')
        self.assertEqual((result['baseline']['objects'], result['final']['objects'],
                          result['observed_object_pages']), (1, 1, 2))
        for old, new in ((frame(889, 1800, 911, 2), frame(889, 1800, 911, 1)),
                         (frame(40, 1880, 1840, 1), frame(40, 1880, 1840, 2))):
            with self.subTest(old=old), self.assertRaisesRegex(ValueError, 'actual object use'):
                validate_execution(data.replace(old, new), baseline, start, end, end, 'x86_64')

    def test_shell_object_created_after_early_boot_diagnostic(self):
        data, baseline, start, end = serial()
        replacements = ((frame(59, 180, 121), frame(59, 180, 121, 1)),
                        (frame(40, 180, 140), frame(40, 180, 140, 1)),
                        (frame(889, 1800, 911, 1), frame(889, 1800, 911, 2)),
                        (frame(40, 1800, 1760), frame(40, 1800, 1760, 1)),
                        (frame(40, 1880, 1840), frame(40, 1880, 1840, 1)))
        for old, new in replacements:
            data = data.replace(old, new)
        result = validate_execution(data, baseline, start, end, end, 'x86_64')
        self.assertEqual((result['baseline']['objects'], result['final']['objects'],
                          result['observed_object_pages']), (1, 1, 2))

    def test_boot_object_cannot_disappear_before_baseline(self):
        data, baseline, start, end = serial()
        data = data.replace(frame(40, 100, 60), frame(40, 100, 60, 1))
        with self.assertRaisesRegex(ValueError, 'actual object use'):
            validate_execution(data, baseline, start, end, end, 'x86_64')

    def test_pressure_scope_failures_and_leaked_objects(self):
        data, baseline, start, end = serial()
        changes = [(b'hello from ObfuscationOS userland', b'wrong native result'),
                   (b'boot=complete', b'boot=failed'),
                   (frame(40, 1880, 1840), frame(40, 1880, 1840, 1)),
                   (frame(40, 1880, 1840), frame(40, 1800, 1760))]
        for old, new in changes:
            changed = data.replace(old, new)
            # Adjust boundaries for edits before the native command.
            delta = len(new) - len(old)
            before, first, last = (offset + delta * data[:offset].count(old)
                                   for offset in (baseline, start, end))
            with self.subTest(old=old), self.assertRaises(ValueError):
                validate_execution(changed, before, first, last, last, 'x86_64')
        with self.assertRaises(ValueError):
            validate_execution(data + SUCCESS, baseline, start, end, end, 'x86_64')
        with self.assertRaises(ValueError):
            validate_execution(data + b'OBJECT_PRESSURE_FAIL line=33', baseline, start, end, end, 'x86_64')

    def test_balanced_user_leak_and_missing_pipeline_baseline(self):
        data, baseline, start, end = serial()
        for old, new in ((frame(40, 1800, 1760), frame(41, 1800, 1759)),
                         (frame(40, 1880, 1840), frame(41, 1880, 1839))):
            changed = data.replace(old, new)
            delta = len(new) - len(old)
            location = data.index(old)
            first = start + (delta if location < start else 0)
            last = end + (delta if location < end else 0)
            with self.subTest(old=old), self.assertRaises(ValueError):
                validate_execution(changed, baseline, first, last, last, 'x86_64')
        old = b'hello from ObfuscationOS userland'
        changed = data[:baseline] + data[baseline:start].replace(old, b'no baseline') + data[start:]
        delta = len(changed) - len(data)
        self.assertIn(old, changed[:baseline])
        with self.assertRaisesRegex(ValueError, 'baseline'):
            validate_execution(changed, baseline, start+delta, end+delta, end+delta, 'x86_64')

    def test_missing_boot_zero_baseline(self):
        data, baseline, start, end = serial()
        changed = data.replace(frame(), frame(1, 1, 0), 1)
        delta = len(changed) - len(data)
        with self.assertRaises(ValueError):
            validate_execution(changed, baseline + delta, start + delta, end + delta, end + delta, 'x86_64')

    def test_baseline_boundaries_are_required_and_ordered(self):
        data, baseline, start, end = serial()
        with self.assertRaises(TypeError):
            validate_execution(data, start, end, end, 'x86_64')
        for boundaries in ((0, start, end, end), (start, start, end, end),
                           (start + 1, start, end, end), (baseline, end, end, end),
                           (baseline, start, start - 1, end), (baseline, start, end, end - 1),
                           (baseline, start, end, len(data)), (True, start, end, end),
                           (baseline, float(start), end, end), (baseline, start, None, end)):
            with self.subTest(boundaries=boundaries), self.assertRaisesRegex(ValueError, 'boundaries'):
                validate_execution(data, *boundaries, 'x86_64')

    def test_boundaries_must_follow_complete_prompts(self):
        data, baseline, start, end = serial()
        boundaries = [baseline, start, end, end]
        for index, delta in ((0, -1), (0, 1), (1, -1), (1, 1), (2, -1), (3, 1)):
            changed = list(boundaries)
            changed[index] += delta
            with self.subTest(index=index, delta=delta), self.assertRaisesRegex(ValueError, 'shell prompt'):
                validate_execution(data, *changed, 'x86_64')

    def test_baseline_frame_must_come_from_baseline_command(self):
        data, baseline, start, end = serial()
        for replacement in (b'', frame(59, 180, 121)):
            span = b'hello from ObfuscationOS userland\n' + replacement + b'oksh> '
            changed = data[:baseline] + span + data[start:]
            delta = len(changed) - len(data)
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                validate_execution(changed, baseline, start + delta, end + delta, end + delta, 'x86_64')

    def test_baseline_allocations_must_advance_from_boot(self):
        data, baseline, start, end = serial()
        span = b'hello from ObfuscationOS userland\n' + frame(40, 100, 60) + b'oksh> '
        changed = data[:baseline] + span + data[start:]
        delta = len(changed) - len(data)
        with self.assertRaisesRegex(ValueError, 'baseline has no fresh allocation'):
            validate_execution(changed, baseline, start + delta, end + delta, end + delta, 'x86_64')

    def test_boot_markers_must_precede_baseline_command(self):
        data, baseline, start, end = serial()
        for marker in (b'OK_SYSTEM_GUI boot=complete\n',
                       b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw\n'):
            changed = data[:baseline].replace(marker, b'') + marker + data[baseline:]
            with self.subTest(marker=marker), self.assertRaisesRegex(ValueError, 'boot evidence'):
                validate_execution(changed, baseline - len(marker), start, end, end, 'x86_64')


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        # Share the exact current admission fixture; no validator is mocked.
        fixture = sdk_fixture.KernelSdkTests('test_valid_sdk')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root, self.sdk, self.manifest = fixture.root, fixture.sdk, fixture.manifest
        self.compiler = self.root / 'g++'
        self.compiler.write_text('#!/bin/sh\ncase "$1" in\n-dumpmachine) echo x86_64-elf;;\n-dumpfullversion) echo 14.2.0;;\nesac\n')
        self.compiler.chmod(0o755)
        self.manifest_path = self.sdk / 'manifest.json'

    def admit(self, manifest=None, **kwargs):
        self.manifest_path.write_text(json.dumps(manifest or self.manifest))
        parameters = dict(sdk=self.sdk, expected=sha(self.manifest_path), arch='x86_64', mode='debug',
                          compiler=self.compiler, compiler_hash=sha(self.compiler))
        parameters.update(kwargs)
        return admit_sdk(**parameters)

    def test_complete_sdk_and_exact_copy(self):
        self.assertEqual(self.admit()['abi_version'], 74)
        copied = self.root / 'copied'
        copy_inventory(self.sdk, copied, self.manifest['files'])
        self.assertEqual({name: sha(copied / name) for name in self.manifest['files']}, self.manifest['files'])
        with self.assertRaises(FileExistsError):
            copy_inventory(self.sdk, copied, self.manifest['files'])

    def test_sdk_version_arch_mode_compiler(self):
        for field, value in (('schema', 2), ('abi_version', 22), ('abi_version', 39), ('abi_version', 40),
                             ('abi_version', 41), ('abi_version', 43), ('abi_version', 44),
                             ('abi_version', 45), ('abi_version', 46), ('abi_version', 47),
                             ('abi_version', 48), ('abi_version', 49), ('abi_version', 50), ('abi_version', 51),
                             ('abi_version', 52), ('abi_version', 53), ('abi_version', 54),
                             ('abi_version', 55), ('abi_version', 56), ('abi_version', 73),
                             ('abi_version', 75), ('abi_version', True), ('abi_version', 74.0),
                             ('ext4_ordered_data_profile', 'disabled'),
                             ('ext4_directory_rename_profile', 'bounded-mounted-dirty-same-dir-absent-fit-v1'),
                             ('ext4_directory_rename_profile', 'bounded-mounted-dirty-same-dir-absent-fit-ordered-home-v1'),
                             ('ext4_directory_rename_profile', 'bounded-mounted-dirty-same-dir-absent-fit-or-relocate-ordered-home-v3'),
                             ('ext4_first_data_profile', 'bounded-mounted-dirty-empty-regular-initial-attrs-ordered-home-v1'),
                             ('ext4_next_data_profile', 'bounded-mounted-dirty-fresh-empty-first-block-ordered-home-v1'),
                             ('arch', 'i386'), ('mode', 'release'),
                             ('triple', 'other-elf'), ('compiler', {'family': 'gcc', 'version': '13.1.0'}),
                             ('compiler', {'family': 'clang', 'version': '14.2.0'})):
            manifest = copy.deepcopy(self.manifest)
            manifest[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.admit(manifest)
        manifest = copy.deepcopy(self.manifest)
        del manifest['ext4_directory_rename_profile']
        with self.assertRaisesRegex(ValueError, 'ordered-home directory-rename profile mismatch'):
            self.admit(manifest)
        manifest = copy.deepcopy(self.manifest)
        del manifest['ext4_first_data_profile']
        with self.assertRaisesRegex(ValueError, 'ordered-home first-data profile mismatch'):
            self.admit(manifest)
        manifest = copy.deepcopy(self.manifest)
        del manifest['ext4_next_data_profile']
        with self.assertRaisesRegex(ValueError, 'ordered-home next-data profile mismatch'):
            self.admit(manifest)

    def test_explicit_hashes_are_not_optional(self):
        for kwargs in ({'expected': '0' * 64}, {'compiler_hash': '0' * 64}, {'expected': ''}):
            with self.assertRaises(ValueError):
                self.admit(**kwargs)

    def test_artifact_corruption_and_missing(self):
        artifact = self.sdk / 'lib/libokernel.a'
        artifact.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.admit()
        artifact.unlink()
        with self.assertRaises(ValueError):
            self.admit()

    def test_inventory_escape_and_missing_required(self):
        outside = self.root / 'outside'
        outside.write_bytes(b'outside')
        for name in ('../outside', str(outside), 'lib/../lib/libokernel.a'):
            manifest = copy.deepcopy(self.manifest)
            manifest['files'][name] = sha(outside)
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.admit(manifest)
        manifest = copy.deepcopy(self.manifest)
        del manifest['files']['image/kernel.bin']
        with self.assertRaises(ValueError):
            self.admit(manifest)
        (self.sdk / 'outside-link').symlink_to(outside)
        with self.assertRaises(ValueError):
            relative_file(self.sdk, 'outside-link')

    def test_source_drift_missing_added_and_symlink(self):
        root = self.root / 'os'
        root.mkdir()
        for name in ('AGENTS.md', 'xmake.lua'):
            (root / name).write_text(name)
        manifest = self.root / 'sources.json'
        manifest.write_text(json.dumps(dict(schema=1, scope='object-pressure-os-sources', files=source_files(root))))
        expected = sha(manifest)
        self.assertEqual(len(admit_sources(root, manifest, expected)['files']), 2)
        (root / 'xmake.lua').write_text('changed')
        with self.assertRaises(ValueError):
            admit_sources(root, manifest, expected)

        (root / 'xmake.lua').write_text('xmake.lua')
        (root / 'tools').mkdir()
        (root / 'tools/extra.py').write_text('extra')
        with self.assertRaises(ValueError):
            admit_sources(root, manifest, expected)
        (root / 'tools/extra.py').unlink()
        (root / 'tools/link').symlink_to(self.compiler)
        with self.assertRaises(ValueError):
            admit_sources(root, manifest, expected)

    def test_source_inventory_schema_is_an_integer(self):
        root = self.root / 'typed-source'
        root.mkdir()
        for name in ('AGENTS.md', 'xmake.lua'):
            (root / name).write_text(name)
        manifest = self.root / 'typed-sources.json'
        for schema in (True, 1.0, '1', None):
            manifest.write_text(json.dumps(dict(schema=schema, scope='object-pressure-os-sources',
                                                files=source_files(root))))
            with self.subTest(schema=schema), self.assertRaisesRegex(ValueError, 'schema/scope'):
                admit_sources(root, manifest, sha(manifest))

    def test_transitive_dependency_inventory_and_escape(self):
        first = self.root / 'source.c'
        second = self.root / 'header with space.h'
        first.write_text('source')
        second.write_text('header')
        output = f'object-pressure: {first} \\\n {str(second).replace(" ", chr(92) + " ")}\n'.encode()
        self.assertEqual(set(dependencies(['cc', '-M'], output, (self.root,))['files']), {str(first), str(second)})
        for bad in (b'wrong: foo\n', b'object-pressure: \n', b'object-pressure: /etc/passwd\n'):
            with self.assertRaises(ValueError):
                dependencies([], bad, (self.root,))


if __name__ == '__main__':
    unittest.main()

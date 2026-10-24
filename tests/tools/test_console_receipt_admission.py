"""Negative admission controls; these tests never execute guests or producers."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / 'tools/console_receipt_admission.py'
SYNTHETIC = Path('/synthetic/console-evidence')
spec = importlib.util.spec_from_file_location('console_receipt_admission', SOURCE)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def guest_fixture(mode):
    """Small synthetic semantic fixture; this is never execution evidence."""
    result = dict(status='passed-bounded-native-console-control', architecture='x86_64', mode=mode,
        actual_native_console_control=True, actual_native_sessions=True, actual_x86_musl_console_control=True,
        guest_executed=True, sdk_only=True, controlling_tty=True, bounded_foreground_groups=True,
        unwrapped_login=True, unwrapped_shell=True, distinct_authenticated_sessions=True,
        frozen_sources_unchanged=True, **{key: False for key in a.FALSE_GUEST})
    result['serial_sha256'] = '1' * 64
    result['musl_source_artifact'] = dict(consumer_mode=mode, mode='debug',
        same_admitted_static_libc_used_for_both_guest_modes=True, path='/synthetic/x86_64/debug-optimized-v1')
    result['process_retirement'] = dict(host_retired_guest=True, synchronized_guest_shutdown=False,
        host_kill_sent=False, host_terminate_sent=True, returncode=0)
    result['commands'] = [dict(returncode=0)]
    result['sessions'] = []
    for number, sid, start in ((1, 20, 100), (2, 40, 400)):
        row = dict(number=number, sid=sid, shell_pid=sid, parent=sid, pid=sid+1, pgid=sid+1, peer=sid+2,
            exact_records=24, scheduler_armed_wait_proven=False, serial_start=start, session_end=start+10,
            after_marker_start=start+80, after_marker_end=start+90)
        row['pipeline'] = dict(bytes=12289, exact_records=6, serial_start=start+10, serial_end=start+20,
            stages=[dict(sid=sid, parent=sid, pid=sid+offset, pgid=sid+3) for offset in (3, 4, 5)])
        row['alias'] = dict(exact_records=2, sid=sid, serial_start=start+20, serial_end=start+30)
        row['musl'] = dict(architecture='x86_64', exact_records=3, executed=True,
            scheduler_armed_wait_proven=False, serial_start=start+30, serial_end=start+40)
        row['nested'] = dict(exact_records=2, sid=sid, serial_start=start+40, serial_end=start+50)
        result['sessions'].append(row)
    result['console_lifecycle'] = dict(
        first_launch=dict(event='launch', generation=1, pid=20, status=0, offset=90),
        first_reap=dict(event='reap', generation=1, pid=20, status=0, offset=200),
        second_launch=dict(event='launch', generation=2, pid=40, status=0, offset=300))
    return result


def qualification_fixture():
    result = dict(schema=1, status='qualified-bounded-native-console-control-not-published',
        sdk_tuples=20, standalone_debug_boots=10, native_guest_boots=2, native_authenticated_sessions=4,
        native_guest_account_uid=0, native_records=136, linux_records=12, musl_supplied_build_profiles=4,
        musl_actual_guest_profiles=['x86_64'], hosted_contract_tests=233, hosted_contract_skips=1,
        controlling_tty=True, bounded_foreground_groups=True, background_reads_eio=True,
        separate_contract_raw_readback=True, hosted_armed_wait_coverage=True, native_uid1000_fixture_peers=True,
        original_failures_preserved=True, production_ext4_owner_buffers=9,
        production_ext4_metadata_time='signed32', **{key: False for key in a.FALSE_QUALIFIED})
    result['inputs'] = [dict(path='/synthetic/input-' + str(n), identity={'sha256': '0'*64}) for n in range(24340)]
    result['native_guests'] = [dict(mode=m, sessions=guest_fixture(m)['sessions'],
        retirement=guest_fixture(m)['process_retirement']) for m in a.MODES]
    return result


def raw_fixture(mode):
    guest = guest_fixture(mode)
    names = ['late-native-record', 'late-linux-record', 'failure-marker']
    names += ['session-' + str(n) + '-' + suffix for n in range(2) for suffix in
              ('alias-reordered', 'musl-reordered', 'pid-width', 'armed-overclaim', 'wrong-consumed-hash')]
    return dict(schema=1, status='passed-separate-contract-raw-reader', producer_imported=False,
        guest_executed_by_reader=False, canonical_mutations=False, raw_nonce_retained=False,
        scheduler_armed_wait_proven=False, orderly_shutdown=False, physical=False, full_M0_M12=False,
        sessions=[dict(sid=r['sid'], native_records=34, linux_records=3, pipeline_bytes=12289,
                       uid1000_peer=r['peer']) for r in guest['sessions']],
        controls=[dict(name=n, status='passed', rejected=True) for n in names],
        campaign={'sha256': '2'*64}, serial={'sha256': guest['serial_sha256']})


def cohort_fixture():
    result = dict(schema=1, status='passed', exact_unique_expected_rows=True, debug_standalone_qemu_rows=10,
        source_origin_unchanged=True, final_artifacts_revalidated=True, canonical_unchanged=True,
        installed_sdks_changed=False, canonical_disks_changed=False, canonical_sources_promoted=False,
        sdk_installation_requested=False, canonical_disk_mutation_requested=False,
        reused_receipts=False, reused_build_products=False, rows=[], commands=[dict(returncode=0)])
    result['expected_rows'] = [[arch, mode] for arch in a.ARCHES for mode in a.MODES]
    for arch, mode in result['expected_rows']:
        row = dict(arch=arch, mode=mode, status='passed', source_unchanged=True, sdk_unchanged=True)
        if mode == 'debug':
            row['standalone_qemu'] = dict(status='passed', marker='OK_TEST_PASS arch=' + arch + ' synthetic=1')
        result['rows'].append(row)
    return result


def contract_fixture():
    labels = ('consumer', 'sessions', 'group-signals', 'console-control', 'uapi-fields',
              'kernel-contracts', 'exporter', 'generator-tests', 'archive-receipts', 'generated-linux-abi')
    commands = [dict(label=name, returncode=0) for name in labels]
    for label, filename, count in (('consumer', 'test_kernel_sdk.py', 91),
                                    ('console-control', 'test_native_console_control_sdk.py', 7)):
        row = next(r for r in commands if r['label'] == label)
        row.update(tests=count, skipped=0, cwd=str(SYNTHETIC/'source/ObfuscationOS'),
            log=str(SYNTHETIC/('contracts-frozen-v1/'+label+'.log')),
            argv=['/usr/bin/python3', '-B', '-m', 'unittest', 'discover', '-s', 'tests/tools', '-p', filename])
    return dict(status='passed', total_tests=233, total_skipped=1, frozen_sources_unchanged=True, commands=commands)


def unittest_log(row):
    return ('Ran ' + str(row['tests']) + ' tests in 1.0s\n\nOK\n').encode()


def successor_fixture():
    original = b"publisher = 'publish_console_controls_v1.py'\n"
    successor = original.replace(b'publish_console_controls_v1.py', b'publish_console_control_v1.py')
    addendum = dict(schema=1, status='admitted-one-reference-canonical-validator-successor',
        original_preserved=True, original_script_executed=False, canonical_mutations=False, full_M0_M12=False,
        controls=dict(original_reference_missing=True, correct_publisher_regular=True,
                      exact_one_replacement=True, python_syntax=True))
    names = ('wrong-publisher', 'missing-sdk', 'wrong-frozen-source', 'wrong-transition-order',
             'unpublished', 'wrong-root', 'wrong-workspace')
    review = dict(schema=1, status='passed-independent-canonical-validator-successor-review',
        canonical_mutations=False, scripts_mutated=False, other_files_mutated=False, blocking_findings=[],
        qualified_original_and_publisher_unchanged=True, scripts_and_qualification_unchanged_after_review=True,
        review_output_directory_created=False, one_replacement=dict(status='passed', occurrences_in_v1=1,
            old='publish_console_controls_v1.py', new='publish_console_control_v1.py',
            successor_bytes_equal_v1_exact_replace=True, other_byte_changes=False),
        refusal_controls=[dict(name=name, status='passed', rejected=True) for name in names])
    return original, successor, addendum, review


def completion_fixture():
    """Synthetic completion semantics; no synthetic publication is admitted."""
    value = dict(schema=2, status='qualified-and-promoted-bounded-native-console-control',
        code_source_paths=90, documentation_paths=2, sdk_tuples=20, installed_module_abi=73,
        installed_uapi='0.15.0', standalone_debug_architectures=10, native_guest_boots=2,
        native_authenticated_uid0_sessions=4, native_console_records=136, linux_console_records=12,
        supplied_musl_build_profiles=4, original_sdk_directories_retained=True,
        source_and_sdk_byte_inverses_retained=True, canonical_source_directories_preserved=True,
        protected_disks_unchanged=True, original_failures_preserved=True, controlling_tty=True,
        bounded_foreground_groups=True, all_complete_milestone_gates_open=True,
        production_ext4='<1,9>', production_ext4_signed32=True, production_ext4_paired_io=False,
        documentation_restore_required_before_publisher_restore=True)
    value.update({key: False for key in ('native_nonzero_uid_login_tested', 'synchronized_guest_shutdown',
        'power_loss_persistence', 'pty', 'scheduler_armed_guest_wait_proven', 'termios',
        'stop_continue', 'job_control', 'smp', 'physical', 'manual_desktop', 'full_M0_M12')})
    return value


def canonical_fixture():
    """Only semantic fields; no synthetic artifact is admitted as a real run."""
    labels = ['sdk-'+arch+'-'+mode for arch in a.ARCHES for mode in a.MODES]
    labels += ['ObfuscationOS-'+name for name in ('test_kernel_sdk', 'test_native_sessions_sdk',
        'test_native_group_signal_sdk', 'test_native_console_control_sdk', 'test_uapi_fields')]
    labels += ['ObfuscationKernel-'+name for name in ('test_native_signal_export',
        'sdk_boot_archive_receipt_tests', 'linux_abi_generator_tests')]
    labels += ['kernel-configure', 'kernel-build', 'standalone-qemu', 'os-debug-configure',
               'os-debug-distro', 'os-release-configure', 'os-release-distro']
    return dict(schema=1, status='passed-canonical-console-control-admission', canonical_unchanged=True,
        sdk_only=True, standalone_qemu=True, protected_images_written=False, full_M0_M12=False,
        physical=False, smp=False, manual_desktop=False,
        installed_sdk_tuples=[[arch,mode] for arch in a.ARCHES for mode in a.MODES],
        commands=[dict(label=name, returncode=0) for name in labels],
        products={mode:dict(artifacts={str(n):{} for n in range(7)}) for mode in a.MODES},
        standalone_products={'kernel.bin':{},'kernel.elf':{}},
        test_rows=[dict(tests=n) for n in (97,6,5,7,15,27,18,15)])


class SemanticControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qualification = qualification_fixture()
        cls.guests = {m: guest_fixture(m) for m in a.MODES}
        cls.raw = {m: raw_fixture(m) for m in a.MODES}
        cls.cohort = cohort_fixture()

    def qualified_guest(self, mode='debug'):
        return next(r for r in self.qualification['native_guests'] if r['mode'] == mode)

    def test_synthetic_semantic_positives(self):
        a.check_qualification(self.qualification)
        for mode in a.MODES:
            a.check_guest(self.guests[mode], mode, self.qualified_guest(mode))
            a.check_raw(self.raw[mode], self.guests[mode])
        a.check_cohort(self.cohort)
        a.check_canonical(canonical_fixture())

    def test_qualification_overclaim_controls(self):
        for key in a.FALSE_QUALIFIED:
            with self.subTest(key=key):
                value = copy.deepcopy(self.qualification)
                value[key] = True
                with self.assertRaisesRegex(ValueError, key):
                    a.check_qualification(value)

    def test_qualification_count_and_type_controls(self):
        for key in ('schema', 'sdk_tuples', 'standalone_debug_boots', 'native_guest_boots',
                    'native_authenticated_sessions', 'native_guest_account_uid', 'native_records',
                    'linux_records', 'musl_supplied_build_profiles', 'hosted_contract_tests',
                    'hosted_contract_skips', 'production_ext4_owner_buffers'):
            with self.subTest(key=key):
                for wrong in (True, self.qualification[key] + 1):
                    value = copy.deepcopy(self.qualification)
                    value[key] = wrong
                    with self.assertRaisesRegex(ValueError, key):
                        a.check_qualification(value)

    def test_qualification_input_missing_or_duplicate(self):
        for kind in ('missing', 'duplicate'):
            with self.subTest(kind=kind):
                value = copy.deepcopy(self.qualification)
                if kind == 'missing':
                    value['inputs'].pop()
                else:
                    value['inputs'][1] = value['inputs'][0]
                with self.assertRaisesRegex(ValueError, 'input'):
                    a.check_qualification(value)

    def test_guest_overclaims_and_missing_fields(self):
        for key in a.FALSE_GUEST:
            for wrong in (True, 'false'):
                with self.subTest(key=key, wrong=wrong):
                    value = copy.deepcopy(self.guests['debug'])
                    value[key] = wrong
                    with self.assertRaisesRegex(ValueError, key):
                        a.check_guest(value, 'debug', self.qualified_guest())
        value = copy.deepcopy(self.guests['debug'])
        del value['guest_executed']
        with self.assertRaisesRegex(ValueError, 'missing guest_executed'):
            a.check_guest(value, 'debug', self.qualified_guest())

    def test_cross_mode_or_architecture_substitution(self):
        value = copy.deepcopy(self.guests['debug'])
        with self.assertRaisesRegex(ValueError, 'mode'):
            a.check_guest(value, 'release', self.qualified_guest())
        value['architecture'] = 'aarch64'
        with self.assertRaisesRegex(ValueError, 'architecture'):
            a.check_guest(value, 'debug', self.qualified_guest())

    def test_guest_and_qualification_must_correlate(self):
        value = copy.deepcopy(self.guests['debug'])
        value['sessions'][0]['sid'] += 1
        with self.assertRaisesRegex(ValueError, 'qualified guest sessions'):
            a.check_guest(value, 'debug', self.qualified_guest())

    def test_rehashed_coherent_guest_scope_controls(self):
        """Change guest and its parent together so correlation alone cannot pass."""
        changes = (
            lambda g: g['sessions'][0].update(pid=1),
            lambda g: g['sessions'][0].update(sid=True, parent=True, shell_pid=True),
            lambda g: g['sessions'][0].update(scheduler_armed_wait_proven=True),
            lambda g: g['sessions'][0]['pipeline'].update(bytes=12288),
            lambda g: g['sessions'][0]['pipeline']['stages'][1].update(pgid=9999),
            lambda g: g['sessions'][0]['musl'].update(executed=False),
            lambda g: g['sessions'][0]['musl'].update(scheduler_armed_wait_proven=True),
            lambda g: g['sessions'][0]['alias'].update(exact_records=3),
            lambda g: g['sessions'][0]['nested'].update(sid=9999),
            lambda g: g['sessions'][0]['pipeline'].update(serial_start=0),
            lambda g: g['console_lifecycle']['first_reap'].update(generation=2),
            lambda g: g['console_lifecycle']['first_reap'].update(offset=0),
            lambda g: g['process_retirement'].update(synchronized_guest_shutdown=True),
            lambda g: g['musl_source_artifact'].update(mode='release'),
            lambda g: g['musl_source_artifact'].update(path='/wrong/profile'),
            lambda g: g['commands'][0].update(returncode=False),
            lambda g: g['commands'][0].update(returncode=1),
        )
        for number, change in enumerate(changes):
            with self.subTest(number=number):
                value = copy.deepcopy(self.guests['debug'])
                change(value)
                parent = copy.deepcopy(self.qualified_guest())
                parent['sessions'] = copy.deepcopy(value['sessions'])
                parent['retirement'] = copy.deepcopy(value['process_retirement'])
                with self.assertRaises(ValueError):
                    a.check_guest(value, 'debug', parent)

    def test_raw_reader_cannot_become_native_or_nonce_proof(self):
        for key in ('producer_imported', 'guest_executed_by_reader', 'canonical_mutations',
                    'raw_nonce_retained', 'scheduler_armed_wait_proven', 'orderly_shutdown',
                    'physical', 'full_M0_M12'):
            with self.subTest(key=key):
                value = copy.deepcopy(self.raw['debug'])
                value[key] = True
                with self.assertRaisesRegex(ValueError, key):
                    a.check_raw(value, self.guests['debug'])

    def test_raw_reader_projection_and_control_corruption(self):
        changes = (
            lambda r: r['sessions'][0].update(sid=9999),
            lambda r: r['sessions'][0].update(native_records=35),
            lambda r: r['sessions'][0].update(linux_records=4),
            lambda r: r['sessions'][0].update(uid1000_peer=0),
            lambda r: r['controls'].pop(),
            lambda r: r['controls'].__setitem__(1, r['controls'][0]),
            lambda r: r['controls'][0].update(rejected=False),
            lambda r: r['controls'][0].update(status='failed'),
            lambda r: r['serial'].update(sha256='0' * 64),
        )
        for number, change in enumerate(changes):
            with self.subTest(number=number):
                value = copy.deepcopy(self.raw['debug'])
                change(value)
                with self.assertRaises(ValueError):
                    a.check_raw(value, self.guests['debug'])

    def test_cohort_cannot_omit_or_duplicate_a_tuple(self):
        for change in (lambda r: r['rows'].pop(), lambda r: r['rows'].__setitem__(1, r['rows'][0]),
                       lambda r: r['expected_rows'].__setitem__(1, r['expected_rows'][0])):
            value = copy.deepcopy(self.cohort)
            change(value)
            with self.assertRaises(ValueError):
                a.check_cohort(value)

    def test_cohort_cannot_upgrade_compiles_to_native_execution(self):
        changes = (
            lambda r: r.update(debug_standalone_qemu_rows=20),
            lambda r: r.update(reused_build_products=True),
            lambda r: r.update(canonical_sources_promoted=True),
            lambda r: r['rows'][0]['standalone_qemu'].update(marker='OK_TEST_PASS arch=wrong '),
            lambda r: r['rows'][1].update(standalone_qemu={'status': 'passed'}),
            lambda r: r['commands'][0].update(returncode=1),
        )
        for number, change in enumerate(changes):
            with self.subTest(number=number):
                value = copy.deepcopy(self.cohort)
                change(value)
                with self.assertRaises(ValueError):
                    a.check_cohort(value)

    def test_completion_requires_exact_bounded_scope(self):
        value = completion_fixture()
        a.check_completion(value)
        for key, wrong in (('status', 'prepared-not-published'), ('installed_module_abi', 72),
                           ('code_source_paths', 89), ('full_M0_M12', True), ('all_complete_milestone_gates_open', False),
                           ('original_failures_preserved', False), ('production_ext4', '<2,9>'),
                           ('native_nonzero_uid_login_tested', True), ('pty', True)):
            with self.subTest(key=key):
                changed = copy.deepcopy(value)
                changed[key] = wrong
                with self.assertRaisesRegex(ValueError, key):
                    a.check_completion(changed)

    def test_canonical_requires_complete_ordered_commands_and_profiles(self):
        value = canonical_fixture()
        a.check_canonical(value)
        changes = (
            lambda r: r.update(status='running'),
            lambda r: r.update(sdk_only=False),
            lambda r: r.update(full_M0_M12=True),
            lambda r: r['installed_sdk_tuples'].pop(),
            lambda r: r['installed_sdk_tuples'].__setitem__(1, r['installed_sdk_tuples'][0]),
            lambda r: r['commands'].pop(),
            lambda r: r['commands'].__setitem__(1, r['commands'][0]),
            lambda r: r['commands'][0].update(returncode=1),
            lambda r: r['commands'][0].update(returncode=False),
            lambda r: r['products'].pop('release'),
            lambda r: r['products']['debug']['artifacts'].pop(next(iter(r['products']['debug']['artifacts']))),
            lambda r: r['standalone_products'].pop('kernel.elf'),
            lambda r: r['test_rows'][0].update(tests=0),
            lambda r: r['test_rows'][0].update(tests=True),
            lambda r: r['test_rows'][0].update(tests=999),
        )
        for number, change in enumerate(changes):
            with self.subTest(number=number):
                mutated = copy.deepcopy(value)
                change(mutated)
                with self.assertRaises(ValueError):
                    a.check_canonical(mutated)

    @patch.object(a, 'CANONICAL_SUCCESSOR_SHA', hashlib.sha256(successor_fixture()[1]).hexdigest())
    def test_validator_successor_requires_exact_bytes_and_bounded_review(self):
        original, successor, addendum, review = successor_fixture()
        a.check_successor(original, successor, addendum, review)
        for wrong in (original, successor + b'\n', successor.replace(b'publisher =', b'owner =', 1)):
            self.assertNotEqual(wrong, successor)
            with self.subTest(byte_mutation=True), self.assertRaises(ValueError):
                a.check_successor(original, wrong, addendum, review)
        for key, wrong in (('original_preserved', False), ('original_script_executed', True),
                           ('canonical_mutations', True), ('full_M0_M12', True)):
            with self.subTest(addendum_key=key):
                changed = copy.deepcopy(addendum)
                changed[key] = wrong
                with self.assertRaises(ValueError):
                    a.check_successor(original, successor, changed, review)
        for key, wrong in (('blocking_findings', ['unresolved']), ('scripts_mutated', True),
                           ('review_output_directory_created', True)):
            with self.subTest(review_key=key):
                changed = copy.deepcopy(review)
                changed[key] = wrong
                with self.assertRaises(ValueError):
                    a.check_successor(original, successor, addendum, changed)
        changed = copy.deepcopy(review)
        changed['refusal_controls'].pop()
        with self.assertRaises(ValueError):
            a.check_successor(original, successor, addendum, changed)

    def test_exact_consumer_and_console_contract_command_bindings(self):
        value = contract_fixture()
        a.check_contracts(value, SYNTHETIC)
        for label in ('consumer', 'console-control'):
            original = next(r for r in value['commands'] if r['label'] == label)
            log = unittest_log(original)
            a.check_unittest_log(log, original)
            for field, wrong in (('tests', 999), ('skipped', 1), ('cwd', '/other/tree'),
                                 ('argv', ['/bin/true']), ('log', '/other/log'), ('returncode', False)):
                with self.subTest(label=label, field=field):
                    changed = copy.deepcopy(value)
                    next(r for r in changed['commands'] if r['label'] == label)[field] = wrong
                    with self.assertRaises(ValueError):
                        a.check_contracts(changed, SYNTHETIC)

    def test_raw_unittest_counts_and_outcomes_are_not_just_metadata(self):
        value = contract_fixture()
        row = value['commands'][0]
        data = unittest_log(row)
        for wrong in (data.replace(b'Ran 91 tests', b'Ran 90 tests'),
                      data.replace(b'\nOK\n', b'\nFAILED\n'),
                      data + b'\nRan 91 tests in 1s\nOK\n',
                      data + b'\nFAIL: injected\n'):
            with self.subTest(raw_log_mutation=True), self.assertRaises(ValueError):
                a.check_unittest_log(wrong, row)

    def test_production_successor_pin_rejects_synthetic_script_bytes(self):
        self.assertEqual(a.CANONICAL_SUCCESSOR_SHA,
                         '2b038fd36de7a2b3df23c3e1521d31b0f1df7a59d44bf03e8df5101259ec5ce0')
        original, successor, addendum, review = successor_fixture()
        with self.assertRaisesRegex(ValueError, 'successor digest'):
            a.check_successor(original, successor, addendum, review)

    def test_exact_eleven_reference_dispatch_never_parses_scripts(self):
        class FakeFiles:
            def __init__(self):
                self.json_reads, self.byte_reads = [], []

            def read(self, path, expected):
                self.json_reads.append(path)
                if path.endswith('.py'):
                    raise AssertionError('script dispatched as JSON')
                return {'synthetic_reference': path}

            def identity(self, path, expected, capture=False):
                self.byte_reads.append(path)
                self_outer.assertTrue(capture)
                self_outer.assertTrue(path.endswith('.py'))
                return expected, b'not JSON; never executable'

        self_outer = self
        refs = {str(SYNTHETIC / n): {'sha256': '0' * 64} for n in a.COMPLETION_JSON + a.COMPLETION_EXTRA}
        self.assertEqual(len(refs), 11)
        files = FakeFiles()
        loaded, scripts = a.read_completion_references(files, refs, SYNTHETIC)
        self.assertEqual(len(loaded), 9)
        self.assertEqual(len(files.json_reads), 9)
        self.assertEqual(len(files.byte_reads), 2)
        self.assertEqual(scripts, [b'not JSON; never executable'] * 2)
        for missing in refs:
            with self.subTest(missing=missing):
                changed = dict(refs)
                del changed[missing]
                untouched = FakeFiles()
                with self.assertRaisesRegex(ValueError, 'reference scope'):
                    a.read_completion_references(untouched, changed, SYNTHETIC)
                self.assertEqual(untouched.json_reads + untouched.byte_reads, [])
        changed = dict(refs)
        changed[str(SYNTHETIC / 'foreign.json')] = {'sha256': '0' * 64}
        with self.assertRaisesRegex(ValueError, 'reference scope'):
            a.read_completion_references(FakeFiles(), changed, SYNTHETIC)


class FileBoundaryControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='console-evidence-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'receipt.json'
        self.path.write_bytes(b'{"schema":1}\n')
        self.sha = hashlib.sha256(self.path.read_bytes()).hexdigest()

    def test_real_regular_file_positive(self):
        files = a.Files()
        self.assertEqual(files.read(self.path, self.sha), {'schema': 1})
        files.stable()

    def test_hash_size_mode_and_bool_identity_corruption(self):
        for expected in ({'sha256': '0' * 64}, {'sha256': self.sha, 'bytes': 999},
                         {'sha256': self.sha, 'mode': 0}, {'sha256': self.sha, 'bytes': True}):
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                a.Files().identity(self.path, expected)

    def test_symlink_file_and_parent_refused(self):
        alias = self.root / 'alias'
        alias.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError, 'redirected'):
            a.Files().identity(alias, self.sha)
        directory = self.root / 'directory'
        directory.symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'redirected'):
            a.Files().identity(directory / self.path.name, self.sha)

    def test_nonregular_artifact_refused(self):
        with self.assertRaisesRegex(ValueError, 'regular'):
            a.Files().identity(self.root, self.sha)

    def test_missing_file_refused(self):
        with self.assertRaises(OSError):
            a.Files().identity(self.root / 'absent', self.sha)

    def test_duplicate_keys_nan_and_nonobject_refused(self):
        for data in (b'{"schema":1,"schema":1}', b'{"number":NaN}', b'{"number":Infinity}', b'[]'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                a.json_object(data)

    def test_traversal_alias_and_invalid_digest_refused(self):
        for name in ('../elsewhere', '/tmp/../etc/passwd', '/tmp//thing', 'relative/file', '/tmp/a\\b'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                a.absolute(name)
        for name in ('../elsewhere', '/absolute', 'a/../../b', 'a//b', '.'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                a.relative(name)
        for value in ('A' * 64, '0' * 63, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                a.digest(value)

    def test_seen_file_mutation_refused_even_when_new_pin_matches(self):
        files = a.Files()
        files.identity(self.path, self.sha)
        self.path.write_bytes(b'{"schema":2}\n')
        new = hashlib.sha256(self.path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'changed'):
            files.identity(self.path, new)
        with self.assertRaisesRegex(ValueError, 'changed'):
            files.stable()

    def test_seen_file_atomic_replacement_refused(self):
        files = a.Files()
        files.identity(self.path, self.sha)
        replacement = self.root / 'replacement'
        replacement.write_bytes(self.path.read_bytes())
        os.replace(replacement, self.path)
        with self.assertRaisesRegex(ValueError, 'changed'):
            files.stable()

    def test_missing_completion_never_admits(self):
        with self.assertRaises(OSError):
            a.Admission(self.root).run('0' * 64)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Read the pinned ABI73 console evidence; propose mappings without closing gates.

This is a deliberately version-specific historical receipt reader. It executes
no receipt-supplied code, producer, compiler, emulator or old baseline guard.
The explicit completion digest is its trust root. The exact qualification digest
also prevents silently admitting another experiment under this slice's contract.
Output is written only to stdout. File contents (including test credentials) are
never included in the report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

ARCHES = ('i386', 'x86_64', 'aarch64', 'arm32', 'rv64', 'rv32',
          'loongarch64', 'mips', 'mips64', 'ppc')
MODES = ('debug', 'release')
QUALIFICATION_SHA = '1c6aab3dc24c9b55ed0db35bdb42129dfcca77d6bafef3c32d23aa90b5e939c7'
CANONICAL_SUCCESSOR_SHA = '2b038fd36de7a2b3df23c3e1521d31b0f1df7a59d44bf03e8df5101259ec5ce0'
COMPLETION_JSON = ('publication-v1/plan.json', 'publication-v1/result.json', 'canonical-admission-v1/result.json',
                   'qualification-v1.json', 'post-doc-source-inventory-v1.json',
                   'documentation-rollout-v1/plan.json', 'documentation-rollout-v1/journal.json')
COMPLETION_EXTRA = ('validate_canonical_console_control_v1.py', 'validate_canonical_console_control_v2.py',
                    'canonical-validator-successor-v1.json', 'independent-canonical-validator-successor-review-v1.json')
FALSE_QUALIFIED = (
    'native_nonzero_uid_login_tested', 'scheduler_armed_guest_wait_proven',
    'native_select', 'retained_group_foreground_guest', 'pty', 'job_control',
    'termios', 'stop_continue', 'synchronized_guest_shutdown',
    'power_loss_persistence', 'protected_images_written', 'smp', 'physical',
    'manual_desktop', 'full_M0_M12', 'production_ext4_paired_io')
FALSE_GUEST = ('native_select', 'scheduler_armed_wait_proven', 'pty', 'retained_group_foreground_case',
               'stop_continue', 'full_job_control', 'synchronized_guest_shutdown',
               'power_loss_persistence', 'smp', 'physical', 'full_M0_M12',
               'canonical_promotion', 'kernel_source_compiled_by_os',
               'development_artifact_reuse')
LIMITATIONS = (
    'Only x86_64 Debug/Release guests execute the console feature; ten architecture selections in hosted adapters are not ten native guests.',
    'Four supplied musl profiles compile; actual musl/Linux console execution is x86_64 only. Both guest modes use the recorded debug-optimized-v1 static libc.',
    'Four authenticated sessions are UID0; UID1000 peers are fixtures, not ordinary-account login evidence.',
    'Guest armed waits remain unproven; armed-state coverage is hosted only.',
    'Retained-group foreground behavior lacks native guest coverage.',
    'Background reads use bounded EIO; this does not implement SIGTTIN/SIGTTOU.',
    'No PTY, termios, line discipline, generic /dev/tty, HUP, stop/continue or full shell job control.',
    'Raw nonce bytes were not retained or reconstructed; the producer checked input/noecho, and the separate reader binds hashes/FNV and chronology.',
    'The raw reader is separate contract code, not a newly completed independent-agent approval.',
    'Guests are host-retired; no synchronized shutdown or power-loss persistence is established by this campaign.',
    'No concurrent SMP, physical-machine or manual desktop acceptance; physical M11 and manual M12 remain user-deferred.',
    'Production ext4 remains <1,9>, signed32, without paired I/O.',
    'Original failed attempts remain failed; successful successors do not replace or relabel them.',
    'Admission rechecks retained immutable inputs and canonical-validation products, not current live sources, installed SDK directory identities, inverse trees or protected disk state.',
    'All full M0-M12 gates remain open. This report neither rewrites the ledger nor supplies reviewed normative indexes.')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def exact(value, expected, label):
    need(type(value) is type(expected) and value == expected, label + ' differs')


def fields(value, expected, label):
    need(type(value) is dict, label + ' must be an object')
    for key, item in expected.items():
        need(key in value, label + ' missing ' + key)
        exact(value[key], item, label + '.' + key)


def json_object(data):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result

    def invalid(_):
        raise ValueError('non-finite JSON number')

    value = json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid)
    need(type(value) is dict, 'receipt root must be an object')
    return value


def digest(value):
    need(type(value) is str and re.fullmatch(r'[0-9a-f]{64}', value), 'invalid SHA256')
    return value


def absolute(value):
    need(type(value) is str, 'artifact path must be a string')
    path = PurePosixPath(value)
    need(path.is_absolute() and '..' not in path.parts and str(path) == value
         and '\\' not in value and '\x00' not in value, 'unsafe absolute artifact path')
    return Path(value)


def relative(value):
    need(type(value) is str, 'relative path must be a string')
    path = PurePosixPath(value)
    need(not path.is_absolute() and '..' not in path.parts and str(path) == value
         and value != '.' and '\\' not in value, 'unsafe relative artifact path')
    return value


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


class Files:
    """No-follow, streaming identity reads; reject changes during one admission."""

    def __init__(self):
        self.seen = {}
        self.total_bytes = 0

    def checked_path(self, name):
        path = absolute(str(name))
        for item in (path, *path.parents):
            need(not item.is_symlink(), 'redirected artifact path: ' + str(item))
        return path

    def identity(self, name, expected, capture=False):
        path = self.checked_path(name)
        expected = {'sha256': digest(expected)} if isinstance(expected, str) else expected
        need(type(expected) is dict and 'sha256' in expected, 'missing artifact identity')
        digest(expected['sha256'])
        for key in ('bytes', 'mode'):
            if key in expected:
                need(type(expected[key]) is int and expected[key] >= 0, 'invalid identity ' + key)
        info = path.lstat()
        need(stat.S_ISREG(info.st_mode), 'artifact is not a regular file: ' + str(path))
        if not capture and str(path) in self.seen:
            prior, observed = self.seen[str(path)]
            need(fingerprint(info) == prior, 'previously read input changed: ' + str(path))
        else:
            chunks, hasher = [], hashlib.sha256()
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                need(fingerprint(os.fstat(fd)) == fingerprint(info), 'artifact changed before open')
                while True:
                    chunk = os.read(fd, 1024 * 1024)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    if capture:
                        need(sum(map(len, chunks)) + len(chunk) <= 64 * 1024 * 1024,
                             'JSON receipt exceeds size limit')
                        chunks.append(chunk)
                need(fingerprint(os.fstat(fd)) == fingerprint(info), 'artifact changed during read')
            finally:
                os.close(fd)
            need(fingerprint(path.lstat()) == fingerprint(info), 'artifact changed after read')
            observed = dict(sha256=hasher.hexdigest(), bytes=info.st_size, mode=stat.S_IMODE(info.st_mode))
            if str(path) in self.seen:
                need(self.seen[str(path)] == (fingerprint(info), observed), 'input changed while parsing')
            else:
                self.total_bytes += info.st_size
                self.seen[str(path)] = (fingerprint(info), observed)
        for key in ('sha256', 'bytes', 'mode'):
            if key in expected:
                exact(observed[key], expected[key], 'artifact ' + key + ': ' + str(path))
        return (observed, b''.join(chunks)) if capture else observed

    def read(self, name, expected):
        _, data = self.identity(name, expected, capture=True)
        return json_object(data)

    def stable(self):
        for name, (old, _) in self.seen.items():
            path = self.checked_path(name)
            need(fingerprint(path.lstat()) == old, 'input changed before report: ' + name)


def check_qualification(value):
    fields(value, dict(schema=1, status='qualified-bounded-native-console-control-not-published',
        sdk_tuples=20, standalone_debug_boots=10, native_guest_boots=2,
        native_authenticated_sessions=4, native_guest_account_uid=0, native_records=136,
        linux_records=12, musl_supplied_build_profiles=4, musl_actual_guest_profiles=['x86_64'],
        hosted_contract_tests=233, hosted_contract_skips=1, controlling_tty=True,
        bounded_foreground_groups=True, background_reads_eio=True, separate_contract_raw_readback=True,
        hosted_armed_wait_coverage=True, native_uid1000_fixture_peers=True,
        original_failures_preserved=True, production_ext4_owner_buffers=9,
        production_ext4_metadata_time='signed32', **{key: False for key in FALSE_QUALIFIED}), 'qualification')
    need(len(value['inputs']) == 24340, 'qualification immutable input count differs')
    names = [row['path'] for row in value['inputs']]
    need(len(names) == len(set(names)), 'duplicate qualification input')
    need(len(value['native_guests']) == 2 and
         {row['mode'] for row in value['native_guests']} == set(MODES), 'qualification guest modes differ')


def check_guest(value, mode, qualified):
    fields(value, dict(status='passed-bounded-native-console-control', architecture='x86_64', mode=mode,
        actual_native_console_control=True, actual_native_sessions=True,
        actual_x86_musl_console_control=True, guest_executed=True, sdk_only=True,
        controlling_tty=True, bounded_foreground_groups=True, unwrapped_login=True,
        unwrapped_shell=True, distinct_authenticated_sessions=True,
        frozen_sources_unchanged=True, **{key: False for key in FALSE_GUEST}), 'guest')
    exact(value['sessions'], qualified['sessions'], 'qualified guest sessions')
    exact(value['process_retirement'], qualified['retirement'], 'qualified retirement')
    fields(value['musl_source_artifact'], dict(consumer_mode=mode, mode='debug',
        same_admitted_static_libc_used_for_both_guest_modes=True), 'musl libc artifact')
    need(value['musl_source_artifact']['path'].endswith('/x86_64/debug-optimized-v1'),
         'musl source build profile differs')
    fields(value['process_retirement'], dict(host_retired_guest=True, synchronized_guest_shutdown=False,
                                           host_kill_sent=False, host_terminate_sent=True, returncode=0), 'retirement')
    rows = value['sessions']
    need(len(rows) == 2 and rows[0]['sid'] != rows[1]['sid'], 'two distinct sessions required')
    previous = 0
    for number, row in enumerate(rows, 1):
        fields(row, dict(number=number, exact_records=24, scheduler_armed_wait_proven=False), 'session')
        need(row['sid'] == row['shell_pid'] == row['parent'] and row['pid'] == row['pgid'] and
             len({row['sid'], row['pid'], row['peer'], 1}) == 4, 'session identity differs')
        for key in ('sid', 'shell_pid', 'parent', 'pid', 'pgid', 'peer'):
            need(type(row[key]) is int and 1 < row[key] <= 0x7fffffff, 'invalid signed32 PID')
        need(previous <= row['serial_start'] < row['session_end'] <= row['pipeline']['serial_start'] <
             row['pipeline']['serial_end'] <= row['alias']['serial_start'] < row['alias']['serial_end'] <=
             row['musl']['serial_start'] < row['musl']['serial_end'] <= row['nested']['serial_start'] <
             row['nested']['serial_end'] <= row['after_marker_start'] < row['after_marker_end'], 'session chronology differs')
        previous = row['after_marker_end']
        fields(row['pipeline'], dict(bytes=12289, exact_records=6), 'pipeline')
        stages = row['pipeline']['stages']
        need(len(stages) == 3 and len({s['pid'] for s in stages}) == 3 and
             all(s['sid'] == row['sid'] and s['parent'] == row['sid'] and
                 s['pgid'] == stages[0]['pid'] for s in stages), 'pipeline identity differs')
        for key in ('alias', 'nested'):
            fields(row[key], dict(exact_records=2, sid=row['sid']), key)
        fields(row['musl'], dict(architecture='x86_64', exact_records=3, executed=True,
                                scheduler_armed_wait_proven=False), 'Linux probe')
    life = value['console_lifecycle']
    fields(life['first_launch'], dict(event='launch', generation=1, pid=rows[0]['sid'], status=0), 'first launch')
    fields(life['first_reap'], dict(event='reap', generation=1, pid=rows[0]['sid'], status=0), 'first reap')
    fields(life['second_launch'], dict(event='launch', generation=2, pid=rows[1]['sid'], status=0), 'second launch')
    need(life['first_launch']['offset'] < rows[0]['serial_start'] < rows[0]['after_marker_end'] <=
         life['first_reap']['offset'] < life['second_launch']['offset'] < rows[1]['serial_start'], 'PID1 chronology differs')
    for row in value['commands']:
        exact(row['returncode'], 0, 'guest command returncode')


def check_raw(value, guest):
    fields(value, dict(schema=1, status='passed-separate-contract-raw-reader', producer_imported=False,
        guest_executed_by_reader=False, canonical_mutations=False, raw_nonce_retained=False,
        scheduler_armed_wait_proven=False, orderly_shutdown=False, physical=False, full_M0_M12=False), 'raw reader')
    expected = [dict(sid=row['sid'], native_records=34, linux_records=3, pipeline_bytes=12289,
                     uid1000_peer=row['peer']) for row in guest['sessions']]
    exact(value['sessions'], expected, 'raw reader projection')
    names = {'late-native-record', 'late-linux-record', 'failure-marker'}
    names.update('session-' + str(n) + '-' + suffix for n in range(2) for suffix in
                 ('alias-reordered', 'musl-reordered', 'pid-width', 'armed-overclaim', 'wrong-consumed-hash'))
    need(len(value['controls']) == 13 and {r['name'] for r in value['controls']} == names,
         'raw reader controls differ')
    for row in value['controls']:
        fields(row, dict(status='passed', rejected=True), 'raw reader control')
    digest(value['campaign']['sha256'])
    exact(value['serial']['sha256'], guest['serial_sha256'], 'raw/guest serial digest')


def check_cohort(value):
    fields(value, dict(schema=1, status='passed', exact_unique_expected_rows=True,
        debug_standalone_qemu_rows=10, source_origin_unchanged=True, final_artifacts_revalidated=True,
        canonical_unchanged=True, installed_sdks_changed=False, canonical_disks_changed=False,
        canonical_sources_promoted=False, sdk_installation_requested=False,
        canonical_disk_mutation_requested=False, reused_receipts=False, reused_build_products=False), 'cohort')
    expected = {(a, m) for a in ARCHES for m in MODES}
    need(len(value['rows']) == 20 and {(r['arch'], r['mode']) for r in value['rows']} == expected,
         'twenty distinct cohort tuples required')
    need(len(value['expected_rows']) == 20 and set(map(tuple, value['expected_rows'])) == expected,
         'cohort expected matrix differs')
    for row in value['rows']:
        fields(row, dict(status='passed', source_unchanged=True, sdk_unchanged=True), 'cohort tuple')
        if row['mode'] == 'debug':
            fields(row['standalone_qemu'], dict(status='passed'), 'standalone boot')
            need(row['standalone_qemu']['marker'].startswith('OK_TEST_PASS arch=' + row['arch'] + ' '),
                 'standalone architecture differs')
        else:
            need('standalone_qemu' not in row, 'release standalone overclaim')
    for row in value['commands']:
        exact(row['returncode'], 0, 'cohort command returncode')


def check_contracts(value, base):
    fields(value, dict(status='passed', total_tests=233, total_skipped=1, frozen_sources_unchanged=True), 'contracts')
    labels = ('consumer', 'sessions', 'group-signals', 'console-control', 'uapi-fields',
              'kernel-contracts', 'exporter', 'generator-tests', 'archive-receipts', 'generated-linux-abi')
    exact([r['label'] for r in value['commands']], list(labels), 'contract command sequence')
    for row in value['commands']:
        exact(row['returncode'], 0, 'contract command returncode')
    for label, name, tests in (('consumer', 'test_kernel_sdk.py', 91),
                               ('console-control', 'test_native_console_control_sdk.py', 7)):
        row = next(r for r in value['commands'] if r['label'] == label)
        fields(row, dict(tests=tests, skipped=0, cwd=str(base / 'source/ObfuscationOS'),
            log=str(base / ('contracts-frozen-v1/' + label + '.log')),
            argv=['/usr/bin/python3', '-B', '-m', 'unittest', 'discover', '-s', 'tests/tools', '-p', name]),
            'contract command ' + label)


def check_unittest_log(data, row):
    text = data.decode('utf-8')
    counts = re.findall(r'^Ran ([1-9][0-9]*) tests? in ', text, re.M)
    exact(counts, [str(row['tests'])], 'contract raw log test count')
    need(len(re.findall(r'^OK$', text, re.M)) == 1 and
         not re.search(r'^(?:FAILED|ERROR:|FAIL:)', text, re.M), 'contract raw log outcome differs')


def check_completion(value):
    fields(value, dict(schema=2, status='qualified-and-promoted-bounded-native-console-control',
        code_source_paths=90, documentation_paths=2, sdk_tuples=20, installed_module_abi=73,
        installed_uapi='0.15.0', standalone_debug_architectures=10, native_guest_boots=2,
        native_authenticated_uid0_sessions=4, native_console_records=136, linux_console_records=12,
        supplied_musl_build_profiles=4, original_sdk_directories_retained=True,
        source_and_sdk_byte_inverses_retained=True, canonical_source_directories_preserved=True,
        protected_disks_unchanged=True, original_failures_preserved=True, controlling_tty=True,
        bounded_foreground_groups=True, all_complete_milestone_gates_open=True,
        production_ext4='<1,9>', production_ext4_signed32=True, production_ext4_paired_io=False,
        documentation_restore_required_before_publisher_restore=True,
        **{key: False for key in ('native_nonzero_uid_login_tested', 'synchronized_guest_shutdown',
            'power_loss_persistence', 'pty', 'scheduler_armed_guest_wait_proven', 'termios',
            'stop_continue', 'job_control', 'smp', 'physical', 'manual_desktop', 'full_M0_M12')}), 'completion')


def check_canonical(value):
    fields(value, dict(schema=1, status='passed-canonical-console-control-admission', canonical_unchanged=True,
        sdk_only=True, standalone_qemu=True, protected_images_written=False, full_M0_M12=False,
        physical=False, smp=False, manual_desktop=False), 'canonical admission')
    expected = {(a, m) for a in ARCHES for m in MODES}
    need(len(value['installed_sdk_tuples']) == 20 and
         set(map(tuple, value['installed_sdk_tuples'])) == expected, 'canonical SDK tuples differ')
    labels = ['sdk-' + a + '-' + m for a in ARCHES for m in MODES]
    labels += ['ObfuscationOS-' + n for n in ('test_kernel_sdk', 'test_native_sessions_sdk',
        'test_native_group_signal_sdk', 'test_native_console_control_sdk', 'test_uapi_fields')]
    labels += ['ObfuscationKernel-' + n for n in ('test_native_signal_export',
        'sdk_boot_archive_receipt_tests', 'linux_abi_generator_tests')]
    labels += ['kernel-configure', 'kernel-build', 'standalone-qemu', 'os-debug-configure',
               'os-debug-distro', 'os-release-configure', 'os-release-distro']
    exact([r['label'] for r in value['commands']], labels, 'canonical command sequence')
    for row in value['commands']:
        exact(row['returncode'], 0, 'canonical command returncode')
    need(set(value['products']) == set(MODES) and all(len(r['artifacts']) == 7 for r in value['products'].values()),
         'canonical consumer products differ')
    need(set(value['standalone_products']) == {'kernel.bin', 'kernel.elf'}, 'canonical standalone products differ')
    need(len(value['test_rows']) == 8 and all(type(r['tests']) is int and r['tests'] > 0
         for r in value['test_rows']) and sum(r['tests'] for r in value['test_rows']) == 190,
         'canonical targeted test counts differ')


def check_successor(original, successor, addendum, review):
    """Review a literal substitution as bytes; never import either validator."""
    old = b'publish_console_controls_v1.py'
    new = b'publish_console_control_v1.py'
    need(original.count(old) == 1 and original.replace(old, new) == successor,
         'canonical successor is not the exact one-reference delta')
    exact(hashlib.sha256(successor).hexdigest(), CANONICAL_SUCCESSOR_SHA, 'canonical successor digest')
    fields(addendum, dict(schema=1, status='admitted-one-reference-canonical-validator-successor',
        original_preserved=True, original_script_executed=False, canonical_mutations=False,
        full_M0_M12=False), 'successor addendum')
    fields(addendum['controls'], dict(original_reference_missing=True, correct_publisher_regular=True,
        exact_one_replacement=True, python_syntax=True), 'successor controls')
    fields(review, dict(schema=1, status='passed-independent-canonical-validator-successor-review',
        canonical_mutations=False, scripts_mutated=False, other_files_mutated=False,
        blocking_findings=[], qualified_original_and_publisher_unchanged=True,
        scripts_and_qualification_unchanged_after_review=True, review_output_directory_created=False), 'successor review')
    fields(review['one_replacement'], dict(status='passed', occurrences_in_v1=1,
        old=old.decode(), new=new.decode(), successor_bytes_equal_v1_exact_replace=True,
        other_byte_changes=False), 'reviewed delta')
    controls = review['refusal_controls']
    need(len(controls) == 7 and {r['name'] for r in controls} ==
         {'wrong-publisher', 'missing-sdk', 'wrong-frozen-source', 'wrong-transition-order',
          'unpublished', 'wrong-root', 'wrong-workspace'}, 'successor review controls differ')
    for row in controls:
        fields(row, dict(status='passed', rejected=True), 'successor refusal')


def read_completion_references(files, refs, base):
    """Eleven exact references: nine JSON documents and two inert source files."""
    local = lambda name: str(base / name)
    need(type(refs) is dict and set(refs) == {local(n) for n in COMPLETION_JSON + COMPLETION_EXTRA},
         'completion reference scope differs')
    loaded = {name: files.read(local(name), refs[local(name)]) for name in
              COMPLETION_JSON + COMPLETION_EXTRA[2:]}
    scripts = [files.identity(local(name), refs[local(name)], capture=True)[1] for name in COMPLETION_EXTRA[:2]]
    return loaded, scripts


class Admission:
    def __init__(self, project_root, files=None):
        self.root = absolute(str(Path(project_root)))
        self.base = self.root / 'build/qualification/native-console-control-candidate-v1'
        self.files = files or Files()
        self.pins = {}

    def local(self, name):
        return str(self.base / relative(name))

    def pinned(self, name):
        path = self.local(name)
        need(path in self.pins, 'receipt absent from qualification closure: ' + name)
        return self.files.read(path, self.pins[path])

    def qualification(self):
        value = self.files.read(self.local('qualification-v1.json'), QUALIFICATION_SHA)
        check_qualification(value)
        for row in value['inputs']:
            path = str(absolute(row['path']))
            need(path not in self.pins, 'duplicate qualification input')
            self.files.identity(path, row['identity'])
            self.pins[path] = row['identity']
        return value

    def link(self, link, path=None):
        need(type(link) is dict and 'path' in link, 'missing artifact link')
        if path is not None:
            exact(link['path'], str(path), 'linked artifact path')
        identity = link.get('identity', link)
        return self.files.identity(link['path'], identity)

    def historical_closure(self, qualified):
        cohort = self.pinned('full-cohort-v1/result.json')
        check_cohort(cohort)
        for mode in MODES:
            name = 'native-console-control-' + mode + '-v2/result.json'
            guest = self.pinned(name)
            selected = next(r for r in qualified['native_guests'] if r['mode'] == mode)
            self.link(selected['receipt'], self.local(name))
            check_guest(guest, mode, selected)
            raw = self.pinned('raw-' + mode + '-v2-reader-v2.json')
            check_raw(raw, guest)
            self.link(raw['campaign'], self.local(name))
            self.link(raw['serial'], self.base / ('native-console-control-' + mode + '-v2/serial.log'))
            self.link(raw['reader'], self.base / 'read_console_control_raw_v2.py')
            self.link(raw['fixture_contract'], self.base / 'console-fixture-contract-v2.json')
            row = next(r for r in cohort['rows'] if (r['arch'], r['mode']) == ('x86_64', mode))
            exact(guest['sdk_input']['path'], row['sdk_path'], 'guest cohort SDK')
            exact(guest['sdk_input']['manifest_sha256'], row['sdk_manifest_sha256'], 'guest SDK manifest')
            exact(guest['completed_sdk_row'], row['completed_row_receipt'], 'guest completed cohort row')
        for name, sanitized in (('hosted-console-control-frozen-v1', False), ('hosted-console-control-asan-v3', True)):
            value = self.pinned(name + '/result.json')
            fields(value, dict(status='passed', sanitizer=sanitized, architectures=['x86_64']), 'hosted runtime')
            need(len(value['rows']) == 1, 'hosted row count differs')
            fields(value['rows'][0], dict(architecture='x86_64', status='passed',
                output='NATIVE_CONSOLE_CONTROL_RUNTIME_PASS native_calls=75 linux_calls=183 profiles=10 hosted=1 guest=0'), 'hosted row')
        contracts = self.pinned('contracts-frozen-v1/result.json')
        check_contracts(contracts, self.base)
        for row in contracts['commands']:
            if row['label'] in ('consumer', 'console-control'):
                _, data = self.files.identity(row['log'], row['log_identity'], capture=True)
                check_unittest_log(data, row)
        musl = self.pinned('musl-frozen-v1/result.json')
        fields(musl, dict(schema=1, status='passed-four-frozen-musl-builds', executed=False), 'musl compile')
        need(len(musl['musl']) == 4 and {r['arch'] for r in musl['musl']} ==
             {'x86_64', 'aarch64', 'rv64', 'loongarch64'}, 'four supplied musl profiles differ')
        need(all(r['executed'] is False for r in musl['musl']), 'musl compile receipt claims execution')
        controls = self.pinned('console-runner-stream-controls-v1/result.json')
        fields(controls, dict(status='passed-parser-and-read-only-admission-controls', total_controls=127,
            target_executed=False, final_campaign_executed=False, production_sources_modified=False), 'stream controls')
        need(len(controls['controls']) == 127 and all(r['status'] == 'passed' for r in controls['controls']),
             'stream control result differs')
        return cohort

    def promoted(self, completion_sha):
        completion_path = self.local('canonical-rollout-completion-v1.json')
        completed = self.files.read(completion_path, digest(completion_sha))
        check_completion(completed)
        refs = completed['references']
        names, extra = COMPLETION_JSON, COMPLETION_EXTRA
        loaded, scripts = read_completion_references(self.files, refs, self.base)
        addendum, review = (loaded[n] for n in extra[2:])
        check_successor(*scripts, addendum, review)
        for key, name in (('qualified_original', extra[0]), ('successor', extra[1]),
                          ('publisher', 'publish_console_control_v1.py')):
            self.link(addendum[key], self.local(name))
        exact(addendum['qualified_original']['identity'], refs[self.local(extra[0])], 'qualified original validator pin')
        exact(addendum['successor']['identity'], refs[self.local(extra[1])], 'successor validator pin')
        exact(addendum['qualified_original']['qualification_input'],
              {key: addendum['qualified_original'][key] for key in ('path', 'identity')}, 'qualified original input binding')
        expected_review = {self.local(extra[0]): refs[self.local(extra[0])],
                           self.local(extra[1]): refs[self.local(extra[1])],
                           self.local('publish_console_control_v1.py'): addendum['publisher']['identity'],
                           self.local('qualification-v1.json'): refs[self.local('qualification-v1.json')]}
        exact(review['inputs'], expected_review, 'successor review input closure')
        for path, identity in review['inputs'].items():
            self.files.identity(path, identity)
        exact(refs[self.local('qualification-v1.json')]['sha256'], QUALIFICATION_SHA, 'completion qualification pin')
        self.link(completed['runner'])
        plan, published, canonical = (loaded[n] for n in names[:3])
        fields(plan, dict(schema=3, root=str(self.root), workspace=self.local('publication-v1')), 'publication plan')
        self.files.identity(self.local('publish_console_control_v1.py'), plan['publisher'])
        self.link(plan['helper'])
        self.link(plan['qualification'], self.local('qualification-v1.json'))
        exact(plan['qualification']['identity'], refs[self.local('qualification-v1.json')], 'plan qualification identity')
        fields(published, dict(schema=3, status='published-awaiting-canonical-admission', full_M0_M12=False,
            publication_crash_atomic=False, protected_images_written=False, source_directories_changed=False,
            canonical_admission_complete=False), 'publication')
        need('apply_error' not in published and 'restore_errors' not in published, 'publication has errors')
        need(len(plan['sources']) == 90 and len({r['target'] for r in plan['sources']}) == 90,
             'publication source count differs')
        keys = {a + '/' + m for a in ARCHES for m in MODES}
        need(len(plan['sdks']) == 20 and {r['key'] for r in plan['sdks']} == keys, 'publication SDK matrix differs')
        expected = []
        for row in plan['sources']:
            expected.extend(dict(kind='source', target=row['target'], state=s) for s in ('publish-intent', 'published'))
        for row in plan['sdks']:
            expected.extend(dict(kind='sdk', target=row['key'], state=s) for s in
                ('retire-original-intent', 'original-retired', 'install-new-intent', 'new-installed'))
        exact([{k: r[k] for k in ('kind', 'target', 'state')} for r in published['transitions']], expected,
              'publication transition chronology')
        check_canonical(canonical)
        exact(canonical['publication'], {self.local(n): refs[self.local(n)] for n in names[:2]}, 'canonical publication pins')
        self.link(canonical['runner'])
        exact(canonical['runner']['path'], self.local(extra[1]), 'canonical successor runner path')
        exact(canonical['runner']['sha256'], CANONICAL_SUCCESSOR_SHA, 'canonical successor runner digest')
        self.link(canonical['cohort_helper'])
        for row in canonical['commands']:
            self.files.identity(row['log'], row['log_identity'])
        for group in canonical['products'].values():
            for path, identity in group['artifacts'].items():
                self.files.identity(path, identity)
        for name, identity in canonical['standalone_products'].items():
            self.files.identity(self.local('canonical-admission-v1/source/ObfuscationKernel/build/linux/x86_64/debug/' + name), identity)
        docplan, journal = loaded[names[5]], loaded[names[6]]
        fields(docplan, dict(schema=2, publisher_plan=self.local(names[0]),
                            publisher_plan_identity=refs[self.local(names[0])]), 'document plan')
        fields(journal, dict(schema=1, status='published-with-retained-inverses'), 'document journal')
        need(len(docplan['rows']) == 2 and {Path(r['target']).name for r in docplan['rows']} ==
             {'MILESTONE_STATUS.md', 'IMPLEMENTATION_PROGRESS.md'}, 'document scope differs')
        expected_post = json.loads(json.dumps(plan['after']['sources']))
        doc_transitions = []
        for row in docplan['rows']:
            name = Path(row['target']).name
            exact(row['target'], str(self.root / 'ObfuscationOS/docs/plans' / name), 'document target')
            exact(expected_post['ObfuscationOS']['files']['docs/plans/' + name], row['old'], 'document predecessor')
            expected_post['ObfuscationOS']['files']['docs/plans/' + name] = row['new']
            self.files.identity(row['inverse'], row['old'])
            self.files.identity(row['forward'], row['new'])
            doc_transitions.extend(dict(target=row['target'], state=s) for s in ('publish-intent', 'published'))
        exact(journal['transitions'], doc_transitions, 'document transitions')
        exact(loaded[names[4]], expected_post, 'post-document source inventory')
        for path, identity in docplan['authorities'].items():
            self.files.identity(path, identity)
        return completed, canonical

    def run(self, completion_sha):
        completed, canonical = self.promoted(completion_sha)
        qualified = self.qualification()
        self.historical_closure(qualified)
        self.files.stable()
        mappings = []

        def propose(name, test, requirement, classification, artifact, arch='host', mode='host', command=None):
            path = self.local(artifact)
            identity = self.files.seen[path][1]
            execution = 'qemu-native' if classification == 'native-console' else 'host-model' if classification == 'hosted-runtime' else 'host-tool'
            mappings.append(dict(requirement_id=requirement, proposed_requirement_state='native-partial' if
                requirement.endswith('-x86_64') else 'implemented', claim_class=classification,
                requires_reviewed_test_definition=True, evidence=dict(id=name, test_id=test,
                architecture=arch, mode=mode, execution=execution, outcome='pass',
                artifact=path.removeprefix(str(self.root) + '/'), sha256=identity['sha256'])))
            if command is not None:
                mappings[-1]['command_binding'] = {key: command[key] for key in
                    ('label', 'argv', 'cwd', 'log', 'log_identity', 'tests', 'skipped', 'returncode')}
            if classification == 'native-console':
                mappings[-1]['also_supports_requirement_ids'] = ['N.console-login-pipeline-x86_64']

        contracts = self.pinned('contracts-frozen-v1/result.json')
        commands = {row['label']: row for row in contracts['commands']}

        propose('console.hosted', 'T.P10.console-control-hosted', 'P10.console-control', 'hosted-runtime',
                'hosted-console-control-frozen-v1/result.json')
        propose('console.hosted.sanitized', 'T.P10.console-control-hosted', 'P10.console-control', 'hosted-runtime',
                'hosted-console-control-asan-v3/result.json')
        propose('console.contracts', 'T.P10.console-control-contracts', 'P10.console-control', 'hosted-contracts',
                'contracts-frozen-v1/result.json', command=commands['console-control'])
        propose('console.sdk.consumer', 'T.sdk.artifacts', 'A06.sdk', 'hosted-sdk-consumer-contracts',
                'contracts-frozen-v1/result.json', command=commands['consumer'])
        propose('console.stream.controls', 'T.P10.console-stream-controls', 'P10.console-control', 'hosted-parser-controls',
                'console-runner-stream-controls-v1/result.json')
        propose('console.cohort', 'T.P10.console-build-cohort', 'P10.console-control', 'compile-admission',
                'full-cohort-v1/result.json')
        propose('console.musl.compile', 'T.P10.console-musl-compile', 'P10.console-control', 'compile-only',
                'musl-frozen-v1/result.json')
        for mode in MODES:
            propose('console.native.' + mode, 'T.P10.console-control-native-x86_64', 'P10.console-control-x86_64',
                    'native-console', 'native-console-control-' + mode + '-v2/result.json', 'x86_64', mode)
            propose('console.raw.' + mode, 'T.P10.console-raw-contract', 'P10.console-control-x86_64',
                    'hosted-evidence-reader', 'raw-' + mode + '-v2-reader-v2.json')
        return dict(schema=1, status='admitted-historical-console-receipts-proposed-mappings',
            completion_sha256=completion_sha, qualification_sha256=QUALIFICATION_SHA,
            immutable_files_read=len(self.files.seen), immutable_bytes_read=self.files.total_bytes,
            historical_completion_validated=True, current_installation_revalidated=False,
            imported_receipt_code=False, historical_helpers_executed=False, guest_executed_by_admission=False,
            canonical_mutations=False, ledger_mutations=False, full_M0_M12=False,
            all_complete_milestone_gates_open=True, architecture_matrix=list(ARCHES),
            proposed_ledger_revision='2026-10-04.01', ledger_revision_change_requested=False,
            claims=dict(native_guest_architectures=['x86_64'], native_guest_modes=list(MODES),
                native_guest_boots=2, authenticated_uid0_sessions=4, native_records=136,
                linux_records=12, hosted_adapter_profiles=10, hosted_contract_tests=233,
                hosted_contract_skips=1, canonical_targeted_tests=190, standalone_debug_architectures=10,
                supplied_musl_compile_profiles=['x86_64', 'aarch64', 'rv64', 'loongarch64']),
            limitations=list(LIMITATIONS), proposed_evidence_mappings=mappings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, required=True,
                        help='Physical absolute project root used by the retained receipts')
    parser.add_argument('--completion-sha256', required=True, help='Explicit promoted completion trust root')
    args = parser.parse_args()
    try:
        print(json.dumps(Admission(args.project_root).run(args.completion_sha256), indent=2, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as error:
        print('console receipt admission refused: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

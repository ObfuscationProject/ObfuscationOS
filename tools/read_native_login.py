#!/usr/bin/env python3
"""Read retained native-login originals without rebuilding or replaying guests.

Reads exact source, SDK, compile/dependency/link originals, serial transcripts,
protected generated test credentials and original journalled disk snapshots.
Only fresh reader output is written; original disks are opened by debugfs -R
without -w and e2fsck -fn. No clean guest shutdown or physical claim is made.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from qemu_distro import command_for
from native_login_evidence import SEED, CUT, SESSION, account, serial, need
from native_login_build import sha, inspect as inspect_build

INCLUDE = b'\nincludes("tests/native/native_login_fixture.lua")\n'
CONFIG = b'OK_SERVICE_MANIFEST 2\nservice console simple /bin/login - 0 0\n'
LABELS = ('ordinary-first', 'ordinary-restart', 'staged-first', 'staged-restart', 'no-entropy-refusal')


def read(path):
    return json.loads(Path(path).read_text())


def inspect_inputs(record, data, password, wrong):
    """Join emitted bytes to exact input hashes and bounded authentication span."""
    events = record['stdin']
    need(events and all(0 <= row['before_serial_offset'] <= len(data) and row['bytes'] >= 1 for row in events),
         'actual input offsets differ')
    need(all(events[i]['before_serial_offset'] <= events[i + 1]['before_serial_offset'] and
             events[i]['monotonic_seconds'] <= events[i + 1]['monotonic_seconds'] for i in range(len(events) - 1)),
         'actual input order differs')
    digest = lambda value: hashlib.sha256(value).hexdigest()
    if record['label'].endswith('-restart'):
        expected = [b'qual_admin', wrong, b'qual_admin', password, None, b'exit', b'qual_admin', password, None]
        span = record['wrong_password_span']
        need(events[1]['before_serial_offset'] >= span['start'] and
             events[2]['before_serial_offset'] >= span['end'] and span['start'] < span['end'] <= len(data),
             'actual wrong-password span/input join differs')
        denied = data[span['start']:span['end']]
        need(denied.count(b'Login incorrect.') == 1 and denied.endswith(b'Login: ') and
             b'NATIVE_LOGIN_PUBLICATION' not in denied and not SESSION.search(denied),
             'wrong password published account state or entered a session')
        need(record['wrong_password_denied_seconds'] >= 1.0 and
             events[2]['monotonic_seconds'] - events[1]['monotonic_seconds'] >= 1.0,
             'wrong-password input retry skipped one-second lower bound')
        need(b'Create the first administrator' not in data, 'configured restart reopened enrollment')
    else:
        expected = [b'qual_admin', password, password]
        if record['label'] == 'ordinary-first':
            expected.append(None)
        if record['label'] == 'no-entropy-refusal':
            failure = data.find(b'login: unable to establish')
            need(failure >= 0 and data[:failure].count(b'Create the first administrator') == 1 and
                 all(row['before_serial_offset'] < failure for row in events),
                 'entropy refusal enrollment/input order differs')
        else:
            need(data.count(b'Create the first administrator') == 1, 'ordinary enrollment prompt count differs')
    need(len(events) == len(expected), 'exact actual input-line count differs')
    shells = iter(record.get('shell_commands', []))
    for row, value in zip(events, expected):
        if value is None:
            command = next(shells)
            need(command['completed'] is True and re.fullmatch('LOGIN_SHELL_[0-9a-f]{24}', command['output']),
                 'actual shell command token differs')
            token = command['output'].encode()
            output = data[row['before_serial_offset']:].replace(b'\r\n', b'\n')
            need(token + b'\n' in output, 'actual command output absent')
            value = b'echo ' + token
        need(row['line_sha256'] == digest(value) and row['bytes'] == len(value), 'actual input hash/length differs')
    need(next(shells, None) is None, 'unjoined shell command evidence')

class Reader:
    def __init__(self, args):
        self.args, self.original, self.out = args, args.original.resolve(), args.output.resolve()
        self.report = dict(schema=1, status='checking', reader_sha256=sha(__file__), inputs={}, commands=[],
            guest_replayed=False, build_replayed=False, synchronized_guest_shutdown=False, physical=False,
            scope='Read-only retained native login source/SDK/build/serial/account/disk originals; generated test account only.')

    def save(self):
        (self.out / 'result.json').write_text(json.dumps(self.report, indent=2, sort_keys=True) + '\n')

    def pin(self, path, expected=None):
        path = Path(path)
        need(path.is_file() and not path.is_symlink(), 'regular original input required: ' + str(path))
        digest = sha(path)
        need(expected is None or digest == expected, 'original input differs: ' + str(path))
        need(self.report['inputs'].setdefault(str(path), digest) == digest, 'original input changed during reading')
        return digest

    def command(self, label, argv, *, allowed=(0,)):
        path = self.out / (label + '.log')
        with path.open('xb') as output:
            done = subprocess.run(list(map(str, argv)), stdout=output, stderr=subprocess.STDOUT, timeout=60)
        self.report['commands'].append(dict(label=label, argv=list(map(str, argv)), returncode=done.returncode,
                                           log_sha256=sha(path)))
        self.save()
        need(done.returncode in allowed, 'read-only disk command failed: ' + label)
        return path.read_bytes()

    def dump(self, label, disk, name):
        output = self.out / (label + '.bytes')
        self.command(label, [self.args.debugfs.resolve(), '-R', 'dump ' + name + ' ' + str(output), disk])
        need(output.is_file(), 'actual retained disk pathname missing: ' + name)
        return output.read_bytes()

    def metadata(self, label, disk, name, expected):
        observed = {}
        for index, (path, kind, mode) in enumerate(((name, 'regular', 0o600), ('/root', 'directory', 0o700))):
            text = self.command(label + '-' + str(index), [self.args.debugfs.resolve(), '-R', 'stat ' + path, disk]).decode()
            identity = re.search(r'Inode:\s*([0-9]+)\s+Type:\s*(\S+)\s+Mode:\s*0([0-7]+)', text)
            owner = re.search(r'User:\s*([0-9]+)\s+Group:\s*([0-9]+)', text)
            links = re.search(r'Links:\s*([0-9]+)', text)
            need(identity and owner and links and identity[2] == kind and int(identity[3], 8) == mode and
                 int(owner[1]) == int(owner[2]) == 0 and (path != name or int(links[1]) == 1), 'protected disk metadata differs')
            observed[path] = dict(inode=int(identity[1]), kind=kind, mode=mode, uid=0, gid=0, links=int(links[1]))
        need(observed == expected, 'retained disk metadata differs from original recorded metadata')

    def run(self):
        need(sys.dont_write_bytecode and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1', 'use PYTHONDONTWRITEBYTECODE=1 python3 -B')
        need(not self.out.exists() and not self.out.is_relative_to(self.original) and not self.original.is_relative_to(self.out)
             and not self.out.is_relative_to(ROOT), 'fresh output outside original and OS required')
        need(re.fullmatch(r'/[A-Za-z0-9_./+-]+', str(self.out)), 'literal-safe debugfs output pathname required')
        self.out.mkdir(parents=True)
        self.save()
        try:
            self.pin(Path(__file__).resolve(), self.report['reader_sha256'])
            result_path = self.original / 'result.json'
            original_digest = self.pin(result_path, self.args.result_sha256)
            result = read(result_path)
            terminal = read(self.args.producer_terminal)
            self.pin(self.args.producer_terminal, self.args.producer_terminal_sha256)
            need(terminal.get('exit_code') == 0 and str(terminal.get('session_id', '')) and terminal.get('chunk_id') and
                 terminal.get('result_sha256') == original_digest, 'actual producer completion receipt differs')
            need(result['status'] == 'passed-native-journalled-login' and result['architecture'] == 'x86_64' and
                 result['mode'] == self.args.mode and result['guest_boots'] == 5 and result['sdk_only'] and
                 not any(result[key] for key in ('kernel_source_compiled', 'physical', 'smp', 'manual_desktop',
                                                'full_M0_M12', 'synchronized_guest_shutdown')), 'original campaign scope/status differs')
            consumer, sdk = self.original / 'ObfuscationOS', self.original / 'sdk'
            self.pin(consumer / 'tools/qualify_native_login.py', result['runner_sha256'])
            contract = result['qualified_input_contract']
            self.pin(self.original / 'qualification-inputs.json', result['qualification_inputs_sha256'])
            need(read(self.original / 'qualification-inputs.json') == contract, 'retained qualified handoff differs')
            need(contract['status'] == 'ready' and contract['schema'] == 1, 'SDK handoff is not qualified')
            admitted = {}
            for key in ('sdk_producer', 'sdk_readback', 'sdk_producer_terminal', 'sdk_reader_terminal', 'source_ready'):
                item = contract[key]
                need(set(item) == {'path', 'sha256'} and Path(item['path']).is_absolute(), 'explicit qualified input required')
                self.pin(item['path'], item['sha256'])
                admitted[key] = read(item['path'])
            need(admitted['sdk_producer']['status'] == 'pass' and admitted['sdk_readback']['status'] == 'passed' and
                 admitted['sdk_readback']['input_result_sha256'] == contract['sdk_producer']['sha256'], 'SDK producer/reader join differs')
            matrix = {(arch, mode) for arch in ARCH_TRIPLES for mode in ('debug', 'release')}
            sdk_rows, reader_rows = admitted['sdk_producer']['rows'], admitted['sdk_readback']['rows']
            need(len(sdk_rows) == len(reader_rows) == 20 and {(row['arch'], row['mode']) for row in sdk_rows} == matrix and
                 {(row['arch'], row['mode']) for row in reader_rows} == matrix and
                 admitted['sdk_readback']['exact_unique_expected_rows'] == 20 and admitted['sdk_readback']['original_commands'] == 61 and
                 all(row.get('pass_') is True for row in reader_rows), 'qualified SDK full-profile coverage differs')
            for key, target in (('sdk_producer_terminal', 'sdk_producer'), ('sdk_reader_terminal', 'sdk_readback')):
                receipt = admitted[key]
                need(receipt.get('exit_code') == 0 and str(receipt.get('session_id', '')) and receipt.get('chunk_id') and
                     receipt.get('result_sha256') == contract[target]['sha256'], 'actual qualified SDK terminal join differs')
            sources = result['source_sha256']
            need(sources == admitted['source_ready']['files'], 'qualified source inventory differs')
            for name in ('kernel_sdk', 'qemu_distro', 'native_login_evidence', 'native_login_build'):
                path = Path(sys.modules[name].__file__).resolve()
                need(path.is_relative_to(ROOT), 'foreign active reader support module')
                self.pin(path, sources[path.relative_to(ROOT).as_posix()])
            frozen = Path(contract['frozen_source'])
            need(frozen.is_absolute() and frozen.is_dir(), 'explicit frozen source directory required')
            for name, digest in sources.items():
                need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'relative frozen source name required')
                self.pin(frozen / name, digest)
                if name not in ('xmake.lua', 'config/services.conf'):
                    self.pin(consumer / name, digest)
            need((consumer / 'xmake.lua').read_bytes() == (frozen / 'xmake.lua').read_bytes() + INCLUDE and
                 (consumer / 'config/services.conf').read_bytes() == CONFIG, 'exact fixture source overrides differ')
            for name, digest in result['fixture_overrides'].items():
                self.pin(consumer / name, digest)
            tools = result['tools']
            for path, digest in tools.items():
                self.pin(path, digest)
            for tool in (self.args.debugfs, self.args.e2fsck):
                need(str(tool.resolve()) in tools and sha(tool.resolve()) == tools[str(tool.resolve())], 'reader tool differs from original provider tool')
            need(str(self.args.compiler.resolve()) in tools and str(self.args.qemu.resolve()) in tools,
                 'explicit reader compiler/QEMU differs from original executed tools')
            self.pin(sdk / 'manifest.json', result['sdk_manifest_sha256'])
            manifest = validate_sdk(sdk, 'x86_64', self.args.mode, self.args.compiler.resolve())
            need(manifest['abi_version'] == 69 and manifest['native_persistent_sync_profile'] ==
                 'retained-linked-mounted-ordered-journal-device-flush-v1', 'strict persistent SDK absent')
            for name, digest in manifest['files'].items():
                self.pin(sdk / name, digest)
            rows = [row for row in admitted['sdk_producer']['rows'] if row['arch'] == 'x86_64' and row['mode'] == self.args.mode]
            need(len(rows) == 1 and rows[0]['sdk']['manifest_sha256'] == result['sdk_manifest_sha256'] and
                 rows[0]['sdk_build_pass'] is True and rows[0]['consumer_pass'] is True, 'selected actual SDK producer row differs')
            commands = result['commands']
            need(len({row['label'] for row in commands}) == len(commands), 'duplicate original command label')
            for row in commands:
                need(row['cwd'] == str(consumer) and row['returncode'] in ((0, 1) if row['label'].endswith('-offline-recovery') else (0,)),
                     'original command execution failed or wrong working directory')
                self.pin(self.original / (row['label'] + '.log'), row['log_sha256'])
                need(str(Path(row['argv'][0]).resolve()) in tools, 'unbound original command tool')
            command_map = {row['label']: row for row in commands}
            configure, distro = command_map['configure']['argv'], command_map['distro']['argv']
            need(configure[1:] == ['f', '-y', '-a', 'x86_64', '-m', self.args.mode, '--kernel_sdk=' + str(sdk),
                 '--systoolchain_dir=' + str(self.args.compiler.resolve().parent.parent), '--native_init_control=y', '--ccache=n'] and
                 distro == [configure[0], '-y', '-v', '-b', 'distro_image'], 'actual SDK-only configure/build command differs')
            for name, digest in result['original_compile_dependency_products'].items():
                self.pin(consumer / name, digest)
            fixture_sources = dict(sources, **result['fixture_overrides'])
            build_evidence = inspect_build(consumer, sdk, self.args.mode, manifest, fixture_sources,
                result['original_compile_dependency_products'], tools, (self.original / 'distro.log').read_text())
            need(build_evidence == result['build_readback'], 'original build proof differs from retained originals')
            build = consumer / 'build/x86_64' / self.args.mode
            for name, digest in result['built_artifacts'].items():
                self.pin(build / name, digest)
            for product, staged in [('apps/login.elf', 'rootfs/bin/login'), ('apps/oksh.elf', 'rootfs/bin/oksh-real'),
                    ('fixtures/native-login-session.elf', 'rootfs/bin/oksh'), ('fixtures/native-login-cut.elf', 'rootfs/bin/login-cut')]:
                self.pin(build / staged, sha(build / product))
                need(stat.S_IMODE((build / staged).stat().st_mode) == 0o755, 'staged executable mode differs')
            credentials = result['qualification_credentials']
            need(Path(credentials['path']) == self.original / 'qualification-credentials.json' and
                 stat.S_IMODE(Path(credentials['path']).stat().st_mode) == 0o600, 'protected generated credentials path/mode differs')
            self.pin(credentials['path'], credentials['sha256'])
            secrets = read(credentials['path'])
            need(secrets['schema'] == 1 and secrets['account'] == 'qual_admin' and
                 all(re.fullmatch('[0-9a-f]{64}', secrets[key]) for key in ('password', 'wrong_password')) and
                 secrets['password'] != secrets['wrong_password'], 'explicit generated test credentials differ')
            password, wrong = secrets['password'].encode(), secrets['wrong_password'].encode()
            guests = {row['label']: row for row in result['guests']}
            need(len(result['guests']) == 5 and set(guests) == set(LABELS), 'exact actual five-boot inventory differs')
            execution = {}
            for label in LABELS:
                row = guests[label]
                cohort = 'no-entropy' if label == 'no-entropy-refusal' else label.split('-')[0]
                disk = self.original / (cohort + '.img')
                entropy = 'none' if cohort == 'no-entropy' else 'virtio'
                expected = list(map(str, command_for(self.args.qemu.resolve(), 'x86_64', build / 'distro/kernel.bin', disk,
                                                    'none', native_profile=True, entropy=entropy)))
                need(row['argv'] == expected and row['entropy'] == entropy and row['guest_executed'] and
                     row['host_retired_guest'] and row['post_acceptance_hold_ms'] >= 250 and
                     not row['synchronized_guest_shutdown'], 'actual guest command/provider/retirement differs')
                transcript = self.original / (label + '.serial')
                self.pin(transcript, row['serial_sha256'])
                data = transcript.read_bytes()
                need(b'ObfuscationOS\n' in data.replace(b'\r\n', b'\n'), 'login product identity banner absent')
                expected_sessions = 2 if label.endswith('-restart') else int(label == 'ordinary-first')
                execution[label] = serial(data, (password, wrong), expected_sessions, cut=label == 'staged-first',
                    publications=('pending', 'active') if label == 'staged-restart' else ())
                inspect_inputs(row, data, password, wrong)
                if label == 'no-entropy-refusal':
                    need(b'OK_ENTROPY source=none state=unavailable' in data and b'login: unable to establish' in data,
                         'actual entropy refusal missing')
            accounts = {}
            for cohort in ('ordinary', 'staged', 'no-entropy'):
                initial = result['artifacts'][cohort + '-initial']
                need(Path(initial['path']) == self.original / (cohort + '-initial.img'), 'retained initial disk path differs')
                self.pin(initial['path'], initial['sha256'])
                self.pin(initial['manifest_path'], initial['manifest_sha256'])
                activation = read(initial['manifest_path'])
                need(activation['schema'] == 1 and activation['profile'] == 'linux-activated-clean-1k-jbd2-crc32c-v3-normalized-head' and
                     activation['image_sha256'] == initial['sha256'] and activation['linux_image_sha256'] == result['linux_reference']['sha256'] and
                     activation['journal_features'] == 16 and activation['normalized_journal_head'] == 0 and activation['needs_recovery'] is False,
                     'actual initial journal activation profile differs')
                self.pin(result['linux_reference']['path'], result['linux_reference']['sha256'])
                need(activation['bootstrap_metadata_policy_source_sha256'] == sources['tools/journalled_rootfs_policy.py'],
                     'journal activation bootstrap policy differs from frozen source')
                self.pin(self.original / (cohort + '.img.activation.log'), activation['activation_log_sha256'])
                need(activation['activation_source_sha256'] == sources['tools/jbd2/activate_root_journal.c'],
                     'journal activation helper differs from frozen source')
                first_label = 'no-entropy-refusal' if cohort == 'no-entropy' else cohort + '-first'
                need(guests[first_label]['disk_before_sha256'] == initial['sha256'], 'first guest did not use retained actual initial disk')
                need(self.dump(cohort + '-initial-database', initial['path'], '/etc/accounts.db') == SEED,
                     'actual retained initial disk has configured credentials')
                config = CONFIG.replace(b'/bin/login ', b'/bin/login-cut ') if cohort == 'staged' else CONFIG
                need(self.dump(cohort + '-initial-config', initial['path'], '/etc/services.conf') == config, 'actual boot disk service executable differs')
                for target, product in [('login', 'apps/login.elf'), ('oksh-real', 'apps/oksh.elf'),
                        ('oksh', 'fixtures/native-login-session.elf'), ('login-cut', 'fixtures/native-login-cut.elf')]:
                    need(self.dump(cohort + '-initial-' + target, initial['path'], '/bin/' + target) == (build / product).read_bytes(),
                         'actual initial disk executable differs from linked product')
                case = result['cases'][cohort]
                disk = self.original / (cohort + '.img')
                if cohort == 'no-entropy':
                    self.pin(disk, case['disk_sha256'])
                    need(guests[first_label]['disk_after_sha256'] == case['disk_sha256'], 'entropy-refusal disk retirement join differs')
                    need(self.dump(cohort + '-final-database', disk, '/etc/accounts.db') == SEED, 'entropy refusal changed seed')
                    namespace = self.command(cohort + '-final-namespace', [self.args.debugfs.resolve(), '-R', 'ls -l /etc', disk])
                    need(b'.accounts.next' not in namespace, 'entropy refusal published staging')
                    self.metadata(cohort + '-metadata', disk, '/etc/accounts.db', case['metadata'])
                    continue
                first = self.original / (cohort + '-after-first.img')
                self.pin(first, case['after_first_sha256'])
                self.pin(self.original / (cohort + '-after-restart.img'), case['after_restart_sha256'])
                self.pin(disk, case['original_disk_sha256'])
                need(case['after_restart_sha256'] == case['original_disk_sha256'], 'restart disk snapshot differs')
                need(guests[cohort + '-first']['disk_after_sha256'] == case['after_first_sha256'] ==
                     guests[cohort + '-restart']['disk_before_sha256'] and
                     guests[cohort + '-restart']['disk_after_sha256'] == case['original_disk_sha256'],
                     'actual persistent disk first/restart byte join differs')
                first_database = self.dump(cohort + '-first-database', first, '/etc/accounts.db')
                if cohort == 'staged':
                    need(first_database == SEED, 'actual cut followed database publication')
                    staged = self.dump(cohort + '-staging', first, '/etc/.accounts.next')
                    before = account(staged, password, 'pending')
                    self.metadata(cohort + '-staging-metadata', first, '/etc/.accounts.next', case['staging_metadata'])
                else:
                    before = account(first_database, password, 'active')
                self.metadata(cohort + '-first-metadata', first, '/etc/accounts.db', case['first_metadata'])
                final = self.dump(cohort + '-final-database', disk, '/etc/accounts.db')
                after = account(final, password, 'active')
                self.metadata(cohort + '-final-metadata', disk, '/etc/accounts.db', case['final_metadata'])
                need(before == case['before'] and after == case['after'] and before['salt_hex'] == after['salt_hex'] and
                     before['verifier_hex'] == after['verifier_hex'], 'independently derived account/recovery credentials differ')
                namespace = self.command(cohort + '-final-namespace', [self.args.debugfs.resolve(), '-R', 'ls -l /etc', disk])
                need(b'.accounts.next' not in namespace, 'completed recovery left account staging')
                recovered = self.original / (cohort + '-offline-recovered.img')
                self.pin(recovered, case['offline_recovered_sha256'])
                self.command(cohort + '-offline-fsck', [self.args.e2fsck.resolve(), '-fn', recovered])
                need(self.dump(cohort + '-offline-database', recovered, '/etc/accounts.db') == final, 'offline journal recovery changed account bytes')
                accounts[cohort] = dict(before=before, after=after)
            for path, digest in tuple(self.report['inputs'].items()):
                need(sha(path) == digest, 'original input mutated during read-only campaign')
            self.report.update(status='passed-retained-native-login', original_result_sha256=original_digest,
                mode=self.args.mode, execution=execution, accounts=accounts, actual_guest_boots=5,
                source_files_checked=len(sources), original_build_objects_checked=len(build_evidence['objects']),
                password_noecho=True, account_pbkdf2_rederived=True, generated_test_credentials_only=True)
        except BaseException as error:
            self.report.update(status='failed-preserved', error=repr(error))
            raise
        finally:
            self.save()
        print('NATIVE_LOGIN_RETAINED_READBACK_PASS', self.out / 'result.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('original', 'output', 'producer-terminal', 'compiler', 'qemu', 'debugfs', 'e2fsck'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('result-sha256', 'producer-terminal-sha256'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    Reader(parser.parse_args()).run()


if __name__ == '__main__':
    main()

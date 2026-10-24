#!/usr/bin/env python3
"""SDK-only journalled native login, restart, staged recovery and entropy refusal.

Requires a new explicit qualified ABI69/UAPI0.9 handoff. Historical workflow
receipt profiles are never admitted. Failed originals remain preserved. QEMU
is retired by the host; this campaign does not establish clean guest shutdown.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import select
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from object_pressure_evidence import source_files
from qemu_distro import command_for
from native_login_evidence import SEED, CUT, SESSION, account, serial as inspect_serial, need
from native_login_build import commands as build_commands, original_products, inspect as inspect_build

INCLUDE = '\nincludes("tests/native/native_login_fixture.lua")\n'
CONFIG = 'OK_SERVICE_MANIFEST 2\nservice console simple /bin/login - 0 0\n'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def login_source_files(root):
    files = source_files(root)
    configuration = root / 'config/services.conf'
    need(configuration.is_file() and not configuration.is_symlink(), 'ordinary service configuration source required')
    files['config/services.conf'] = sha(configuration)
    return files


def admit_handoff(path, digest, sdk, sdk_pin, mode):
    need(sha(path) == digest, 'qualified input handoff pin differs')
    contract = json.loads(path.read_text())
    need(contract.get('schema') == 1 and contract.get('status') == 'ready', 'new qualified handoff is not ready')
    values = {}
    for key in ('sdk_producer', 'sdk_readback', 'sdk_producer_terminal', 'sdk_reader_terminal', 'source_ready'):
        item = contract[key]
        need(isinstance(item, dict) and set(item) == {'path', 'sha256'}, 'explicit input pin required: ' + key)
        original = Path(item['path'])
        need(original.is_absolute() and original.is_file() and not original.is_symlink() and
             re.fullmatch('[0-9a-f]{64}', item['sha256']) and sha(original) == item['sha256'],
             'qualified input differs: ' + key)
        values[key] = json.loads(original.read_text())
    need(values['sdk_producer'].get('status') == 'pass' and values['sdk_readback'].get('status') == 'passed',
         'new SDK producer/readback did not pass')
    need(values['sdk_readback'].get('input_result_sha256') == contract['sdk_producer']['sha256'],
         'independent SDK readback does not bind this original producer result')
    frozen = Path(contract['frozen_source'])
    need(frozen.is_absolute() and frozen.is_dir() and not frozen.is_symlink(), 'explicit frozen OS source required')
    for name, expected in values['source_ready']['files'].items():
        relative = Path(name)
        original = frozen / relative
        need(not relative.is_absolute() and '..' not in relative.parts and original.is_file() and
             not original.is_symlink() and sha(original) == expected, 'frozen source handoff differs: ' + name)
    for key, result in (('sdk_producer_terminal', 'sdk_producer'), ('sdk_reader_terminal', 'sdk_readback')):
        receipt = values[key]
        need(receipt.get('exit_code') == 0 and str(receipt.get('session_id', '')) and
             isinstance(receipt.get('chunk_id'), str) and receipt['chunk_id'] and
             receipt.get('result_sha256') == contract[result]['sha256'], 'actual terminal completion absent: ' + key)
    rows = values['sdk_producer'].get('rows', [])
    expected = {(arch, build_mode) for arch in ARCH_TRIPLES for build_mode in ('debug', 'release')}
    reader_rows = values['sdk_readback'].get('rows', [])
    need(len(rows) == len(reader_rows) == 20 and {(row['arch'], row['mode']) for row in rows} == expected and
         {(row['arch'], row['mode']) for row in reader_rows} == expected and
         values['sdk_readback'].get('exact_unique_expected_rows') == 20 and
         values['sdk_readback'].get('original_commands') == 61 and all(row.get('pass_') is True for row in reader_rows),
         'completed all-twenty-profile producer/readback required')
    matched = [row for row in rows if row.get('arch') == 'x86_64' and row.get('mode') == mode]
    need(len(matched) == 1 and Path(matched[0]['sdk_path']).resolve() == sdk and
         matched[0]['sdk']['manifest_sha256'] == sdk_pin and matched[0].get('sdk_build_pass') is True and
         matched[0].get('consumer_pass') is True, 'SDK handoff does not identify this actual artifact')
    return contract, values


class Guest:
    def __init__(self, owner, label, image, disk, *, entropy='virtio'):
        self.owner, self.label = owner, label
        self.data = bytearray()
        self.command = list(map(str, command_for(owner.args.qemu.resolve(), 'x86_64', image, disk,
                                               'none', native_profile=True, entropy=entropy)))
        self.row = dict(label=label, argv=self.command, entropy=entropy, disk_before_sha256=sha(disk))
        owner.report['guests'].append(self.row)
        self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, env=owner.environment)
        self.row['guest_executed'] = True
        self.started = time.monotonic()

    def receive(self, predicate, *, start=0, allow_refusal=False):
        deadline = time.monotonic() + self.owner.args.timeout
        while not predicate(bytes(self.data[start:])):
            need(time.monotonic() < deadline, self.label + ': timeout awaiting actual guest action')
            ready, _, _ = select.select([self.process.stdout], [], [], 0.1)
            if not ready:
                need(self.process.poll() is None, self.label + ': QEMU exited early')
                continue
            chunk = os.read(self.process.stdout.fileno(), 16384)
            need(chunk, self.label + ': serial output ended')
            self.data.extend(chunk)
            need(len(self.data) < 4 * 1024 * 1024, 'bounded serial capacity exceeded')
            for marker in (b'OK_TEST_FAIL', b'NATIVE_LOGIN_FIXTURE_FAIL', b'event=fatal-hold', b'Kernel panic', b'boot=failed'):
                need(marker not in self.data, self.label + ': guest failure ' + marker.decode())
            if not allow_refusal:
                need(b'login: unable to establish' not in self.data, self.label + ': login refused unexpectedly')
            self.save()
        return len(self.data)

    def prompt(self, text, *, start=0, allow_refusal=False):
        self.receive(lambda data: text in data, start=start, allow_refusal=allow_refusal)
        return self.data.index(text, start) + len(text)

    def send(self, value):
        need(b'\n' not in value and b'\r' not in value, 'one complete input line per prompt')
        self.row.setdefault('stdin', []).append(dict(before_serial_offset=len(self.data),
            monotonic_seconds=time.monotonic() - self.started, bytes=len(value),
            line_sha256=hashlib.sha256(value).hexdigest()))
        self.process.stdin.write(value + b'\n')
        self.process.stdin.flush()

    def save(self):
        (self.owner.out / (self.label + '.serial')).write_bytes(self.data)

    def quiet(self):
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            need(self.process.poll() is None, self.label + ': QEMU exited during acceptance hold')
            ready, _, _ = select.select([self.process.stdout], [], [], min(0.05, max(0, deadline - time.monotonic())))
            if ready:
                chunk = os.read(self.process.stdout.fileno(), 16384)
                need(chunk, self.label + ': serial ended during acceptance hold')
                self.data.extend(chunk)
                need(len(self.data) < 4 * 1024 * 1024, 'bounded serial capacity exceeded')
        self.save()
        self.row['post_acceptance_hold_ms'] = 250

    def stop(self, disk):
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill(); self.process.wait(timeout=3)
        self.process.stdin.close(); self.process.stdout.close()
        self.save()
        self.row.update(returncode=self.process.returncode, elapsed=time.monotonic() - self.started,
            host_retired_guest=True, synchronized_guest_shutdown=False,
            serial_sha256=hashlib.sha256(self.data).hexdigest(), disk_after_sha256=sha(disk))
        self.owner.save()


class Campaign:
    def __init__(self, args):
        self.args, self.out = args, args.output.resolve()
        self.report = dict(schema=1, status='preparing', architecture='x86_64', mode=args.mode,
            scope='Native production login on an actual journalled provider: ordinary two boots, '
                  'real staged transaction interruption and authenticated recovery, no-entropy refusal.',
            sdk_only=True, kernel_source_compiled=False, physical=False, smp=False,
            full_M0_M12=False, manual_desktop=False, synchronized_guest_shutdown=False,
            fixture_shell_wrapper=True, fixture_rename_wrapper='staged-recovery cohort only',
            passwords_recorded=True, test_credentials_only=True, commands=[], guests=[], artifacts={}, cases={},
            runner_sha256=sha(Path(__file__)))
        self.environment = dict(os.environ, XMAKE_ROOT='y', PYTHONDONTWRITEBYTECODE='1', TZ='UTC',
            XMAKE_GLOBALDIR=str(self.out / 'xmake-global'), XMAKE_TMPDIR=str(self.out / 'xmake-tmp'))
        for name in ('CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH', 'GCC_EXEC_PREFIX', 'COMPILER_PATH'):
            self.environment.pop(name, None)

    def save(self):
        temporary = self.out / 'result.tmp'
        temporary.write_text(json.dumps(self.report, indent=2, sort_keys=True) + '\n')
        temporary.replace(self.out / 'result.json')

    def call(self, label, command, *, allowed=(0,)):
        row = dict(label=label, argv=list(map(str, command)), cwd=str(self.consumer))
        self.report['commands'].append(row); self.save()
        path = self.out / (label + '.log')
        with path.open('xb') as output:
            result = subprocess.run(row['argv'], cwd=self.consumer, env=self.environment,
                                    stdout=output, stderr=subprocess.STDOUT)
        row.update(returncode=result.returncode, log_sha256=sha(path)); self.save()
        need(result.returncode in allowed, label + ' failed; exact original log retained')
        return path.read_bytes()

    def dump(self, label, disk, name):
        destination = self.out / (label + '.bytes')
        self.call(label, [self.args.debugfs.resolve(), '-R', 'dump ' + name + ' ' + str(destination), disk])
        need(destination.is_file(), label + ': actual disk pathname absent')
        return destination.read_bytes()

    def namespace(self, label, disk):
        return self.call(label, [self.args.debugfs.resolve(), '-R', 'ls -l /etc', disk])

    def account_metadata(self, disk, name):
        observed = {}
        for path, kind, mode in ((name, 'regular', 0o600), ('/root', 'directory', 0o700)):
            text = self.call('metadata-' + str(len(self.report['commands'])),
                [self.args.debugfs.resolve(), '-R', 'stat ' + path, disk]).decode()
            identity = re.search(r'Inode:\s*([0-9]+)\s+Type:\s*(\S+)\s+Mode:\s*0([0-7]+)', text)
            owner = re.search(r'User:\s*([0-9]+)\s+Group:\s*([0-9]+)', text)
            links = re.search(r'Links:\s*([0-9]+)', text)
            need(identity and owner and links and identity[2] == kind and int(identity[3], 8) == mode and
                 int(owner[1]) == int(owner[2]) == 0 and (path != name or int(links[1]) == 1),
                 'actual protected account/home metadata differs: ' + path)
            observed[path] = dict(inode=int(identity[1]), kind=kind, mode=mode, uid=0, gid=0, links=int(links[1]))
        return observed

    def image(self, label, *, cut=False):
        stage = self.out / (label + '-rootfs')
        shutil.copytree(self.build / 'rootfs', stage)
        (stage / 'etc/services.conf').write_text(CONFIG.replace('/bin/login ', '/bin/login-cut ') if cut else CONFIG)
        need((stage / 'etc/accounts.db').read_bytes() == SEED, 'image must start from the explicit unconfigured seed')
        disk = self.out / (label + '.img')
        self.call(label + '-image', [sys.executable, '-B', self.consumer / 'tools/mkext4_journalled.py',
            '--root', stage, '--out', disk, '--linux-image', self.args.linux_image.resolve(),
            '--linux-image-sha256', self.args.linux_image_sha256])
        initial = self.out / (label + '-initial.img')
        shutil.copy2(disk, initial)
        self.report['artifacts'][label + '-initial'] = dict(path=str(initial), sha256=sha(initial),
            manifest_path=str(disk.with_name(disk.name + '.manifest.json')),
            manifest_sha256=sha(disk.with_name(disk.name + '.manifest.json')))
        return disk

    def enroll(self, guest, password):
        at = guest.prompt(b'Account name: ')
        guest.send(b'qual_admin')
        at = guest.prompt(b'Password: ', start=at)
        guest.send(password)
        at = guest.prompt(b'Repeat password: ', start=at)
        guest.send(password)
        return at

    def authenticate(self, guest, password, wrong, *, start=0):
        at = guest.prompt(b'Login: ', start=start)
        need(b'Create the first administrator' not in guest.data[start:], 'configured restart reopened enrollment')
        guest.send(b'qual_admin'); at = guest.prompt(b'Password: ', start=at)
        if wrong is None:
            guest.send(password)
            return at
        attempt = at
        began = time.monotonic(); guest.send(wrong)
        at = guest.prompt(b'Login incorrect.', start=at)
        need(b'NATIVE_LOGIN_PUBLICATION' not in guest.data[attempt:] and not SESSION.search(guest.data[attempt:]),
             'wrong authentication published staged state or entered a session')
        at = guest.prompt(b'Login: ', start=at)
        elapsed = time.monotonic() - began
        need(elapsed >= 1.0, 'wrong-password retry bypassed the ordinary one-second lower bound')
        guest.row['wrong_password_denied_seconds'] = elapsed
        guest.row['wrong_password_span'] = dict(start=attempt, end=at)
        guest.send(b'qual_admin'); at = guest.prompt(b'Password: ', start=at)
        guest.send(password)
        return at

    def shell(self, guest, *, start=0):
        guest.receive(lambda data: SESSION.search(data), start=start)
        at = SESSION.search(guest.data, start).end()
        at = guest.prompt(b'oksh> ', start=at)
        token = ('LOGIN_SHELL_' + secrets.token_hex(12)).encode()
        guest.send(b'echo ' + token)
        output = re.compile(re.escape(token) + rb'\r?\n')
        guest.receive(lambda data: output.search(data), start=at)
        at = output.search(guest.data, at).end()
        at = guest.prompt(b'oksh> ', start=at)
        guest.row.setdefault('shell_commands', []).append(dict(output=token.decode(), completed=True))
        return at

    def run_guest(self, label, disk, handler, *, entropy='virtio'):
        guest = Guest(self, label, self.image_path, disk, entropy=entropy)
        try:
            handler(guest)
            guest.quiet()
            return bytes(guest.data)
        finally:
            guest.stop(disk)

    def cohorts(self):
        password = secrets.token_hex(32).encode()
        wrong = secrets.token_hex(32).encode()
        need(password != wrong, 'distinct generated qualification credentials required')
        credentials = self.out / 'qualification-credentials.json'
        descriptor = os.open(credentials, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(dict(schema=1, scope='generated qualification account only; never product defaults',
                account='qual_admin', password=password.decode(), wrong_password=wrong.decode()), stream, indent=2)
            stream.write('\n')
        self.report['qualification_credentials'] = dict(path=str(credentials), sha256=sha(credentials), mode=0o600)
        for label, cut in (('ordinary', False), ('staged', True)):
            disk = self.image(label, cut=cut)
            def first(guest):
                at = self.enroll(guest, password)
                if cut:
                    guest.prompt(CUT, start=at)
                else:
                    self.shell(guest, start=at)
            original = self.run_guest(label + '-first', disk, first)
            first_evidence = inspect_serial(original, (password, wrong), 0 if cut else 1, cut=cut)
            shutil.copy2(disk, self.out / (label + '-after-first.img'))
            database = self.dump(label + '-first-database', disk, '/etc/accounts.db')
            if cut:
                need(database == SEED, 'cut must precede actual database publication')
                staged = self.dump(label + '-first-staging', disk, '/etc/.accounts.next')
                before = account(staged, password, 'pending')
                staging_metadata = self.account_metadata(disk, '/etc/.accounts.next')
            else:
                before = account(database, password, 'active')
                need(b'.accounts.next' not in self.namespace(label + '-first-namespace', disk), 'ordinary enrollment left staging')
            first_metadata = self.account_metadata(disk, '/etc/accounts.db')
            def second(guest):
                at = self.authenticate(guest, password, wrong)
                at = self.shell(guest, start=at)
                guest.send(b'exit')
                at = self.authenticate(guest, password, None, start=at)
                self.shell(guest, start=at)
            restarted = self.run_guest(label + '-restart', disk, second)
            evidence = inspect_serial(restarted, (password, wrong), 2,
                publications=('pending', 'active') if cut else ())
            after_bytes = self.dump(label + '-final-database', disk, '/etc/accounts.db')
            after = account(after_bytes, password, 'active')
            need(before['salt_hex'] == after['salt_hex'] and before['verifier_hex'] == after['verifier_hex'],
                 'restart changed credentials')
            final_metadata = self.account_metadata(disk, '/etc/accounts.db')
            need(b'.accounts.next' not in self.namespace(label + '-final-namespace', disk), 'completed recovery left staging')
            shutil.copy2(disk, self.out / (label + '-after-restart.img'))
            recovered = self.out / (label + '-offline-recovered.img')
            shutil.copy2(disk, recovered)
            self.call(label + '-offline-recovery', [self.args.e2fsck.resolve(), '-fy', recovered], allowed=(0, 1))
            self.call(label + '-offline-fsck', [self.args.e2fsck.resolve(), '-fn', recovered])
            need(self.dump(label + '-offline-database', recovered, '/etc/accounts.db') == after_bytes,
                 'offline recovery changed completed account bytes')
            self.report['cases'][label] = dict(first=first_evidence, restart=evidence,
                before=before, after=after, ordinary_login_bytes=cut is False,
                first_metadata=first_metadata, final_metadata=final_metadata,
                staging_metadata=staging_metadata if cut else None,
                after_first_sha256=sha(self.out / (label + '-after-first.img')),
                after_restart_sha256=sha(self.out / (label + '-after-restart.img')),
                original_disk_sha256=sha(disk), offline_recovered_sha256=sha(recovered))
            self.save()
        disk = self.image('no-entropy')
        def absent(guest):
            at = self.enroll(guest, password)
            guest.prompt(b'login: unable to establish', start=at, allow_refusal=True)
        refused = self.run_guest('no-entropy-refusal', disk, absent, entropy='none')
        need(b'OK_ENTROPY source=none state=unavailable' in refused, 'actual unavailable entropy source not observed')
        refusal = inspect_serial(refused, (password, wrong), 0)
        need(self.dump('no-entropy-database', disk, '/etc/accounts.db') == SEED and
             b'.accounts.next' not in self.namespace('no-entropy-namespace', disk),
             'entropy refusal wrote account credentials')
        metadata = self.account_metadata(disk, '/etc/accounts.db')
        self.report['cases']['no-entropy'] = dict(evidence=refusal, explicit_failure=True,
            seed_unchanged=True, staging_absent=True, disk_sha256=sha(disk), metadata=metadata)

    def run(self):
        need(sys.dont_write_bytecode and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1', 'use python3 -B with PYTHONDONTWRITEBYTECODE=1')
        need(not self.out.exists() and not self.out.is_relative_to(ROOT) and not ROOT.is_relative_to(self.out), 'fresh output outside OS source required')
        need(re.fullmatch(r'/[A-Za-z0-9_./+-]+', str(self.out)), 'debugfs output pathname must use literal-safe bytes')
        sdk_input = self.args.kernel_sdk.resolve()
        need(sha(sdk_input / 'manifest.json') == self.args.sdk_manifest_sha256, 'explicit SDK pin differs')
        manifest = validate_sdk(sdk_input, 'x86_64', self.args.mode, self.args.compiler.resolve())
        need(manifest['abi_version'] == 69 and manifest['native_persistent_sync_profile'] ==
             'retained-linked-mounted-ordered-journal-device-flush-v1', 'new ABI69 persistent provider SDK required')
        contract, values = admit_handoff(self.args.qualification_inputs.resolve(), self.args.qualification_inputs_sha256,
                                        sdk_input, self.args.sdk_manifest_sha256, self.args.mode)
        files = login_source_files(ROOT)
        need(values['source_ready']['files'] == files, 'exact OS source-ready inventory differs')
        need(sha(self.args.linux_image.resolve()) == self.args.linux_image_sha256, 'explicit Linux activation binary pin differs')
        self.out.mkdir(parents=True)
        self.consumer = self.out / 'ObfuscationOS'
        self.report.update(source_sha256=files, sdk_manifest_sha256=self.args.sdk_manifest_sha256,
            qualified_input_contract=contract, qualification_inputs_sha256=self.args.qualification_inputs_sha256,
            linux_reference=dict(path=str(self.args.linux_image.resolve()), sha256=self.args.linux_image_sha256,
                                 provenance='explicit pinned binary; source provenance not established'))
        self.save()
        try:
            shutil.copy2(self.args.qualification_inputs.resolve(), self.out / 'qualification-inputs.json')
            need(sha(self.out / 'qualification-inputs.json') == self.args.qualification_inputs_sha256, 'handoff changed while retaining original')
            for name, digest in files.items():
                target = self.consumer / name; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, target); need(sha(target) == digest, 'source changed while freezing ' + name)
            (self.consumer / 'xmake.lua').write_bytes((self.consumer / 'xmake.lua').read_bytes() + INCLUDE.encode())
            (self.consumer / 'config/services.conf').write_text(CONFIG)
            self.report['fixture_overrides'] = {name: sha(self.consumer / name) for name in ('xmake.lua', 'config/services.conf')}
            sdk = self.out / 'sdk'
            for name, digest in {**manifest['files'], 'manifest.json': self.args.sdk_manifest_sha256}.items():
                target = sdk / name; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(sdk_input / name, target); need(sha(target) == digest, 'SDK changed while freezing ' + name)
            validate_sdk(sdk, 'x86_64', self.args.mode, self.args.compiler.resolve())
            self.call('configure', [self.args.xmake.resolve(), 'f', '-y', '-a', 'x86_64', '-m', self.args.mode,
                '--kernel_sdk=' + str(sdk), '--systoolchain_dir=' + str(self.args.compiler.resolve().parent.parent),
                '--native_init_control=y', '--ccache=n'])
            self.call('distro', [self.args.xmake.resolve(), '-y', '-v', '-b', 'distro_image'])
            self.build = self.consumer / 'build/x86_64' / self.args.mode
            self.image_path = self.build / 'distro/kernel.bin'
            pairs = [('apps/login.elf', 'rootfs/bin/login'), ('apps/oksh.elf', 'rootfs/bin/oksh-real'),
                ('fixtures/native-login-session.elf', 'rootfs/bin/oksh'), ('fixtures/native-login-cut.elf', 'rootfs/bin/login-cut')]
            for product, staged in pairs:
                need(sha(self.build / product) == sha(self.build / staged), 'fixture product association differs')
            self.report['built_artifacts'] = {name: sha(self.build / name) for name in
                ('apps/login.elf', 'apps/oksh.elf', 'fixtures/native-login-session.elf', 'fixtures/native-login-cut.elf',
                 'distro/kernel.bin', 'distro/kernel.elf', 'boot.okar', 'lib/libokcrt.a')}
            self.report['tools'] = {str(path.resolve()): sha(path.resolve()) for path in
                (self.args.qemu, self.args.xmake, self.args.compiler, self.args.debugfs, self.args.e2fsck, Path(sys.executable))}
            for command in build_commands((self.out / 'distro.log').read_text()):
                path = Path(command[0]).resolve()
                self.report['tools'][str(path)] = sha(path)
            self.report['original_compile_dependency_products'] = original_products(self.consumer)
            fixture_sources = dict(files, **self.report['fixture_overrides'])
            self.report['build_readback'] = inspect_build(self.consumer, sdk, self.args.mode, manifest,
                fixture_sources, self.report['original_compile_dependency_products'], self.report['tools'],
                (self.out / 'distro.log').read_text())
            self.report['status'] = 'running-guests'; self.save()
            self.cohorts()
            for name, digest in files.items():
                need(sha(ROOT / name) == digest, 'canonical source changed during campaign ' + name)
                need(sha(self.consumer / name) == self.report['fixture_overrides'].get(name, digest), 'retained source changed ' + name)
            validate_sdk(sdk, 'x86_64', self.args.mode, self.args.compiler.resolve())
            need(sha(self.image_path) == self.report['built_artifacts']['distro/kernel.bin'], 'boot image changed')
            need(all(sha(path) == digest for path, digest in self.report['tools'].items()), 'executed tool changed')
            self.report.update(status='passed-native-journalled-login', guest_boots=5,
                ordinary_two_boot_login=True, staged_authentication_before_recovery=True,
                no_entropy_refusal_before_account_mutation=True, password_noecho=True)
        except BaseException as error:
            self.report.update(status='failed-preserved', error=repr(error)); raise
        finally:
            self.save()
        print('NATIVE_JOURNALLED_LOGIN_PASS', self.out / 'result.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('kernel-sdk', 'qualification-inputs', 'compiler', 'qemu', 'xmake', 'linux-image', 'debugfs', 'e2fsck', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('sdk-manifest-sha256', 'qualification-inputs-sha256', 'linux-image-sha256'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--timeout', type=float, default=180)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    args = parser.parse_args()
    need(0 < args.timeout <= 600, 'bounded positive timeout required')
    Campaign(args).run()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Execute a fresh SDK-only native console lease fixture using only the boot archive."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import secrets
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from qemu_distro import command_for, virtio_disk_args
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from object_pressure_evidence import source_files
from native_console_lease_evidence import PASS_PREFIX, validate_console_lease

CONFIGURATION = ('OK_SERVICE_MANIFEST 2\n'
                 'service guard notify /bin/console-lease-probe - 0 0\n'
                 'service console simple /bin/console-lease-probe guard 0 0\n')
INCLUDE = '\nincludes("tests/native/native_console_lease_fixture.lua")\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def need(value, message):
    if not value:
        raise ValueError(message)


def archive_only_command(qemu, arch, image):
    """Remove exactly the builder's explicit distribution disk attachment."""
    unused = Path('/unused-native-console-lease-rootfs.img')
    command = command_for(qemu, arch, image, unused, 'none', native_profile=True)
    attachment = virtio_disk_args(unused, mmio=arch in ('aarch64', 'arm32', 'rv64', 'rv32'))
    matches = [i for i in range(len(command)) if command[i:i + len(attachment)] == attachment]
    need(len(matches) == 1, 'unexpected QEMU disk attachment shape')
    at = matches[0]
    result = command[:at] + command[at + len(attachment):]
    need(not any('fsdisk' in item or 'virtio-blk' in item or str(unused) in item for item in result),
         'archive-only guest still has a distribution disk')
    return result


def run(args):
    need(sys.dont_write_bytecode and os.environ.get('PYTHONDONTWRITEBYTECODE') == '1',
         'use PYTHONDONTWRITEBYTECODE=1 python3 -B')
    out = args.output.resolve()
    need(not out.exists() and not ROOT.is_relative_to(out) and not out.is_relative_to(ROOT),
         'fresh output outside OS source required')
    sdk_input = args.kernel_sdk.resolve()
    need(re.fullmatch('[0-9a-f]{64}', args.sdk_manifest_sha256) and
         sha(sdk_input / 'manifest.json') == args.sdk_manifest_sha256, 'explicit SDK identity differs')
    compiler = args.compiler.resolve()
    manifest = validate_sdk(sdk_input, args.arch, args.mode, compiler)
    out.mkdir(parents=True)
    record = dict(schema=1, status='preparing', architecture=args.arch, mode=args.mode,
        sdk_manifest_sha256=args.sdk_manifest_sha256, sdk_only=True, kernel_source_compiled=False,
        guest_executed=False, archive_only=True, distribution_disk_attached=False,
        synchronized_guest_shutdown=False, physical=False, smp=False, full_M7=False, account_authentication=False, durable_password_storage=False,
        commands=[], runner_sha256=sha(Path(__file__)))
    serial = bytearray()
    process = None
    environment = dict(os.environ, XMAKE_ROOT='y', XMAKE_GLOBALDIR=str(out / 'xmake-global'),
                       XMAKE_TMPDIR=str(out / 'xmake-temp'), PYTHONDONTWRITEBYTECODE='1')
    for name in ('CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH', 'GCC_EXEC_PREFIX', 'COMPILER_PATH'):
        environment.pop(name, None)

    def save():
        (out / 'serial.log').write_bytes(serial)
        temporary = out / 'result.tmp'
        temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
        temporary.replace(out / 'result.json')

    def call(label, argv):
        row = dict(label=label, argv=list(map(str, argv)))
        record['commands'].append(row); save()
        with (out / (label + '.log')).open('xb') as stream:
            done = subprocess.run(row['argv'], cwd=consumer, env=environment,
                                  stdout=stream, stderr=subprocess.STDOUT)
        row.update(returncode=done.returncode, log_sha256=sha(out / (label + '.log'))); save()
        need(done.returncode == 0, label + ' failed; original log retained')

    save()
    try:
        consumer = out / 'ObfuscationOS'
        files = source_files(ROOT)
        files['config/services.conf'] = sha(ROOT / 'config/services.conf')
        record['original_source_files'] = files
        for name, digest in files.items():
            source = ROOT / name
            target = consumer / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            need(sha(target) == digest, 'OS source changed while copying ' + name)
        (consumer / 'xmake.lua').write_bytes((consumer / 'xmake.lua').read_bytes() + INCLUDE.encode())
        (consumer / 'config/services.conf').write_text(CONFIGURATION)
        record.update(consumer_xmake_sha256=sha(consumer / 'xmake.lua'),
                      fixture_configuration_sha256=sha(consumer / 'config/services.conf'))
        sdk = out / 'sdk'
        for name, digest in {**manifest['files'], 'manifest.json': args.sdk_manifest_sha256}.items():
            target = sdk / name; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sdk_input / name, target)
            need(sha(target) == digest, 'SDK source changed while copying ' + name)
        validate_sdk(sdk, args.arch, args.mode, compiler)
        call('configure', [args.xmake, 'f', '-y', '-a', args.arch, '-m', args.mode,
             '--kernel_sdk=' + str(sdk), '--systoolchain_dir=' + str(compiler.parent.parent),
             '--native_init_control=y', '--ccache=n'])
        call('distro', [args.xmake, '-y', '-v', '-b', 'distro_image'])
        build = consumer / 'build' / args.arch / args.mode
        root = build / 'rootfs'
        image = build / 'distro' / ('kernel.bin' if args.arch in ('i386', 'x86_64') else 'kernel.elf')
        record.update(image_sha256=sha(image), archive_sha256=sha(build / 'boot.okar'),
            fixture_sha256=sha(root / 'bin/console-lease-probe'), init_sha256=sha(root / 'init'),
            qemu_sha256=sha(args.qemu.resolve()), compiler_sha256=sha(compiler), xmake_sha256=sha(args.xmake.resolve()))
        command = archive_only_command(args.qemu.resolve(), args.arch, image)
        record.update(qemu_argv=command, status='running-guest'); save()
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, env=environment)
        record['guest_executed'] = True

        def receive(predicate):
            deadline = time.monotonic() + args.timeout
            while not predicate():
                need(time.monotonic() < deadline, 'timeout waiting for console lease execution')
                ready, _, _ = select.select([process.stdout], [], [], 0.1)
                if not ready:
                    need(process.poll() is None, 'QEMU exited before console lease acceptance')
                    continue
                chunk = os.read(process.stdout.fileno(), 16384)
                need(chunk, 'QEMU output ended before console lease acceptance')
                serial.extend(chunk)
                need(len(serial) < 4 * 1024 * 1024, 'serial capacity exceeded')
                for marker in (b'NATIVE_CONSOLE_FAIL', b'event=fatal-hold', b'OK_TEST_FAIL', b'Kernel panic'):
                    need(marker not in serial, 'native console guest failure: ' + marker.decode())
                save()

        # Wait for a complete unique prompt before injecting exactly once.
        prompt = rb'^NATIVE_CONSOLE_PROMPT generation=2 pid=[1-9][0-9]* epoch=[1-9][0-9]* bytes=32\r?$'
        receive(lambda: re.search(prompt, serial, re.M))
        key = secrets.token_hex(16).encode()
        while any(not re.search(rb'[a-f]', key[i:i + 8]) for i in range(len(key) - 7)):
            key = secrets.token_hex(16).encode()
        record['input'] = dict(hex32=key.decode(), bytes=32, injections=1,
            before_serial_offset=len(serial), sha256=hashlib.sha256(key).hexdigest())
        save()
        process.stdin.write(key); process.stdin.flush()
        receive(lambda: re.search(rb'^' + PASS_PREFIX + rb'pid=[1-9][0-9]* epoch=[1-9][0-9]* '
                    rb'guard=live old_children=3 key=exact\r?\n', serial, re.M) and
                len(re.findall(rb'^NATIVE_PID1 scope=hardware profile=dependency-graph-v1 '
                    rb'event=other-child service=none pid=[1-9][0-9]* generation=0 time_ms=[0-9]+ '
                    rb'next_ms=0 errno=0 status=[0-9]+\r?\n', serial, re.M)) >= 3)
        # Both unrelated guard and new console deliberately stay alive. Observe
        # a bounded quiet tail so a late restart/failure cannot pass unnoticed.
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline:
            need(process.poll() is None, 'QEMU exited during the acceptance hold')
            ready, _, _ = select.select([process.stdout], [], [], min(0.05, max(0, deadline - time.monotonic())))
            if ready:
                chunk = os.read(process.stdout.fileno(), 16384)
                need(chunk, 'QEMU output ended during the acceptance hold')
                serial.extend(chunk)
                need(len(serial) < 4 * 1024 * 1024, 'serial capacity exceeded')
        record['post_acceptance_hold_ms'] = 250
        record['execution'] = validate_console_lease(bytes(serial), key)
        need(sha(image) == record['image_sha256'], 'boot image changed during execution')
        need(sha(build / 'boot.okar') == record['archive_sha256'], 'boot archive changed during execution')
        for name, digest in files.items():
            if name not in ('xmake.lua', 'config/services.conf'):
                need(sha(consumer / name) == digest, 'retained OS source changed: ' + name)
        need(sha(consumer / 'xmake.lua') == record['consumer_xmake_sha256'] and
             sha(consumer / 'config/services.conf') == record['fixture_configuration_sha256'],
             'retained fixture configuration changed')
        validate_sdk(sdk, args.arch, args.mode, compiler)
        record.update(status='passed-native-console-lease', serial_sha256=hashlib.sha256(serial).hexdigest())
    except BaseException as error:
        record.update(status='failed', error=repr(error)); raise
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait(timeout=3)
            process.stdin.close(); process.stdout.close()
            record.update(qemu_returncode=process.returncode, host_retired_guest=True)
        save()
    print('NATIVE_CONSOLE_LEASE_PASS', args.arch, args.mode, out / 'result.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=tuple(ARCH_TRIPLES), required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    parser.add_argument('--kernel-sdk', type=Path, required=True)
    parser.add_argument('--sdk-manifest-sha256', required=True)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--qemu', type=Path, required=True)
    parser.add_argument('--xmake', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    if not 0 < args.timeout <= 600:
        parser.error('timeout must be positive and bounded')
    run(args)


if __name__ == '__main__':
    main()

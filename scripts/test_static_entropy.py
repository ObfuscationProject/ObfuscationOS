#!/usr/bin/env python3
"""Execute exact static-musl entropy probes and no-device rollbacks on scratch ext4."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import select
import shutil
import subprocess
import sys
import time

from qemu_distro import command_for
TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
from build_musl_probe import admit_musl_build
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from musl_source import inspect_elf
from dynamic_startup_observer import FAILURES, validate_static_run
from entropy_observer import validate_complete

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def receive(process, serial, expected, deadline, start=0):
    while expected not in serial[start:]:
        if time.monotonic() > deadline:
            raise RuntimeError('timeout waiting for complete guest command')
        readable, _, _ = select.select([process.stdout], [], [], .1)
        if not readable:
            continue
        chunk = os.read(process.stdout.fileno(), 8192)
        if not chunk:
            raise RuntimeError('QEMU exited before guest command completed')
        serial.extend(chunk)
        if any(bad in serial for bad in FAILURES):
            raise RuntimeError('guest or kernel failure in entropy transcript')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=ARCH_TRIPLES, required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    for name in ('qemu', 'kernel', 'kernel-sdk', 'rootfs-tree', 'probe', 'runner', 'musl-build', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--rng', choices=('virtio', 'none'), required=True)
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    if not __debug__ or not sys.dont_write_bytecode or os.environ.get('PYTHONDONTWRITEBYTECODE') != '1':
        raise ValueError('run with PYTHONDONTWRITEBYTECODE=1 python3 -B')
    validate_sdk(args.kernel_sdk.resolve(), args.arch, args.mode)
    musl = admit_musl_build(args.musl_build.resolve(), args.arch)
    manifest_path = args.probe.resolve().parent / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('architecture') != args.arch or manifest.get('mode') != args.mode or
            manifest.get('status') != 'built-not-executed' or manifest.get('executed') is not False or
            manifest.get('source_manifest_sha256') != sha(args.musl_build.resolve() / 'manifest.json') or
            musl['mode'] != args.mode or manifest.get('elf_sha256') != sha(args.probe.resolve()) or
            manifest.get('probe_sha256') != sha(TOOLS.parent / 'tests/musl/entropy_static.c')):
        raise ValueError('static entropy payload is not the exact mode-matching musl build')
    inspect_elf(args.probe.resolve(), args.arch)
    inspect_elf(args.runner.resolve(), args.arch)
    if args.probe.read_bytes()[7] != 3 or args.runner.read_bytes()[7] != 0:
        raise ValueError('probe and runner personalities are not Linux and native')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = out / 'root'
    shutil.copytree(args.rootfs_tree.resolve(), root, symlinks=True)
    for source, target in [(args.probe.resolve(), root / 'bin/entropy-static'),
                           (args.runner.resolve(), root / 'bin/static-entropy-runner')]:
        shutil.copy2(source, target)
        target.chmod(0o755)
    disk = out / 'rootfs.ext4.img'
    with (out / 'package.log').open('xb') as log:
        subprocess.run([sys.executable, '-B', str(TOOLS / 'mkext4.py'), '--root', str(root), '--out', str(disk)],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    initial = out / 'rootfs-input.ext4.img'
    shutil.copy2(disk, initial)
    kernel = out / 'kernel-input.bin'
    shutil.copy2(args.kernel.resolve(), kernel)
    command = command_for(args.qemu.resolve(), args.arch, kernel, disk, 'none',
                          native_profile=True, entropy=args.rng)
    record = dict(schema=1, architecture=args.arch, mode=args.mode, scope='actual-static-musl-qemu-entropy',
                  status='running', rng=args.rng, command=command, guest_runs=0,
                  sdk_manifest_sha256=sha(args.kernel_sdk.resolve() / 'manifest.json'),
                  musl_manifest_sha256=sha(args.musl_build.resolve() / 'manifest.json'),
                  probe_manifest_sha256=sha(manifest_path), probe_sha256=sha(args.probe.resolve()),
                  runner_sha256=sha(args.runner.resolve()), kernel_sha256=sha(kernel),
                  qemu_sha256=sha(args.qemu.resolve()), input_disk_sha256=sha(initial),
                  observer_sha256=sha(TOOLS / 'entropy_observer.py'),
                  observer_dependency_sha256=sha(TOOLS / 'dynamic_startup_observer.py'),
                  script_sha256=sha(Path(__file__)), physical=False, smp=False,
                  synchronized_shutdown=False)
    serial = bytearray()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        receive(process, serial, b'OK_SYSTEM_GUI boot=complete', time.monotonic() + args.timeout)
        receive(process, serial, b'oksh> ', time.monotonic() + args.timeout)
        if b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw' not in serial:
            raise RuntimeError('guest did not mount actual prepared ext4 storage')
        boundaries = []
        for _ in range(2):
            start = len(serial)
            process.stdin.write(b'static-entropy-runner\n')
            process.stdin.flush()
            receive(process, serial, b'oksh> ', time.monotonic() + args.timeout, start)
            validate_static_run(bytes(serial[start:]), no_entropy=args.rng == 'none')
            boundaries.append((start, len(serial)))
            record['guest_runs'] += 1
        start = len(serial)
        process.stdin.write(b'hello | cat\n')
        process.stdin.flush()
        receive(process, serial, b'oksh> ', time.monotonic() + args.timeout, start)
        record['execution'] = validate_complete(bytes(serial), boundaries, (start, len(serial)),
                                               architecture=args.arch, enabled=args.rng == 'virtio')
        record['status'] = 'awaiting-offline'
    except BaseException as error:
        record.update(status='fail', failure=repr(error))
        raise
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()
        (out / 'serial.log').write_bytes(serial)
        record.update(serial_sha256=sha(out / 'serial.log'), input_disk_unchanged=sha(initial) == record['input_disk_sha256'])
        (out / 'result.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    with (out / 'fsck.log').open('xb') as log:
        check = subprocess.run(['/usr/sbin/e2fsck', '-fn', str(disk)], stdout=log, stderr=subprocess.STDOUT)
    record.update(fsck_exit_code=check.returncode, fsck_log_sha256=sha(out / 'fsck.log'), final_disk_sha256=sha(disk))
    record['status'] = 'pass' if check.returncode == 0 and record['input_disk_unchanged'] and record['guest_runs'] == 2 else 'fail'
    (out / 'result.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    if record['status'] != 'pass':
        raise RuntimeError('final offline filesystem check failed')
    print('PASS ' + args.arch + '/' + args.mode + ': two static entropy commands rng=' + args.rng)

if __name__ == '__main__':
    main()

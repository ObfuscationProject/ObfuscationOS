#!/usr/bin/env python3
"""Run an explicit x86-64 shared-musl PIE from an SDK-linked ext4 guest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time

from qemu_distro import command_for
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from dynamic_startup_observer import FAILURES, validate_run, validate_static_run, validate_pipeline, validate_complete


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receive(process: subprocess.Popen, serial: bytearray, expected: bytes, deadline: float,
            start: int = 0) -> None:
    assert process.stdout is not None
    while expected not in serial[start:]:
        if time.monotonic() > deadline:
            raise RuntimeError('timeout waiting for complete guest record: ' + repr(expected))
        readable, _, _ = select.select([process.stdout], [], [], 0.1)
        if not readable:
            continue
        chunk = os.read(process.stdout.fileno(), 8192)
        if not chunk:
            raise RuntimeError('QEMU exited before guest record: ' + repr(expected))
        serial.extend(chunk)
        if any(bad in serial for bad in FAILURES):
            raise RuntimeError('guest failure record precedes shared-musl acceptance')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    parser.add_argument('--qemu', type=Path, required=True)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--rootfs-tree', type=Path, required=True)
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--runner', type=Path, required=True)
    parser.add_argument('--static-probe', type=Path, required=True)
    parser.add_argument('--static-runner', type=Path, required=True)
    parser.add_argument('--shared-build', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--omit-loader', action='store_true',
                        help='Guest negative control: fail exec before commit, then run native commands')
    parser.add_argument('--rng', choices=('virtio', 'none'), required=True,
                        help='Explicit QEMU entropy device selection')
    args = parser.parse_args()
    if args.omit_loader and args.rng == 'none':
        raise ValueError('run one negative control at a time')

    shared = args.shared_build.resolve()
    manifest_path = shared / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    libc = shared / 'sysroot/usr/lib/libc.so'
    if (manifest.get('schema') != 1 or manifest.get('architecture') != 'x86_64' or
            manifest.get('mode') != args.mode or manifest.get('status') != 'built-not-executed' or
            manifest.get('loader_path') != '/lib/ld-musl-x86_64.so.1' or
            manifest.get('files', {}).get('sysroot/usr/lib/libc.so') != digest(libc)):
        raise ValueError('shared musl build is not the exact x86-64 mode-matching loader')
    probe = args.probe.resolve()
    runner = args.runner.resolve()
    static_probe = args.static_probe.resolve()
    static_runner = args.static_runner.resolve()
    static_manifest_path = static_probe.parent / 'manifest.json'
    static_manifest = json.loads(static_manifest_path.read_text())
    if (static_manifest.get('schema') != 1 or static_manifest.get('architecture') != 'x86_64' or
            static_manifest.get('mode') != args.mode or
            static_manifest.get('status') != 'built-not-executed' or
            static_manifest.get('target_executed') is not False or
            static_manifest.get('musl_manifest_sha256') != digest(manifest_path) or
            static_manifest.get('elf_sha256') != digest(static_probe)):
        raise ValueError('static musl ELF differs from its exact mode-matching build manifest')
    static_bytes = static_probe.read_bytes()
    if (len(static_bytes) < 64 or static_bytes[:9] != b'\x7fELF\x02\x01\x01\x03\x00' or
            int.from_bytes(static_bytes[16:18], 'little') != 2 or
            int.from_bytes(static_bytes[18:20], 'little') != 62):
        raise ValueError('static entropy probe is not the explicit x86-64 Linux ET_EXEC')
    probe_manifest_path = probe.parent / 'manifest.json'
    probe_manifest = json.loads(probe_manifest_path.read_text())
    if (probe_manifest.get('schema') != 1 or probe_manifest.get('architecture') != 'x86_64' or
            probe_manifest.get('mode') != args.mode or
            probe_manifest.get('status') != 'built-not-executed' or
            probe_manifest.get('target_executed') is not False or
            probe_manifest.get('musl_manifest_sha256') != digest(manifest_path) or
            probe_manifest.get('elf_sha256') != digest(probe)):
        raise ValueError('dynamic PIE differs from its exact mode-matching build manifest')
    payload = probe.read_bytes()
    if (len(payload) < 64 or payload[:9] != b'\x7fELF\x02\x01\x01\x03\x00' or
            int.from_bytes(payload[16:18], 'little') != 3 or
            int.from_bytes(payload[18:20], 'little') != 62 or
            b'/lib/ld-musl-x86_64.so.1\x00' not in payload[:65536]):
        raise ValueError('probe is not the explicit x86-64 Linux PT_INTERP PIE')

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = out / 'root'
    shutil.copytree(args.rootfs_tree.resolve(), root, symlinks=True)
    (root / 'bin/dynamic-startup').write_bytes(payload)
    (root / 'bin/dynamic-startup').chmod(0o755)
    shutil.copy2(runner, root / 'bin/dynamic-startup-runner')
    (root / 'bin/dynamic-startup-runner').chmod(0o755)
    (root / 'bin/entropy-static').write_bytes(static_bytes)
    (root / 'bin/entropy-static').chmod(0o755)
    shutil.copy2(static_runner, root / 'bin/static-entropy-runner')
    (root / 'bin/static-entropy-runner').chmod(0o755)
    if not args.omit_loader:
        (root / 'usr/lib').mkdir(parents=True)
        shutil.copy2(libc, root / 'usr/lib/libc.so')
        (root / 'lib').mkdir()
        (root / 'lib/ld-musl-x86_64.so.1').symlink_to('../usr/lib/libc.so')
    disk = out / 'rootfs.ext4.img'
    mkext4 = Path(__file__).resolve().parents[1] / 'tools/mkext4.py'
    with (out / 'package.log').open('w') as log:
        subprocess.run([sys.executable, '-B', str(mkext4), '--root', str(root), '--out', str(disk)],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    kernel = out / 'kernel-input.bin'
    shutil.copyfile(args.kernel.resolve(), kernel)
    initial_disk = out / 'rootfs-input.ext4.img'
    shutil.copyfile(disk, initial_disk)
    input_disk_sha = digest(initial_disk)
    record = {'schema': 1, 'scope': 'x86_64-qemu-native-shared-musl-startup', 'mode': args.mode,
              'status': 'running', 'shared_manifest_sha256': digest(manifest_path),
              'negative_missing_loader': args.omit_loader,
              'rng': args.rng,
              'probe_sha256': digest(probe), 'libc_sha256': digest(libc),
              'static_probe_sha256': digest(static_probe),
              'static_manifest_sha256': digest(static_manifest_path),
              'static_runner_sha256': digest(static_runner),
              'probe_manifest_sha256': digest(probe_manifest_path),
              'runner_sha256': digest(runner),
              'kernel_sha256': digest(kernel), 'input_disk_sha256': input_disk_sha,
              'qemu_sha256': digest(args.qemu.resolve()), 'guest_runs': 0,
              'static_guest_runs': 0}
    command = command_for(args.qemu.resolve(), 'x86_64', kernel, disk, 'none', entropy=args.rng)
    record['command'] = list(map(str, command))
    serial = bytearray()
    run_boundaries = []
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    assert process.stdin is not None
    try:
        receive(process, serial, b'OK_SYSTEM_GUI boot=complete', time.monotonic() + args.timeout)
        receive(process, serial, b'oksh> ', time.monotonic() + args.timeout)
        if b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw' not in serial:
            raise RuntimeError('guest did not mount the prepared ext4 root')
        entropy_marker = (b'OK_ENTROPY source=virtio-rng-pci state=ready' if args.rng == 'virtio' else
                          b'OK_ENTROPY source=none state=unavailable')
        if entropy_marker not in serial:
            raise RuntimeError('guest entropy source differs from the explicit QEMU configuration')
        static_boundaries = []
        for _ in range(2):
            start = len(serial)
            process.stdin.write(b'static-entropy-runner\n')
            process.stdin.flush()
            receive(process, serial, b'oksh> ', time.monotonic() + args.timeout, start)
            validate_static_run(bytes(serial[start:]), no_entropy=args.rng == 'none')
            static_boundaries.append((start, len(serial)))
            record['static_guest_runs'] += 1
        for _ in range(2):
            start = len(serial)
            process.stdin.write(b'dynamic-startup-runner\n')
            process.stdin.flush()
            receive(process, serial, b'oksh> ', time.monotonic() + args.timeout, start)
            result = bytes(serial[start:])
            validate_run(result, missing_loader=args.omit_loader, no_entropy=args.rng == 'none')
            run_boundaries.append((start, len(serial)))
            record['guest_runs'] += 1
        start = len(serial)
        process.stdin.write(b'hello | cat\n')
        process.stdin.flush()
        receive(process, serial, b'oksh> ', time.monotonic() + args.timeout, start)
        validate_pipeline(bytes(serial[start:]))
        record['execution'] = validate_complete(bytes(serial), run_boundaries, (start, len(serial)),
                                                missing_loader=args.omit_loader,
                                                no_entropy=args.rng == 'none')
        record['execution']['static_boundaries'] = [list(row) for row in static_boundaries]
        record['observer_sha256'] = digest(Path(__file__).resolve().parents[1] / 'tools/dynamic_startup_observer.py')
        record['status'] = 'awaiting-offline'
    except Exception as error:
        record['status'] = 'fail'
        record['failure'] = str(error)
        raise
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdin.close()
        assert process.stdout is not None
        process.stdout.close()
        (out / 'serial.log').write_bytes(serial)
        record['serial_sha256'] = digest(out / 'serial.log')
        record['input_disk_unchanged'] = digest(initial_disk) == input_disk_sha
        (out / 'result.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    if not record['input_disk_unchanged']:
        raise RuntimeError('preserved input disk changed during guest execution')
    with (out / 'fsck.log').open('w') as log:
        check = subprocess.run(['e2fsck', '-fn', str(disk)], stdout=log, stderr=subprocess.STDOUT)
    record['fsck_exit_code'] = check.returncode
    record['final_disk_sha256'] = digest(disk)
    record['fsck_log_sha256'] = digest(out / 'fsck.log')
    record['status'] = 'pass' if check.returncode == 0 and record['guest_runs'] == 2 and record['static_guest_runs'] == 2 else 'fail'
    (out / 'result.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    if record['status'] != 'pass':
        raise RuntimeError('offline filesystem or guest execution check failed')
    action = ('missing-loader rollback controls' if args.omit_loader else
              'no-entropy rollback controls' if args.rng == 'none' else 'shared-musl startup executions')
    print('PASS x86_64 ' + args.mode + ': two native ' + action + ' and final fsck')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

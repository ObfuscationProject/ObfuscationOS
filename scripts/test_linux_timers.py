#!/usr/bin/env python3
"""Run the static-musl interval timer probe (tests/musl/linux_timers.c) on scratch ext4.

The probe exercises alarm, setitimer/getitimer and the timer_create family in
the guest's Linux personality and prints one TIMERS_PASS line; the kernel adds
its OK_TIMERS counters to the interrupt report when the probe exits.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
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
from dynamic_startup_observer import FAILURES

PROMPT = b'oksh> '
RESULT = re.compile(rb'TIMERS_(PASS|FAIL) arch=([a-z0-9_]+)[^\r\n]*')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receive(process, serial, done, deadline):
    while not done():
        if time.monotonic() > deadline:
            raise RuntimeError('timeout waiting for the guest')
        readable, _, _ = select.select([process.stdout], [], [], .1)
        if not readable:
            continue
        chunk = os.read(process.stdout.fileno(), 8192)
        if not chunk:
            raise RuntimeError('QEMU exited before the probe completed')
        serial.extend(chunk)
        if any(bad in serial for bad in FAILURES):
            raise RuntimeError('guest or kernel failure in the timer transcript')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=ARCH_TRIPLES, required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    for name in ('qemu', 'kernel', 'kernel-sdk', 'rootfs-tree', 'probe', 'musl-build', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=600)
    args = parser.parse_args()
    validate_sdk(args.kernel_sdk.resolve(), args.arch, args.mode)
    musl = admit_musl_build(args.musl_build.resolve(), args.arch)
    manifest_path = args.probe.resolve().parent / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('architecture') != args.arch or manifest.get('mode') != args.mode or
            manifest.get('status') != 'built-not-executed' or manifest.get('executed') is not False or
            manifest.get('source_manifest_sha256') != sha(args.musl_build.resolve() / 'manifest.json') or
            musl['mode'] != args.mode or manifest.get('elf_sha256') != sha(args.probe.resolve()) or
            manifest.get('probe_sha256') != sha(TOOLS.parent / 'tests/musl/linux_timers.c')):
        raise ValueError('timer probe is not the exact mode-matching musl build of tests/musl/linux_timers.c')
    inspect_elf(args.probe.resolve(), args.arch)
    if args.probe.read_bytes()[7] != 3:
        raise ValueError('timer probe lacks the Linux ELF personality')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = out / 'root'
    shutil.copytree(args.rootfs_tree.resolve(), root, symlinks=True)
    shutil.copy2(args.probe.resolve(), root / 'bin/linux-timers')
    (root / 'bin/linux-timers').chmod(0o755)
    disk = out / 'rootfs.ext4.img'
    with (out / 'package.log').open('xb') as log:
        subprocess.run([sys.executable, '-B', str(TOOLS / 'mkext4.py'), '--root', str(root), '--out', str(disk)],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    kernel = out / 'kernel-input.bin'
    shutil.copy2(args.kernel.resolve(), kernel)
    command = command_for(args.qemu.resolve(), args.arch, kernel, disk, 'none', native_profile=True)
    record = dict(schema=1, architecture=args.arch, mode=args.mode, scope='actual-static-musl-qemu-timers',
                  status='running', command=command,
                  sdk_manifest_sha256=sha(args.kernel_sdk.resolve() / 'manifest.json'),
                  musl_manifest_sha256=sha(args.musl_build.resolve() / 'manifest.json'),
                  probe_manifest_sha256=sha(manifest_path), probe_sha256=sha(args.probe.resolve()),
                  kernel_sha256=sha(kernel), qemu_sha256=sha(args.qemu.resolve()), input_disk_sha256=sha(disk),
                  script_sha256=sha(Path(__file__)), physical=False, smp=False)
    serial = bytearray()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        receive(process, serial, lambda: b'OK_SYSTEM_GUI boot=complete' in serial and PROMPT in serial,
                time.monotonic() + args.timeout)
        start = len(serial)
        process.stdin.write(b'/bin/linux-timers\n')
        process.stdin.flush()
        began = time.monotonic()

        def finished():
            match = RESULT.search(serial, start)
            return match is not None and PROMPT in serial[match.end():]
        receive(process, serial, finished, time.monotonic() + args.timeout)
        record['probe_seconds'] = round(time.monotonic() - began, 2)
        result = RESULT.search(serial, start)
        record['result'] = result.group(0).decode()
        timers = re.findall(rb'OK_TIMERS scope=hardware[^\r\n]*', serial[start:])
        record['kernel_timers'] = timers[-1].decode() if timers else None
        if result.group(1) != b'PASS' or result.group(2).decode() != args.arch:
            raise RuntimeError('timer probe failed: ' + record['result'])
        if not timers:
            raise RuntimeError('kernel reported no OK_TIMERS counters after the probe')
        record['status'] = 'pass'
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
        record['serial_sha256'] = sha(out / 'serial.log')
        (out / 'result.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print('PASS ' + args.arch + '/' + args.mode + ': ' + record['result'])
    print(record['kernel_timers'])


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Execute native FAT media write/read/delete phases across three QEMU boots."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import shutil
import subprocess
import time

from qemu_distro import command_for


MARKERS = {
    'write': b'OK_FAT_NATIVE scope=hardware phase=write create=pass read=pass write=pass truncate=pass zero=pass list=pass remove=pass flush=pass',
    'read': b'OK_FAT_NATIVE scope=hardware phase=read restart=pass content=pass casefold=pass list=pass',
    'delete': b'OK_FAT_NATIVE scope=hardware phase=delete remove=pass flush=pass',
}
FAILURES = (b'FAT_CHECK failed', b'POSIX_CHECK failed:', b'OK_TEST_FAIL ',
            b'boot=failed', b'boot=degraded')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def complete_lines(data):
    return [line.rstrip(b'\r\n') for line in data.splitlines(keepends=True) if line.endswith(b'\n')]


def check_failures(data):
    if any(marker in data for marker in FAILURES):
        raise ValueError('native FAT guest reported an assertion or boot failure')


def validate_boot(data, filesystem):
    check_failures(data)
    expected = f'OK_STORAGE scope=hardware source=virtio filesystem={filesystem} mode=rw mount=/media'.encode()
    lines = complete_lines(data)
    if lines.count(expected) != 1 or lines.count(b'OK_SYSTEM_GUI boot=complete') != 1:
        raise ValueError('missing unique actual FAT /media mount and distribution boot markers')
    if not data.endswith(b'oksh> '):
        raise ValueError('FAT boot did not reach a complete native shell prompt')


def validate_phase(data, phase):
    check_failures(data)
    if phase not in MARKERS:
        raise ValueError('unknown native FAT phase')
    records = [line for line in complete_lines(data) if b'OK_FAT_NATIVE' in line]
    if records != [MARKERS[phase]] or not data.endswith(b'oksh> '):
        raise ValueError('missing unique complete FAT phase result and returning shell prompt')


def format_command(program, filesystem, disk):
    if filesystem == 'fat32':
        return [str(program), '-F', '32', '-n', 'OBOSFAT', str(disk)]
    if filesystem == 'exfat':
        return [str(program), '-L', 'OBOSFAT', str(disk)]
    raise ValueError('unsupported explicit FAT filesystem')


def fsck_command(program, disk):
    return [str(program), '-n', str(disk)]


def guest(args, kernel, disk, phase, output):
    serial = bytearray()
    command = command_for(args.qemu, args.arch, kernel, disk, 'none', native_profile=True)
    (output / (phase + '-command.json')).write_text(json.dumps(command, indent=2) + '\n')
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    assert process.stdin is not None and process.stdout is not None
    row = dict(phase=phase, command=command, status='running')

    def receive(start):
        deadline = time.monotonic() + args.timeout
        while not serial[start:].endswith(b'oksh> '):
            if time.monotonic() >= deadline:
                raise TimeoutError('native FAT ' + phase + ' guest timed out')
            readable, _, _ = select.select([process.stdout], [], [], min(.1, max(0, deadline-time.monotonic())))
            if not readable:
                if process.poll() is not None:
                    raise RuntimeError('FAT guest exited before acceptance')
                continue
            chunk = os.read(process.stdout.fileno(), 65536)
            if not chunk:
                raise RuntimeError('FAT guest closed serial before acceptance')
            serial.extend(chunk)
            check_failures(serial)

    try:
        receive(0)
        validate_boot(bytes(serial), args.filesystem)
        start = len(serial)
        process.stdin.write(('posix-check --fat-' + phase + '\n').encode('ascii'))
        process.stdin.flush()
        receive(start)
        validate_phase(bytes(serial[start:]), phase)
        sync_start = len(serial)
        process.stdin.write(b'sync /media\n')
        process.stdin.flush()
        receive(sync_start)
        if complete_lines(bytes(serial[sync_start:])).count(b'Filesystem synchronized') != 1:
            raise ValueError('explicit data-volume sync failed')
        row.update(status='passed', command_begin=start, command_end=len(serial))
        return row
    except BaseException as error:
        row.update(status='failed', error=str(error))
        raise
    finally:
        process.terminate()
        try:
            tail, _ = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            tail, _ = process.communicate(timeout=3)
        serial.extend(tail)
        log = output / (phase + '-serial.log')
        log.write_bytes(serial)
        row.update(qemu_returncode=process.returncode, serial_sha256=sha(log))
        # A delayed guest failure must not be hidden by the preceding prompt.
        try:
            check_failures(serial)
            if process.returncode not in (0, -signal.SIGTERM):
                raise ValueError('unexpected QEMU exit status: ' + str(process.returncode))
        except ValueError as error:
            row.update(status='failed', error=str(error))
            raise
        finally:
            (output / (phase + '-result.json')).write_text(json.dumps(row, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', required=True)
    parser.add_argument('--qemu', required=True, type=Path)
    parser.add_argument('--kernel', required=True, type=Path)
    parser.add_argument('--filesystem', choices=('fat32', 'exfat'), required=True)
    parser.add_argument('--mkfs', required=True, type=Path)
    parser.add_argument('--fsck', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path, help='Fresh directory; existing evidence is never replaced')
    parser.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    if not 0 < args.timeout <= 3600:
        parser.error('--timeout must be positive and at most 3600 seconds')
    for name in ('qemu', 'kernel', 'mkfs', 'fsck'):
        path = getattr(args, name).resolve(strict=True)
        if not path.is_file() or (name != 'kernel' and not os.access(path, os.X_OK)):
            parser.error(name + ' must be an explicit existing ' + ('file' if name == 'kernel' else 'executable'))
        if ',' in str(path):
            parser.error('commas are not supported in QEMU input paths')
        setattr(args, name, path)
    output = args.out.resolve()
    if ',' in str(output):
        parser.error('commas are not supported in QEMU output paths')
    # Validate architecture before reserving output or formatting any image.
    command_for(args.qemu, args.arch, args.kernel, output / 'media.img', 'none', native_profile=True)
    output.mkdir(parents=True, exist_ok=False)
    inputs = {name: dict(path=str(getattr(args, name)), sha256=sha(getattr(args, name)))
              for name in ('qemu', 'kernel', 'mkfs', 'fsck')}
    report = dict(status='running', scope='qemu-native-fat-media', physical=False,
                  architecture=args.arch, filesystem=args.filesystem, bytes=64 * 1024 * 1024,
                  native_execution=False, restart_kind='qemu-stop-start-after-fsync', power_failure=False,
                  inputs=inputs, commands=[], phases=[])

    def save():
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')

    def run_tool(label, command, readonly=False):
        before = sha(disk) if readonly else None
        row = dict(label=label, argv=command, status='running')
        report['commands'].append(row)
        save()
        environment = dict(os.environ, LC_ALL='C', TZ='UTC')
        for variable in ('LD_PRELOAD', 'LD_AUDIT', 'LD_LIBRARY_PATH'):
            environment.pop(variable, None)
        with (output / (label + '.log')).open('xb') as stream:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT,
                                    env=environment, timeout=args.timeout)
        row.update(returncode=result.returncode, status='passed' if result.returncode == 0 else 'failed')
        if readonly:
            row['image_unchanged'] = sha(disk) == before
            if not row['image_unchanged']:
                raise RuntimeError('read-only FAT checker changed the image')
        save()
        if result.returncode:
            raise RuntimeError(label + ' failed; original output retained')

    save()
    disk = output / 'media.img'
    kernel = output / ('retained-kernel' + args.kernel.suffix)
    try:
        # BIOS QEMU recipes attach the boot image as a disk: use a private copy.
        shutil.copy2(args.kernel, kernel)
        with disk.open('xb') as stream:
            stream.truncate(report['bytes'])
        run_tool('format', format_command(args.mkfs, args.filesystem, disk))
        run_tool('initial-fsck', fsck_command(args.fsck, disk), readonly=True)
        for phase in ('write', 'read', 'delete'):
            report['phases'].append(guest(args, kernel, disk, phase, output))
            run_tool(phase + '-fsck', fsck_command(args.fsck, disk), readonly=True)
            if phase == 'write':
                checkpoint = output / 'with-file.img'
                shutil.copy2(disk, checkpoint)
                report['file_checkpoint_sha256'] = sha(checkpoint)
            save()
        for name, identity in inputs.items():
            if sha(identity['path']) != identity['sha256']:
                raise RuntimeError('explicit input changed during execution: ' + name)
        if sha(kernel) != inputs['kernel']['sha256']:
            raise RuntimeError('retained kernel changed during boot')
        report.update(status='passed', native_execution=True, final_disk_sha256=sha(disk))
    except BaseException as error:
        report.update(status='failed', error=str(error))
        raise
    finally:
        save()
    print(f'PASS scope=qemu-native arch={args.arch} filesystem={args.filesystem} mount=/media phases=write-read-delete fsck=clean')


if __name__ == '__main__':
    main()

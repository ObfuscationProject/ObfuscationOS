#!/usr/bin/env python3
"""Run a separately built native shell acceptance app in an SDK consumer image.

The image must explicitly package tests/native/oksh_pipeline.c as
/bin/oksh-acceptance. This observer does not build or inspect Kernel source.
Hosted parser/process tests do not substitute for this guest execution.
"""
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
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from qemu_distro import command_for

MARKER = (b'OK_OKSH_NATIVE scope=hardware pipeline=pass redirection=pass append=pass '
          b'stderr=pass order=pass status=pass quoting=pass errors=pass repeat=pass bytes=12289')
ARCHITECTURES = ('i386', 'x86_64', 'aarch64', 'arm32', 'rv64', 'rv32', 'loongarch64', 'mips', 'mips64', 'ppc')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', required=True, choices=ARCHITECTURES)
    parser.add_argument('--qemu', required=True, type=Path)
    parser.add_argument('--kernel', required=True, type=Path)
    parser.add_argument('--rootfs', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--timeout', type=float, default=90)
    parser.add_argument('--source-manifest', type=Path)
    parser.add_argument('--sdk-manifest', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    paths = {'qemu': args.qemu.resolve(), 'kernel': args.kernel.resolve(), 'rootfs': args.rootfs.resolve()}
    for name in ('source_manifest', 'sdk_manifest'):
        value = getattr(args, name)
        if value is not None:
            paths[name] = value.resolve()
    record = {'architecture': args.arch, 'cpus': 1, 'smp': False, 'physical': False,
              'executed': False, 'status': 'preparing', 'boundaries': [],
              'inputs': {name: {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                         for name, path in paths.items()},
              'scope': 'Native QEMU fork/pipe/exec shell pipelines, file redirections, status and repeated cleanup; no job control, PTY or complete POSIX shell claim'}
    # Retain the exact bytes used by this run before a later producer rebuild
    # can replace its outputs. Manifest pins describe inputs, not linker closure.
    for name, path in paths.items():
        if name == 'qemu':
            continue
        retained = args.output / (name + path.suffix)
        shutil.copy2(path, retained)
        if hashlib.sha256(retained.read_bytes()).hexdigest() != record['inputs'][name]['sha256']:
            raise RuntimeError('input changed while retaining ' + name)
        record['inputs'][name]['retained_path'] = str(retained.resolve())
    serial = bytearray()
    with tempfile.TemporaryDirectory(prefix='oksh-guest-disk-') as temporary:
        disk = Path(temporary) / 'rootfs.img'
        shutil.copy2(record['inputs']['rootfs']['retained_path'], disk)
        command = command_for(paths['qemu'], args.arch, Path(record['inputs']['kernel']['retained_path']), disk, 'none')
        record['command'] = command
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        assert process.stdin is not None and process.stdout is not None

        def receive(start=0):
            deadline = time.monotonic() + args.timeout
            while not serial[start:].endswith(b'oksh> '):
                if time.monotonic() >= deadline:
                    raise RuntimeError('timeout waiting for native shell')
                ready, _, _ = select.select([process.stdout], [], [], .1)
                if not ready:
                    continue
                data = os.read(process.stdout.fileno(), 8192)
                if not data:
                    raise RuntimeError('QEMU exited before shell completion')
                serial.extend(data)

        try:
            receive()
            if b'OK_TEST_FAIL ' in serial:
                raise RuntimeError('guest boot assertion failed')
            for text, marker in [('hello | cat | cat', b'hello from ObfuscationOS userland'),
                                 ('oksh-acceptance', MARKER),
                                 ('echo OKSH_AFTER_ACCEPTANCE | cat | cat', b'OKSH_AFTER_ACCEPTANCE\n')]:
                start = len(serial)
                process.stdin.write((text + '\n').encode())
                process.stdin.flush()
                receive(start)
                span = bytes(serial[start:]).replace(b'\r\n', b'\n')
                if b'OKSH_NATIVE_FAIL ' in span or b'OK_TEST_FAIL ' in span:
                    raise RuntimeError('guest assertion failed')
                # Match a complete output record, never a command echo substring.
                if marker not in span or (marker == MARKER and span.count(MARKER) != 1):
                    raise RuntimeError('missing native output for ' + text)
                record['boundaries'].append({'command': text, 'start': start, 'end': len(serial)})
            record.update(status='passed', executed=True)
        except Exception as error:
            record.update(status='failed', error=str(error))
        finally:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            process.stdin.close(); process.stdout.close()
            (args.output / 'serial.log').write_bytes(serial)
            record['serial_sha256'] = hashlib.sha256(serial).hexdigest()
            (args.output / 'result.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': record['status'], 'executed': record['executed'], 'output': str(args.output)}))
    return 0 if record['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

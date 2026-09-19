#!/usr/bin/env python3
"""Boot a Virtio ext4 root, write via native syscalls, reboot, then check offline."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import time
from qemu_distro import command_for


def guest(args, disk: Path, commands, logfile: Path):
    serial = bytearray()
    process = subprocess.Popen(command_for(args.qemu.resolve(), args.arch, args.kernel.resolve(), disk, 'none'),
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert process.stdin is not None and process.stdout is not None
    def receive(predicate):
        deadline = time.monotonic() + args.timeout
        while not predicate():
            if time.monotonic() >= deadline:
                raise RuntimeError('native ext4 guest timed out')
            readable, _, _ = select.select([process.stdout], [], [], .1)
            if not readable:
                continue
            chunk = os.read(process.stdout.fileno(), 4096)
            if not chunk:
                raise RuntimeError('guest exited before acceptance')
            serial.extend(chunk)
            if b'POSIX_CHECK failed:' in serial or b'OK_TEST_FAIL ' in serial:
                raise RuntimeError('guest regression failed')
    try:
        receive(lambda: b'oksh> ' in serial)
        if b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw' not in serial:
            raise RuntimeError('guest did not mount the real ext4 block device')
        if b'OK_MODE debug' in serial and b'OK_USERLAND scope=hardware acceptance=pass' not in serial:
            raise RuntimeError('native debug acceptance missing')
        for command, expected in commands:
            start = len(serial)
            process.stdin.write((command + '\n').encode())
            process.stdin.flush()
            receive(lambda: b'oksh> ' in serial[start:])
            if expected not in serial[start:]:
                raise RuntimeError(f'wrong result for {command!r}: {serial[start:].decode(errors="replace")}')
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        logfile.parent.mkdir(parents=True, exist_ok=True)
        logfile.write_bytes(serial)
        process.stdin.close()
        process.stdout.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', required=True)
    parser.add_argument('--qemu', required=True, type=Path)
    parser.add_argument('--kernel', required=True, type=Path)
    parser.add_argument('--rootfs', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--timeout', type=float, default=100)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    token = 'EXT4_REBOOT_' + args.arch
    with tempfile.TemporaryDirectory(prefix='ok-ext4-hardware-') as directory:
        disk = Path(directory) / 'persistent.img'
        shutil.copy2(args.rootfs, disk)
        guest(args, disk, [(f'notes /home/persistent.txt {token}', b'Saved /home/persistent.txt'),
                           ('sync', b'Filesystem synchronized')], args.out/'first-boot.log')
        subprocess.run(['e2fsck', '-fn', str(disk)], check=True)
        guest(args, disk, [('cat /home/persistent.txt', token.encode()),
                           ('sync', b'Filesystem synchronized')], args.out/'second-boot.log')
        subprocess.run(['e2fsck', '-fn', str(disk)], check=True)
        contents = subprocess.check_output(['debugfs', '-R', 'cat /home/persistent.txt', str(disk)])
        if contents != (token + '\n').encode():
            raise RuntimeError('offline ext4 reader disagrees with native filesystem')
        (args.out/'offline-content.txt').write_bytes(contents)
        shutil.copy2(disk, args.out/'verified.img')
    print(f'PASS scope=hardware arch={args.arch} virtio=read-write-flush ext4=root-exec-reboot fsck=clean')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Boot a Virtio ext4 root, write via native syscalls, reboot, then check offline."""
from __future__ import annotations
import argparse
import os
import re
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
        if args.require_native and b'OK_USERLAND scope=hardware acceptance=pass' not in serial:
            raise RuntimeError('explicit native init acceptance missing')
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
    parser.add_argument('--require-native', action='store_true', help='Require explicitly selected init acceptance')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    token = 'EXT4_REBOOT_' + args.arch
    long_target = '/home/' + './' * 32 + 'persistent.txt'
    with tempfile.TemporaryDirectory(prefix='ok-ext4-hardware-') as directory:
        disk = Path(directory) / 'persistent.img'
        shutil.copy2(args.rootfs, disk)
        guest(args, disk, [(f'notes /home/pending.txt {token}', b'Saved /home/pending.txt'),
                           ('mv /home/pending.txt /home/persistent.txt', b''),
                           ('ln /home/persistent.txt /home/alias.txt', b''),
                           ('ln -s persistent.txt /home/relative-link', b''),
                           ('ln -s /home/persistent.txt /home/absolute-link', b''),
                           (f'ln -s {long_target} /home/extent-link', b''),
                           ('mv /home/persistent.txt /home/alias.txt', b''),
                           ('cat /home/persistent.txt', token.encode()),
                           ('cat /home/alias.txt', token.encode()),
                           ('cat /home/relative-link', token.encode()),
                           ('cat /home/absolute-link', token.encode()),
                           ('cat /home/extent-link', token.encode()),
                           ('mkdir /home/draft', b''),
                           (f'notes /home/draft/item {token}', b'Saved /home/draft/item'),
                           ('mv /home/draft /home/archive', b''),
                           ('sync', b'Filesystem synchronized')], args.out/'first-boot.log')
        subprocess.run(['e2fsck', '-fn', str(disk)], check=True)
        guest(args, disk, [('cat /home/persistent.txt', token.encode()),
                           ('cat /home/alias.txt', token.encode()),
                           ('cat /home/relative-link', token.encode()),
                           ('cat /home/absolute-link', token.encode()),
                           ('cat /home/extent-link', token.encode()),
                           ('cat /home/archive/item', token.encode()),
                           ('sync', b'Filesystem synchronized')], args.out/'second-boot.log')
        subprocess.run(['e2fsck', '-fn', str(disk)], check=True)
        contents = subprocess.check_output(['debugfs', '-R', 'cat /home/persistent.txt', str(disk)])
        if contents != (token + '\n').encode():
            raise RuntimeError('offline ext4 reader disagrees with native filesystem')
        inode_numbers = []
        for path in ('/home/persistent.txt', '/home/alias.txt'):
            metadata = subprocess.check_output(['debugfs', '-R', 'stat ' + path, str(disk)])
            inode = re.search(rb'Inode:\s+(\d+)', metadata)
            links = re.search(rb'Links:\s+(\d+)', metadata)
            if not inode or not links or int(links[1]) != 2:
                raise RuntimeError('offline hard-link count differs from native filesystem')
            inode_numbers.append(inode[1])
        if inode_numbers[0] != inode_numbers[1]:
            raise RuntimeError('hard links refer to different on-disk inodes')
        for name, target in (('relative-link', 'persistent.txt'), ('absolute-link', '/home/persistent.txt')):
            metadata = subprocess.check_output(['debugfs', '-R', 'stat /home/' + name, str(disk)])
            if b'Type: symlink' not in metadata or ('Fast link dest: "' + target + '"').encode() not in metadata:
                raise RuntimeError('offline symbolic link differs from native filesystem')
        extent_target = subprocess.check_output(['debugfs', '-R', 'cat /home/extent-link', str(disk)])
        if extent_target != long_target.encode():
            raise RuntimeError('offline extent-backed symlink differs from native filesystem')
        for path in ('/home/pending.txt', '/home/draft'):
            missing = subprocess.run(['debugfs', '-R', 'stat ' + path, str(disk)], capture_output=True, check=True)
            if b'File not found' not in missing.stderr or b'Inode:' in missing.stdout:
                raise RuntimeError('renamed source remains visible: ' + path)
        (args.out/'offline-content.txt').write_bytes(contents)
        shutil.copy2(disk, args.out/'verified.img')
    print(f'PASS scope=hardware arch={args.arch} virtio=read-write-flush ext4=root-exec-reboot rename=pass hardlink=pass symlink=pass fsck=clean')


if __name__ == '__main__':
    main()

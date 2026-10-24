#!/usr/bin/env python3
"""Execute two SDK-only ordered-data roots and check the entire disk and I/O trace."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / 'jbd2'))
from admit_linux_fixture import checksum
from journalled_mode_image import extract_volume, inode_metadata
from ordered_data_fixture import expected as ordered_transaction

IO = re.compile(r'JROOT_IO ordinal=(\d+) kind=(write|flush) sector=(\d+) bytes=(\d+) crc32c=(\d+) status=(\d+)')
EPOCH = re.compile(r'JROOT_EPOCH epoch=(\d+) size=(\d+) ctime_seconds=(\d+) '
                   r'ctime_nanoseconds=(\d+) mtime_seconds=(\d+) mtime_nanoseconds=(\d+)')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def boot(argv: list[str], log: Path, timeout: float,
         markers: tuple[bytes, ...] = (b'JROOT_FIXTURE_PASS', b'JROOT_FIXTURE_FAIL')) -> tuple[str, int | None]:
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert process.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    output = bytearray()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for key, _ in selector.select(0.2):
            chunk = os.read(key.fileobj.fileno(), 65536)
            if chunk:
                output.extend(chunk)
        complete_marker = any((at := output.find(marker)) >= 0 and b'\n' in output[at:]
                              for marker in markers)
        if complete_marker or process.poll() is not None:
            break
    timed_out = time.monotonic() >= deadline
    if process.poll() is None:
        process.terminate()
    try:
        tail, _ = process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        tail, _ = process.communicate(timeout=5)
    output.extend(tail or b'')
    log.write_bytes(output)
    require(not timed_out, 'QEMU boot timed out: ' + str(log))
    return output.decode(errors='replace').replace('\r\n', '\n'), process.returncode


def io_records(text: str) -> list[tuple[str, int, int, int]]:
    records = []
    for line in text.splitlines():
        if not line.startswith('JROOT_IO'):
            continue
        match = IO.fullmatch(line)
        require(match is not None, 'malformed completed transport record')
        ordinal, kind, sector, size, crc, status = match.groups()
        require(int(ordinal) == len(records) + 1 and int(status) == 0, 'I/O ordinal or status')
        records.append((kind, int(sector), int(size), int(crc)))
    return records


def epoch_records(text: str) -> list[tuple[int, ...]]:
    records = []
    for line in text.splitlines():
        if line.startswith('JROOT_EPOCH'):
            match = EPOCH.fullmatch(line)
            require(match is not None, 'malformed ordered-data epoch record')
            records.append(tuple(int(value) for value in match.groups()))
    return records


def transaction_io(facts: dict, before: bytes, published: bytes, complete: bytes,
                   target: int, data_block: int) -> list[tuple[str, int, int, int]]:
    journal = facts['journal_first']
    inode = inode_metadata(before, target)

    def write(block: int, data: bytes) -> tuple[str, int, int, int]:
        payload = data[block * 1024:(block + 1) * 1024]
        return ('write', facts['origin'] + block * 2, 1024, checksum(0xffffffff, payload))

    flush = ('flush', 0, 0, 0)
    return [write(data_block, published), flush, flush,
            write(journal + 1, published), write(journal + 2, published),
            write(journal + 3, published), write(journal + 5, published), flush,
            write(journal + 4, published), flush, write(1, published), flush,
            write(journal, published), flush, flush, write(1, published),
            write(inode['block'], complete), flush, write(journal, complete), flush,
            write(1, complete), flush]


def check_markers(text: str, mutations: int) -> None:
    markers = ['JROOT_FIXTURE_BEGIN', 'JROOT_OWNER acquired=1',
               'JROOT_RECOVERY_PASS', 'JROOT_OWNER retired=1',
               'JROOT_STORAGE virtio=1', 'OK_NATIVE_IMAGE personality=linux',
               'OK_NATIVE scope=hardware init=loaded', 'JROOT_CREDENTIALS',
               'JROOT_USER_BEGIN source=disk path=/init',
               f'JROOT_USER_PASS source=disk mutations={mutations}',
               f'JROOT_FIXTURE_PASS uid=1000 exit=0 reaped=0 retained=1 personality=linux epoch={mutations + 1}']
    positions = [text.find(marker) for marker in markers]
    require(all(index >= 0 for index in positions) and positions == sorted(positions),
            'recovery, disk root, Linux /init or exit marker absent/out of order')
    require('JROOT_FIXTURE_FAIL' not in text and 'JROOT_USER_FAIL' not in text,
            'guest fixture or /init reported failure')
    require(text.count('JROOT_USER_BEGIN') == 1 and text.count('JROOT_FIXTURE_PASS') == 1,
            'duplicate or missing user execution')
    require('JROOT_RECOVERY_PASS clean=1 empty=1 actions=0' in text,
            'clean root admission did not preflight recovery')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--build-result-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=90)
    args = parser.parse_args()
    build, out = args.build.resolve(), args.output.resolve()
    require(sha(build / 'result.json') == args.build_result_sha256, 'explicit build receipt changed')
    built = json.loads((build / 'result.json').read_text())
    require(built.get('status') == 'prepared-not-executed' and built.get('sdk_abi') == 38 and
            built.get('kernel_source_compiled') is False, 'build is not an SDK38 artifact consumer')
    for name, key in [('initial-guarded.img', 'initial_disk_sha256'),
                      ('fixture.bin', 'kernel_image_sha256'), ('rootfs.okar', 'archive_sha256')]:
        require(sha(build / name) == built[key], 'build artifact changed: ' + name)
    require((build / 'rootfs.okar').stat().st_size == 16, 'archive must contain no /init')
    out.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'scope': 'SDK38 QEMU guest, actual completed Virtio calls and independent full-image oracle',
              'build_result_sha256': args.build_result_sha256, 'runner_sha256': sha(Path(__file__)),
              'architecture': built['architecture'], 'mode': built['mode'], 'sdk_manifest_sha256': built['sdk_manifest_sha256'],
              'kernel_image_sha256': built['kernel_image_sha256'], 'user_elf_sha256': built['user_elf_sha256'],
              'initial_disk_sha256': built['initial_disk_sha256'], 'physical': False, 'smp': False, 'boots': []}

    def save() -> None:
        (out / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')

    save()
    try:
        disk = out / 'disk.img'
        shutil.copy2(build / 'initial-guarded.img', disk)
        original = extract_volume(disk.read_bytes())
        facts = json.loads((build / 'facts.json').read_text())
        argv = list(built['guest_argv'])
        old = 'file=' + str(build / 'disk.img') + ',format=raw,if=none,id=fsdisk'
        new = 'file=' + str(disk) + ',format=raw,if=none,id=fsdisk'
        require(argv.count(old) == 1 and sha(Path(argv[0])) == built['tool_sha256'][str(Path(argv[0]).resolve())],
                'QEMU executable or disk argument changed')
        argv[argv.index(old)] = new
        report['guest_argv'] = argv
        final = None
        for ordinal, mutations in ((1, 3), (2, 0)):
            log = out / f'boot-{ordinal}.log'
            text, exit_code = boot(argv, log, args.timeout)
            check_markers(text, mutations)
            observed = io_records(text)
            epochs = epoch_records(text)
            after = extract_volume(disk.read_bytes())
            flush = ('flush', 0, 0, 0)
            if ordinal == 1:
                seed = inode_metadata(after, facts['nodes']['seed']['inode'])
                require((seed['mode'], seed['uid'], seed['gid'], seed['size'], seed['blocks512']) ==
                        (0o100600, 1000, 1001, 4005, 8),
                        'first boot did not persist bounded seed size and identity')
                require([row[:2] for row in epochs] == [(2, 4096), (3, 4000), (4, 4005)],
                        'ordered-data epochs or sizes absent/out of order')
                expected = [flush]
                current = original
                for operation, row in zip(('overwrite', 'truncate', 'append'), epochs):
                    _, _, ctime_seconds, ctime_nanoseconds, mtime_seconds, mtime_nanoseconds = row
                    published, complete, data_block = ordered_transaction(
                        current, facts, operation, ctime_seconds, ctime_nanoseconds,
                        mtime_seconds, mtime_nanoseconds)
                    expected.extend(transaction_io(facts, current, published, complete,
                                                   seed['inode'], data_block))
                    current = complete
                final = current
                expected.append(flush)
                require(after == final, 'entire disk differs from independent libext2fs checksum oracle')
            else:
                require(not epochs, 'clean boot unexpectedly changed ordered-data epoch')
                expected = [flush, flush]
                require(after == final, 'second clean boot changed the disk')
            require(observed == expected, 'completed Virtio write/FLUSH order or byte CRC differs')
            report['boots'].append({'ordinal': ordinal, 'mutations': mutations,
                                    'log_sha256': sha(log), 'disk_sha256': sha(disk),
                                    'writes': sum(item[0] == 'write' for item in observed),
                                    'flushes': sum(item[0] == 'flush' for item in observed),
                                    'qemu_exit_code': exit_code, 'guest_pass': True,
                                    'independent_full_image_oracle': True})
            save()
        volume = out / 'final-volume.img'
        volume.write_bytes(final)
        e2fsck = Path(shutil.which('e2fsck')).resolve()
        done = subprocess.run([str(e2fsck), '-fn', str(volume)], stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
        fsck_log = out / 'final-fsck.log'
        fsck_log.write_bytes(done.stdout)
        require(done.returncode == 0, 'offline final ext4 check failed')
        report.update(status='passed', final_volume_sha256=sha(volume), final_disk_sha256=sha(disk),
                      fsck_log_sha256=sha(fsck_log), e2fsck_sha256=sha(e2fsck),
                      archive_init_present=False, dirty_recovery_executed=False,
                      interruption_matrix_executed=False)
    except BaseException as exc:
        report.update(status='failed', error=repr(exc))
        save()
        raise
    save()
    print('PASS SDK38 disk-root two-boot guest and full-image oracle:', built['architecture'], built['mode'])


if __name__ == '__main__':
    main()

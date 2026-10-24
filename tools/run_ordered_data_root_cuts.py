#!/usr/bin/env python3
"""Cut each completed first-transaction I/O, recover, and check the full disk."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / 'jbd2'))
from admit_linux_fixture import checksum
from journalled_mode_image import extract_volume, inode_metadata
from ordered_data_fixture import expected as ordered_transaction
from run_ordered_data_root import boot, epoch_records, io_records, require, sha, transaction_io


def cut_oracle(initial: bytes, cut_volume: bytes, facts: dict, local: int):
    """Model the exact durable prefix; early descriptor time is not yet observable."""
    require(0 <= local <= 22, 'first transaction cut boundary outside profile')
    journal = facts['journal_first']
    seed = facts['nodes']['seed']
    if local >= 6:
        inode_at = (journal + 3) * 1024 + seed['offset']
        ctime_seconds = struct.unpack_from('<I', cut_volume, inode_at + 12)[0]
        ctime_nanoseconds = struct.unpack_from('<I', cut_volume, inode_at + 132)[0] >> 2
        mtime_seconds = struct.unpack_from('<I', cut_volume, inode_at + 16)[0]
        mtime_nanoseconds = struct.unpack_from('<I', cut_volume, inode_at + 136)[0] >> 2
        require(struct.unpack_from('<I', cut_volume, inode_at + 4)[0] == 4096,
                'cut inode payload size differs from overwrite')
    else:
        ctime_seconds = mtime_seconds = 1700000000
        ctime_nanoseconds = mtime_nanoseconds = 0
    published, complete, data_block = ordered_transaction(
        initial, facts, 'overwrite', ctime_seconds, ctime_nanoseconds,
        mtime_seconds, mtime_nanoseconds)
    if 4 <= local < 6:
        at = (journal + 1) * 1024
        actual = bytearray(cut_volume[at:at + 1024])
        wanted = published[at:at + 1024]
        seed_crc = checksum(0xffffffff, bytes.fromhex(facts['uuid']))
        recorded = struct.unpack_from('>I', actual, 1020)[0]
        struct.pack_into('>I', actual, 1020, 0)
        require(checksum(seed_crc, actual) == recorded, 'early descriptor checksum')
        variable = set(range(56, 60)) | set(range(1020, 1024))
        require(all(a == b for index, (a, b) in enumerate(zip(actual, wanted))
                    if index not in variable), 'early descriptor fixed fields')
        patched = bytearray(published)
        patched[at:at + 1024] = cut_volume[at:at + 1024]
        published = bytes(patched)
    recipe = [
        (data_block, published), None, None,
        (journal + 1, published), (journal + 2, published),
        (journal + 3, published), (journal + 5, published), None,
        (journal + 4, published), None, (1, published), None,
        (journal, published), None, None, (1, published),
        (seed['block'], complete), None, (journal, complete), None,
        (1, complete), None,
    ]
    require(len(recipe) == 22, 'ordered transaction recipe length')
    expected = bytearray(initial)
    for event in recipe[:local]:
        if event is None:
            continue
        block, source = event
        expected[block * 1024:(block + 1) * 1024] = source[block * 1024:(block + 1) * 1024]
    require(bytes(expected) == cut_volume, 'cut disk differs from exact completed-call prefix')
    return published, complete, data_block


def run_one(ordinal: int, built: dict, build: Path, output: Path, facts: dict, initial: bytes):
    local = ordinal - 1
    row_dir = output / f'cut-{ordinal:02d}'
    row_dir.mkdir()
    disk = row_dir / 'disk.img'
    shutil.copy2(build / 'initial-guarded.img', disk)
    with disk.open('r+b') as stream:
        stream.write(b'JROOTCTL' + bytes([1, 0, 0, 0]) + struct.pack('<I', ordinal))
    argv = list(built['guest_argv'])
    old = 'file=' + str(build / 'disk.img') + ',format=raw,if=none,id=fsdisk'
    require(argv.count(old) == 1, 'exact build disk argument absent')
    argv[argv.index(old)] = 'file=' + str(disk) + ',format=raw,if=none,id=fsdisk'
    cut_log = row_dir / 'cut.log'
    cut, cut_exit = boot(argv, cut_log, 60, (b'JROOT_CUT', b'JROOT_FIXTURE_FAIL'))
    require(f'JROOT_CONTROL action=1 ordinal={ordinal}' in cut and
            re.search(rf'^JROOT_CUT ordinal={ordinal} writes=\d+ flushes=\d+ after-completed-call=1$',
                      cut, re.M) is not None and
            'JROOT_USER_PASS' not in cut and 'JROOT_FIXTURE_PASS' not in cut,
            'completed-call cut absent or execution continued')
    cut_io = io_records(cut)
    require(len(cut_io) == ordinal, 'cut completed I/O count')
    guarded = disk.read_bytes()
    require(guarded[16:facts['origin'] * 512] == bytes([0x9a]) * (facts['origin'] * 512 - 16) and
            guarded[-facts['suffix_sectors'] * 512:] == bytes([0x9a]) * facts['suffix_sectors'] * 512,
            'cut changed partition guards')
    cut_volume = guarded[facts['origin'] * 512:-facts['suffix_sectors'] * 512]
    published, complete, data_block = cut_oracle(initial, cut_volume, facts, local)
    flush = ('flush', 0, 0, 0)
    expected_io = [flush] + transaction_io(facts, initial, published, complete,
                                             facts['nodes']['seed']['inode'], data_block)[:local]
    require(cut_io == expected_io, 'cut completed I/O order or CRC differs from oracle')
    (row_dir / 'cut-volume.img').write_bytes(cut_volume)
    with disk.open('r+b') as stream:
        stream.write(bytes([0x9a]) * 16)
    require(extract_volume(disk.read_bytes()) == cut_volume, 'disarming control changed ext4 volume')
    recovery_log = row_dir / 'recover.log'
    recovery, recovery_exit = boot(argv, recovery_log, 90)
    require('JROOT_USER_PASS source=disk mutations=3' in recovery and
            'JROOT_FIXTURE_PASS uid=1000 exit=0 reaped=0 retained=1 personality=linux epoch=4' in recovery and
            recovery.find('JROOT_RECOVERY_PASS') < recovery.find('JROOT_STORAGE') <
            recovery.find('JROOT_USER_BEGIN') and 'JROOT_FIXTURE_FAIL' not in recovery,
            'recovery did not complete before successful disk /init')
    epochs = epoch_records(recovery)
    require([row[:2] for row in epochs] == [(2, 4096), (3, 4000), (4, 4005)],
            'recovery guest ordered-data epochs')
    recovered = bytearray(cut_volume)
    recovered[1024:2048] = initial[1024:2048]
    if local >= 13:
        inode_at = facts['nodes']['seed']['block'] * 1024
        recovered[inode_at:inode_at + 1024] = complete[inode_at:inode_at + 1024]
        journal_at = facts['journal_first'] * 1024
        recovered[journal_at:journal_at + 1024] = complete[journal_at:journal_at + 1024]
    current = bytes(recovered)
    expected_post = [flush]
    for operation, row in zip(('overwrite', 'truncate', 'append'), epochs):
        _, _, ctime_seconds, ctime_nanoseconds, mtime_seconds, mtime_nanoseconds = row
        next_published, next_complete, next_data = ordered_transaction(
            current, facts, operation, ctime_seconds, ctime_nanoseconds,
            mtime_seconds, mtime_nanoseconds)
        expected_post.extend(transaction_io(facts, current, next_published, next_complete,
                                            facts['nodes']['seed']['inode'], next_data))
        current = next_complete
    expected_post.append(flush)
    recovery_io = io_records(recovery)
    require(recovery_io[-len(expected_post):] == expected_post,
            'recovery resumed user I/O suffix differs from independent oracle')
    final = extract_volume(disk.read_bytes())
    require(final == current, 'recovery and resumed /init whole disk differs from oracle')
    seed = inode_metadata(final, facts['nodes']['seed']['inode'])
    require(seed['size'] == 4005 and seed['mode'] == 0o100600, 'recovered seed size or mode')
    clean_log = row_dir / 'clean.log'
    clean, clean_exit = boot(argv, clean_log, 60)
    require('JROOT_USER_PASS source=disk mutations=0' in clean and
            'JROOT_FIXTURE_PASS uid=1000 exit=0 reaped=0 retained=1 personality=linux epoch=1' in clean and
            io_records(clean) == [flush, flush] and extract_volume(disk.read_bytes()) == final,
            'second boot is not a clean read-only disk /init boot')
    volume_path = row_dir / 'final-volume.img'
    volume_path.write_bytes(final)
    fsck = subprocess.run(['e2fsck', '-fn', str(volume_path)], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT)
    fsck_log = row_dir / 'fsck.log'
    fsck_log.write_bytes(fsck.stdout)
    require(fsck.returncode == 0, 'offline fsck failed after cut recovery')
    return dict(cut_ordinal=ordinal, transaction_boundary=local,
                cut_exit_code=cut_exit, recovery_exit_code=recovery_exit,
                clean_exit_code=clean_exit, cut_log_sha256=sha(cut_log),
                recovery_log_sha256=sha(recovery_log), clean_log_sha256=sha(clean_log),
                cut_volume_sha256=sha(row_dir / 'cut-volume.img'),
                final_disk_sha256=sha(disk), final_volume_sha256=sha(volume_path),
                fsck_log_sha256=sha(fsck_log), recovery_writes=sum(x[0] == 'write' for x in recovery_io),
                recovery_flushes=sum(x[0] == 'flush' for x in recovery_io),
                full_disk_oracle=True, guest_cut_recovery_clean_boot=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--build-result-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--start', type=int, default=2)
    parser.add_argument('--end', type=int, default=23)
    args = parser.parse_args()
    build, output = args.build.resolve(), args.output.resolve()
    require(2 <= args.start <= args.end <= 23, 'cut range outside first ordered-data transaction')
    require(sha(build / 'result.json') == args.build_result_sha256, 'exact build receipt pin mismatch')
    built = json.loads((build / 'result.json').read_text())
    require(built.get('status') == 'prepared-not-executed' and built.get('sdk_abi') == 38 and
            built.get('kernel_source_compiled') is False, 'cut campaign requires SDK38 artifact consumer')
    require(sha(build / 'initial-guarded.img') == built['initial_disk_sha256'], 'initial disk pin mismatch')
    facts = json.loads((build / 'facts.json').read_text())
    initial = extract_volume((build / 'initial-guarded.img').read_bytes())
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status='running', scope='completed-call QEMU cuts, reboot recovery, clean boot and exact disk oracle',
                  runner_sha256=sha(Path(__file__)), build_result_sha256=args.build_result_sha256,
                  architecture=built['architecture'], mode=built['mode'],
                  sdk_manifest_sha256=built['sdk_manifest_sha256'], start=args.start, end=args.end,
                  physical_power_loss=False, volatile_cache_or_torn_media=False, rows=[])

    def save():
        (output / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')

    save()
    try:
        for ordinal in range(args.start, args.end + 1):
            report['rows'].append(run_one(ordinal, built, build, output, facts, initial))
            save()
            print('PASS ordered-data cut:', built['architecture'], ordinal, flush=True)
        report['status'] = 'passed'
    except BaseException as exc:
        report.update(status='failed', failed_ordinal=ordinal, error=repr(exc))
        save()
        raise
    save()


if __name__ == '__main__':
    main()

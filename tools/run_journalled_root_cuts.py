#!/usr/bin/env python3
"""Cut every first-chmod Virtio completion, then recover and clean-boot."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent / 'jbd2'))
from admit_linux_fixture import checksum
from journalled_mode_image import extract_volume, inode_metadata
from mounted_fixture import expected as file_transaction
from journalled_directory_transaction import expected as directory_transaction
from run_journalled_root import boot, io_records, transaction_io, sha, require


def marker(text: str, name: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(name)]


def cut_oracle(initial: bytes, cut_volume: bytes, facts: dict, local: int):
    journal = facts['journal_first']
    target = facts['nodes']['seed']
    if local >= 4:
        at = (journal + 3) * 1024 + target['offset']
        seconds = struct.unpack_from('<I', cut_volume, at + 12)[0]
        nanos = struct.unpack_from('<I', cut_volume, at + 132)[0] >> 2
        require(1700000000 <= seconds < 1700003600 and nanos < 1000000000,
                'cut journal payload ctime outside guest range')
    else:
        seconds, nanos = 1700000000, 0
    published, complete = file_transaction(initial, facts, target['inode'], target['uid'], target['gid'],
                                           seconds, nanos, 0o640)
    if 2 <= local < 4:
        at = (journal + 1) * 1024
        actual = bytearray(cut_volume[at:at + 1024])
        wanted = published[at:at + 1024]
        seed = checksum(0xffffffff, bytes.fromhex(facts['uuid']))
        recorded = struct.unpack_from('>I', actual, 1020)[0]
        struct.pack_into('>I', actual, 1020, 0)
        require(checksum(seed, actual) == recorded, 'early descriptor checksum')
        require(all(a == b for index, (a, b) in enumerate(zip(actual, wanted))
                    if index not in set(range(56, 60)) | set(range(1020, 1024))),
                'early descriptor fixed fields')
        materialized = bytearray(published)
        materialized[at:at + 1024] = cut_volume[at:at + 1024]
        published = bytes(materialized)
    inode_block = target['block']
    recipe = [None, (journal + 1, published), (journal + 2, published),
              (journal + 3, published), (journal + 5, published), None,
              (journal + 4, published), None, (1, published), None,
              (journal, published), None, None, (1, published),
              (inode_block, complete), None, (journal, complete), None,
              (1, complete), None]
    require(len(recipe) == 20 and 1 <= local <= 20, 'first transaction boundary domain')
    expected = bytearray(initial)
    for event in recipe[:local]:
        if event is None:
            continue
        block, source = event
        expected[block * 1024:(block + 1) * 1024] = source[block * 1024:(block + 1) * 1024]
    require(bytes(expected) == cut_volume, 'cut disk differs from exact completed-call prefix')
    return published, complete, recipe


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
    text, cut_exit = boot(argv, cut_log, 45, (b'JROOT_CUT', b'JROOT_FIXTURE_FAIL'))
    require(marker(text, 'JROOT_CONTROL') == [f'JROOT_CONTROL action=1 ordinal={ordinal}'],
            'cut control was not admitted')
    require(len(marker(text, 'JROOT_CUT')) == 1 and
            re.fullmatch(rf'JROOT_CUT ordinal={ordinal} writes=\d+ flushes=\d+ after-completed-call=1',
                         marker(text, 'JROOT_CUT')[0]) is not None,
            'actual completed-call cut absent')
    require(not marker(text, 'JROOT_USER_PASS') and not marker(text, 'JROOT_FIXTURE_PASS'),
            'cut continued into success')
    cut_io = io_records(text)
    guarded = disk.read_bytes()
    require(guarded[16:facts['origin'] * 512] == bytes([0x9a]) * (facts['origin'] * 512 - 16) and
            guarded[-facts['suffix_sectors'] * 512:] == bytes([0x9a]) * facts['suffix_sectors'] * 512,
            'cut changed partition guards')
    cut_volume = guarded[facts['origin'] * 512:-facts['suffix_sectors'] * 512]
    published, complete, recipe = cut_oracle(initial, cut_volume, facts, local)
    expected_io = [('flush', 0, 0, 0)] + transaction_io(facts, initial, published, complete,
                                                        facts['nodes']['seed']['inode'])[:local]
    require(cut_io == expected_io, 'cut completed-call I/O prefix differs from independent oracle')
    (row_dir / 'cut-volume.img').write_bytes(cut_volume)
    # Clear only the out-of-volume test control. The cut ext4 bytes are retained.
    with disk.open('r+b') as stream:
        stream.write(bytes([0x9a]) * 16)
    require(extract_volume(disk.read_bytes()) == cut_volume, 'cut volume changed while disarming control')
    recovery_log = row_dir / 'recover.log'
    recovery, recovery_exit = boot(argv, recovery_log, 60)
    expected_mutations = 1 if local >= 11 else 2
    require(f'JROOT_USER_PASS source=disk mutations={expected_mutations}' in recovery and
            f'JROOT_FIXTURE_PASS uid=1000 exit=0 reaped=0 retained=1 personality=linux epoch={expected_mutations + 1}' in recovery,
            'recovery did not boot disk /init and finish remaining metadata operations')
    require(recovery.find('JROOT_RECOVERY_PASS') < recovery.find('JROOT_STORAGE') <
            recovery.find('JROOT_USER_BEGIN') and 'JROOT_FIXTURE_FAIL' not in recovery,
            'recovery was not durable before root publication')
    recovery_io = io_records(recovery)
    final_volume = extract_volume(disk.read_bytes())
    seed = inode_metadata(final_volume, facts['nodes']['seed']['inode'])
    child = inode_metadata(final_volume, facts['nodes']['child']['inode'])
    require(seed['mode'] == 0o100640 and child['mode'] == 0o40750,
            'recovery boot failed to persist both target modes')
    recovered = bytearray(cut_volume)
    recovered[1024:2048] = initial[1024:2048]
    if local >= 11:
        at = facts['nodes']['seed']['block'] * 1024
        recovered[at:at + 1024] = complete[at:at + 1024]
        at = facts['journal_first'] * 1024
        recovered[at:at + 1024] = complete[at:at + 1024]
        before_child = bytes(recovered)
        child_published, wanted = directory_transaction(before_child, facts, child['inode'], child['uid'],
            child['gid'], child['ctime']['seconds'], child['ctime']['nanoseconds'], 0o750)
        post_recovery_io = [('flush', 0, 0, 0)] + transaction_io(facts, before_child,
            child_published, wanted, child['inode']) + [('flush', 0, 0, 0)]
    else:
        before_seed = bytes(recovered)
        seed_published, seed_complete = file_transaction(before_seed, facts, seed['inode'], seed['uid'],
            seed['gid'], seed['ctime']['seconds'], seed['ctime']['nanoseconds'], 0o640)
        child_published, wanted = directory_transaction(seed_complete, facts, child['inode'], child['uid'],
            child['gid'], child['ctime']['seconds'], child['ctime']['nanoseconds'], 0o750)
        post_recovery_io = [('flush', 0, 0, 0)] + transaction_io(facts, before_seed,
            seed_published, seed_complete, seed['inode']) + [('flush', 0, 0, 0)] + \
            transaction_io(facts, seed_complete, child_published, wanted, child['inode']) + [('flush', 0, 0, 0)]
    require(final_volume == wanted, 'recovery and resumed /init whole disk differs from independent oracle')
    require(recovery_io[-len(post_recovery_io):] == post_recovery_io,
            'resumed user transaction write/FLUSH sequence differs')
    clean_log = row_dir / 'clean.log'
    clean, clean_exit = boot(argv, clean_log, 60)
    require('JROOT_USER_PASS source=disk mutations=0' in clean and
            'JROOT_FIXTURE_PASS uid=1000 exit=0 reaped=0 retained=1 personality=linux epoch=1' in clean and
            io_records(clean) == [('flush', 0, 0, 0)] * 3,
            'second boot is not a clean read-only /init boot')
    require(extract_volume(disk.read_bytes()) == final_volume, 'clean boot changed recovered disk')
    return {'cut_ordinal': ordinal, 'transaction_boundary': local, 'cut_exit_code': cut_exit,
            'recovery_exit_code': recovery_exit, 'clean_exit_code': clean_exit,
            'cut_log_sha256': sha(cut_log), 'recovery_log_sha256': sha(recovery_log),
            'clean_log_sha256': sha(clean_log), 'cut_volume_sha256': sha(row_dir / 'cut-volume.img'),
            'final_disk_sha256': sha(disk), 'recovery_mutations': expected_mutations,
            'recovery_writes': sum(item[0] == 'write' for item in recovery_io),
            'recovery_flushes': sum(item[0] == 'flush' for item in recovery_io),
            'full_disk_oracle': True, 'guest_cut_recovery_clean_boot': True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--build-result-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--start', type=int, default=2)
    parser.add_argument('--end', type=int, default=21)
    args = parser.parse_args()
    build, output = args.build.resolve(), args.output.resolve()
    require(2 <= args.start <= args.end <= 21, 'cut range outside first transaction')
    require(sha(build / 'result.json') == args.build_result_sha256, 'exact build receipt pin mismatch')
    built = json.loads((build / 'result.json').read_text())
    require(built.get('status') == 'prepared-not-executed' and built.get('sdk_abi') == 34,
            'cut campaign requires SDK34 artifact consumer')
    require(sha(build / 'initial-guarded.img') == built['initial_disk_sha256'],
            'initial disk pin mismatch')
    facts = json.loads((build / 'facts.json').read_text())
    initial = extract_volume((build / 'initial-guarded.img').read_bytes())
    output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'scope': 'completed-call QEMU cuts, reboot recovery, clean boot and exact disk oracle',
              'runner_sha256': sha(Path(__file__)), 'build_result_sha256': args.build_result_sha256,
              'architecture': built['architecture'], 'mode': built['mode'],
              'sdk_manifest_sha256': built['sdk_manifest_sha256'], 'start': args.start, 'end': args.end,
              'physical_power_loss': False, 'volatile_cache_or_torn_media': False, 'rows': []}

    def save() -> None:
        (output / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')

    save()
    try:
        for ordinal in range(args.start, args.end + 1):
            row = run_one(ordinal, built, build, output, facts, initial)
            report['rows'].append(row)
            save()
        report['status'] = 'passed'
    except BaseException as exc:
        report.update(status='failed', error=repr(exc), failed_ordinal=ordinal)
        save()
        raise
    save()
    print('PASS journalled-root cut/recovery/clean boots:', built['architecture'], args.start, args.end)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Exercise ordered-data prepublication and actual Virtio error controls."""
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
from journalled_mode_image import extract_volume, inode_metadata
from ordered_data_fixture import expected as ordered_transaction
from run_ordered_data_root import boot, epoch_records, io_records, require, sha, transaction_io
from run_ordered_data_root_cuts import cut_oracle

ERROR_IO = re.compile(r'JROOT_IO ordinal=(\d+) kind=(write|flush) sector=(\d+) bytes=(\d+) crc32c=(\d+) status=(\d+)')


def events(text: str) -> list[tuple[int, str, int]]:
    result = []
    for line in text.splitlines():
        if not line.startswith('JROOT_IO'):
            continue
        match = ERROR_IO.fullmatch(line)
        require(match is not None, 'malformed fault I/O record')
        ordinal, kind, _, _, _, status = match.groups()
        require(int(ordinal) == len(result) + 1, 'fault I/O ordinal gap')
        result.append((int(ordinal), kind, int(status)))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--build-result-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build, out = args.build.resolve(), args.output.resolve()
    require(sha(build / 'result.json') == args.build_result_sha256, 'exact SDK build receipt pin mismatch')
    built = json.loads((build / 'result.json').read_text())
    require(built.get('status') == 'prepared-not-executed' and built.get('sdk_abi') == 38 and
            built.get('kernel_source_compiled') is False, 'fault campaign requires SDK38 artifact consumer')
    require(sha(build / 'initial-guarded.img') == built['initial_disk_sha256'], 'initial disk changed')
    facts = json.loads((build / 'facts.json').read_text())
    initial = extract_volume((build / 'initial-guarded.img').read_bytes())
    out.mkdir(parents=True, exist_ok=False)
    report = dict(status='running', scope='QEMU guest synthetic pre-device I/O failures and prepublication rejection',
                  runner_sha256=sha(Path(__file__)), build_result_sha256=args.build_result_sha256,
                  architecture=built['architecture'], mode=built['mode'],
                  physical_power_loss=False, actual_media_error=False, rows=[])

    def save():
        (out / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')

    save()
    cases = [('journal-super-checksum', 0, 0, True),
             ('recovery-preflight-flush', 2, 1, True),
             ('data-write', 3, 2, False),
             ('data-flush', 2, 3, False),
             ('descriptor-write', 3, 5, False),
             ('commit-flush', 2, 11, False)]
    try:
        for name, action, ordinal, prepublication in cases:
            case = out / name
            case.mkdir()
            disk = case / 'disk.img'
            shutil.copy2(build / 'initial-guarded.img', disk)
            if action:
                with disk.open('r+b') as stream:
                    stream.write(b'JROOTCTL' + bytes([action, 0, 0, 0]) + struct.pack('<I', ordinal))
            else:
                with disk.open('r+b') as stream:
                    stream.seek(facts['origin'] * 512 + facts['journal_first'] * 1024 + 252)
                    value = stream.read(1)
                    stream.seek(-1, 1)
                    stream.write(bytes([value[0] ^ 1]))
            input_sha = sha(disk)
            argv = list(built['guest_argv'])
            old = 'file=' + str(build / 'disk.img') + ',format=raw,if=none,id=fsdisk'
            require(argv.count(old) == 1, 'exact QEMU root disk argument missing')
            argv[argv.index(old)] = 'file=' + str(disk) + ',format=raw,if=none,id=fsdisk'
            fault_log = case / 'fault.log'
            fault, fault_exit = boot(argv, fault_log, 60)
            require('JROOT_FIXTURE_FAIL' in fault and 'JROOT_FIXTURE_PASS' not in fault and
                    'JROOT_USER_PASS' not in fault, 'fault unexpectedly succeeded')
            if prepublication:
                require('JROOT_STORAGE' not in fault and 'JROOT_USER_BEGIN' not in fault and
                        sha(disk) == input_sha, 'rejected root was published or disk changed')
                require('JROOT_RECOVERY_ERROR reason=' +
                        ('injected Virtio FLUSH error' if action else 'JBD2 superblock checksum') in fault,
                        'prepublication recovery rejection absent')
            else:
                require('JROOT_STORAGE' in fault and 'JROOT_USER_BEGIN' in fault and
                        'JROOT_USER_FAIL' in fault, 'user-space I/O error not reported')
                records = events(fault)
                require(len(records) == ordinal and all(row[2] == 0 for row in records[:-1]) and
                        records[-1][0] == ordinal and records[-1][2] != 0,
                        'exact injected operation was not sole failed I/O')
                require(f'JROOT_INJECTED kind={"flush" if action == 2 else "write"} before-device=1' in fault,
                        'fault provenance marker absent')
                completed = ordinal - 2
                cut_volume = disk.read_bytes()[facts['origin'] * 512:-facts['suffix_sectors'] * 512]
                published, complete, data_block = cut_oracle(initial, cut_volume, facts, completed)
                expected = [('flush', 0, 0, 0)] + transaction_io(facts, initial, published, complete,
                            facts['nodes']['seed']['inode'], data_block)[:completed]
                observed = []
                for line in fault.splitlines():
                    match = ERROR_IO.fullmatch(line)
                    if match and int(match.group(6)) == 0:
                        observed.append((match.group(2), int(match.group(3)),
                                         int(match.group(4)), int(match.group(5))))
                require(observed == expected, 'successful fault prefix differs from independent oracle')
            row = dict(name=name, action=action, ordinal=ordinal, fault_exit_code=fault_exit,
                       fault_log_sha256=sha(fault_log), input_disk_sha256=input_sha,
                       fault_disk_sha256=sha(disk), prepublication=prepublication,
                       disk_unchanged_on_rejection=prepublication,
                       completed_prefix_oracle=not prepublication)
            if action:
                with disk.open('r+b') as stream:
                    stream.write(bytes([0x9a]) * 16)
                retry_log = case / 'retry.log'
                retry, retry_exit = boot(argv, retry_log, 90)
                require('JROOT_USER_PASS source=disk mutations=3' in retry and
                        'JROOT_FIXTURE_PASS uid=1000 exit=0 reaped=0 retained=1 personality=linux epoch=4' in retry and
                        retry.find('JROOT_RECOVERY_PASS') < retry.find('JROOT_STORAGE') <
                        retry.find('JROOT_USER_BEGIN'), 'retry after control removal failed')
                epochs = epoch_records(retry)
                require([event[:2] for event in epochs] == [(2, 4096), (3, 4000), (4, 4005)],
                        'retry ordered-data epochs')
                # Reconstruct from the exact pre-retry volume: a faulted call
                # never reached Virtio, while earlier completed calls remain.
                current = bytearray(cut_volume if not prepublication else initial)
                current[1024:2048] = initial[1024:2048]
                current = bytes(current)
                flush = ('flush', 0, 0, 0)
                expected_retry = [flush]
                for operation, event in zip(('overwrite', 'truncate', 'append'), epochs):
                    published, complete, block = ordered_transaction(current, facts, operation, *event[2:])
                    expected_retry.extend(transaction_io(facts, current, published, complete,
                                                        facts['nodes']['seed']['inode'], block))
                    current = complete
                expected_retry.append(flush)
                require(io_records(retry) == expected_retry and extract_volume(disk.read_bytes()) == current,
                        'retry full disk or completed I/O differs from independent oracle')
                seed = inode_metadata(current, facts['nodes']['seed']['inode'])
                require(seed['size'] == 4005 and seed['mode'] == 0o100600, 'retry seed metadata')
                clean_log = case / 'clean.log'
                clean, clean_exit = boot(argv, clean_log, 60)
                require('JROOT_USER_PASS source=disk mutations=0' in clean and
                        'JROOT_FIXTURE_PASS uid=1000 exit=0 reaped=0 retained=1 personality=linux epoch=1' in clean and
                        io_records(clean) == [flush, flush] and extract_volume(disk.read_bytes()) == current,
                        'clean restart after injected error failed')
                volume_path = case / 'final-volume.img'
                volume_path.write_bytes(current)
                fsck = subprocess.run(['e2fsck', '-fn', str(volume_path)], stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT)
                fsck_log = case / 'fsck.log'
                fsck_log.write_bytes(fsck.stdout)
                require(fsck.returncode == 0, 'offline fsck failed after injected-error retry')
                row.update(retry_exit_code=retry_exit, clean_exit_code=clean_exit,
                           retry_log_sha256=sha(retry_log), clean_log_sha256=sha(clean_log),
                           final_disk_sha256=sha(disk), final_volume_sha256=sha(volume_path),
                           final_fsck_log_sha256=sha(fsck_log), full_disk_oracle=True)
            report['rows'].append(row)
            save()
            print('PASS ordered-data fault:', name, flush=True)
        report['status'] = 'passed'
    except BaseException as exc:
        report.update(status='failed', failed_case=name, error=repr(exc))
        save()
        raise
    save()


if __name__ == '__main__':
    main()

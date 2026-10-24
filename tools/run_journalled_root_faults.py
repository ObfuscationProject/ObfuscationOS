#!/usr/bin/env python3
"""Exercise prepublication rejection and explicit Virtio error controls."""
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
from run_journalled_root import boot, sha, require
from run_journalled_root_cuts import cut_oracle

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
    require(built.get('status') == 'prepared-not-executed' and built.get('sdk_abi') == 34,
            'fault campaign requires SDK34 artifact consumer')
    require(sha(build / 'initial-guarded.img') == built['initial_disk_sha256'], 'initial disk changed')
    facts = json.loads((build / 'facts.json').read_text())
    initial = extract_volume((build / 'initial-guarded.img').read_bytes())
    out.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'scope': 'QEMU guest synthetic pre-device I/O failures and prepublication rejection',
              'runner_sha256': sha(Path(__file__)), 'build_result_sha256': args.build_result_sha256,
              'architecture': built['architecture'], 'mode': built['mode'],
              'physical_power_loss': False, 'actual_media_error': False, 'rows': []}

    def save() -> None:
        (out / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')

    save()
    cases = [('journal-super-checksum', 0, 0, True, None),
             ('flush-preflight', 2, 1, True, None),
             ('write-descriptor', 3, 3, False, 1),
             ('flush-payload', 2, 7, False, 5),
             ('flush-commit', 2, 13, False, 11)]
    try:
        for name, action, ordinal, prepublication, completed in cases:
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
            fault, fault_exit = boot(argv, fault_log, 45)
            require('JROOT_FIXTURE_FAIL' in fault and 'JROOT_FIXTURE_PASS' not in fault and
                    'JROOT_USER_PASS' not in fault, 'fault unexpectedly succeeded')
            if prepublication:
                require('JROOT_STORAGE' not in fault and 'JROOT_USER_BEGIN' not in fault and
                        sha(disk) == input_sha, 'rejected root was published or disk changed')
                if action:
                    require('JROOT_RECOVERY_ERROR reason=injected Virtio FLUSH error' in fault,
                            'preflight FLUSH error was not returned')
                else:
                    require('JROOT_RECOVERY_ERROR reason=JBD2 superblock checksum' in fault,
                            'journal checksum rejection absent')
            else:
                require('JROOT_STORAGE' in fault and 'JROOT_USER_BEGIN' in fault and
                        'JROOT_USER_FAIL' in fault, 'user-space I/O failure was not reported')
                records = events(fault)
                require(len(records) == ordinal and all(row[2] == 0 for row in records[:-1]) and
                        records[-1][0] == ordinal and records[-1][2] != 0,
                        'exact injected operation was not the sole failed I/O')
                require(f'JROOT_INJECTED kind={"flush" if action == 2 else "write"} before-device=1' in fault,
                        'fault provenance marker absent')
                # A synthetic failed request was never submitted to Virtio;
                # previous successful calls alone explain the retained disk.
                volume = disk.read_bytes()[facts['origin'] * 512:-facts['suffix_sectors'] * 512]
                cut_oracle(initial, volume, facts, completed)
            row = {'name': name, 'action': action, 'ordinal': ordinal,
                   'fault_exit_code': fault_exit, 'fault_log_sha256': sha(fault_log),
                   'input_disk_sha256': input_sha, 'fault_disk_sha256': sha(disk),
                   'prepublication': prepublication,
                   'disk_unchanged_on_rejection': prepublication,
                   'completed_prefix_oracle': completed is not None}
            if action:
                with disk.open('r+b') as stream:
                    stream.write(bytes([0x9a]) * 16)
                recovery_log = case / 'retry.log'
                retry, retry_exit = boot(argv, recovery_log, 60)
                expected_mutations = 1 if completed is not None and completed >= 11 else 2
                require(f'JROOT_USER_PASS source=disk mutations={expected_mutations}' in retry and
                        'JROOT_FIXTURE_PASS uid=1000 exit=0 reaped=0 retained=1' in retry and
                        retry.find('JROOT_RECOVERY_PASS') < retry.find('JROOT_STORAGE') < retry.find('JROOT_USER_BEGIN'),
                        'retry after clearing test control did not finish from disk')
                final = extract_volume(disk.read_bytes())
                seed = inode_metadata(final, facts['nodes']['seed']['inode'])
                child = inode_metadata(final, facts['nodes']['child']['inode'])
                require(seed['mode'] == 0o100640 and child['mode'] == 0o40750,
                        'retry target metadata not persistent')
                clean_log = case / 'clean.log'
                clean, clean_exit = boot(argv, clean_log, 60)
                require('JROOT_USER_PASS source=disk mutations=0' in clean and
                        'JROOT_FIXTURE_PASS uid=1000 exit=0 reaped=0 retained=1' in clean and
                        extract_volume(disk.read_bytes()) == final,
                        'clean restart after injected error failed')
                row.update(retry_exit_code=retry_exit, clean_exit_code=clean_exit,
                           retry_log_sha256=sha(recovery_log), clean_log_sha256=sha(clean_log),
                           final_disk_sha256=sha(disk), retry_mutations=expected_mutations)
                volume_path = case / 'final-volume.img'
                volume_path.write_bytes(final)
                done = subprocess.run(['e2fsck', '-fn', str(volume_path)], stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT)
                fsck_log = case / 'fsck.log'
                fsck_log.write_bytes(done.stdout)
                require(done.returncode == 0, 'offline fsck failed after injected-error retry')
                row.update(final_fsck_log_sha256=sha(fsck_log), final_volume_sha256=sha(volume_path))
            report['rows'].append(row)
            save()
        report['status'] = 'passed'
    except BaseException as exc:
        report.update(status='failed', failed_case=name, error=repr(exc))
        save()
        raise
    save()
    print('PASS journalled-root fault controls:', built['architecture'])


if __name__ == '__main__':
    main()

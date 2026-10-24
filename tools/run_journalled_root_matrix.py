#!/usr/bin/env python3
"""Build and execute explicit SDK34 journalled-root Debug representatives."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
from kernel_sdk import ARCH_TRIPLES


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--base-fixture', type=Path, required=True)
    parser.add_argument('--base-result-sha256', required=True)
    parser.add_argument('--promotion-receipt', type=Path, required=True)
    parser.add_argument('--promotion-receipt-sha256', required=True)
    parser.add_argument('--arches', nargs='+', choices=('x86_64', 'i386', 'mips'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    workspace, base, output = args.workspace.resolve(), args.base_fixture.resolve(), args.output.resolve()
    if sha(base / 'result.json') != args.base_result_sha256 or \
            sha(args.promotion_receipt) != args.promotion_receipt_sha256:
        raise ValueError('explicit base fixture or SDK34 promotion pin mismatch')
    promotion = json.loads(args.promotion_receipt.read_text())
    if promotion.get('status') != 'promoted-bounded-sdk34-paging-file-private-x86-dynamic':
        raise ValueError('wrong accepted SDK34 promotion')
    source = Path(__file__).resolve().parents[1]
    output.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'scope': 'SDK34 x86_64/i386/MIPS Debug representative journalled disk root',
              'runner_sha256': sha(Path(__file__)), 'base_result_sha256': args.base_result_sha256,
              'promotion_receipt_sha256': args.promotion_receipt_sha256, 'rows': []}

    def save() -> None:
        (output / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')

    def run(command: list[object], label: str) -> None:
        argv = list(map(str, command))
        done = subprocess.run(argv, cwd=source, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TZ='UTC'),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / (label + '.log')).write_bytes(done.stdout)
        report['rows'][-1]['commands'].append({'argv': argv, 'returncode': done.returncode,
                                               'log_sha256': sha(output / (label + '.log'))})
        save()
        if done.returncode:
            raise RuntimeError(label + ' failed; inspect its log')

    save()
    try:
        for arch in args.arches:
            triple = ARCH_TRIPLES[arch]
            toolchain = workspace / 'ObfuscationKernel/toolchains' / triple
            musl_build = workspace / 'ObfuscationOS/build/ports/musl/1.2.5' / arch / 'debug-optimized-v1'
            matches = [row for row in promotion['sdk_artifacts'] if row['architecture'] == arch and row['mode'] == 'debug']
            if len(matches) != 1:
                raise ValueError('missing/ambiguous exact SDK34 row for ' + arch)
            sdk = Path(matches[0]['sdk_path'])
            if sha(sdk / 'manifest.json') != matches[0]['manifest_sha256']:
                raise ValueError('SDK34 manifest pin changed for ' + arch)
            row = {'architecture': arch, 'mode': 'debug', 'status': 'running',
                   'sdk_manifest_sha256': matches[0]['manifest_sha256'],
                   'musl_source_manifest_sha256': sha(musl_build / 'manifest.json'),
                   'commands': []}
            report['rows'].append(row)
            save()
            musl = output / (arch + '-musl')
            run([sys.executable, '-B', source / 'tools/build_musl_probe.py', '--arch', arch,
                 '--musl-build', musl_build, '--toolchain', toolchain,
                 '--source', source / 'tests/musl/journalled_root.c',
                 '--linker-script', source / 'tests/musl/bootstrap.ld', '--out', musl], arch + '-musl-build')
            image = output / (arch + '-image')
            run([sys.executable, '-B', source / 'tools/jbd2/journalled_root_image.py',
                 '--base', base, '--base-result-sha256', args.base_result_sha256,
                 '--init', musl / 'bootstrap.elf', '--init-sha256', sha(musl / 'bootstrap.elf'),
                 '--output', image], arch + '-image-build')
            built = output / (arch + '-build')
            run([sys.executable, '-B', source / 'tools/test_journalled_root.py',
                 '--arch', arch, '--mode', 'debug', '--uid', '1000',
                 '--kernel-sdk', sdk, '--sdk-manifest-sha256', matches[0]['manifest_sha256'],
                 '--toolchain', toolchain, '--musl-probe', musl,
                 '--musl-manifest-sha256', sha(musl / 'manifest.json'),
                 '--fixture', image, '--fixture-facts-sha256', sha(image / 'facts.json'),
                 '--fixture-disk-sha256', sha(image / 'guarded.img'),
                 '--fixture-result-sha256', sha(image / 'result.json'),
                 '--output', built], arch + '-sdk-build')
            campaign = output / (arch + '-campaign')
            run([sys.executable, '-B', source / 'tools/run_journalled_root.py',
                 '--build', built, '--build-result-sha256', sha(built / 'result.json'),
                 '--output', campaign], arch + '-guest-campaign')
            result = json.loads((campaign / 'result.json').read_text())
            if result.get('status') != 'passed' or len(result.get('boots', [])) != 2:
                raise ValueError('root guest campaign did not pass both boots: ' + arch)
            row.update(status='passed', musl_manifest_sha256=sha(musl / 'manifest.json'),
                       user_elf_sha256=sha(musl / 'bootstrap.elf'),
                       image_result_sha256=sha(image / 'result.json'),
                       build_result_sha256=sha(built / 'result.json'),
                       campaign_result_sha256=sha(campaign / 'result.json'),
                       final_disk_sha256=result['final_disk_sha256'])
            save()
        report['status'] = 'passed'
    except BaseException as exc:
        report.update(status='failed', error=repr(exc))
        save()
        raise
    save()
    print('PASS SDK34 journalled-root representatives:', ', '.join(args.arches))


if __name__ == '__main__':
    main()

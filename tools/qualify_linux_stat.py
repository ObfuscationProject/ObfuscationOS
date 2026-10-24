#!/usr/bin/env python3
"""Qualify six stat policy/epoch guests against one exact SDK export."""
from pathlib import Path
import argparse
import json
import subprocess
import sys

sys.dont_write_bytecode = True
from test_linux_stat_user import ARCH_TRIPLES, EPOCHS, POLICIES, ROOT, inventory, sha


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=tuple(ARCH_TRIPLES), required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    parser.add_argument('--kernel-sdk', type=Path, required=True)
    parser.add_argument('--sdk-manifest-sha256', required=True)
    parser.add_argument('--rootfs', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--musl-build', type=Path, required=True)
    parser.add_argument('--ppc-clang', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record = dict(status='running', architecture=args.arch, mode=args.mode,
                  sdk_manifest_sha256=args.sdk_manifest_sha256, commands=[], rows=[],
                  guest_parallelism=1, scope='Actual native/musl stat subset; Linux reference, physical and SMP evidence are separate')

    def save():
        (out / 'result.json').write_text(json.dumps(record, indent=2) + '\n')

    def run(argv, label):
        if sha(args.kernel_sdk / 'manifest.json') != args.sdk_manifest_sha256:
            raise ValueError('SDK changed during stat qualification')
        argv = list(map(str, argv))
        log = out / (label + '.log')
        with log.open('x') as stream:
            completed = subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        record['commands'].append(dict(label=label, argv=argv, returncode=completed.returncode, log_sha256=sha(log)))
        save()
        if completed.returncode:
            raise RuntimeError(label + ' failed; see ' + str(log))

    save()
    try:
        source = out / 'source-inventory.json'
        run([sys.executable, ROOT / 'tools/freeze_linux_stat_sources.py', '--output', source], 'freeze-sources')
        digest = sha(source)
        record['source_inventory_sha256'] = digest
        common = ['--arch', args.arch, '--toolchain', args.toolchain.resolve(),
                  '--source-inventory', source, '--source-inventory-sha256', digest]
        for kind in ('maintained', 'controls'):
            run([sys.executable, ROOT / 'tools/build_linux_stat_musl.py', *common, '--kind', kind,
                 '--musl-build', args.musl_build.resolve(), '--output', out / ('musl-' + kind),
                 *(['--ppc-clang', args.ppc_clang.resolve()] if args.ppc_clang else [])], 'musl-' + kind)
        for policy in POLICIES:
            for epoch in EPOCHS:
                label = policy + '-' + epoch
                native = out / label / 'native'
                guest = out / label / 'guest'
                musl = out / ('musl-maintained' if policy == 'maintained' else 'musl-controls')
                parameters = [*common, '--mode', args.mode, '--policy', policy, '--epoch', epoch,
                              '--kernel-sdk', args.kernel_sdk.resolve(), '--sdk-manifest-sha256', args.sdk_manifest_sha256]
                run([sys.executable, ROOT / 'tools/build_linux_stat_runner.py', *parameters,
                     '--output', native], label + '-native')
                run([sys.executable, ROOT / 'tools/test_linux_stat_user.py', *parameters,
                     '--rootfs', args.rootfs.resolve(), '--native-runner', native / 'native-runner.elf',
                     '--native-identity', native / 'identity.json', '--musl-probe', musl,
                     '--musl-dependencies', musl / 'dependencies.json', '--output', guest, '--execute'], label + '-guest')
                result = json.loads((guest / 'result.json').read_text())
                if (result['status'] != 'passed' or result['policy'] != policy or result['epoch'] != epoch or
                        result['sdk_manifest_sha256'] != args.sdk_manifest_sha256 or
                        not result['native_execution'] or not result['musl_execution']):
                    raise ValueError('guest did not pass the explicit execution contract')
                record['rows'].append(dict(policy=policy, epoch=epoch, result=str((guest / 'result.json').relative_to(out)),
                                           result_sha256=sha(guest / 'result.json')))
                inventory(source)
                save()
        if len(record['rows']) != 6:
            raise ValueError('incomplete policy/epoch matrix')
        record['status'] = 'passed'
    except BaseException as error:
        record.update(status='failed', error=str(error))
        save()
        raise
    save()
    print('PASS', args.arch, args.mode, 'six actual stat policy/epoch guests')


if __name__ == '__main__':
    main()

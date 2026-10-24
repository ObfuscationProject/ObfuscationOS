#!/usr/bin/env python3
"""Build a static musl fixture and bind every local source/header dependency."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT
sys.path.insert(0, str(ROOT / 'tools'))
from test_linux_stat_user import ARCH_TRIPLES, inventory, sha

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=tuple(ARCH_TRIPLES), required=True)
    parser.add_argument('--kind', choices=('maintained', 'controls'), required=True)
    parser.add_argument('--musl-build', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--ppc-clang', type=Path)
    parser.add_argument('--source-inventory', type=Path, required=True)
    parser.add_argument('--source-inventory-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if sha(args.source_inventory) != args.source_inventory_sha256:
        raise ValueError('source inventory hash mismatch')
    source_inventory = inventory(args.source_inventory)
    source_name = 'tests/musl/linux_stat.c' if args.kind == 'maintained' else 'tests/musl/linux_stat_controls.c'
    source = ROOT / source_name
    out = args.output.resolve()
    if out.exists():
        raise ValueError('fresh output directory required')
    inputs = {'musl-source.c': source, 'stat_fixture.h': ROOT / 'tests/stat_fixture.h',
              'stat_probe_log.h': ROOT / 'tests/stat_probe_log.h'}
    before = {name: sha(path) for name, path in inputs.items()}
    tools = [BASE / 'tools' / p for p in ('build_musl_probe.py', 'musl_source.py', 'kernel_sdk.py', 'plan_ledger.py')]
    tools += [BASE / 'docs/plans/contracts/ledger.json', BASE / 'tests/musl/bootstrap.ld']
    tool_hashes = {str(path): sha(path) for path in tools}
    argv = [sys.executable, str(BASE / 'tools/build_musl_probe.py'), '--arch', args.arch,
            '--musl-build', str(args.musl_build.resolve()), '--toolchain', str(args.toolchain.resolve()),
            '--source', str(source), '--out', str(out), '--linker-script', str(BASE / 'tests/musl/bootstrap.ld')]
    if args.ppc_clang:
        argv += ['--ppc-clang', str(args.ppc_clang.resolve())]
    subprocess.run(argv, cwd=BASE, check=True)
    manifest = json.loads((out / 'manifest.json').read_text())
    if (manifest['status'] != 'built-not-executed' or manifest['executed'] is not False or
            manifest['probe_sha256'] != before['musl-source.c'] or
            any(sha(inputs[name]) != expected for name, expected in before.items()) or
            any(sha(Path(name)) != expected for name, expected in tool_hashes.items())):
        raise ValueError('build source/tool identity drift')
    inventory(args.source_inventory)
    shutil.copy2(args.source_inventory, out / 'source-inventory.json')
    dependencies = dict(status='built-not-executed', architecture=args.arch, mode=manifest['mode'],
                        kind=args.kind, musl_manifest_sha256=sha(out / 'manifest.json'),
                        elf_sha256=manifest['elf_sha256'], source_rechecked_after_build=True,
                        source_snapshot_sha256=args.source_inventory_sha256, files=before,
                        tool_sha256=tool_hashes, command=argv, executed=False)
    (out / 'dependencies.json').write_text(json.dumps(dependencies, indent=2) + '\n')
    print(out / 'dependencies.json')

if __name__ == '__main__':
    main()

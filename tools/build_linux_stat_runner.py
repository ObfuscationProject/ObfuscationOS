#!/usr/bin/env python3
"""Build a private native stat runner against an exact exported SDK31."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from test_linux_stat_user import ARCH_TRIPLES, POLICIES, EPOCHS, inventory, sha, executable_identity
from kernel_sdk import validate_sdk

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=tuple(ARCH_TRIPLES), required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    parser.add_argument('--policy', choices=tuple(POLICIES), required=True)
    parser.add_argument('--epoch', choices=tuple(EPOCHS), required=True)
    parser.add_argument('--kernel-sdk', type=Path, required=True)
    parser.add_argument('--sdk-manifest-sha256', required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--source-inventory', type=Path, required=True)
    parser.add_argument('--source-inventory-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    identity = dict(status='building', architecture=args.arch, mode=args.mode, policy=args.policy,
                    epoch=args.epoch, sdk_manifest_sha256=args.sdk_manifest_sha256,
                    source_snapshot_sha256=args.source_inventory_sha256, executed=False,
                    kernel_source_compiled=False, commands=[])
    def save():
        (out / 'identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    def run(argv, label, cwd):
        argv = list(map(str, argv))
        env = dict(os.environ, XMAKE_ROOT='y')
        for name in ('CPATH', 'CPLUS_INCLUDE_PATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH', 'GCC_EXEC_PREFIX', 'COMPILER_PATH'):
            env.pop(name, None)
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        log = out / (label + '.log')
        log.write_bytes(result.stdout)
        identity['commands'].append(dict(argv=argv, returncode=result.returncode, log_sha256=sha(log)))
        save()
        if result.returncode:
            raise ValueError(label + ' failed')
        return result.stdout
    save()
    try:
        if sha(args.source_inventory) != args.source_inventory_sha256:
            raise ValueError('source inventory hash mismatch')
        source_inventory = inventory(args.source_inventory)
        sdk = args.kernel_sdk.resolve()
        if sha(sdk / 'manifest.json') != args.sdk_manifest_sha256:
            raise ValueError('SDK manifest hash mismatch')
        triple = ARCH_TRIPLES[args.arch]
        cxx = args.toolchain.resolve() / 'bin' / (triple + '-g++')
        manifest = validate_sdk(sdk, args.arch, args.mode, cxx)
        if manifest['abi_version'] != 31:
            raise ValueError('native runner requires SDK31')
        selected = [name for name in source_inventory['files'] if
                    name.startswith(('sdk/include/', 'lib/okcrt/')) or name in
                    ('xmake/linux_stat_runner.lua', 'xmake/arch.lua', 'tools/kernel_sdk.py', 'tests/stat_fixture.h',
                     'tests/native/linux_stat_runner.c', 'tests/native/linux_stat_controls_runner.c')]
        required = ('xmake/linux_stat_runner.lua', 'xmake/arch.lua', 'tools/kernel_sdk.py', 'sdk/include/unistd.h',
                    'lib/okcrt/src/syscalls.c', 'lib/okcrt/arch/' + args.arch + '/crt0.S',
                    'lib/okcrt/arch/' + args.arch + '/syscall.S')
        if not all(name in selected for name in required):
            raise ValueError('source inventory omits native build inputs')
        project = out / 'project'
        project.mkdir()
        for name in selected:
            source = ROOT / name
            if sha(source) != source_inventory['files'][name]:
                raise ValueError('native source pin changed: ' + name)
            target = project / ('xmake.lua' if name == 'xmake/linux_stat_runner.lua' else name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        identity['source_sha256'] = {name: source_inventory['files'][name] for name in selected}
        xmake = Path(shutil.which('xmake') or '')
        if not xmake.is_file():
            raise ValueError('xmake unavailable')
        run([xmake, 'f', '-P', project, '-c', '-y', '--ccache=n', '-a', args.arch, '-m', args.mode,
             '--systoolchain_dir=' + str(args.toolchain.resolve()), '--kernel_sdk=' + str(sdk),
             '--stat_policy=' + args.policy, '--stat_epoch=' + args.epoch], 'configure', project)
        run([xmake, 'build', '-P', project, '-j2', '-v', 'app-linux-stat-runner'], 'build', project)
        binary = project / 'build' / args.arch / args.mode / 'apps/linux-stat-runner.elf'
        identity['elf'] = executable_identity(binary, args.arch, False)
        nm = args.toolchain.resolve() / 'bin' / (triple + '-nm')
        if run([nm, '-u', binary], 'undefined-symbols', project).strip():
            raise ValueError('native runner has unresolved symbols')
        shutil.copy2(binary, out / 'native-runner.elf')
        source = ROOT / ('tests/native/linux_stat_runner.c' if args.policy == 'maintained' else
                         'tests/native/linux_stat_controls_runner.c')
        identity['files'] = {'native-source.c': sha(source), 'stat_fixture.h': sha(ROOT / 'tests/stat_fixture.h'),
                             'native-runner.elf': sha(out / 'native-runner.elf')}
        identity['tool_sha256'] = {str(p): sha(p) for p in (cxx, nm, xmake.resolve())}
        validate_sdk(sdk, args.arch, args.mode, cxx)
        if sha(sdk / 'manifest.json') != args.sdk_manifest_sha256:
            raise ValueError('SDK changed during native build')
        for name in selected:
            if sha(ROOT / name) != source_inventory['files'][name] or sha(project / ('xmake.lua' if name == 'xmake/linux_stat_runner.lua' else name)) != source_inventory['files'][name]:
                raise ValueError('native source changed during build')
        identity['status'] = 'built-not-executed'
        save()
        print(out / 'native-runner.elf')
    except BaseException as error:
        identity.update(status='failed', error=str(error))
        save()
        raise

if __name__ == '__main__':
    main()

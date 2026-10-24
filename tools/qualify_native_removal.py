#!/usr/bin/env python3
"""Execute a pinned static-musl removal probe through a fresh SDK45-only consumer."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from qemu_distro import command_for
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from build_musl_probe import admit_musl_build
from object_pressure_evidence import admit_sources, relative_file, require_hash, sha, source_files
from native_removal_evidence import failure_line, validate

SCOPE = 'native-removal-os-sources'


def save(path, record):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def run(args):
    out = args.output.resolve()
    if out == ROOT or out.is_relative_to(ROOT) or ROOT.is_relative_to(out):
        raise ValueError('output must be outside the OS source tree')
    out.mkdir(parents=True, exist_ok=False)
    record = dict(schema=1, status='preparing', sdk_abi=None, architecture=args.arch,
        mode=args.mode, sdk_only=True, kernel_source_compiled=False,
        stdin_commands=['/bin/removal-probe\n', '/bin/removal-probe\n', 'hello | cat\n'],
        physical=False, smp=False, shutdown=False, executed=False, commands=[], inputs={})
    consumer, sdk, musl = out / 'ObfuscationOS', out / 'sdk', out / 'musl-build'
    process, disk, serial, boundaries = None, None, bytearray(), None
    env = os.environ.copy()
    for name in ('CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH',
                 'GCC_EXEC_PREFIX', 'COMPILER_PATH'):
        env.pop(name, None)
    env.update(PYTHONDONTWRITEBYTECODE='1', XMAKE_ROOT='y', XMAKE_GLOBALDIR=str(out / 'xmake-global'))

    def pin(path, expected=None):
        path = Path(path).resolve()
        if expected is not None:
            require_hash(path, expected, str(path))
        digest = sha(path)
        if str(path) in record['inputs'] and record['inputs'][str(path)] != digest:
            raise ValueError('input changed: ' + str(path))
        record['inputs'][str(path)] = digest
        return digest

    def copy(source, target, files):
        target.mkdir(parents=True, exist_ok=False)
        for name, expected in files.items():
            original = relative_file(source, name)
            pin(original, expected)
            retained = target / name
            retained.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, retained)
            pin(retained, expected)

    def call(label, argv):
        command = dict(label=label, argv=list(map(str, argv)), status='running')
        record['commands'].append(command)
        save(out / 'result.json', record)
        log = out / (label + '.log')
        with log.open('xb') as stream:
            done = subprocess.run(command['argv'], cwd=consumer, env=env,
                                  stdout=stream, stderr=subprocess.STDOUT)
        command.update(returncode=done.returncode, log_sha256=sha(log),
                       status='passed' if not done.returncode else 'failed')
        save(out / 'result.json', record)
        if done.returncode:
            raise RuntimeError(label + ' failed')

    try:
        sources = admit_sources(ROOT, args.source_inventory, args.source_inventory_sha256, scope=SCOPE)
        pin(args.source_inventory, args.source_inventory_sha256)
        copy(ROOT, consumer, sources['files'])
        toolchain = args.toolchain.resolve()
        triple = ARCH_TRIPLES[args.arch]
        compiler = toolchain / 'bin' / (triple + '-g++')
        pin(compiler, args.compiler_sha256)
        original_sdk = args.kernel_sdk.resolve()
        pin(original_sdk / 'manifest.json', args.sdk_manifest_sha256)
        manifest = json.loads((original_sdk / 'manifest.json').read_text())
        for name in manifest['files']:
            relative_file(original_sdk, name)
        validate_sdk(original_sdk, args.arch, args.mode, compiler)
        if manifest['abi_version'] != 52 or manifest['compiler'].get('family') != 'gcc':
            raise ValueError('removal qualification requires SDK53 GCC ABI52')
        record['sdk_abi'] = manifest['abi_version']
        copy(original_sdk, sdk, {**manifest['files'], 'manifest.json': args.sdk_manifest_sha256})
        validate_sdk(sdk, args.arch, args.mode, compiler)
        original_musl = args.musl_build.resolve()
        pin(original_musl / 'manifest.json', args.musl_manifest_sha256)
        musl_manifest = admit_musl_build(original_musl, args.arch)
        if (musl_manifest['mode'] != args.mode or musl_manifest['compiler']['triple'] != triple or
                musl_manifest['compiler']['version'] != manifest['compiler']['version']):
            raise ValueError('musl/SDK mode or compiler ABI differs')
        copy(original_musl, musl, {**{n: v for n, v in musl_manifest['files'].items()
             if n.startswith('sysroot/')}, 'manifest.json': args.musl_manifest_sha256})
        for name in ('gcc', 'g++', 'as', 'ld', 'ar', 'ranlib', 'readelf', 'objcopy'):
            pin(toolchain / 'bin' / (triple + '-' + name), musl_manifest['tool_sha256'].get(name))
        c_compiler = toolchain / 'bin' / (triple + '-gcc')
        for driver, name in ((c_compiler, 'cc1'), (compiler, 'cc1plus'), (c_compiler, 'collect2')):
            pin(Path(subprocess.check_output([str(driver), '-print-prog-name=' + name], env=env, text=True).strip()))
        from musl_source import FLAGS
        runtime = Path(subprocess.check_output([str(c_compiler), *FLAGS[args.arch],
                       '-print-libgcc-file-name'], env=env, text=True).strip())
        pin(runtime, musl_manifest['compiler_runtime']['sha256'])
        programs = {name: Path(shutil.which(name)).resolve() for name in ('xmake', 'e2fsck', 'mke2fs')}
        for path in programs.values():
            pin(path)
        pin(Path(sys.executable))
        pin(args.qemu, args.qemu_sha256)
        if bool(args.softfp_build) != bool(args.softfp_manifest_sha256):
            raise ValueError('binary128 supplement and hash must be paired')
        if (args.arch == 'mips64') != bool(args.softfp_build):
            raise ValueError('native MIPS64 probe requires explicit binary128 supplement')
        supplement = []
        if args.softfp_build:
            from mips64_softfp import admit
            original = args.softfp_build.resolve()
            pin(original / 'manifest.json', args.softfp_manifest_sha256)
            _, softfp = admit(original, args.softfp_manifest_sha256, args.arch, args.mode, c_compiler)
            retained = out / 'softfp-build'
            copy(original, retained, {**softfp['files'], 'manifest.json': args.softfp_manifest_sha256})
            supplement = ['--softfp-build', retained, '--softfp-manifest-sha256', args.softfp_manifest_sha256]
        if args.ppc_clang:
            pin(args.ppc_clang)
            supplement += ['--ppc-clang', args.ppc_clang.resolve()]
        probe = out / 'probe'
        call('probe-build', [sys.executable, '-B', consumer / 'tools/build_musl_probe.py',
             '--arch', args.arch, '--musl-build', musl, '--toolchain', toolchain,
             '--source', consumer / 'tests/musl/native_removal.c',
             '--linker-script', consumer / 'tests/musl/bootstrap.ld', '--out', probe, *supplement])
        probe_manifest = json.loads((probe / 'manifest.json').read_text())
        if (probe_manifest['status'] != 'built-not-executed' or probe_manifest['executed'] is not False or
                probe_manifest['source_manifest_sha256'] != args.musl_manifest_sha256 or
                probe_manifest['probe_sha256'] != sha(consumer / 'tests/musl/native_removal.c')):
            raise ValueError('probe is not bound to the requested inputs')
        pin(probe / 'bootstrap.elf', probe_manifest['elf_sha256'])
        pin(probe / 'manifest.json')
        call('os-configure', [programs['xmake'], 'f', '-P', consumer, '-c', '-y', '-a', args.arch,
             '-m', args.mode, '--systoolchain_dir=' + str(toolchain), '--kernel_sdk=' + str(sdk), '--ccache=n'])
        for target in ('distro_image', 'rootfs-stage'):
            call('os-' + target, [programs['xmake'], 'build', '-P', consumer, '-j2', target])
        build = consumer / 'build' / args.arch / args.mode
        image = out / 'kernel-input.bin'
        shutil.copy2(build / 'distro/kernel.bin', image)
        pin(image)
        pin(build / 'distro/kernel.elf')
        root = out / 'root'
        shutil.copytree(build / 'rootfs', root, symlinks=True)
        shutil.copy2(probe / 'bootstrap.elf', root / 'bin/removal-probe')
        (root / 'bin/removal-probe').chmod(0o755)
        record['rootfs_files'] = {str(p.relative_to(root)): {'symlink': os.readlink(p)} if p.is_symlink()
                                  else {'sha256': sha(p)} for p in sorted(root.rglob('*')) if p.is_file() or p.is_symlink()}
        disk = out / 'rootfs.ext4.img'
        call('package', [sys.executable, '-B', consumer / 'tools/mkext4.py', '--root', root, '--out', disk])
        call('initial-fsck', [programs['e2fsck'], '-fn', disk])
        initial = out / 'rootfs-input.ext4.img'
        shutil.copy2(disk, initial)
        pin(initial)
        for name, digest in record['inputs'].items():
            require_hash(Path(name), digest, 'pre-execution input')
        argv = list(map(str, command_for(args.qemu.resolve(), args.arch, image, disk, 'none')))
        if args.arch == 'ppc':
            if '-cpu' in argv or '-smp' in argv or '-accel' in argv:
                raise ValueError('PPC base recipe already contains private CPU controls')
            argv += ['-cpu', 'e500v2_v22', '-smp', '1', '-accel', 'tcg,thread=single']
        record.update(status='running-guest', qemu_command=argv)
        save(out / 'result.json', record)
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def receive(after):
            deadline = time.monotonic() + args.timeout
            while len(serial) <= after or not serial.endswith(b'oksh> '):
                if time.monotonic() > deadline:
                    raise RuntimeError('guest timeout')
                if not select.select([process.stdout], [], [], .1)[0]:
                    continue
                data = os.read(process.stdout.fileno(), 65536)
                if not data:
                    raise RuntimeError('guest exited before prompt')
                serial.extend(data)
                if len(serial) > 16 * 1024 * 1024:
                    raise RuntimeError('serial evidence budget exceeded')
                if error := failure_line(serial):
                    raise RuntimeError(error)

        receive(0)
        positions = [len(serial)]
        for _ in range(2):
            process.stdin.write(b'/bin/removal-probe\n')
            process.stdin.flush()
            receive(positions[-1])
            positions.append(len(serial))
        boundaries = tuple(positions)
        process.stdin.write(b'hello | cat\n')
        process.stdin.flush()
        receive(positions[-1])
        if b'hello from ObfuscationOS userland\n' not in bytes(serial[positions[-1]:]).replace(b'\r\n', b'\n'):
            raise RuntimeError('native pipeline failed after Linux removal')
        record.update(status='guest-passed-awaiting-offline', executed=True, command_boundaries=positions)
    except BaseException as error:
        record.update(status='failed', error=repr(error))
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            serial.extend(process.stdout.read())
            process.stdout.close()
            process.stdin.close()
            record['qemu_returncode'] = process.returncode
        (out / 'serial.log').write_bytes(serial)
        record['serial_sha256'] = sha(out / 'serial.log')
        if disk is not None and disk.is_file():
            record['final_disk_sha256'] = sha(disk)
            try:
                call('final-fsck', [programs['e2fsck'], '-fn', disk])
            except BaseException as error:
                record.update(status='failed', offline_error=repr(error))
        save(out / 'result.json', record)
    if record['status'] != 'failed':
        try:
            record['execution'] = validate(bytes(serial), boundaries, args.arch)
            for name, digest in record['inputs'].items():
                require_hash(Path(name), digest, 'final input')
            admit_sources(ROOT, args.source_inventory, args.source_inventory_sha256, scope=SCOPE)
            record.update(status='passed', inputs_rechecked=True)
            record['outputs'] = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*'))
                if p.is_file() and not p.is_symlink() and p != out / 'result.json'}
        except BaseException as error:
            record.update(status='failed', error=repr(error))
        save(out / 'result.json', record)
    if record['status'] != 'passed':
        raise RuntimeError('removal qualification failed; see retained result.json')
    print('PASS', args.arch, args.mode, 'two actual static-musl removal runs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    freeze = commands.add_parser('freeze')
    freeze.add_argument('--output', type=Path, required=True)
    execute = commands.add_parser('run')
    execute.add_argument('--arch', choices=tuple(ARCH_TRIPLES), required=True)
    execute.add_argument('--mode', choices=('debug', 'release'), required=True)
    for name in ('kernel-sdk', 'toolchain', 'qemu', 'musl-build', 'source-inventory', 'output'):
        execute.add_argument('--' + name, type=Path, required=True)
    for name in ('sdk-manifest-sha256', 'compiler-sha256', 'qemu-sha256',
                 'musl-manifest-sha256', 'source-inventory-sha256'):
        execute.add_argument('--' + name, required=True)
    execute.add_argument('--softfp-build', type=Path)
    execute.add_argument('--softfp-manifest-sha256')
    execute.add_argument('--ppc-clang', type=Path)
    execute.add_argument('--timeout', type=float, default=120)
    args = parser.parse_args()
    if not sys.dont_write_bytecode or os.environ.get('PYTHONDONTWRITEBYTECODE') != '1':
        raise ValueError('run Python with -B and PYTHONDONTWRITEBYTECODE=1')
    if args.command == 'freeze':
        with args.output.open('x') as stream:
            json.dump(dict(schema=1, scope=SCOPE, files=source_files(ROOT)), stream, indent=2, sort_keys=True)
            stream.write('\n')
        print(sha(args.output))
    else:
        if not 0 < args.timeout <= 600:
            raise ValueError('timeout outside (0, 600]')
        run(args)


if __name__ == '__main__':
    main()

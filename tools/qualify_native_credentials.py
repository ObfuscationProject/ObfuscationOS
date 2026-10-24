#!/usr/bin/env python3
"""Build a fresh SDK-only OS consumer and run an explicitly pinned native saved-ID credential guest.

The freeze command records the complete OS source input. The run command never
opens a Kernel checkout or compiles Kernel source. Every output directory is new;
failures retain the same source, SDK, disk, serial and command evidence as passes.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import select
import shlex
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from qemu_distro import command_for
from build_musl_probe import admit_musl_build
from kernel_sdk import ARCH_TRIPLES
from musl_source import FLAGS, inspect_elf, ppc_frontend
from mips64_softfp import admit as admit_softfp
from object_pressure_evidence import (admit_sources,
    relative_file, require_hash, sha, source_files)
from native_credentials_evidence import failure_line, admit_sdk, validate_execution, probe_spec, incomplete_failure_line


def save_json(path, record):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def copy_inventory(source, destination, files):
    destination.mkdir(parents=True, exist_ok=False)
    for name, expected in files.items():
        original = relative_file(source, name)
        require_hash(original, expected, name)
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
        require_hash(target, expected, 'retained ' + name)


def dependencies(command, output, allowed_roots):
    """Consume compiler-emitted make dependencies, including transitive headers."""
    text = output.decode().replace('\\\n', '')
    if not text.startswith('object-pressure:'):
        raise ValueError('compiler dependency output has unexpected target')
    files = {}
    for name in shlex.split(text.split(':', 1)[1]):
        path = Path(name).resolve()
        if not path.is_file() or not any(path.is_relative_to(root) for root in allowed_roots):
            raise ValueError('probe dependency outside explicit retained roots: ' + name)
        files[str(path)] = sha(path)
    if not files:
        raise ValueError('empty probe source dependencies')
    return dict(command=command, files=files)


def validate_runtime_options(arch, build, digest):
    if bool(build) != bool(digest):
        raise ValueError('binary128 build and manifest hash must be supplied together')
    if arch == 'mips64' and not build:
        raise ValueError('private n64 probes require the explicit pinned binary128 runtime')
    if arch != 'mips64' and build:
        raise ValueError('binary128 supplement is limited to the native n64 profile')


def delivery_qemu_command(qemu, arch, image, disk):
    """Keep prior recipes exact; explicitly pin the private PPC serialized CPU."""
    command = list(map(str, command_for(qemu, arch, image, disk, 'none')))
    if arch == 'ppc':
        expected = [str(qemu), '-M', 'ppce500', '-m', '256M', '-kernel', str(image),
                    '-serial', 'stdio', '-monitor', 'none', '-no-reboot', '-display', 'none',
                    '-drive', f'file={disk},format=raw,if=none,id=fsdisk',
                    '-device', 'virtio-blk-pci,drive=fsdisk',
                    '-object', 'rng-random,id=entropy0,filename=/dev/urandom',
                    '-device', 'virtio-rng-pci-non-transitional,rng=entropy0']
        if command != expected:
            raise ValueError('private PPC32 distribution QEMU recipe differs from the admitted ppce500 profile')
        command += ['-cpu', 'e500v2_v22', '-smp', '1', '-accel', 'tcg,thread=single']
    return command


def probe_layout(arch, kind):
    """Select one exact credential source for all admitted native profiles."""
    _, _, command, _ = probe_spec(arch, kind)
    return 'native_credentials', command.decode().removeprefix('/bin/'), command.decode()


def run(args):
    if args.arch not in ('i386', 'x86_64', 'aarch64', 'arm32', 'rv32', 'rv64', 'loongarch64', 'mips', 'mips64', 'ppc') or args.mode != 'debug':
        raise ValueError('credential fixture requires i386/x86_64/AArch64/ARM32/RV32/RV64/LoongArch64/MIPS o32/MIPS64 n64/PPC32 e500v2 Debug')
    probe_spec(args.arch, args.probe)
    validate_runtime_options(args.arch, args.softfp_build, args.softfp_manifest_sha256)
    probe_name, command_name, command_line = probe_layout(args.arch, args.probe)
    out = args.output.resolve()
    if out == ROOT or ROOT.is_relative_to(out) or out.is_relative_to(ROOT):
        raise ValueError('qualification output must be outside the mutable OS source tree')
    out.mkdir(parents=True, exist_ok=False)
    record = dict(schema=1, status='preparing', architecture=args.arch, mode=args.mode,
                  sdk_abi=31, probe_kind=args.probe, sdk_only=True, kernel_source_compiled=False, cpus=1,
                  physical=False, smp=False, executed=False, commands=[], inputs={},
                  scope='SDK31 native saved UID/GID transitions, fork, exec, effective file permissions and explicit single-live-thread setter gate. No Linux per-thread credentials, libc setxid synchronization, supplementary groups, capabilities, set-ID exec elevation, SMP or physical claim')
    if args.arch == 'ppc':
        record.update(cpu_profile='e500v2_v22', serialized_cpu=0,
                      private_profile='ppc32-be-e500v2-scalar-credentials')
    process = None
    serial = bytearray()
    disk = None
    consumer = out / 'ObfuscationOS'
    retained_sdk = out / 'sdk'
    retained_musl = out / 'musl-build'
    source_root = ROOT
    env = os.environ.copy()
    for name in ('CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH', 'GCC_EXEC_PREFIX', 'COMPILER_PATH'):
        env.pop(name, None)
    env.update(XMAKE_ROOT='y', XMAKE_GLOBALDIR=str(out / 'xmake-global'), PYTHONDONTWRITEBYTECODE='1')

    def save():
        save_json(out / 'result.json', record)

    def pin(path, expected=None):
        path = path.resolve()
        digest = sha(path)
        if expected is not None:
            require_hash(path, expected, str(path))
        if str(path) in record['inputs'] and record['inputs'][str(path)] != digest:
            raise ValueError('input changed before second use: ' + str(path))
        record['inputs'][str(path)] = digest
        return digest

    def call(label, argv, capture=False):
        argv = list(map(str, argv))
        entry = dict(label=label, argv=argv, status='running')
        record['commands'].append(entry)
        record['status'] = 'running-' + label
        save()
        start = time.monotonic()
        with (out / (label + '.log')).open('xb') as stream:
            done = subprocess.run(argv, cwd=consumer, env=env,
                                  stdout=subprocess.PIPE if capture else stream,
                                  stderr=stream if capture else subprocess.STDOUT)
        if capture:
            (out / (label + '.stdout')).write_bytes(done.stdout)
            entry['stdout_sha256'] = sha(out / (label + '.stdout'))
        entry.update(status='passed' if done.returncode == 0 else 'failed',
                     returncode=done.returncode, seconds=time.monotonic() - start,
                     log_sha256=sha(out / (label + '.log')))
        save()
        if done.returncode:
            raise RuntimeError(label + ' failed; see retained log')
        return done.stdout if capture else None

    save()
    try:
        sources = admit_sources(source_root, args.source_inventory, args.source_inventory_sha256)
        pin(args.source_inventory, args.source_inventory_sha256)
        copy_inventory(source_root, consumer, sources['files'])
        shutil.copy2(args.source_inventory, out / 'source-inventory.json')
        pin(out / 'source-inventory.json', args.source_inventory_sha256)
        for name, expected in sources['files'].items():
            pin(source_root / name, expected)
            pin(consumer / name, expected)
        toolchain = args.toolchain.resolve()
        triple = ARCH_TRIPLES[args.arch]
        compiler = toolchain / 'bin' / (triple + '-g++')
        c_compiler = toolchain / 'bin' / (triple + '-gcc')
        sdk = args.kernel_sdk.resolve()
        manifest = admit_sdk(sdk, args.sdk_manifest_sha256, args.arch, args.mode, compiler, args.compiler_sha256)
        sdk_files = {**manifest['files'], 'manifest.json': args.sdk_manifest_sha256}
        copy_inventory(sdk, retained_sdk, sdk_files)
        for name, expected in sdk_files.items():
            pin(sdk / name, expected)
            pin(retained_sdk / name, expected)
        admit_sdk(retained_sdk, args.sdk_manifest_sha256, args.arch, args.mode, compiler, args.compiler_sha256)
        record['sdk_manifest_sha256'] = args.sdk_manifest_sha256
        record['compiler_sha256'] = pin(compiler, args.compiler_sha256)
        record['qemu_sha256'] = pin(args.qemu, args.qemu_sha256)
        qemu = args.qemu.resolve()
        for name in ('gcc', 'g++', 'as', 'ld', 'ar', 'ranlib', 'readelf', 'objcopy'):
            pin(toolchain / 'bin' / (triple + '-' + name))
        programs = {}
        for name in ('xmake', 'python3', 'mke2fs', 'e2fsck'):
            path = shutil.which(name)
            if path is None:
                raise ValueError('required tool missing: ' + name)
            programs[name] = Path(path).resolve()
            pin(programs[name])
        pin(Path(sys.executable))
        musl = args.musl_build.resolve()
        pin(musl / 'manifest.json', args.musl_manifest_sha256)
        musl_manifest = admit_musl_build(musl, args.arch)
        if musl_manifest['mode'] != args.mode:
            raise ValueError('musl source mode differs from explicit SDK/OS mode')
        if (musl_manifest.get('compiler', {}).get('triple') != triple or
                musl_manifest.get('compiler', {}).get('version') != manifest['compiler']['version']):
            raise ValueError('musl and SDK compiler ABI differ')
        for name, expected in musl_manifest['tool_sha256'].items():
            pin(toolchain / 'bin' / (triple + '-' + name), expected)
        musl_files = {name: value for name, value in musl_manifest['files'].items() if name.startswith('sysroot/')}
        musl_files['manifest.json'] = args.musl_manifest_sha256
        copy_inventory(musl, retained_musl, musl_files)
        for name, expected in musl_files.items():
            pin(musl / name, expected)
            pin(retained_musl / name, expected)
        frontend = ppc_frontend(args.arch, args.ppc_clang, required=True)
        if frontend:
            pin(Path(frontend['path']), frontend['sha256'])
        runtime = subprocess.check_output([str(c_compiler), *FLAGS[args.arch], '-print-libgcc-file-name'], env=env, text=True).strip()
        pin(Path(runtime), musl_manifest['compiler_runtime']['sha256'])
        for driver, frontend_name in ((c_compiler, 'cc1'), (compiler, 'cc1plus'), (c_compiler, 'collect2')):
            internal = subprocess.check_output([str(driver), '-print-prog-name=' + frontend_name], env=env, text=True).strip()
            pin(Path(internal))

        supplement_args = []
        if args.softfp_build:
            runtime_root = args.softfp_build.resolve()
            pin(runtime_root / 'manifest.json', args.softfp_manifest_sha256)
            _, runtime_record = admit_softfp(runtime_root, args.softfp_manifest_sha256,
                                              args.arch, args.mode, c_compiler)
            retained_runtime = out / 'softfp-build'
            runtime_files = {**runtime_record['files'], 'manifest.json': args.softfp_manifest_sha256}
            copy_inventory(runtime_root, retained_runtime, runtime_files)
            for name, expected in runtime_files.items():
                pin(runtime_root / name, expected)
                pin(retained_runtime / name, expected)
            admit_softfp(retained_runtime, args.softfp_manifest_sha256, args.arch, args.mode, c_compiler)
            record['softfp_manifest_sha256'] = args.softfp_manifest_sha256
            supplement_args = ['--softfp-build', retained_runtime,
                               '--softfp-manifest-sha256', args.softfp_manifest_sha256]

        probe = out / 'probe'
        source = consumer / ('tests/musl/' + probe_name + '.c')
        call('musl-build', [sys.executable, '-B', consumer / 'tools/build_musl_probe.py',
             '--arch', args.arch, '--musl-build', retained_musl, '--toolchain', toolchain,
             '--source', source, '--linker-script', consumer / 'tests/musl/bootstrap.ld', '--out', probe,
             *supplement_args,
             *(['--ppc-clang', args.ppc_clang.resolve()] if args.ppc_clang else [])])
        probe_manifest = json.loads((probe / 'manifest.json').read_text())
        if (probe_manifest['status'] != 'built-not-executed' or probe_manifest['executed'] is not False or
                probe_manifest['probe_sha256'] != sha(source) or probe_manifest['source_manifest_sha256'] != args.musl_manifest_sha256):
            raise ValueError('probe manifest does not bind the requested source/sysroot')
        pin(probe / 'bootstrap.elf', probe_manifest['elf_sha256'])
        pin(probe / 'manifest.json')
        inspect_elf(probe / 'bootstrap.elf', args.arch)
        if (probe / 'bootstrap.elf').read_bytes()[7] != 3:
            raise ValueError('probe lacks explicit Linux ELF personality')
        compile_command = probe_manifest['commands'][0]
        source_index = compile_command.index('-c')
        dep_command = [*compile_command[:source_index], '-M', '-MT', 'object-pressure', str(source)]
        deps = dependencies(dep_command, call('probe-dependencies', dep_command, capture=True),
                            (consumer, retained_musl))
        if str(source) not in deps['files']:
            raise ValueError('dependency output omitted the native credential source')
        save_json(out / 'probe-dependencies.json', deps)
        pin(out / 'probe-dependencies.json')
        for name, expected in deps['files'].items():
            pin(Path(name), expected)
        call('os-configure', [programs['xmake'], 'f', '-P', consumer, '-c', '-y', '-a', args.arch,
             '-m', args.mode, '--systoolchain_dir=' + str(toolchain), '--kernel_sdk=' + str(retained_sdk), '--ccache=n'])
        for target in ('distro_image', 'rootfs-stage'):
            call('os-' + target, [programs['xmake'], 'build', '-P', consumer, '-j2', '-v', target])
        build = consumer / 'build' / args.arch / args.mode
        image = out / 'kernel-input.bin'
        shutil.copy2(build / 'distro/kernel.bin', image)
        pin(image)
        pin(build / 'distro/kernel.elf')
        root = out / 'root'
        shutil.copytree(build / 'rootfs', root, symlinks=True)
        shutil.copy2(probe / 'bootstrap.elf', root / ('bin/' + command_name))
        (root / ('bin/' + command_name)).chmod(0o755)
        record['rootfs_files'] = {str(path.relative_to(root)): ({'symlink': os.readlink(path)} if path.is_symlink()
                                  else {'sha256': sha(path)}) for path in sorted(root.rglob('*')) if path.is_file() or path.is_symlink()}
        disk = out / 'rootfs.ext4.img'
        call('package', [sys.executable, '-B', consumer / 'tools/mkext4.py', '--root', root, '--out', disk])
        call('initial-fsck', [programs['e2fsck'], '-fn', disk])
        initial = out / 'rootfs-input.ext4.img'
        shutil.copy2(disk, initial)
        pin(initial)
        record['initial_disk_sha256'] = sha(initial)
        for name, expected in record['inputs'].items():
            require_hash(Path(name), expected, 'pre-execution input ' + name)
        argv = delivery_qemu_command(qemu, args.arch, image, disk)
        record.update(status='running-guest', qemu_command=argv)
        save()
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        def receive(predicate):
            deadline = time.monotonic() + args.timeout
            while not predicate():
                if time.monotonic() > deadline:
                    raise RuntimeError('guest timeout')
                if not select.select([process.stdout], [], [], .1)[0]:
                    continue
                data = os.read(process.stdout.fileno(), 65536)
                if not data:
                    raise RuntimeError('guest exited before complete evidence')
                serial.extend(data)
                if len(serial) > 16 * 1024 * 1024:
                    raise RuntimeError('guest serial exceeds evidence budget')
                if error := failure_line(serial):
                    # Retain the complete diagnostic before stopping the guest;
                    # the integer-only logger can emit it over several writes.
                    if incomplete_failure_line(serial):
                        continue
                    raise RuntimeError('guest assertion failed: ' + error)

        receive(lambda: b'OK_SYSTEM_GUI boot=complete' in serial and serial.endswith(b'oksh> '))
        baseline_start = len(serial)
        process.stdin.write(b'hello | cat\n')
        process.stdin.flush()
        receive(lambda: len(serial) > baseline_start and serial.endswith(b'oksh> '))
        start = len(serial)
        process.stdin.write((command_line + '\n').encode())
        process.stdin.flush()
        receive(lambda: len(serial) > start and serial.endswith(b'oksh> '))
        middle = len(serial)
        process.stdin.write((command_line + '\n').encode())
        process.stdin.flush()
        receive(lambda: len(serial) > middle and serial.endswith(b'oksh> '))
        end = len(serial)
        record['command_boundaries'] = dict(baseline_begin=baseline_start, probe_begin=start, probe_mid=middle, probe_end=end, native_begin=end)
        process.stdin.write(b'hello | cat\n')
        process.stdin.flush()
        receive(lambda: len(serial) > end and serial.endswith(b'oksh> '))
        record['execution'] = validate_execution(bytes(serial), baseline_start, start, middle, end, end, args.arch, args.probe)
        record.update(status='guest-passed-awaiting-offline', executed=True)
    except BaseException as error:
        record.update(status='failed', error=repr(error))
        raise
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            tail = process.stdout.read()
            serial.extend(tail)
            process.stdin.close()
            process.stdout.close()
            record['qemu_returncode'] = process.returncode
        (out / 'serial.log').write_bytes(serial)
        record['serial_sha256'] = sha(out / 'serial.log')
        if disk is not None and disk.is_file():
            record['final_disk_sha256'] = sha(disk)
            # Preserve offline diagnostics even when a guest assertion fails.
            prior_status = record['status']
            try:
                call('final-fsck', [programs['e2fsck'], '-fn', disk])
                record['status'] = prior_status
            except BaseException as error:
                record.update(status='failed', offline_error=repr(error))
                save()
                if prior_status != 'failed':
                    raise
        save()
    try:
        record['execution'] = validate_execution(bytes(serial), baseline_start, start, middle, end, end, args.arch, args.probe)
        for name, expected in record['inputs'].items():
            require_hash(Path(name), expected, 'final input ' + name)
        admit_sources(source_root, args.source_inventory, args.source_inventory_sha256)
        record.update(status='passed', final_disk_sha256=sha(disk), inputs_rechecked=True)
        record['outputs'] = {str(path.relative_to(out)): sha(path) for path in sorted(out.rglob('*'))
                             if path.is_file() and not path.is_symlink() and path != out / 'result.json'}
    except BaseException as error:
        record.update(status='failed', error=repr(error))
        raise
    finally:
        save()
    print('PASS', args.arch, args.mode, record['execution']['runs'])


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
    for name in ('sdk-manifest-sha256', 'compiler-sha256', 'qemu-sha256', 'musl-manifest-sha256', 'source-inventory-sha256'):
        execute.add_argument('--' + name, required=True)
    execute.add_argument('--softfp-build', type=Path)
    execute.add_argument('--softfp-manifest-sha256')
    execute.add_argument('--ppc-clang', type=Path)
    execute.add_argument('--timeout', type=float, default=120)
    execute.add_argument('--probe', choices=('credentials',), default='credentials')
    args = parser.parse_args()
    if args.command == 'freeze':
        with args.output.open('x') as stream:
            json.dump(dict(schema=1, scope='object-pressure-os-sources', files=source_files(ROOT)), stream, indent=2, sort_keys=True)
            stream.write('\n')
        print(sha(args.output))
    else:
        if not 0 < args.timeout <= 600:
            raise ValueError('timeout must be in (0, 600] seconds')
        run(args)


if __name__ == '__main__':
    main()

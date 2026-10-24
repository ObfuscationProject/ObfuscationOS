#!/usr/bin/env python3
"""Execute the pinned access DAC guest using explicit SDK-only distro artifacts."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'scripts')]
from build_musl_probe import admit_musl_build
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from qemu_distro import command_for

QEMU = {'x86_64': 'qemu-system-x86_64', 'aarch64': 'qemu-system-aarch64',
        'rv64': 'qemu-system-riscv64', 'loongarch64': 'qemu-system-loongarch64'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_map(root):
    files = {}
    for folder, directories, names in os.walk(root):
        directories[:] = sorted(name for name in directories if name not in
                                 ('build', '.xmake', '__pycache__', '.git', 'toolchains'))
        for name in sorted(names):
            path = Path(folder) / name
            if path.suffix != '.pyc':
                if path.is_symlink():
                    raise ValueError('source inventory cannot contain symlinks')
                files[path.relative_to(root).as_posix()] = sha(path)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=QEMU, default='x86_64')
    for name in ('kernel-sdk', 'distro-image', 'musl-build', 'toolchain', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('sdk-manifest-sha256', 'distro-sha256', 'musl-manifest-sha256'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.is_relative_to(ROOT) or ROOT.is_relative_to(out):
        raise ValueError('evidence must be outside the OS source tree')
    out.mkdir(parents=True, exist_ok=False)
    record = dict(schema=1, status='preparing', architecture=args.arch, mode='debug',
                  sdk_only=True, kernel_source_compiled=False, executed=False,
                  physical=False, smp=False, cpus=1, dac_only=True,
                  kernel_profiles=['i386', 'x86_64', 'aarch64', 'arm32', 'rv64', 'rv32',
                                   'loongarch64', 'mips', 'mips64', 'ppc'],
                  supplied_musl_userlands=['x86_64', 'aarch64', 'rv64', 'loongarch64'],
                  scope='Actual static-musl Linux-personality access/faccessat/faccessat2 '
                        'ELF/traps on Virtio ext4; real/effective primary IDs, modes, flags, '
                        'relative and empty paths, symlinks and checked-copy faults. '
                        'No readonly/noexec/ACL/supplementary groups/capabilities/SMP qualification.',
                  commands=[], inputs={})
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', XMAKE_ROOT='y',
               XMAKE_GLOBALDIR=str(out / 'xmake-global'))
    for name in ('CPATH', 'CPLUS_INCLUDE_PATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH',
                 'GCC_EXEC_PREFIX', 'COMPILER_PATH'):
        env.pop(name, None)

    def save():
        (out / 'RESULT.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')

    def copy(path, destination, expected):
        if sha(path) != expected:
            raise ValueError('input hash mismatch: ' + str(path))
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        if sha(destination) != expected or sha(path) != expected:
            raise ValueError('copy input changed: ' + str(path))
        record['inputs'][str(path)] = expected

    def run(label, argv):
        command = list(map(str, argv))
        log = out / (label + '.log')
        with log.open('xb') as stream:
            result = subprocess.run(command, cwd=out, env=env, stdin=subprocess.DEVNULL,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=300)
        record['commands'].append(dict(label=label, argv=command, exit_code=result.returncode,
                                       log_sha256=sha(log)))
        save()
        if result.returncode:
            raise RuntimeError(label + ' failed; evidence retained')
        return log.read_text()

    process = None
    serial = bytearray()
    save()
    try:
        sources = source_map(ROOT)
        source = out / 'source/ObfuscationOS'
        for name, expected in sources.items():
            copy(ROOT / name, source / name, expected)
        record['source_sha256'] = sources
        toolchain = args.toolchain.resolve()
        triple = ARCH_TRIPLES[args.arch]
        compiler = toolchain / 'bin' / (triple + '-g++')
        sdk = args.kernel_sdk.resolve()
        if sha(sdk / 'manifest.json') != args.sdk_manifest_sha256:
            raise ValueError('explicit SDK manifest differs')
        manifest = validate_sdk(sdk, args.arch, 'debug', compiler)
        if manifest['abi_version'] != 52:
            raise ValueError('candidate requires explicit experimental ABI52')
        retained_sdk = out / 'sdk'
        for name, expected in {**manifest['files'], 'manifest.json': args.sdk_manifest_sha256}.items():
            copy(sdk / name, retained_sdk / name, expected)
        validate_sdk(retained_sdk, args.arch, 'debug', compiler)
        record['sdk_artifacts'] = manifest['files']
        copy(args.distro_image.resolve(), out / 'kernel.bin', args.distro_sha256)
        musl = args.musl_build.resolve()
        if sha(musl / 'manifest.json') != args.musl_manifest_sha256:
            raise ValueError('explicit musl manifest differs')
        musl_manifest = admit_musl_build(musl, args.arch)
        retained_musl = out / 'musl-build'
        copy(musl / 'manifest.json', retained_musl / 'manifest.json', args.musl_manifest_sha256)
        for name, expected in musl_manifest['files'].items():
            if name.startswith('sysroot/'):
                copy(musl / name, retained_musl / name, expected)
        admit_musl_build(retained_musl, args.arch)
        record.update(sdk_manifest_sha256=args.sdk_manifest_sha256, distro_sha256=args.distro_sha256,
                      musl_manifest_sha256=args.musl_manifest_sha256)
        tools = [Path(shutil.which(name)).resolve() for name in
                 (QEMU[args.arch], 'mke2fs', 'e2fsck', 'debugfs', 'xmake')]
        tools += [compiler, compiler.with_name(triple + '-gcc'), Path(sys.executable).resolve()]
        record['tool_sha256'] = {str(path): sha(path) for path in tools}
        run('musl-probe', [sys.executable, '-B', source / 'tools/build_musl_probe.py', '--arch', args.arch,
             '--musl-build', retained_musl, '--toolchain', toolchain,
             '--source', source / 'tests/musl/native_access.c', '--out', out / 'probe'])
        probe = json.loads((out / 'probe/manifest.json').read_text())
        if probe['status'] != 'built-not-executed' or probe['personality']['elf_osabi'] != 3:
            raise ValueError('probe is not an explicit Linux personality ELF')
        record['probe'] = probe
        root = out / 'rootfs'
        (root / 'access/search').mkdir(parents=True)
        shutil.copyfile(out / 'probe/bootstrap.elf', root / 'init')
        (root / 'init').chmod(0o755)
        fixture = {'root': (0o600, 0, 0), 'owner': (0o400, 1000, 2000),
                   'group': (0o040, 3000, 2000), 'none': (0o000, 0, 0),
                   'execute': (0o010, 0, 0), 'search/child': (0o644, 1000, 2000)}
        for name in fixture:
            path = root / 'access' / name
            path.write_bytes(b'access fixture\n')
            path.chmod(0o644)
        (root / 'access/dangling').symlink_to('absent')
        (root / 'access/search').chmod(0o700)
        disk = out / 'disk.img'
        run('image', [sys.executable, '-B', source / 'tools/mkext4.py', '--root', root, '--out', disk])
        pins = {'/': (0, 0), '/init': (0, 0), '/access': (0, 0), '/access/search': (1000, 2000)}
        pins.update({'/access/' + name: (uid, gid) for name, (_, uid, gid) in fixture.items()})
        for index, (name, (mode, _, _)) in enumerate(fixture.items()):
            run('mode-' + str(index), ['debugfs', '-w', '-R',
                'set_inode_field /access/' + name + ' mode 0' + format(0o100000 | mode, 'o'), disk])
        for index, (path, (uid, gid)) in enumerate(pins.items()):
            for field, value in (('uid', uid), ('gid', gid)):
                run('identity-' + str(index) + '-' + field,
                    ['debugfs', '-w', '-R', 'set_inode_field ' + path + ' ' + field + ' ' + str(value), disk])
        for index, (name, (mode, uid, gid)) in enumerate(fixture.items()):
            text = run('fixture-readback-' + str(index), ['debugfs', '-R', 'stat /access/' + name, disk])
            actual_mode = re.search(r'Mode:\s+0([0-7]+)', text)
            actual_ids = re.search(r'User:\s+(\d+)\s+Group:\s+(\d+)', text)
            if (not actual_mode or int(actual_mode.group(1), 8) != mode or not actual_ids or
                    tuple(map(int, actual_ids.groups())) != (uid, gid)):
                raise ValueError('offline fixture metadata readback differs: ' + name)
        run('initial-fsck', ['e2fsck', '-fn', disk])
        shutil.copyfile(disk, out / 'initial.img')
        run('readback-init', ['debugfs', '-R', 'dump /init ' + str(out / 'disk-init.elf'), disk])
        if sha(out / 'disk-init.elf') != probe['elf_sha256']:
            raise ValueError('disk initial-program identity differs')
        qemu = Path(shutil.which(QEMU[args.arch])).resolve()
        command = command_for(qemu, args.arch, out / 'kernel.bin', disk, 'none')
        command += ['-smp', '1']
        record['qemu_command'] = command
        process = subprocess.Popen(command, cwd=out, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 120
        passed = False
        while time.monotonic() < deadline:
            if select.select([process.stdout], [], [], 0.2)[0]:
                data = os.read(process.stdout.fileno(), 65536)
                if data: serial.extend(data)
            text = serial.decode(errors='replace')
            if 'ACCESS_NATIVE_FAIL' in text or 'OK_PANIC' in text or 'OK_TEST_FAIL' in text:
                break
            if re.search(r'ACCESS_NATIVE_PASS checks=\d+ profile=' + re.escape(args.arch) +
                         r' real_effective=1 primary_group=1 checked_copy=1 dac_only=1\r?\n', text):
                passed = True
                break
            if process.poll() is not None:
                break
        process.terminate()
        tail, _ = process.communicate(timeout=10)
        serial.extend(tail)
        record['qemu_exit_code'] = process.returncode
        process = None
        (out / 'serial.log').write_bytes(serial)
        text = serial.decode(errors='replace')
        backing = 'linker' if args.arch == 'loongarch64' else 'firmware'
        if (not passed or 'OK_NATIVE_IMAGE personality=linux source=' + backing not in text or
                'OK_NATIVE scope=hardware init=loaded' not in text or
                'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none' not in text):
            raise ValueError('actual access guest did not complete the explicit Linux ELF path')
        record['native_checks'] = int(re.search(r'ACCESS_NATIVE_PASS checks=(\d+)', text).group(1))
        if record['native_checks'] != 69:
            raise ValueError('native assertion count is incomplete')
        record.update(status='passed-native-access-dac', executed=True,
                      serial_sha256=sha(out / 'serial.log'), disk_sha256=sha(disk), clean_shutdown=False)
        run('final-fsck', ['e2fsck', '-fn', disk])
        if source_map(ROOT) != sources or source_map(source) != sources:
            raise ValueError('OS source inventory changed during qualification')
        for path, expected in record['tool_sha256'].items():
            if sha(path) != expected:
                raise ValueError('tool identity changed')
    except BaseException as error:
        record.update(status='failed-preserved-native-access', error=repr(error))
        if process:
            process.terminate()
            tail, _ = process.communicate(timeout=10)
            serial.extend(tail)
        (out / 'serial.log').write_bytes(serial)
        save()
        raise
    save()
    print('PASS actual native access DAC checks=' + str(record['native_checks']) + '; SDK-only consumer')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Prepare an exact SDK31 user fixture; execution is a separate explicit mode."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import selectors
import shutil
import struct
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools/jbd2'), str(ROOT / 'tools'), str(ROOT / 'scripts')]
from native_support import ARCH_TRIPLES, QEMU, snapshot_sdk, validate_sdk
from qemu_distro import command_for
from linux_stat_image import prepare_root, seed_image
from linux_stat_oracle import validate as validate_evidence

POLICIES = {'readonly': 0, 'maintained': 1, 'unqualified': 2}
EPOCHS = {'post2038': 2208988800, 'negative': -123456789}
SOURCES = (
    'tests/native/linux_stat_user.cpp', 'tests/native/linux_stat_runner.c',
    'tests/native/linux_stat_controls_runner.c', 'tests/musl/linux_stat.c',
    'tests/musl/linux_stat_controls.c', 'tests/stat_fixture.h', 'tests/stat_probe_log.h',
    'drivers/virtio/block.cpp', 'drivers/virtio/block.hpp', 'drivers/virtio/poll.hpp',
    'tools/test_linux_stat_user.py', 'tools/linux_stat_oracle.py', 'tools/linux_stat_image.py',
    'tools/kernel_sdk.py', 'tools/mkext4.py', 'tools/rootfs_policy.py',
    'tools/jbd2/native_support.py', 'scripts/qemu_distro.py',
    'tools/build_linux_stat_runner.py', 'tools/build_linux_stat_musl.py',
    'tools/freeze_linux_stat_sources.py', 'tools/qualify_linux_stat.py',
    'tests/tools/test_linux_stat_oracle.py', 'xmake/linux_stat_runner.lua', 'xmake/arch.lua',
    'tools/build_musl_probe.py', 'tools/musl_source.py', 'tools/plan_ledger.py',
    'tests/musl/bootstrap.ld', 'docs/plans/contracts/ledger.json',
)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def executable_identity(path, arch, linux):
    expected = {'i386': (1, 1, 3), 'x86_64': (2, 1, 62), 'aarch64': (2, 1, 183),
                'arm32': (1, 1, 40), 'rv32': (1, 1, 243), 'rv64': (2, 1, 243),
                'loongarch64': (2, 1, 258), 'mips': (1, 2, 8), 'mips64': (2, 2, 8), 'ppc': (1, 2, 20)}
    data = Path(path).read_bytes()
    if len(data) < 64 or data[:4] != b'\x7fELF' or data[6] != 1 or data[5] not in (1, 2):
        raise ValueError('invalid explicit user ELF identity')
    kind, machine = struct.unpack_from(('<' if data[5] == 1 else '>') + 'HH', data, 16)
    abi = 1 if linux and arch in ('mips', 'mips64') else 0
    if kind != 2 or (data[4], data[5], machine) != expected[arch] or data[7] != (3 if linux else 0) or data[8] != abi:
        raise ValueError('explicit user ELF architecture/personality mismatch')
    return dict(elf_class=32 if data[4] == 1 else 64, byte_order='little' if data[5] == 1 else 'big',
                machine=machine, osabi=data[7], abi_version=data[8])

def inventory(path):
    data = json.loads(path.read_text())
    if data.get('schema') != 1 or data.get('scope') != 'linux-stat-user-harness-sources':
        raise ValueError('source inventory schema/scope mismatch')
    files = data.get('files', {})
    if not isinstance(files, dict) or any(name not in files for name in SOURCES):
        raise ValueError('source inventory omits required harness files')
    if any(not isinstance(name, str) or not (ROOT / name).resolve().is_relative_to(ROOT.resolve()) or
           Path(name).is_absolute() or sha(ROOT / name) != expected for name, expected in files.items()):
        raise ValueError('harness source differs from explicit inventory')
    return data

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=tuple(ARCH_TRIPLES), required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    parser.add_argument('--policy', choices=tuple(POLICIES), required=True)
    parser.add_argument('--epoch', choices=tuple(EPOCHS), required=True)
    parser.add_argument('--kernel-sdk', type=Path, required=True)
    parser.add_argument('--sdk-manifest-sha256', required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--rootfs', type=Path, required=True)
    parser.add_argument('--native-runner', type=Path, required=True)
    parser.add_argument('--native-identity', type=Path, required=True)
    parser.add_argument('--musl-probe', type=Path, required=True)
    parser.add_argument('--musl-dependencies', type=Path, required=True)
    parser.add_argument('--source-inventory', type=Path, required=True)
    parser.add_argument('--source-inventory-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', '--execute-after-sdk20-delivery', dest='execute', action='store_true',
                        help='Boot the private fixture; default is prepare-only. The SDK20 spelling is a compatibility alias.')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(status='running', scope='SDK31 native/musl stat fixture', architecture=args.arch,
                  mode=args.mode, policy=args.policy, epoch=args.epoch, epoch_seconds=EPOCHS[args.epoch],
                  authority='uid1000', sdk_only=True, kernel_source_compiled=False, physical=False,
                  smp=False, cpus=1, native_execution=False, musl_execution=False,
                  linux_stat='not-executed', linux_reference_boot=False, commands=[])
    process = None
    serial = bytearray()
    disk = initial = None
    def save():
        (out / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    def run(command, label, binary=False, **kwargs):
        argv = list(map(str, command))
        row = dict(label=label, argv=argv)
        report['commands'].append(row)
        save()
        start = time.monotonic()
        done = subprocess.run(argv, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE if binary else subprocess.STDOUT, **kwargs)
        log = out / (label + '.log')
        log.write_bytes(done.stderr if binary else done.stdout)
        if binary:
            (out / (label + '.bin')).write_bytes(done.stdout)
            row['binary_sha256'] = sha(out / (label + '.bin'))
        row.update(returncode=done.returncode, seconds=time.monotonic() - start, log_sha256=sha(log))
        save()
        if done.returncode:
            raise RuntimeError(label + ' failed')
        return done.stdout
    def snapshot_json(path, name):
        data = path.read_bytes()
        (out / name).write_bytes(data)
        return json.loads(data)
    save()
    try:
        if sha(args.source_inventory) != args.source_inventory_sha256:
            raise ValueError('source inventory pin mismatch')
        source_inventory = inventory(args.source_inventory)
        snapshot_json(args.source_inventory, 'source-inventory.json')
        if sha(args.kernel_sdk / 'manifest.json') != args.sdk_manifest_sha256:
            raise ValueError('explicit SDK manifest pin mismatch')
        prefix = args.toolchain.resolve() / 'bin' / (ARCH_TRIPLES[args.arch] + '-')
        cxx, ar, objcopy = [Path(str(prefix) + suffix) for suffix in ('g++', 'ar', 'objcopy')]
        sdk = out / 'sdk'
        manifest, sdk_hash = snapshot_sdk(args.kernel_sdk, sdk, args.arch, cxx, args.mode)
        if manifest['abi_version'] != 31 or sdk_hash != args.sdk_manifest_sha256:
            raise ValueError('exact matched SDK31 required')
        report.update(sdk_manifest_sha256=sdk_hash, sdk_abi=31, compiler=manifest['compiler'])
        native_source = 'tests/native/linux_stat_runner.c' if args.policy == 'maintained' else 'tests/native/linux_stat_controls_runner.c'
        musl_source = 'tests/musl/linux_stat.c' if args.policy == 'maintained' else 'tests/musl/linux_stat_controls.c'
        native_identity = snapshot_json(args.native_identity, 'native-identity.json')
        expected_native = dict(status='built-not-executed', architecture=args.arch, mode=args.mode,
                               policy=args.policy, epoch=args.epoch, sdk_manifest_sha256=sdk_hash,
                               source_snapshot_sha256=args.source_inventory_sha256)
        if any(native_identity.get(k) != v for k, v in expected_native.items()):
            raise ValueError('native SDK/architecture/mode/policy/epoch identity mismatch')
        native_hashes = {'native-source.c': sha(ROOT / native_source),
                         'stat_fixture.h': sha(ROOT / 'tests/stat_fixture.h'),
                         'native-runner.elf': sha(args.native_runner)}
        if any(native_identity.get('files', {}).get(k) != v for k, v in native_hashes.items()):
            raise ValueError('native artifact/source dependency mismatch')
        musl = args.musl_probe.resolve()
        musl_manifest = snapshot_json(musl / 'manifest.json', 'musl-manifest.json')
        if (musl_manifest.get('status') != 'built-not-executed' or musl_manifest.get('executed') is not False or
                musl_manifest.get('architecture') != args.arch or musl_manifest.get('source_mode') not in ('debug', 'release') or
                musl_manifest.get('elf_sha256') != sha(musl / 'bootstrap.elf') or
                musl_manifest.get('probe_sha256') != sha(ROOT / musl_source)):
            raise ValueError('actual musl artifact/source identity mismatch')
        if musl_manifest.get('probe_sources', {}).get(str((ROOT / musl_source).resolve())) != sha(ROOT / musl_source):
            raise ValueError('musl source path differs from the recorded build input')
        deps = snapshot_json(args.musl_dependencies, 'musl-dependencies.json')
        expected_deps = dict(status='built-not-executed', architecture=args.arch,
                             mode=musl_manifest['mode'], source_rechecked_after_build=True,
                             musl_manifest_sha256=sha(out / 'musl-manifest.json'),
                             elf_sha256=musl_manifest['elf_sha256'],
                             source_snapshot_sha256=args.source_inventory_sha256)
        if any(deps.get(k) != v for k, v in expected_deps.items()):
            raise ValueError('musl dependency identity mismatch')
        expected_sources = {'musl-source.c': ROOT / musl_source,
                            'stat_fixture.h': ROOT / 'tests/stat_fixture.h',
                            'stat_probe_log.h': ROOT / 'tests/stat_probe_log.h'}
        if any(deps.get('files', {}).get(k) != sha(p) for k, p in expected_sources.items()):
            raise ValueError('musl source/header dependency mismatch')
        report['user_elf_identity'] = dict(native=executable_identity(args.native_runner, args.arch, False),
                                           musl=executable_identity(musl / 'bootstrap.elf', args.arch, True))
        report.update(musl_source_mode=musl_manifest['source_mode'], musl_artifact_mode=musl_manifest['mode'],
                      musl_mode_reused=musl_manifest['mode'] != args.mode,
                      musl_sdk_dependency='none; static Linux ABI source-build artifact')
        for name in SOURCES:
            target = out / 'sources' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
            if sha(target) != source_inventory['files'][name]:
                raise ValueError('source changed while snapshotting: ' + name)
        report['source_sha256'] = {name: source_inventory['files'][name] for name in SOURCES}
        members = run([ar, 't', sdk / 'lib/libokernel_boot.a'], 'boot-members').decode().splitlines()
        for name in ('boot.S.o', 'platform.cpp.o', 'kernel_main.cpp.o'):
            if members.count(name) != 1:
                raise ValueError('ambiguous SDK boot object: ' + name)
            (out / name).write_bytes(run([ar, 'p', sdk / 'lib/libokernel_boot.a', name], 'extract-' + name, binary=True))
        run([objcopy, '--redefine-sym', 'kernel_main=stat_fixture_unused_sdk_entry',
             out / 'kernel_main.cpp.o', out / 'sdk-support.o'], 'rename-unused-entry')
        report['sdk_support_transform'] = dict(input_member='kernel_main.cpp.o',
            input_sha256=sha(out / 'kernel_main.cpp.o'), output_sha256=sha(out / 'sdk-support.o'),
            change='rename kernel_main only in a separate SDK object copy; no Kernel source build')
        project = out / 'project'
        project.mkdir()
        lua = lambda value: json.dumps(str(value))
        values = lambda items: ', '.join(lua(x) for x in items)
        flags = ['-std=c++23', *manifest['cxxflags'], '-fno-builtin', '-Werror']
        definitions = [*manifest['defines'], 'LINUX_STAT_POLICY=' + str(POLICIES[args.policy]),
                       'LINUX_STAT_NEGATIVE=' + str(int(args.epoch == 'negative'))]
        objects = [out / name for name in ('boot.S.o', 'platform.cpp.o', 'sdk-support.o')]
        link = [*manifest['ldflags'], '-nostdlib', '-static', '-no-pie', '-Wl,--build-id=none',
                '-Wl,-z,max-page-size=0x1000', '-Wl,-T,' + str(sdk / 'boot/linker.ld'),
                '-Wl,--start-group', *objects, sdk / 'lib/libokernel.a', '-lgcc', '-Wl,--end-group']
        (project / 'xmake.lua').write_text('\n'.join([
            'set_project("linux-stat-user-fixture")', 'set_languages("c++23")',
            'toolchain("stat-fixture-cross")', 'set_kind("standalone")',
            'set_toolset("cxx", ' + lua(cxx) + ')', 'set_toolset("ld", ' + lua(cxx) + ')', 'toolchain_end()',
            'target("linux-stat-user-fixture")', 'set_kind("binary")', 'set_toolchains("stat-fixture-cross")',
            'set_targetdir(' + lua(out) + ')', 'set_filename("fixture.elf")',
            'add_cxxflags(' + values(flags) + ', {force = true})', 'add_defines(' + values(definitions) + ')',
            'add_includedirs(' + lua(sdk / 'include') + ')',
            'add_files(' + values(out / 'sources' / p for p in ('tests/native/linux_stat_user.cpp', 'drivers/virtio/block.cpp')) + ')',
            'add_ldflags(' + values(link) + ', {force = true})', 'target_end()', '']))
        env = dict(os.environ, XMAKE_ROOT='y', TZ='UTC')
        for name in ('CPATH', 'CPLUS_INCLUDE_PATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH', 'GCC_EXEC_PREFIX', 'COMPILER_PATH'):
            env.pop(name, None)
        xmake = Path(shutil.which('xmake') or '')
        if not xmake.is_file():
            raise ValueError('xmake unavailable')
        run([xmake, 'f', '-P', project, '-y', '--ccache=n'], 'xmake-configure', env=env, cwd=project)
        run([xmake, '-vD', '-P', project, '-j2', 'linux-stat-user-fixture'], 'xmake-build', env=env, cwd=project)
        image = out / 'fixture.bin'
        run([sys.executable, out / 'sources/tools/kernel_sdk.py', 'assemble', '--sdk', sdk,
             '--arch', args.arch, '--mode', args.mode, '--compiler', cxx, '--elf', out / 'fixture.elf',
             '--out', image, '--objcopy', objcopy], 'assemble')
        root = out / 'rootfs'
        shutil.copytree(args.rootfs.resolve(), root, symlinks=True)
        for name, permissions in [('apps', 0o755), ('bin', 0o755), ('home', 0o777), ('tmp', 0o1777)]:
            directory = root / name
            if directory.is_symlink():
                raise ValueError('fixture directory is a symlink: ' + name)
            directory.mkdir(exist_ok=True)
            directory.chmod(permissions)
        if args.policy != 'maintained':
            prepare_root(root)
        else:
            for name in ('stat-file', 'stat-alias', 'stat-link', 'stat-dangling', 'stat-loop', 'stat-missing',
                         'stat-held', 'stat-dir', 'stat-renamed-dir', 'stat-cwd', 'stat-empty', 'stat-hole'):
                p = root / 'home' / name
                if p.exists() or p.is_symlink():
                    raise ValueError('maintained fixture collision: ' + name)
        binary_name = 'musl-linux-stat' if args.policy == 'maintained' else 'musl-linux-stat-controls'
        for source, target in [(args.native_runner, root / 'apps/linux-stat-runner.elf'),
                               (musl / 'bootstrap.elf', root / 'bin' / binary_name)]:
            if target.exists() or target.is_symlink():
                raise ValueError('fixture executable collision: ' + str(target))
            shutil.copy2(source, target)
            target.chmod(0o555)
        if sha(root / 'apps/linux-stat-runner.elf') != native_hashes['native-runner.elf'] or sha(root / 'bin' / binary_name) != musl_manifest['elf_sha256']:
            raise ValueError('user artifact changed while staging')
        disk = out / 'rootfs.ext4.img'
        initial = out / 'rootfs-input.ext4.img'
        profile = ['--profile', 'linux-stat-fixture-v1'] if args.policy != 'maintained' else []
        run([sys.executable, out / 'sources/tools/mkext4.py', '--root', root, '--out', disk,
             *profile], 'package-ext4')
        report['image_seed'] = (seed_image(disk, EPOCHS[args.epoch]) if args.policy != 'maintained' else
                                dict(image_seeded=False, epoch=EPOCHS[args.epoch],
                                     source='new native fixture objects sample the explicitly seeded software clock'))
        shutil.copy2(disk, initial)
        report['initial_disk_sha256'] = sha(initial)
        run(['e2fsck', '-fn', initial], 'initial-fsck')
        if sha(initial) != report['initial_disk_sha256']:
            raise ValueError('readonly initial fsck changed image')
        report.update(kernel_image_sha256=sha(image), fixture_elf_sha256=sha(out / 'fixture.elf'))
        qemu = Path(shutil.which(QEMU[args.arch]) or '')
        if not qemu.is_file():
            raise ValueError('QEMU executable unavailable')
        command = command_for(qemu, args.arch, image, disk, 'none')
        command += ['-smp', '1', '-rtc', 'base=2024-02-29T12:34:56,clock=vm,driftfix=none']
        if args.arch in ('x86_64', 'i386'):
            command += ['-device', 'isa-debug-exit,iobase=0xf4,iosize=0x04']
        report['guest_argv'] = list(map(str, command))
        report['tool_sha256'] = {str(p.resolve()): sha(p.resolve()) for p in
                                (cxx, ar, objcopy, xmake, qemu, Path(sys.executable), Path(shutil.which('e2fsck')))}
        validate_sdk(sdk, args.arch, args.mode, cxx)
        inventory(args.source_inventory)
        if not args.execute:
            report.update(status='prepared-not-executed', sdk_snapshot_revalidated=True)
            return
        report['execution_requested_after_sdk20_delivery'] = True
        save()
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        start = time.monotonic()
        deadline = start + 100
        while time.monotonic() < deadline:
            for key, _ in selector.select(timeout=0.1):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if chunk:
                    serial.extend(chunk)
            lines = serial.split(b'\n')[:-1]
            if any(line.startswith(b'LINUX_STAT_USER_FIXTURE_PASS ') or b'_FAIL' in line for line in lines) or process.poll() is not None:
                break
        report.update(guest_elapsed_seconds=time.monotonic() - start, guest_timed_out=time.monotonic() >= deadline)
        if process.poll() is None:
            process.terminate()
        try:
            tail, _ = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            tail, _ = process.communicate()
        serial.extend(tail or b'')
        selector.close()
        report['guest_returncode'] = process.returncode
        process = None
        (out / 'serial.log').write_bytes(serial)
        if report['guest_timed_out']:
            raise ValueError('user fixture timed out after 100 seconds')
        text = serial.decode(errors='replace')
        lines = text.splitlines()
        required_markers = (
            'LINUX_STAT_USER_FIXTURE_BEGIN scope=actual-user-mode sdk-only=1',
            'LINUX_STAT_USER_CREDENTIALS uid=1000 euid=1000 gid=1000 egid=1000 before-entry=1',
            'LINUX_STAT_USER_STORAGE policy=' + args.policy + ' epoch=' + args.epoch + ' clock=administrator-software',
            'LINUX_STAT_USER_FIXTURE_PASS policy=' + args.policy + ' epoch=' + args.epoch + ' exit=0 actual-native-and-musl=1 uid=1000',
        )
        if any(lines.count(marker) != 1 for marker in required_markers) or '_FAIL' in text:
            raise ValueError('incomplete kernel fixture identity/lifecycle/sync evidence')
        report['evidence'] = validate_evidence(text, initial.read_bytes(), disk.read_bytes(),
                                                args.arch, args.policy, EPOCHS[args.epoch])
        report.update(native_execution=True, musl_execution=True,
                      linux_stat='qualified' if args.policy != 'unqualified' else 'EOPNOTSUPP')
        final_hash = sha(disk)
        run(['e2fsck', '-fn', disk], 'final-fsck')
        if sha(disk) != final_hash or sha(initial) != report['initial_disk_sha256']:
            raise ValueError('readonly fsck or guest changed retained initial bytes')
        inventory(args.source_inventory)
        validate_sdk(sdk, args.arch, args.mode, cxx)
        if sha(args.kernel_sdk / 'manifest.json') != args.sdk_manifest_sha256:
            raise ValueError('producer SDK manifest changed')
        report.update(status='passed', sdk_snapshot_revalidated=True, final_disk_sha256=final_hash,
                      initial_disk_unchanged=True)
    except BaseException as error:
        report.update(status='failed', error=str(error))
        print('FAIL', error, flush=True)
    finally:
        if process is not None:
            process.terminate()
            try:
                tail, _ = process.communicate(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                tail, _ = process.communicate()
            serial.extend(tail or b'')
        if serial:
            (out / 'serial.log').write_bytes(serial)
        if disk and disk.exists():
            report['final_disk_sha256'] = sha(disk)
        if initial and initial.exists():
            report['retained_initial_disk_sha256'] = sha(initial)
        report['artifact_sha256'] = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*'))
                                    if p.is_file() and p.name != 'result.json' and 'sdk' not in p.relative_to(out).parts}
        save()
    if report['status'] == 'failed':
        raise SystemExit(1)

if __name__ == '__main__':
    main()

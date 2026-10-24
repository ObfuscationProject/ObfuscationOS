#!/usr/bin/env python3
"""Build an SDK41-only mounted-dirty disk-root fixture; execution belongs to the outer campaign.

The generated result binds an invocation snapshot, never a production milestone.
The outer qualification campaign must pin this source and preserve each result.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
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
from mkarchive import pack

SOURCES = (
    'tests/native/ordered_data_root.cpp', 'tests/musl/ordered_data_root.c',
    'tests/chmod_probe_log.h', 'tests/musl/bootstrap.ld',
    'drivers/virtio/block.cpp', 'drivers/virtio/block.hpp', 'drivers/virtio/poll.hpp',
    'drivers/virtio/rng.cpp', 'drivers/virtio/rng.hpp', 'modules/boot/entropy.cpp',
    'tools/test_ordered_data_root.py', 'tools/kernel_sdk.py', 'tools/mkarchive.py',
    'tools/jbd2/journalled_root_image.py', 'tools/run_ordered_data_root.py',
    'tools/run_ordered_data_root_cuts.py', 'tools/run_ordered_data_root_faults.py',
    'tools/jbd2/ordered_data_fixture.py', 'tools/jbd2/mounted_fixture.py',
    'tools/jbd2/journalled_directory_transaction.py',
    'tools/jbd2/journalled_mode_image.py', 'tools/jbd2/admit_linux_fixture.py',
    'tools/jbd2/native_support.py', 'scripts/qemu_distro.py',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def executable_identity(path, arch):
    profiles = {'i386': (1, 1, 3), 'x86_64': (2, 1, 62), 'aarch64': (2, 1, 183),
                'arm32': (1, 1, 40), 'rv32': (1, 1, 243), 'rv64': (2, 1, 243),
                'loongarch64': (2, 1, 258), 'mips': (1, 2, 8), 'mips64': (2, 2, 8), 'ppc': (1, 2, 20)}
    data = Path(path).read_bytes()
    if len(data) < 64 or data[:4] != b'\x7fELF' or data[6] != 1 or data[5] not in (1, 2):
        raise ValueError('invalid explicit user ELF identity')
    kind, machine = struct.unpack_from(('<' if data[5] == 1 else '>') + 'HH', data, 16)
    abi = int(arch in ('mips', 'mips64'))
    if kind != 2 or (data[4], data[5], machine) != profiles[arch] or data[7] != 3 or data[8] != abi:
        raise ValueError('explicit user ELF architecture/Linux personality mismatch')
    return dict(elf_class=32 if data[4] == 1 else 64, byte_order='little' if data[5] == 1 else 'big',
                machine=machine, osabi=3, abi_version=abi)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=tuple(ARCH_TRIPLES), required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    parser.add_argument('--uid', type=int, choices=(0, 1000), required=True)
    parser.add_argument('--negative-clock', action='store_true')
    parser.add_argument('--kernel-sdk', type=Path, required=True)
    parser.add_argument('--sdk-manifest-sha256', required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--musl-probe', type=Path, required=True)
    parser.add_argument('--musl-manifest-sha256', required=True)
    parser.add_argument('--fixture', type=Path, required=True, help='Exact prepared volume/facts/header directory')
    parser.add_argument('--fixture-facts-sha256', required=True)
    parser.add_argument('--fixture-disk-sha256', required=True)
    parser.add_argument('--fixture-result-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.negative_clock or args.uid != 1000:
        raise ValueError('native recovery probe requires UID1000 and in-range clock')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(status='running', scope='SDK41 mounted-dirty disk-root fixture build only', architecture=args.arch,
                  mode=args.mode, uid=args.uid, negative_clock=args.negative_clock, sdk_only=True, kernel_source_compiled=False,
                  native_execution=False, musl_execution=False, physical=False, smp=False, cpus=1, commands=[])

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
        row.update(returncode=done.returncode, seconds=time.monotonic() - start, log_sha256=sha(log))
        if binary:
            (out / (label + '.bin')).write_bytes(done.stdout)
            row['binary_sha256'] = sha(out / (label + '.bin'))
        save()
        if done.returncode:
            raise RuntimeError(label + ' failed; inspect ' + str(log))
        return done.stdout

    def pinned_copy(source, target, expected):
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('explicit input pin mismatch: ' + str(source))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    save()
    try:
        source_hashes = {name: sha(ROOT / name) for name in SOURCES}
        for name, expected in source_hashes.items():
            pinned_copy(ROOT / name, out / 'sources' / name, expected)
        report['source_sha256'] = source_hashes
        (out / 'source-inventory.json').write_text(json.dumps(dict(schema=1,
            scope='journalled-root-user-invocation-snapshot', files=source_hashes), indent=2, sort_keys=True) + '\n')
        report['source_inventory_sha256'] = sha(out / 'source-inventory.json')
        prefix = args.toolchain.resolve() / 'bin' / (ARCH_TRIPLES[args.arch] + '-')
        cc, cxx, ar, objcopy = [Path(str(prefix) + suffix) for suffix in ('gcc', 'g++', 'ar', 'objcopy')]
        if sha(args.kernel_sdk / 'manifest.json') != args.sdk_manifest_sha256:
            raise ValueError('explicit SDK manifest pin mismatch')
        sdk = out / 'sdk'
        manifest, sdk_hash = snapshot_sdk(args.kernel_sdk, sdk, args.arch, cxx, args.mode)
        if manifest['abi_version'] != 41 or sdk_hash != args.sdk_manifest_sha256:
            raise ValueError('exact architecture/mode/compiler SDK41 required')
        report.update(sdk_manifest_sha256=sdk_hash, sdk_abi=41, compiler=manifest['compiler'])
        musl = args.musl_probe.resolve()
        pinned_copy(musl / 'manifest.json', out / 'musl-manifest.json', args.musl_manifest_sha256)
        mm = json.loads((out / 'musl-manifest.json').read_text())
        if (mm.get('status') != 'built-not-executed' or mm.get('executed') is not False or
                mm.get('architecture') != args.arch or mm.get('source_mode') not in ('debug', 'release') or
                mm.get('probe_sha256') != source_hashes['tests/musl/ordered_data_root.c']):
            raise ValueError('musl architecture/source identity mismatch')
        pinned_copy(musl / 'bootstrap.elf', out / 'musl-journalled-root.elf', mm['elf_sha256'])
        report.update(user_elf_identity=executable_identity(out / 'musl-journalled-root.elf', args.arch),
                      musl_manifest_sha256=args.musl_manifest_sha256,
                      user_elf_sha256=mm['elf_sha256'], musl_source_mode=mm['source_mode'],
                      musl_artifact_mode=mm['mode'], musl_sdk_dependency='none; static Linux ABI executable')
        fixture = args.fixture.resolve()
        pinned_copy(fixture / 'result.json', out / 'fixture-result.json', args.fixture_result_sha256)
        prepared = json.loads((out / 'fixture-result.json').read_text())
        if (prepared.get('status') != 'passed' or prepared.get('init_readback_sha256') != mm['elf_sha256'] or
                prepared.get('facts_sha256') != args.fixture_facts_sha256 or
                prepared.get('guarded_sha256') != args.fixture_disk_sha256):
            raise ValueError('on-disk /init or root image is not the exact static ELF')
        pinned_copy(fixture / 'facts.json', out / 'facts.json', args.fixture_facts_sha256)
        pinned_copy(fixture / 'guarded.img', out / 'initial-guarded.img', args.fixture_disk_sha256)
        shutil.copy2(out / 'initial-guarded.img', out / 'disk.img')
        facts = json.loads((out / 'facts.json').read_text())
        if (facts.get('origin') != 11 or facts.get('sectors') != 65536 or
                facts.get('suffix_sectors') != 19 or (out / 'disk.img').stat().st_size != (11 + 65536 + 19) * 512):
            raise ValueError('guarded fixture geometry mismatch')
        header = '#pragma once\n#include <ok/core/types.hpp>\nnamespace journalled_fixture {\n'
        header += f'inline constexpr ok::u64 origin = {facts["origin"]}, sectors = {facts["sectors"]};\n'
        header += f'inline constexpr ok::u64 journal_first = {facts["journal_first"]};\n'
        header += 'struct Inode { ok::u32 number; ok::u64 block; ok::usize offset; };\n'
        for name in ('root', 'seed', 'other_owner', 'child', 'seed_link', 'init'):
            node = facts['nodes'][name]
            header += f'inline constexpr Inode {name}{{{node["inode"]}, {node["block"]}, {node["offset"]}}};\n'
        header += '}\n'
        # Generate from pinned numeric facts, never compile an unbound header.
        (out / 'journalled_root_fixture.hpp').write_text(header)
        report.update(fixture_result_sha256=args.fixture_result_sha256, fixture_facts_sha256=args.fixture_facts_sha256,
                      initial_disk_sha256=args.fixture_disk_sha256,
                      fixture_header_sha256=sha(out / 'journalled_root_fixture.hpp'))
        root = out / 'rootfs'
        root.mkdir()
        # The archive is deliberately empty: a passing /init can only come from the disk root.
        archive = out / 'rootfs.okar'
        archive.write_bytes(pack(root))
        assembly = out / 'archive.S'
        assembly.write_text('.section .rodata\n.balign 16\n.global jroot_archive_start\n'
            '.global jroot_archive_end\njroot_archive_start:\n.incbin ' + json.dumps(str(archive)) +
            '\njroot_archive_end:\n.section .note.GNU-stack,"",%progbits\n')
        members = run([ar, 't', sdk / 'lib/libokernel_boot.a'], 'boot-members').decode().splitlines()
        for name in ('boot.S.o', 'platform.cpp.o', 'kernel_main.cpp.o'):
            if members.count(name) != 1:
                raise ValueError('ambiguous SDK boot object: ' + name)
            (out / name).write_bytes(run([ar, 'p', sdk / 'lib/libokernel_boot.a', name], 'extract-' + name, binary=True))
        run([objcopy, '--redefine-sym', 'kernel_main=jroot_unused_sdk_entry',
             out / 'kernel_main.cpp.o', out / 'sdk-support.o'], 'rename-unused-entry')
        report['sdk_support_transform'] = dict(input_member='kernel_main.cpp.o',
            input_sha256=sha(out / 'kernel_main.cpp.o'), output_sha256=sha(out / 'sdk-support.o'),
            change='rename kernel_main only in an SDK object copy; no Kernel source build')
        project = out / 'project'
        project.mkdir()
        lua = lambda value: json.dumps(str(value))
        values = lambda items: ', '.join(lua(x) for x in items)
        flags = ['-std=c++23', *manifest['cxxflags'], '-fno-builtin', '-Werror']
        definitions = [*manifest['defines'], 'JROOT_UID=' + str(args.uid),
                       'JROOT_NEGATIVE_CLOCK=' + str(int(args.negative_clock))]
        objects = [out / name for name in ('boot.S.o', 'platform.cpp.o', 'sdk-support.o')]
        link = [*manifest['ldflags'], '-nostdlib', '-static', '-no-pie', '-Wl,--build-id=none',
                '-Wl,-z,max-page-size=0x1000', '-Wl,-T,' + str(sdk / 'boot/linker.ld'),
                '-Wl,--start-group', *objects, sdk / 'lib/libokernel.a', '-lgcc', '-Wl,--end-group']
        (project / 'xmake.lua').write_text('\n'.join([
            'set_project("journalled-root-fixture")', 'set_languages("c++23")',
            'toolchain("jroot-fixture-cross")', 'set_kind("standalone")',
            'set_toolset("cxx", ' + lua(cxx) + ')', 'set_toolset("ld", ' + lua(cxx) + ')',
            'set_toolset("as", ' + lua(cc) + ')', 'toolchain_end()',
            'target("journalled-root-fixture")', 'set_kind("binary")', 'set_toolchains("jroot-fixture-cross")',
            'set_targetdir(' + lua(out) + ')', 'set_filename("fixture.elf")',
            'add_cxxflags(' + values(flags) + ', {force = true})',
            'add_asflags(' + values(manifest['asflags']) + ', {force = true})',
            'add_defines(' + values(definitions) + ')',
            'add_includedirs(' + values((sdk / 'include', out)) + ')',
            'add_files(' + values([out / 'sources/tests/native/ordered_data_root.cpp',
                                 out / 'sources/drivers/virtio/block.cpp',
                                 out / 'sources/drivers/virtio/rng.cpp',
                                 out / 'sources/modules/boot/entropy.cpp', assembly]) + ')',
            'add_ldflags(' + values(link) + ', {force = true})', 'target_end()', '']))
        env = dict(os.environ, XMAKE_ROOT='y', TZ='UTC', PYTHONDONTWRITEBYTECODE='1')
        for name in ('CPATH', 'CPLUS_INCLUDE_PATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH', 'GCC_EXEC_PREFIX', 'COMPILER_PATH'):
            env.pop(name, None)
        xmake = Path(shutil.which('xmake') or '')
        if not xmake.is_file():
            raise ValueError('xmake unavailable')
        run([xmake, 'f', '-P', project, '-y', '--ccache=n'], 'xmake-configure', env=env, cwd=project)
        run([xmake, '-vD', '-P', project, '-j2', 'journalled-root-fixture'], 'xmake-build', env=env, cwd=project)
        image = out / 'fixture.bin'
        run([sys.executable, '-B', out / 'sources/tools/kernel_sdk.py', 'assemble', '--sdk', sdk,
             '--arch', args.arch, '--mode', args.mode, '--compiler', cxx, '--elf', out / 'fixture.elf',
             '--out', image, '--objcopy', objcopy], 'assemble', env=env)
        qemu = Path(shutil.which(QEMU[args.arch]) or '')
        if not qemu.is_file():
            raise ValueError('QEMU executable unavailable')
        command = command_for(qemu, args.arch, image, out / 'disk.img', 'none')
        if args.arch == 'ppc':
            # The SDK runtime admits this exact measured, serialized PPC CPU.
            command += ['-cpu', 'e500v2_v22', '-accel', 'tcg,thread=single']
        command += ['-smp', '1', '-rtc', 'base=2024-02-29T12:34:56,clock=vm,driftfix=none']
        if args.arch in ('x86_64', 'i386'):
            command += ['-device', 'isa-debug-exit,iobase=0xf4,iosize=0x04']
        report['guest_argv'] = list(map(str, command))
        report['tool_sha256'] = {str(p.resolve()): sha(p.resolve()) for p in (cc, cxx, ar, objcopy, xmake, qemu, Path(sys.executable))}
        report.update(kernel_image_sha256=sha(image), fixture_elf_sha256=sha(out / 'fixture.elf'),
                      archive_sha256=sha(archive), assembly_sha256=sha(assembly))
        validate_sdk(sdk, args.arch, args.mode, cxx)
        if sha(args.kernel_sdk / 'manifest.json') != args.sdk_manifest_sha256:
            raise ValueError('producer SDK changed')
        if any(sha(ROOT / name) != expected or sha(out / 'sources' / name) != expected
               for name, expected in source_hashes.items()):
            raise ValueError('harness source changed during build')
        if (sha(fixture / 'guarded.img') != args.fixture_disk_sha256 or
                sha(fixture / 'facts.json') != args.fixture_facts_sha256 or
                sha(fixture / 'result.json') != args.fixture_result_sha256):
            raise ValueError('fixture input changed during build')
        report.update(status='prepared-not-executed', sdk_snapshot_revalidated=True)
    except BaseException as error:
        report.update(status='failed', error=str(error))
        print('FAIL', error, flush=True)
    finally:
        report['artifact_sha256'] = {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob('*'))
                                    if p.is_file() and p.name != 'result.json' and 'sdk' not in p.relative_to(out).parts}
        save()
    if report['status'] == 'failed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()

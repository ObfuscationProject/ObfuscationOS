#!/usr/bin/env python3
"""SDK-only actual-device maintained timestamp diagnostic; no public user proof."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tools/jbd2')]
from native_support import ARCH_TRIPLES, QEMU, machine, snapshot_sdk, validate_sdk
from ext4_timestamp_evidence import MARKER, validate_serial, inspect_image

SOURCES = ('tests/native/ext4_timestamps.cpp', 'drivers/virtio/block.cpp', 'drivers/virtio/block.hpp',
           'drivers/virtio/poll.hpp', 'tools/test_ext4_timestamps.py', 'tools/ext4_timestamp_evidence.py',
           'tools/jbd2/native_support.py', 'tools/kernel_sdk.py')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''): digest.update(block)
    return digest.hexdigest()


def guest(command, logfile, timeout):
    serial = bytearray()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for key, _ in selector.select(timeout=0.1):
                data = os.read(key.fileobj.fileno(), 65536)
                if data: serial.extend(data)
            lines = serial.split(b'\n')[:-1]
            if any(line == MARKER.encode() or line.startswith(b'EXT4_TIMESTAMPS_FAIL ') for line in lines) or process.poll() is not None:
                break
    finally:
        if process.poll() is None: process.terminate()
        try: tail, _ = process.communicate(timeout=3)
        except subprocess.TimeoutExpired: process.kill(); tail, _ = process.communicate()
        serial.extend(tail or b'')
        selector.close()
        logfile.write_bytes(serial)
    return process.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=tuple(ARCH_TRIPLES), required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    parser.add_argument('--kernel-sdk', type=Path, required=True)
    parser.add_argument('--sdk-manifest-sha256', required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--block-size', type=int, choices=(1024, 2048, 4096), action='append')
    parser.add_argument('--inode-size', type=int, choices=(128, 256), action='append')
    parser.add_argument('--timeout', type=float, default=100)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'scope': 'privileged actual-clock Virtio maintained ext4 provider diagnostic',
              'architecture': args.arch, 'mode': args.mode, 'sdk_only': True, 'kernel_source_compiled': False,
              'user_mode_execution': False, 'public_adapters_exercised': False, 'physical': False, 'smp': False,
              'rtc_calendar_writes': False, 'clock_origin': 'administrator-software', 'utc_accuracy': 'unknown',
              'clock_loss_scope': 'hosted-only; invalidating the shared monotonic clock also disables Virtio deadlines',
              'fault_injection': False, 'linux_mount_qualification': False, 'durability_scope': 'synchronous device operations and existing flush protocol; no physical/power-loss claim',
              'commands': [], 'cases': []}
    def save(): (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    def run(command, label, binary=False, **kwargs):
        entry = {'label': label, 'argv': list(map(str, command))}; report['commands'].append(entry); save()
        started = time.monotonic(); result = subprocess.run(entry['argv'], capture_output=True, **kwargs)
        (out / (label + '.log')).write_bytes(result.stderr if binary else result.stdout + result.stderr)
        if binary: (out / (label + '.bin')).write_bytes(result.stdout)
        entry.update(returncode=result.returncode, seconds=time.monotonic() - started, log_sha256=sha(out / (label + '.log')))
        save()
        if result.returncode: raise RuntimeError(label + ' failed')
        return result.stdout
    save()
    try:
        original_sdk = args.kernel_sdk.resolve()
        if sha(original_sdk / 'manifest.json') != args.sdk_manifest_sha256:
            raise ValueError('explicit SDK manifest identity mismatch')
        prefix = args.toolchain.resolve() / 'bin' / (ARCH_TRIPLES[args.arch] + '-')
        cxx, ar, objcopy = [Path(str(prefix) + suffix) for suffix in ('g++', 'ar', 'objcopy')]
        sdk = out / 'sdk'; manifest, sdk_sha = snapshot_sdk(original_sdk, sdk, args.arch, cxx, args.mode)
        required = {'include/ok/fs/ext4_fs.hpp', 'include/ok/fs/ext4_times.hpp', 'include/ok/arch/realtime.hpp'}
        if sdk_sha != args.sdk_manifest_sha256 or manifest['abi_version'] != 31 or not required.issubset(manifest['files']):
            raise ValueError('exact SDK31 maintained interfaces required')
        if '-frtti' not in manifest['cxxflags'] or '-fno-rtti' in manifest['cxxflags']:
            raise ValueError('SDK RTTI contract')
        report.update(sdk_abi=31, sdk_manifest_sha256=sdk_sha, compiler=manifest['compiler'], sdk_input=str(original_sdk))
        sources = {}
        for relative in SOURCES:
            target = out / 'sources' / relative; target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / relative).read_bytes()); sources[relative] = sha(target)
        report['source_sha256'] = sources
        tools = {}
        for name in ('xmake', QEMU[args.arch], 'mke2fs', 'e2fsck'):
            found = shutil.which(name)
            if not found: raise ValueError('missing tool ' + name)
            tools[name] = Path(found).resolve()
        xmake, qemu = tools['xmake'], tools[QEMU[args.arch]]
        report['tool_sha256'] = {str(path): sha(path) for path in (cxx, ar, objcopy, Path(sys.executable).resolve(), *tools.values())}
        members = run([ar, 't', sdk / 'lib/libokernel_boot.a'], 'boot-members').decode().splitlines()
        if members.count('boot.S.o') != 1: raise ValueError('nonunique boot archive member')
        (out / 'boot.o').write_bytes(run([ar, 'p', sdk / 'lib/libokernel_boot.a', 'boot.S.o'], 'extract-boot', binary=True))
        report['qemu_version'] = run([qemu, '--version'], 'qemu-version').decode().splitlines()[0]
        blocks, inodes = args.block_size or [1024, 2048, 4096], args.inode_size or [128, 256]
        if len(set(blocks)) != len(blocks) or len(set(inodes)) != len(inodes): raise ValueError('duplicate fixture selection')
        report['complete_six_layouts'] = set(blocks) == {1024, 2048, 4096} and set(inodes) == {128, 256}
        lua = lambda value: json.dumps(str(value))
        values = lambda sequence: ', '.join(lua(value) for value in sequence)
        for block_size in blocks:
            for inode_size in inodes:
                label = f'block{block_size}-inode{inode_size}'
                case = out / label; case.mkdir(); project = case / 'project'; project.mkdir()
                (case / 'timestamp_fixture.hpp').write_text('#pragma once\nnamespace timestamp_fixture {\n'
                    f'inline constexpr unsigned block_size = {block_size};\n'
                    f'inline constexpr unsigned inode_size = {inode_size};\n' + '}\n')
                flags = ['-std=c++23', *manifest['cxxflags'], '-fno-builtin', '-Werror']
                link = [*manifest['ldflags'], '-nostdlib', '-static', '-Wl,--build-id=none',
                        '-Wl,-T,' + str(sdk / 'boot/linker.ld'), out / 'boot.o', sdk / 'lib/libokernel.a', '-lgcc']
                (project / 'xmake.lua').write_text('\n'.join([
                    'set_project("ext4-timestamps")', 'set_languages("c++23")',
                    'toolchain("timestamp-fixture-cross")', 'set_kind("standalone")',
                    'set_toolset("cxx", ' + lua(cxx) + ')', 'set_toolset("ld", ' + lua(cxx) + ')', 'toolchain_end()',
                    'target("ext4-timestamps")', 'set_kind("binary")', 'set_toolchains("timestamp-fixture-cross")',
                    'set_targetdir(' + lua(case) + ')', 'set_filename("fixture.elf")',
                    'add_cxxflags(' + values(flags) + ', {force = true})', 'add_defines(' + values(manifest['defines']) + ')',
                    'add_includedirs(' + values([sdk / 'include', out / 'sources', case]) + ')',
                    'add_files(' + values(out / 'sources' / name for name in ('tests/native/ext4_timestamps.cpp', 'drivers/virtio/block.cpp')) + ')',
                    'add_ldflags(' + values(link) + ', {force = true})', 'target_end()', '']))
                environment = dict(os.environ, XMAKE_ROOT='y')
                run([xmake, 'f', '-P', project, '-y', '--ccache=n'], label + '-configure', env=environment, cwd=project)
                run([xmake, '-vD', '-P', project, 'ext4-timestamps'], label + '-build', env=environment, cwd=project)
                image = case / 'fixture.bin'
                run([sys.executable, out / 'sources/tools/kernel_sdk.py', 'assemble', '--sdk', sdk, '--arch', args.arch,
                     '--mode', args.mode, '--compiler', cxx, '--elf', case / 'fixture.elf', '--out', image,
                     '--objcopy', objcopy], label + '-assemble')
                initial, disk = case / 'initial.ext4.img', case / 'final.ext4.img'
                run([tools['mke2fs'], '-q', '-t', 'ext4', '-b', block_size, '-I', inode_size,
                     '-O', 'none,extent,filetype,sparse_super,large_file', '-E', 'lazy_itable_init=0',
                     '-m', '0', initial, '16M'], label + '-mkfs')
                run([tools['e2fsck'], '-fn', initial], label + '-initial-fsck')
                shutil.copy2(initial, disk)
                record = {'layout': label, 'block_size': block_size, 'inode_size': inode_size, 'status': 'running',
                          'initial_disk_sha256': sha(initial), 'image_sha256': sha(image)}
                report['cases'].append(record)
                transport = 'virtio-blk-device' if args.arch in ('aarch64', 'arm32', 'rv32', 'rv64') else 'virtio-blk-pci'
                command = list(map(str, machine(qemu, args.arch, image))) + ['-smp', '1', '-rtc',
                    'base=2024-02-29T12:34:56,clock=vm,driftfix=none', '-drive',
                    f'file={disk},format=raw,if=none,id=timestamps,cache=writeback', '-device', transport + ',drive=timestamps',
                    '-display', 'none', '-serial', 'stdio', '-monitor', 'none', '-no-reboot']
                record['guest_argv'] = command; save()
                serial = case / 'serial.log'
                record['guest_returncode'] = guest(command, serial, args.timeout)
                record['serial_sha256'] = sha(serial)
                evidence = validate_serial(serial.read_text(), inode_size)
                record['evidence'] = evidence
                record['raw_final_inodes'] = inspect_image(disk.read_bytes(), evidence, block_size, inode_size)
                before_fsck = sha(disk)
                run([tools['e2fsck'], '-fn', disk], label + '-final-fsck')
                if sha(disk) != before_fsck or sha(initial) != record['initial_disk_sha256'] or sha(image) != record['image_sha256']:
                    raise ValueError('retained input/final image changed unexpectedly')
                record.update(status='passed', final_disk_sha256=before_fsck, initial_disk_unchanged=True)
                save(); print('PASS', label, evidence['event_count'], 'actual-device events', flush=True)
        validate_sdk(sdk, args.arch, args.mode, cxx)
        for name, digest in sources.items():
            if sha(ROOT / name) != digest or sha(out / 'sources' / name) != digest:
                raise ValueError('source changed during diagnostic: ' + name)
        for name, digest in report['tool_sha256'].items():
            if sha(Path(name)) != digest: raise ValueError('tool changed during diagnostic')
        report.update(status='passed', sdk_snapshot_revalidated=True, source_unchanged=True)
    except Exception as error:
        report.update(status='failed', error=str(error)); print('FAIL', error, flush=True)
    finally:
        for case in report['cases']:
            path = out / case['layout']
            for label, name in [('final_disk_sha256', 'final.ext4.img'), ('retained_initial_disk_sha256', 'initial.ext4.img')]:
                if (path / name).exists(): case[label] = sha(path / name)
        report['artifact_sha256'] = {str(path.relative_to(out)): sha(path) for path in sorted(out.rglob('*'))
            if path.is_file() and path.name != 'result.json' and 'sdk' not in path.relative_to(out).parts}
        save()
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__': raise SystemExit(main())

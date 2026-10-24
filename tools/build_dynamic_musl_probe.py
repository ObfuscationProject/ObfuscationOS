#!/usr/bin/env python3
"""Build a mode-matched x86-64 shared-musl PIE without executing target code."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    parser.add_argument('--shared-build', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    shared = args.shared_build.resolve()
    manifest_path = shared / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    required = ('sysroot/usr/lib/Scrt1.o', 'sysroot/usr/lib/crti.o',
                'sysroot/usr/lib/crtn.o', 'sysroot/usr/lib/libc.so',
                'sysroot/usr/include/errno.h', 'sysroot/usr/include/sys/auxv.h')
    if (manifest.get('schema') != 1 or manifest.get('architecture') != 'x86_64' or
            manifest.get('mode') != args.mode or manifest.get('version') != '1.2.5' or
            manifest.get('status') != 'built-not-executed' or
            manifest.get('loader_path') != '/lib/ld-musl-x86_64.so.1'):
        raise ValueError('shared build identity does not match requested x86-64 mode')
    for name in required:
        if manifest.get('files', {}).get(name) != digest(shared / name):
            raise ValueError('shared build file differs from its exact manifest: ' + name)
    toolchain = args.toolchain.resolve()
    compiler = toolchain / 'bin/x86_64-elf-gcc'
    readelf = toolchain / 'bin/x86_64-elf-readelf'
    if subprocess.check_output([str(compiler), '-dumpmachine'], text=True).strip() != 'x86_64-elf':
        raise ValueError('selected compiler is not the x86-64 freestanding cross compiler')
    source = Path(__file__).resolve().parents[1] / 'tests/musl/dynamic_startup.c'
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    flags = ['-m64', '-mno-red-zone']
    compile_command = [str(compiler), *flags, '-O2', '-fPIC', '-fno-builtin', '-fno-stack-protector',
                       '-nostdinc', '-isystem', str(shared / 'sysroot/usr/include'), '-c', str(source),
                       '-o', str(out / 'probe.o')]
    link_command = [str(compiler), *flags, '-nostdlib', '-pie', '-Wl,-e,_start',
                    '-Wl,--dynamic-linker=/lib/ld-musl-x86_64.so.1', '-Wl,-z,max-page-size=4096',
                    '-Wl,-z,noexecstack', '-Wl,-z,now', '-Wl,-z,relro', '-Wl,--hash-style=both',
                    '-Wl,--build-id=none', str(shared / required[0]), str(shared / required[1]),
                    str(out / 'probe.o'), '-L' + str(shared / 'sysroot/usr/lib'), '-lc',
                    str(shared / required[2]), '-o', str(out / 'probe.elf')]
    record = {'schema': 1, 'architecture': 'x86_64', 'mode': args.mode,
              'musl_manifest_sha256': digest(manifest_path), 'source_sha256': digest(source),
              'compiler_sha256': digest(compiler), 'readelf_sha256': digest(readelf),
              'libc_sha256': digest(shared / required[3]),
              'commands': [compile_command, link_command], 'status': 'building', 'target_executed': False}
    env = os.environ.copy()
    for name in ('CPATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH', 'COMPILER_PATH', 'GCC_EXEC_PREFIX'):
        env.pop(name, None)
    try:
        for index, command in enumerate((compile_command, link_command)):
            with (out / f'{index}.log').open('w') as log:
                subprocess.run(command, env=env, check=True, stdout=log, stderr=subprocess.STDOUT)
        elf = out / 'probe.elf'
        payload = bytearray(elf.read_bytes())
        if (payload[:9] != b'\x7fELF\x02\x01\x01\x00\x00' or
                int.from_bytes(payload[16:18], 'little') != 3 or
                int.from_bytes(payload[18:20], 'little') != 62):
            raise ValueError('linked probe is not a SYSV x86-64 ET_DYN PIE')
        payload[7] = 3
        elf.write_bytes(payload)
        inspection = subprocess.check_output([str(readelf), '-h', '-l', '-d', '-r', str(elf)], text=True)
        (out / 'readelf.log').write_text(inspection)
        if ('/lib/ld-musl-x86_64.so.1' not in inspection or
                'Shared library: [libc.so]' not in inspection or
                'R_X86_64_RELATIVE' not in inspection):
            raise ValueError('PIE lacks pinned interpreter, libc dependency or pointer relocation')
        record['elf_sha256'] = digest(elf)
        record['object_sha256'] = digest(out / 'probe.o')
        record['readelf_log_sha256'] = digest(out / 'readelf.log')
        record['status'] = 'built-not-executed'
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        record['status'] = 'build-failed'
        record['failure'] = str(error)
        raise
    finally:
        (out / 'manifest.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print('PASS x86_64 ' + args.mode + ': shared-musl PT_INTERP PIE built, target execution pending')


if __name__ == '__main__':
    main()

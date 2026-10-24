#!/usr/bin/env python3
"""Build a pinned x86-64 static-musl entropy probe without target execution."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
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
    build = args.shared_build.resolve()
    manifest_path = build / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    required = ('sysroot/usr/lib/crt1.o', 'sysroot/usr/lib/crti.o',
                'sysroot/usr/lib/crtn.o', 'sysroot/usr/lib/libc.a',
                'sysroot/usr/include/sys/random.h', 'sysroot/usr/include/sys/auxv.h')
    if (manifest.get('schema') != 1 or manifest.get('version') != '1.2.5' or
            manifest.get('architecture') != 'x86_64' or manifest.get('mode') != args.mode or
            manifest.get('status') != 'built-not-executed'):
        raise ValueError('shared musl source identity differs from requested static build')
    for name in required:
        if manifest.get('files', {}).get(name) != digest(build / name):
            raise ValueError('static musl input differs from exact manifest: ' + name)
    toolchain = args.toolchain.resolve() / 'bin'
    gcc = toolchain / 'x86_64-elf-gcc'
    readelf = toolchain / 'x86_64-elf-readelf'
    if subprocess.check_output([str(gcc), '-dumpmachine'], text=True).strip() != 'x86_64-elf':
        raise ValueError('selected compiler is not x86-64 freestanding GCC')
    project = Path(__file__).resolve().parents[1]
    source = project / 'tests/musl/entropy_static.c'
    linker = project / 'tests/musl/bootstrap.ld'
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    flags = ['-m64', '-mno-red-zone', '-O2', '-fno-builtin', '-fno-stack-protector',
             '-fno-pie', '-ftls-model=local-exec']
    lib = build / 'sysroot/usr/lib'
    commands = [
        [str(gcc), *flags, '-nostdinc', '-isystem', str(build / 'sysroot/usr/include'),
         '-c', str(source), '-o', str(output / 'probe.o')],
        [str(gcc), *flags, '-nostdlib', '-static', '-Wl,-e,_start',
         '-Wl,-T,' + str(linker), '-Wl,--defsym,USER_BASE=0x40000000',
         '-Wl,-z,max-page-size=4096', '-Wl,-z,noexecstack', '-Wl,--build-id=none',
         str(lib / 'crt1.o'), str(lib / 'crti.o'), str(output / 'probe.o'),
         '-Wl,--start-group', str(lib / 'libc.a'), '-lgcc', '-Wl,--end-group',
         str(lib / 'crtn.o'), '-o', str(output / 'probe.elf')],
    ]
    env = os.environ.copy()
    for name in ('CPATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH', 'COMPILER_PATH', 'GCC_EXEC_PREFIX'):
        env.pop(name, None)
    for index, command in enumerate(commands):
        with (output / f'{index}.log').open('w') as log:
            subprocess.run(command, env=env, check=True, stdout=log, stderr=subprocess.STDOUT)
    elf = output / 'probe.elf'
    image = bytearray(elf.read_bytes())
    if (image[:7] != b'\x7fELF\x02\x01\x01' or int.from_bytes(image[16:18], 'little') != 2 or
            int.from_bytes(image[18:20], 'little') != 62):
        raise ValueError('static entropy probe is not an x86-64 ET_EXEC image')
    image[7] = 3
    elf.write_bytes(image)
    inspection = subprocess.check_output([str(readelf), '-h', '-l', str(elf)], text=True)
    (output / 'readelf.log').write_text(inspection)
    if 'INTERP' in inspection or not re.search(r'Entry point address:\s+0x4[0-9a-f]+', inspection):
        raise ValueError('static entropy probe has an interpreter or wrong user entry')
    record = {'schema': 1, 'architecture': 'x86_64', 'mode': args.mode,
              'status': 'built-not-executed', 'target_executed': False,
              'musl_manifest_sha256': digest(manifest_path), 'source_sha256': digest(source),
              'linker_sha256': digest(linker), 'compiler_sha256': digest(gcc),
              'readelf_sha256': digest(readelf), 'elf_sha256': digest(elf),
              'commands': commands}
    (output / 'manifest.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print('PASS x86_64 ' + args.mode + ': static musl entropy ELF built, target execution pending')


if __name__ == '__main__':
    main()

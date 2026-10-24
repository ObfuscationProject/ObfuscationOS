#!/usr/bin/env python3
"""Build an explicit pinned static-musl guest probe; never execute target code."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat
import subprocess

from kernel_sdk import ARCH_TRIPLES
from musl_source import FLAGS, VERSION, digest, inspect_elf, ppc_frontend, source_pin
from plan_ledger import load_json
from mips64_softfp import admit as admit_softfp


def compile_dependency_names(text: str) -> list[str]:
    """Parse the single -MD rule emitted by the actual object compilation."""
    text = text.replace('\\\r\n', ' ').replace('\\\n', ' ').strip()
    prefix = 'musl-probe-object:'
    if not text.startswith(prefix) or '\n' in text or '\r' in text:
        raise ValueError('unexpected compiler dependency rule')
    result, token = [], []
    at = len(prefix)
    while at < len(text):
        char = text[at]
        if char == '\\':
            at += 1
            if at == len(text):
                raise ValueError('unfinished compiler dependency escape')
            token.append(text[at])
        elif char == '$':
            at += 1
            if at == len(text) or text[at] != '$':
                raise ValueError('compiler dependency contains make expansion')
            token.append('$')
        elif char == '#' or char == '\0':
            raise ValueError('unexpected compiler dependency comment or NUL')
        elif char.isspace():
            if token:
                result.append(''.join(token))
                token = []
        else:
            token.append(char)
        at += 1
    if token:
        result.append(''.join(token))
    if not result:
        raise ValueError('empty compiler dependencies')
    return result


def dependency_entry(path: Path) -> dict:
    if not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('missing regular compiler dependency: ' + str(path))
    return {'sha256': digest(path), 'mode': oct(stat.S_IMODE(path.stat().st_mode))}


def capture_compile_dependencies(depfile: Path, source: Path, cwd: Path) -> dict:
    names = compile_dependency_names(depfile.read_text())
    paths = [str((cwd / name).resolve()) for name in names]
    if str(source.resolve()) not in paths:
        raise ValueError('compiler dependencies omit the probe source')
    files = {name: dependency_entry(Path(name)) for name in paths}
    return {'command_index': 0, 'compiler_generated': True, 'includes_system_headers': True,
            'same_command_as_object': True, 'captured_after_object_compilation': True,
            'linker_library_and_subprocess_closure_qualified': False,
            'cwd': str(cwd), 'source': str(source.resolve()),
            'depfile': {'path': str(depfile), **dependency_entry(depfile)},
            'occurrences': paths, 'files': files}


def verify_compile_dependencies(record: dict) -> None:
    depfile = Path(record['depfile']['path'])
    expected = {name: value for name, value in record['depfile'].items() if name != 'path'}
    if dependency_entry(depfile) != expected:
        raise ValueError('compiler dependency file changed')
    actual = capture_compile_dependencies(depfile, Path(record['source']), Path(record['cwd']))
    if actual != record:
        raise ValueError('compiler dependency closure changed')


def admit_musl_build(build: Path, arch: str) -> dict:
    manifest = load_json(build / 'manifest.json')
    if manifest.get('schema_version') != 1 or manifest.get('version') != VERSION:
        raise ValueError('musl build schema/source version mismatch')
    if manifest.get('architecture') != arch or manifest.get('archive_sha256') != source_pin()['archive_sha256']:
        raise ValueError('musl build architecture/source pin mismatch')
    if manifest.get('mode') not in ('debug', 'release'):
        raise ValueError('musl build mode must be debug or release')
    if manifest.get('status') != 'built-not-executed' or manifest.get('native_execution') is not False:
        raise ValueError('musl source build must be built-not-executed; failed or partial sysroots are not admitted')
    files = manifest.get('files')
    if not isinstance(files, dict):
        raise ValueError('musl build lacks audited artifact inventory')
    required = ('sysroot/usr/lib/crt1.o', 'sysroot/usr/lib/crti.o', 'sysroot/usr/lib/crtn.o',
                'sysroot/usr/lib/libc.a', 'sysroot/usr/include/unistd.h',
                'sysroot/usr/include/errno.h', 'sysroot/usr/include/time.h')
    if any(name not in files for name in required):
        raise ValueError('musl build lacks audited startup/libc/header artifact')
    for name, expected in files.items():
        if name.startswith('sysroot/'):
            target = build / name
            if not target.resolve().is_relative_to(build) or not target.is_file() or digest(target) != expected:
                raise ValueError('musl sysroot artifact mismatch: ' + name)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arch', choices=ARCH_TRIPLES, required=True)
    parser.add_argument('--musl-build', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--ppc-clang', type=Path,
                        help='Explicit Linux-targeted Clang frontend for ordinary PowerPC main/TLS')
    parser.add_argument('--source', type=Path, help='Explicit C probe source; default tests/musl/bootstrap.c')
    parser.add_argument('--linker-script', type=Path, help='Explicit linker script; default tests/musl/bootstrap.ld')
    parser.add_argument('--no-builtins', action='store_true', help='Explicitly request actual libc calls (already enforced for all probes)')
    parser.add_argument('--capture-compile-dependencies', action='store_true',
                        help='Record -MD dependencies from the actual object-producing invocation')
    parser.add_argument('--softfp-build', type=Path, help='Explicit pinned MIPS64 binary128 runtime build')
    parser.add_argument('--softfp-manifest-sha256', help='Required exact manifest hash with --softfp-build')
    args = parser.parse_args()
    build = args.musl_build.resolve()
    manifest = admit_musl_build(build, args.arch)
    frontend = ppc_frontend(args.arch, args.ppc_clang, required=True)
    triple = ARCH_TRIPLES[args.arch]
    bindir = args.toolchain.resolve() / 'bin'
    compiler = bindir / (triple + '-gcc')
    if subprocess.check_output([str(compiler), '-dumpmachine'], text=True).strip() != triple:
        raise ValueError('wrong explicit target compiler')
    if bool(args.softfp_build) != bool(args.softfp_manifest_sha256):
        raise ValueError('soft-fp build and manifest hash must be supplied together')
    supplement = []
    supplement_record = None
    if args.softfp_build:
        archive, runtime = admit_softfp(args.softfp_build, args.softfp_manifest_sha256,
                                      args.arch, manifest['mode'], compiler)
        supplement = [str(archive)]
        supplement_record = {'manifest_sha256': args.softfp_manifest_sha256,
                             'archive_sha256': digest(archive), 'path': str(archive),
                             'profile': runtime['profile'], 'source_version': runtime['source_version']}
    output = args.out.resolve()
    default_source = Path(__file__).resolve().parents[1] / 'tests/musl/bootstrap.c'
    source = (args.source or default_source).resolve()
    linker_script = (args.linker_script or default_source.with_suffix('.ld')).resolve()
    if not source.is_file() or not linker_script.is_file():
        raise ValueError('explicit probe source and linker script must exist')
    sysroot = build / 'sysroot/usr'
    lib = sysroot / 'lib'
    flags = [*FLAGS[args.arch], '-O2', '-fno-builtin', '-fno-stack-protector', '-fno-pie', '-ftls-model=local-exec']
    compile_command = [str(compiler), *flags]
    if frontend:
        compile_command = [frontend['path'], *frontend['flags'], '-O2', '-fno-builtin', '-fno-stack-protector', '-fno-pie']
    address = 0x10000000 if args.arch in ('aarch64', 'arm32') else 0x40000000
    commands = [compile_command + ['-nostdinc', '-isystem', str(sysroot / 'include'), '-c', str(source),
                                  '-o', str(output / 'bootstrap.o')],
                [str(compiler), *flags, '-nostdlib', '-static', '-Wl,-e,_start',
                 '-Wl,-T,' + str(linker_script), '-Wl,--defsym,USER_BASE=' + hex(address),
                 '-Wl,-z,max-page-size=4096', '-Wl,-z,noexecstack',
                 *(['-Wl,--oformat=elf64-bigmips'] if args.arch == 'mips64' else []),
                 str(lib / 'crt1.o'), str(lib / 'crti.o'), str(output / 'bootstrap.o'),
                 '-Wl,--start-group', str(lib / 'libc.a'), *supplement, '-lgcc', '-Wl,--end-group',
                 str(lib / 'crtn.o'), '-o', str(output / 'bootstrap.elf')],
                [str(bindir / (triple + '-readelf')), '-h', '-l', str(output / 'bootstrap.elf')]]
    if args.capture_compile_dependencies:
        commands[0][1:1] = ['-MD', '-MF', str(output / 'bootstrap.d'), '-MT', 'musl-probe-object']
    record = {'schema_version': 1, 'architecture': args.arch, 'musl': manifest['version'],
              'source_version': manifest['version'], 'source_mode': manifest['mode'], 'mode': manifest['mode'],
              'source_manifest_sha256': digest(build / 'manifest.json'), 'probe_sha256': digest(source),
              'probe_sources': {str(source): digest(source)},
              'linker_script_sha256': digest(linker_script),
              'compiler_sha256': digest(Path(compile_command[0])), 'link_driver_sha256': digest(compiler),
              'probe_compiler': frontend or {'path': str(compiler), 'target': triple, 'sha256': digest(compiler)},
              'tool_sha256': {tool: digest(bindir / (triple + '-' + tool)) for tool in ('gcc', 'as', 'ld', 'readelf')},
              'commands': commands, 'user_begin': address, 'status': 'building', 'executed': False,
              'compiler_runtime_supplement': supplement_record,
              'personality': {'elf_osabi': 3, 'elf_abi_version': 1 if args.arch in ('mips', 'mips64') else 0, 'name': 'linux'}}
    env = os.environ.copy()
    for name in ('CPATH', 'C_INCLUDE_PATH', 'LIBRARY_PATH', 'GCC_EXEC_PREFIX', 'COMPILER_PATH'):
        env.pop(name, None)
    output.mkdir(parents=True, exist_ok=False)
    try:
        for index, command in enumerate(commands):
            with (output / f'{index}.log').open('w') as log:
                subprocess.run(command, env=env, check=True, stdout=log, stderr=subprocess.STDOUT)
            if index == 0 and args.capture_compile_dependencies:
                record['compile_dependencies'] = capture_compile_dependencies(
                    output / 'bootstrap.d', source, Path.cwd().resolve())
            if index == 1:
                # Linux ET_EXEC objects commonly use OSABI_NONE. This distro
                # explicitly marks the executable's syscall personality; the
                # loader must never infer it from a filename or syscall number.
                executable = output / 'bootstrap.elf'
                data = bytearray(executable.read_bytes())
                if len(data) < 16 or data[:4] != b'\x7fELF' or data[8] != record['personality']['elf_abi_version']:
                    raise ValueError('unexpected ELF identity before personality marking')
                data[7] = 3  # ELFOSABI_LINUX
                executable.write_bytes(data)
        record['elf'] = inspect_elf(output / 'bootstrap.elf', args.arch)
        record['elf_sha256'] = digest(output / 'bootstrap.elf')
        if args.capture_compile_dependencies:
            verify_compile_dependencies(record['compile_dependencies'])
            if digest(source) != record['probe_sha256'] or digest(linker_script) != record['linker_script_sha256']:
                raise ValueError('probe source or linker script changed during build')
            if admit_musl_build(build, args.arch) != manifest or digest(build / 'manifest.json') != record['source_manifest_sha256']:
                raise ValueError('admitted musl build changed during probe compilation')
        record['status'] = 'built-not-executed'
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        record['status'] = 'build-failed'
        record['failure'] = str(exc)
        raise
    finally:
        (output / 'manifest.json').write_text(json.dumps(record, indent=2) + '\n')
    print(f"PASS {args.arch}: static musl bootstrap ELF built; target execution remains unqualified")


if __name__ == '__main__':
    main()

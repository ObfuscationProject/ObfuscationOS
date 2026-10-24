#!/usr/bin/env python3
"""Build pinned musl's shared libc/loader; inspect artifacts without executing them."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import struct
import subprocess
import sys

from musl_source import ARCH_TRIPLES, FLAGS, VERSION, digest, extract_archive, inspect_archive, validate_build_path

PROFILES = {
    'i386': (1, 1, 3), 'x86_64': (2, 1, 62), 'aarch64': (2, 1, 183),
    'arm32': (1, 1, 40), 'rv64': (2, 1, 243), 'rv32': (1, 1, 243),
    'loongarch64': (2, 1, 258), 'mips': (1, 2, 8), 'mips64': (2, 2, 8), 'ppc': (1, 2, 20),
}
# Exact compiler experiments retained by musl_source.FLAGS, including FP/ISA ABI.
ELF_FLAGS = {'i386': 0, 'x86_64': 0, 'aarch64': 0, 'arm32': 0x05000200,
             'rv64': 5, 'rv32': 5, 'loongarch64': 0x43, 'mips': 0x70001007,
             'mips64': 0x80000007, 'ppc': 0x8000}
LDFLAGS = ['-Wl,-shared,-soname,libc.so', '-Wl,-z,defs,-z,text,-z,noexecstack']


def link_program_inputs(compiler: Path, flags: list[str], ldflags: list[str], env: dict) -> tuple[list[Path], dict]:
    # -### expands the actual GCC specs without creating objects or running ld.
    command = [str(compiler), *flags, *ldflags, '-###', '-shared', '-nostdlib',
               '-x', 'c', '/dev/null', '-o', '/dev/null']
    query = subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, check=True)
    selected = Path(subprocess.check_output([str(compiler), '-print-prog-name=collect2'],
                                           env=env, text=True).strip()).resolve()
    invocations = []
    for line in query.stdout.splitlines():
        parts = shlex.split(line)
        if parts and parts[0].startswith('/') and Path(parts[0]).resolve() == selected:
            invocations.append(parts)
    if len(invocations) != 1:
        raise ValueError('compiler link query must select exactly one collect2 invocation')
    parts = invocations[0]
    programs = [selected]
    for index, part in enumerate(parts):
        if part == '-plugin':
            if index + 1 == len(parts) or not parts[index + 1].startswith('/'):
                raise ValueError('compiler link plugin path is not explicit')
            programs.append(Path(parts[index + 1]).resolve())
        elif part.startswith('-plugin-opt=/'):
            programs.append(Path(part.removeprefix('-plugin-opt=')).resolve())
    return programs, dict(argv=command, returncode=query.returncode,
                          output=query.stdout, collect2_argv=parts)


def admit_runtimes(args, compiler: Path) -> list[dict]:
    """Select only architecture-, mode- and compiler-admitted helper archives."""
    pic = getattr(args, 'pic_runtime_build', None)
    pic_hash = getattr(args, 'pic_runtime_manifest_sha256', None)
    softfp = getattr(args, 'softfp_build', None)
    softfp_hash = getattr(args, 'softfp_manifest_sha256', None)
    gcc_pic = getattr(args, 'gcc_pic_runtime_build', None)
    gcc_pic_hash = getattr(args, 'gcc_pic_runtime_manifest_sha256', None)
    ppc_pic = getattr(args, 'ppc_pic_runtime_build', None)
    ppc_pic_hash = getattr(args, 'ppc_pic_runtime_manifest_sha256', None)
    if any(bool(directory) != bool(expected) for directory, expected in
           ((pic, pic_hash), (softfp, softfp_hash), (gcc_pic, gcc_pic_hash), (ppc_pic, ppc_pic_hash))):
        raise ValueError('runtime builds and exact manifest hashes must be supplied together')
    if bool(pic) != (args.arch in ('mips', 'mips64')):
        raise ValueError('MIPS shared libc requires its explicit PIC runtime; other profiles reject it')
    if bool(softfp) != (args.arch == 'mips64'):
        raise ValueError('MIPS64 shared libc requires its explicit binary128 supplement; other profiles reject it')
    if bool(gcc_pic) != (args.arch in ('rv32', 'rv64', 'loongarch64')):
        raise ValueError('RISC-V/LoongArch shared libc requires its explicit PIC runtime; other profiles reject it')
    if bool(ppc_pic) != (args.arch == 'ppc'):
        raise ValueError('PPC shared libc requires its explicit secure-PLT PIC runtime; other profiles reject it')
    result = []
    if pic:
        from mips_pic_runtime import admit as admit_pic
        archive, _ = admit_pic(pic, pic_hash, args.arch, args.mode, compiler)
        result.append(dict(kind='pic-libgcc', original_directory=str(pic.resolve()),
                           manifest_sha256=pic_hash, archive=str(archive), sha256=digest(archive)))
    if softfp:
        from mips64_softfp import admit as admit_softfp
        archive, _ = admit_softfp(softfp, softfp_hash, args.arch, args.mode, compiler)
        result.append(dict(kind='binary128', original_directory=str(softfp.resolve()),
                           manifest_sha256=softfp_hash, archive=str(archive), sha256=digest(archive)))
    if gcc_pic:
        from gcc_pic_runtime import admit as admit_gcc_pic
        archive, _ = admit_gcc_pic(gcc_pic, gcc_pic_hash, args.arch, args.mode, compiler)
        result.append(dict(kind='gcc-pic', original_directory=str(gcc_pic.resolve()),
                           manifest_sha256=gcc_pic_hash, archive=str(archive), sha256=digest(archive)))
    if ppc_pic:
        from ppc_pic_runtime import admit as admit_ppc_pic
        archive, _ = admit_ppc_pic(ppc_pic, ppc_pic_hash, args.arch, args.mode, compiler)
        result.append(dict(kind='ppc-pic', original_directory=str(ppc_pic.resolve()),
                           manifest_sha256=ppc_pic_hash, archive=str(archive), sha256=digest(archive)))
    for item in result:
        validate_build_path(Path(item['archive']))
        root = Path(item['original_directory'])
        item['files'] = {str(path.relative_to(root)): digest(path)
                         for path in sorted(root.rglob('*')) if path.is_file()}
    return result


def admit_linker(directory: Path | None, expected_sha256: str | None, arch: str) -> dict | None:
    if bool(directory) != bool(expected_sha256):
        raise ValueError('linker build and exact manifest hash must be supplied together')
    if directory is None: return None
    directory = directory.resolve()
    validate_build_path(directory)
    manifest = directory / 'manifest.json'
    if digest(manifest) != expected_sha256: raise ValueError('linker manifest checksum mismatch')
    record = json.loads(manifest.read_text())
    targets = {'rv64': 'riscv64-linux-gnu', 'rv32': 'riscv32-linux-gnu', 'loongarch64': 'loongarch64-linux-gnu', 'mips64': 'mips64-linux-gnuabi64', 'mips': 'mips-linux-gnu'}
    if (arch not in targets or record.get('architecture') != arch or record.get('target') != targets[arch] or
            record.get('native_compiler_triple') != ARCH_TRIPLES[arch] or
            record.get('status') != 'built-linker-not-libc-qualified' or record.get('target_executed') is not False or
            record.get('source_version') != '2.42' or
            record.get('source_archive_sha256') != 'f6e4d41fd5fc778b06b7891457b3620da5ecea1006c6a4a41ae998109f85a800'):
        raise ValueError('linker build architecture, source or qualification mismatch')
    linker = directory / 'prefix/bin' / (targets[arch] + '-ld')
    adapter = directory / 'compiler-adapter'
    if record.get('linker_path') != str(linker) or digest(linker) != record.get('linker_sha256'):
        raise ValueError('linker executable differs from the explicit artifact')
    aliases = ['ld', ARCH_TRIPLES[arch] + '-ld']
    assembler = None
    if 'assembler_path' in record:
        if arch not in ('mips', 'mips64'): raise ValueError('assembler override is restricted to explicit MIPS profiles')
        assembler = directory / 'prefix/bin' / (targets[arch] + '-as')
        if record['assembler_path'] != str(assembler) or digest(assembler) != record.get('assembler_sha256'):
            raise ValueError('assembler executable differs from the explicit artifact')
        aliases += ['as', ARCH_TRIPLES[arch] + '-as']
    if record.get('compiler_adapter_path') != str(adapter) or record.get('adapter_aliases') != aliases:
        raise ValueError('linker compiler adapter mismatch')
    for name in record['adapter_aliases']:
        alias = adapter / name
        selected = assembler if name in ('as', ARCH_TRIPLES[arch] + '-as') else linker
        if not alias.is_symlink() or alias.resolve() != selected.resolve():
            raise ValueError('linker adapter does not select the pinned executable')
    for command in record['commands']:
        if command['returncode'] or digest(directory / (command['label'] + '.log')) != command['log_sha256']:
            raise ValueError('linker command receipt mismatch')
    return dict(manifest_sha256=expected_sha256, linker_path=str(linker), linker_sha256=digest(linker),
                compiler_adapter_path=str(adapter), target=targets[arch],
                assembler_path=str(assembler) if assembler else None,
                assembler_sha256=digest(assembler) if assembler else None)


def inspect_loader(data: bytes, arch: str) -> dict:
    """Check a standalone musl ET_DYN and its bounded dynamic-table identity."""
    elf_class, order, machine = PROFILES[arch]
    header_size, ph_size, word_size = (52, 32, 4) if elf_class == 1 else (64, 56, 8)
    endian = '<' if order == 1 else '>'
    word_limit = 1 << (word_size * 8)
    if len(data) < header_size or data[:7] != b'\x7fELF' + bytes((elf_class, order, 1)):
        raise ValueError('shared libc ELF class/endian/version mismatch')
    if data[7] not in (0, 3) or data[8] not in (0, 1):
        raise ValueError('shared libc ELF personality is unsupported')
    if struct.unpack_from(endian + 'HHI', data, 16) != (3, machine, 1):
        raise ValueError('shared libc must be ET_DYN for the explicit architecture')
    elf_flags = struct.unpack_from(endian + 'I', data, 36 if elf_class == 1 else 48)[0]
    if elf_flags != ELF_FLAGS[arch]:
        raise ValueError('shared libc ELF architecture ABI flags mismatch')
    if elf_class == 1:
        entry, phoff = struct.unpack_from(endian + 'II', data, 24)
        ehsize, phentsize, phnum = struct.unpack_from(endian + 'HHH', data, 40)
    else:
        entry, phoff = struct.unpack_from(endian + 'QQ', data, 24)
        ehsize, phentsize, phnum = struct.unpack_from(endian + 'HHH', data, 52)
    if (ehsize != header_size or phentsize != ph_size or not 0 < phnum <= 128 or
            phoff < header_size or phoff + ph_size * phnum > len(data)):
        raise ValueError('shared libc ELF program table is invalid')
    loads, dynamics, stacks, mips_abi = [], [], [], []
    for index in range(phnum):
        offset = phoff + index * ph_size
        if elf_class == 1:
            kind, file_offset, address, _, size, memory, flags, align = struct.unpack_from(endian + 'IIIIIIII', data, offset)
        else:
            kind, flags, file_offset, address, _, size, memory, align = struct.unpack_from(endian + 'IIQQQQQQ', data, offset)
        if file_offset + size > len(data):
            raise ValueError('shared libc program segment extent is invalid')
        # Processor attributes describe file metadata without a memory mapping.
        # Memory size constraints apply to mapped LOAD/DYNAMIC segments only.
        if kind in (1, 2) and (size > memory or memory > word_limit - 1 - address):
            raise ValueError('shared libc mapped segment extent is invalid')
        if kind == 3:
            raise ValueError('standalone musl loader must not have an interpreter')
        if kind == 1:
            if flags & 3 == 3:
                raise ValueError('shared libc must not have a writable executable load')
            if align not in (0, 1) and (align & (align - 1) or address % align != file_offset % align):
                raise ValueError('shared libc load alignment is invalid')
            loads.append((file_offset, address, size, memory, flags))
        elif kind == 2:
            dynamics.append((file_offset, address, size))
        elif kind == 0x6474e551:
            stacks.append(flags)
        elif kind == 0x70000003 and arch in ('mips', 'mips64'):
            if size != 24:
                raise ValueError('shared libc MIPS ABI record size mismatch')
            mips_abi.append(struct.unpack_from('>HBBBBBBIIII', data, file_offset))
    if stacks != [6]:
        raise ValueError('shared libc requires one nonexecutable read/write stack declaration')
    if arch in ('mips', 'mips64'):
        isa, register = (32, 1) if arch == 'mips' else (64, 2)
        if mips_abi != [(0, isa, 2, register, register, 0, 1, 0, 0, 1, 0)]:
            raise ValueError('shared libc MIPS ISA/register/FP ABI record mismatch')
    mapped_pages = []
    for _, address, _, memory, _ in loads:
        if not memory: continue
        begin, end = address & ~4095, (address + memory + 4095) & ~4095
        if end >= word_limit or any(begin < old_end and old_begin < end
                                   for old_begin, old_end in mapped_pages):
            raise ValueError('shared libc load pages overlap or exceed the target word range')
        mapped_pages.append((begin, end))
    if not loads or not any(flags & 1 and address <= entry < address + size
                            for _, address, size, _, flags in loads):
        raise ValueError('shared libc lacks a file-backed executable loader entry')
    if len(dynamics) != 1:
        raise ValueError('shared libc must have exactly one dynamic table')
    offset, address, size = dynamics[0]
    if not size or size % (2 * word_size) or not any(
            address >= vaddr and address + size <= vaddr + length and offset == start + address - vaddr
            for start, vaddr, length, _, _ in loads):
        raise ValueError('shared libc dynamic table is not mapped from its file bytes')
    tags = {}
    terminated = False
    for at in range(offset, offset + size, 2 * word_size):
        tag, value = struct.unpack_from(endian + ('II' if word_size == 4 else 'QQ'), data, at)
        if tag == 0:
            terminated = True
            break
        if tag in (1, 0x7fffffff, 0x7ffffffd, 0x6ffffefc, 0x6ffffefb):
            raise ValueError('standalone musl loader must not depend on another shared library')
        if tag in tags:
            raise ValueError('duplicate shared libc dynamic tag')
        tags[tag] = value
    if 22 in tags or tags.get(30, 0) & 4:
        raise ValueError('shared libc text relocations are unsupported')
    if not terminated or not {5, 6, 10, 11, 14} <= tags.keys() or tags[11] != (16 if word_size == 4 else 24):
        raise ValueError('shared libc dynamic symbol/string metadata is incomplete')
    if not tags[10] or tags[14] >= tags[10]:
        raise ValueError('shared libc SONAME extent is invalid')
    if not any(vaddr <= tags[6] and tags[6] + tags[11] <= vaddr + length
               for _, vaddr, length, _, _ in loads):
        raise ValueError('shared libc symbol table starts outside file-backed loads')
    strings = None
    for start, vaddr, length, _, _ in loads:
        if vaddr <= tags[5] and tags[5] + tags[10] <= vaddr + length:
            strings = data[start + tags[5] - vaddr:start + tags[5] - vaddr + tags[10]]
            break
    if strings is None or b'\0' not in strings[tags[14]:] or strings[tags[14]:].split(b'\0', 1)[0] != b'libc.so':
        raise ValueError('shared libc SONAME is not the pinned musl libc.so')
    return dict(elf_class=32 if elf_class == 1 else 64, byte_order='little' if order == 1 else 'big',
                machine=machine, flags=elf_flags, type='ET_DYN', soname='libc.so', load_segments=len(loads),
                dynamic_tags=sorted(tags), entry=entry, executed=False)


def build(args) -> dict:
    admitted = inspect_archive(args.archive)
    linker_override = admit_linker(args.linker_build, args.linker_manifest_sha256, args.arch)
    if not 1 <= args.jobs <= 64:
        raise ValueError('jobs must be between 1 and 64')
    if args.out.is_symlink(): raise ValueError('output must not be a symlink')
    output, toolchain = args.out.resolve(), args.toolchain.resolve()
    for path in (output, toolchain): validate_build_path(path)
    if output.exists(): raise ValueError('output already exists; use a new explicit directory')
    triple = ARCH_TRIPLES[args.arch]
    tools = {name: toolchain / 'bin' / (triple + '-' + name)
             for name in ('gcc', 'ar', 'ranlib', 'readelf', 'as', 'ld')}
    for path in tools.values():
        if not path.is_file(): raise ValueError('missing explicit cross tool: ' + str(path))
    compiler = tools['gcc']
    runtimes = admit_runtimes(args, compiler)
    make_path = shutil.which('make')
    if not make_path: raise ValueError('make is unavailable')
    make = Path(make_path).resolve()
    env = dict(os.environ)
    for key in ('CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'OBJC_INCLUDE_PATH', 'LIBRARY_PATH',
                'GCC_EXEC_PREFIX', 'COMPILER_PATH', 'CFLAGS', 'CPPFLAGS', 'LDFLAGS', 'DESTDIR', 'CC',
                'CROSS_COMPILE', 'MAKEFLAGS', 'MFLAGS', 'MAKEFILES', 'GNUMAKEFLAGS'):
        env.pop(key, None)
    env.update(LC_ALL='C', SOURCE_DATE_EPOCH='1708128000', PYTHONDONTWRITEBYTECODE='1')
    if subprocess.check_output([str(compiler), '-dumpmachine'], env=env, text=True).strip() != triple:
        raise ValueError('shared libc cross compiler target mismatch')
    profile_flags = [*FLAGS[args.arch], *(['-msecure-plt'] if args.arch == 'ppc' else [])]
    ldflags = [*LDFLAGS, *(['-Wl,--secure-plt'] if args.arch == 'ppc' else [])]
    selection_flags = [*profile_flags]
    if linker_override:
        selection_flags.append('-B' + linker_override['compiler_adapter_path'] + '/')
    selected = Path(subprocess.check_output([str(compiler), *selection_flags, '-print-prog-name=ld'], env=env, text=True).strip()).resolve()
    if linker_override and selected != Path(linker_override['linker_path']).resolve():
        raise ValueError('compiler does not select the admitted dynamic linker')
    cc1 = Path(subprocess.check_output([str(compiler), '-print-prog-name=cc1'], env=env, text=True).strip()).resolve()
    assembler = Path(subprocess.check_output([str(compiler), *selection_flags, '-print-prog-name=as'], env=env, text=True).strip()).resolve()
    if linker_override and linker_override['assembler_path'] and assembler != Path(linker_override['assembler_path']).resolve():
        raise ValueError('compiler does not select the admitted assembler')
    link_inputs, link_query = link_program_inputs(compiler, selection_flags, ldflags, env)
    compiler_inputs = (selected, cc1, assembler, *link_inputs)
    for path in compiler_inputs:
        if not path.is_file(): raise ValueError('missing actual compiler input: ' + str(path))
    runtime = Path(subprocess.check_output([str(compiler), *selection_flags, '-print-libgcc-file-name'], env=env, text=True).strip()).resolve()
    if not runtime.is_file(): raise ValueError('missing actual compiler runtime')
    project = Path(__file__).resolve().parents[1]
    recipe_files = [project / 'tools' / name for name in
                    ('build_shared_musl.py', 'musl_source.py', 'kernel_sdk.py', 'plan_ledger.py')]
    recipe_files.append(project / 'docs/plans/contracts/ledger.json')
    if args.arch in ('mips', 'mips64'): recipe_files.append(project / 'tools/mips_pic_runtime.py')
    if args.arch in ('rv32', 'rv64', 'loongarch64'): recipe_files.append(project / 'tools/gcc_pic_runtime.py')
    if args.arch == 'ppc': recipe_files.append(project / 'tools/ppc_pic_runtime.py')
    if args.arch == 'mips64':
        recipe_files.extend([project / 'tools/mips64_softfp.py',
                             project / 'docs/plans/contracts/mips64-softfp.json'])
    recipe_inputs = {str(path): digest(path) for path in recipe_files}
    # Reserve the final directory exclusively. Concurrent invocations can never
    # replace an earlier receipt or rename over another empty output directory.
    output.mkdir(parents=True, exist_ok=False)
    work = output
    flags = [*profile_flags, '-O2', *(['-g'] if args.mode == 'debug' else []),
             '-ffile-prefix-map=' + str(work) + '=/usr/src/shared-musl',
             '-fdebug-prefix-map=' + str(work) + '=/usr/src/shared-musl']
    if linker_override:
        flags.append('-B' + linker_override['compiler_adapter_path'] + '/')
    if args.arch in ('mips', 'mips64'): flags.append('-Wa,-KPIC')
    record = dict(schema=1, status='building', architecture=args.arch, mode=args.mode, version=VERSION,
                  recipe_sha256=digest(Path(__file__)), source_inspection=admitted, cflags=flags,
                  ldflags=ldflags, original_work_directory=str(work),
                  make=dict(path=str(make), sha256=digest(make)),
                  recipe_inputs=recipe_inputs,
                  compiler_runtime=dict(path=str(runtime), sha256=digest(runtime)),
                  linker_override=linker_override,
                  runtime_overrides=runtimes,
                  actual_compiler_inputs={str(path): digest(path) for path in compiler_inputs},
                  compiler_link_query=link_query,
                  tools={name: dict(path=str(path), sha256=digest(path)) for name, path in tools.items()},
                  commands=[], files={}, symlinks={}, target_executed=False, kernel_source_compiled=False,
                  qualification='shared-libc-build-only; no OS dynamic loader, dlopen, TLS or pthread acceptance')

    def run(argv, cwd, label):
        with (work / (label + '.log')).open('wb') as log:
            result = subprocess.run(argv, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
        record['commands'].append(dict(argv=argv, cwd=str(cwd), returncode=result.returncode,
                                       log=label + '.log', log_sha256=digest(work / (label + '.log'))))
        if result.returncode: raise ValueError(label + ' failed with exit ' + str(result.returncode))
    try:
        archive = work / ('musl-' + VERSION + '.tar.gz')
        shutil.copyfile(args.archive, archive)
        inspect_archive(archive)
        source = extract_archive(archive, work / 'source')
        runtime_libraries = []
        for item in runtimes:
            retained = work / 'runtime-inputs' / item['kind']
            original = Path(item['original_directory'])
            retained.mkdir(parents=True)
            for name, expected in item['files'].items():
                src = original / name
                if src.is_symlink() or digest(src) != expected:
                    raise ValueError('runtime input changed or is a symlink: ' + str(src))
                dst = retained / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
                if digest(dst) != expected: raise ValueError('retained runtime input mismatch')
            relative_archive = Path(item['archive']).relative_to(original)
            runtime_libraries.append(str(retained / relative_archive))
        if not runtime_libraries:
            retained = work / 'runtime-inputs/default-libgcc/libgcc.a'
            retained.parent.mkdir(parents=True)
            shutil.copyfile(runtime, retained)
            if digest(retained) != record['compiler_runtime']['sha256']:
                raise ValueError('retained compiler runtime changed')
            runtime_libraries.append(str(retained))
        directory = work / 'build'; directory.mkdir()
        stage = work / 'sysroot'
        run([str(source / 'configure'), '--target=' + triple, '--enable-shared', '--disable-wrapper',
             '--prefix=/usr', '--syslibdir=/lib', 'CC=' + str(compiler),
             'CROSS_COMPILE=' + str(toolchain / 'bin' / (triple + '-')),
             'AR=' + str(tools['ar']) + ' -D', 'RANLIB=' + str(tools['ranlib']) + ' -D',
             'CFLAGS=' + ' '.join(flags),
             # Bare-metal GCC specs can accept -shared while omitting it from
             # collect2. Explicit ld forwarding prevents a mislabeled ET_EXEC.
             'LDFLAGS=' + ' '.join(ldflags),
             'LIBCC=' + ' '.join(runtime_libraries)], directory, 'configure')
        run([str(make), '-j' + str(args.jobs)], directory, 'build')
        run([str(make), 'install', 'DESTDIR=' + str(stage)], directory, 'install')
        library = stage / 'usr/lib/libc.so'
        if not library.is_file() or library.is_symlink(): raise ValueError('missing explicit installed musl libc.so')
        record['loader_elf'] = inspect_loader(library.read_bytes(), args.arch)
        configuration = {}
        for line in (directory / 'config.mak').read_text().splitlines():
            if ' = ' in line:
                key, value = line.split(' = ', 1); configuration[key] = value
        loader_name = 'ld-musl-' + configuration['ARCH'] + configuration.get('SUBARCH', '') + '.so.1'
        if '/' in loader_name or '\\' in loader_name: raise ValueError('invalid configured loader name')
        loader = stage / 'lib' / loader_name
        if not loader.is_symlink() or os.readlink(loader) != '/usr/lib/libc.so':
            raise ValueError('installed loader symlink differs from explicit libc artifact')
        loader.unlink(); loader.symlink_to('../usr/lib/libc.so')
        record['loader_path'] = '/lib/' + loader_name
        record['package_loader_link'] = '../usr/lib/libc.so'
        license_dir = stage / 'usr/share/licenses/musl'; license_dir.mkdir(parents=True)
        shutil.copyfile(source / 'COPYRIGHT', license_dir / 'COPYRIGHT')
        run([str(tools['readelf']), '-h', '-l', '-d', str(library)], directory, 'readelf')
        for path, expected in record['actual_compiler_inputs'].items():
            if digest(Path(path)) != expected: raise ValueError('compiler input changed during build: ' + path)
        for entry in record['tools'].values():
            if digest(Path(entry['path'])) != entry['sha256']: raise ValueError('cross tool changed during build')
        if digest(runtime) != record['compiler_runtime']['sha256']: raise ValueError('compiler runtime changed during build')
        for path, expected in recipe_inputs.items():
            if digest(Path(path)) != expected: raise ValueError('recipe input changed during build: ' + path)
        if runtimes != admit_runtimes(args, compiler):
            raise ValueError('admitted runtime inputs changed during build')
        if digest(make) != record['make']['sha256']: raise ValueError('make changed during build')
        if linker_override != admit_linker(args.linker_build, args.linker_manifest_sha256, args.arch):
            raise ValueError('admitted linker inputs changed during build')
        record['status'] = 'built-not-executed'
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.CalledProcessError) as exc:
        record['status'] = 'build-failed'; record['failure'] = str(exc)
    finally:
        for path in sorted(work.rglob('*')):
            if path.is_symlink():
                record['symlinks'][str(path.relative_to(work))] = os.readlink(path)
            elif path.is_file():
                record['files'][str(path.relative_to(work))] = digest(path)
        (work / 'manifest.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    if record['status'] != 'built-not-executed':
        raise ValueError(record['failure'] + '; failed source/logs/artifacts retained at ' + str(output))
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--arch', choices=ARCH_TRIPLES, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--linker-build', type=Path)
    parser.add_argument('--linker-manifest-sha256')
    parser.add_argument('--pic-runtime-build', type=Path)
    parser.add_argument('--pic-runtime-manifest-sha256')
    parser.add_argument('--softfp-build', type=Path)
    parser.add_argument('--softfp-manifest-sha256')
    parser.add_argument('--gcc-pic-runtime-build', type=Path)
    parser.add_argument('--gcc-pic-runtime-manifest-sha256')
    parser.add_argument('--ppc-pic-runtime-build', type=Path)
    parser.add_argument('--ppc-pic-runtime-manifest-sha256')
    args = parser.parse_args()
    try:
        result = build(args)
        print(json.dumps({key: result[key] for key in ('status', 'architecture', 'mode', 'loader_path', 'target_executed')}, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print('shared musl error: ' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

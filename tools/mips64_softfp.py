#!/usr/bin/env python3
"""Build/admit a pinned MIPS64 N64 binary128 user compiler-runtime supplement."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import struct
import subprocess
import tarfile

from musl_source import FLAGS, digest

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / 'docs/plans/contracts/mips64-softfp.json'
LIBRARY = 'sysroot/usr/lib/libobfuscation-mips64-softfp.a'
PROFILE = 'mips64r2-n64-big-hard-float-legacy-nan'
ABI_MACROS = {'__SIZEOF_POINTER__': '8', '__SIZEOF_LONG__': '8',
              '__SIZEOF_LONG_DOUBLE__': '16', '__LDBL_MANT_DIG__': '113',
              '__LDBL_MAX_EXP__': '16384', '__BYTE_ORDER__': '__ORDER_BIG_ENDIAN__',
              '__mips64': '1', '__mips_hard_float': '1', '__mips_fpr': '64',
              '__mips_isa_rev': '2', '_MIPS_SIM': '_ABI64', '_ABI64': '3'}


def clean_env():
    env = os.environ.copy()
    for key in ('CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'LIBRARY_PATH',
                'GCC_EXEC_PREFIX', 'COMPILER_PATH', 'CFLAGS', 'CPPFLAGS', 'LDFLAGS'):
        env.pop(key, None)
    env.update(LC_ALL='C', SOURCE_DATE_EPOCH='1747958400')
    return env


def compiler_abi(compiler, env):
    if subprocess.check_output([str(compiler), '-dumpmachine'], env=env, text=True).strip() != 'mips64-elf':
        raise ValueError('supplement requires the explicit mips64-elf compiler')
    text = subprocess.check_output([str(compiler), *FLAGS['mips64'], '-nostdinc',
                                   '-dM', '-E', '-x', 'c', '-'], input='', env=env, text=True)
    macros = {}
    for line in text.splitlines():
        fields = line.split(maxsplit=2)
        if len(fields) == 3 and fields[0] == '#define':
            macros[fields[1]] = fields[2]
    if any(macros.get(k) != v for k, v in ABI_MACROS.items()) or '__mips_nan2008' in macros:
        raise ValueError('compiler effective ABI differs from the pinned N64 legacy-NaN profile')
    return ABI_MACROS.copy()


def member_path(root, name):
    pure = PurePosixPath(name)
    if pure.is_absolute() or '..' in pure.parts or '\\' in name or str(pure) != name:
        raise ValueError('invalid relative artifact path')
    path = root / name
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('artifact escapes its retained root')
    return path


def extract_selected(archive, destination, pin):
    if digest(archive) != pin['archive_sha256']:
        raise ValueError('GCC source archive checksum mismatch')
    wanted = {f"gcc-{pin['version']}/" + name: name for name in pin['files']}
    found = set()
    # Streaming avoids repeated decompression and never extracts unselected entries.
    with tarfile.open(archive, 'r|xz') as stream:
        for item in stream:
            if item.name not in wanted:
                continue
            name = wanted[item.name]
            if not item.isfile() or name in found or item.size > 1024 * 1024:
                raise ValueError('invalid selected GCC archive member: ' + name)
            path = member_path(destination, name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with stream.extractfile(item) as source, path.open('xb') as output:
                shutil.copyfileobj(source, output)
            if digest(path) != pin['files'][name]:
                raise ValueError('selected GCC source checksum mismatch: ' + name)
            found.add(name)
    if found != set(pin['files']):
        raise ValueError('GCC archive lacks selected source/license files')


def expected_symbols(pin):
    return sorted(['__' + name for name in pin['functions']] + ['__netf2', '__lttf2', '__gttf2'])


def inspect_object(path):
    data = path.read_bytes()
    if (len(data) < 64 or data[:9] != b'\x7fELF\x02\x02\x01\x00\x00'
            or struct.unpack_from('>HHI', data, 16) != (1, 8, 1)
            or struct.unpack_from('>I', data, 48)[0] != 0x80000007):
        raise ValueError('soft-fp object ELF N64 ISA/ABI mismatch')
    offset = struct.unpack_from('>Q', data, 40)[0]
    size, count, names_index = struct.unpack_from('>HHH', data, 58)
    if size != 64 or not 0 < names_index < count or offset + size * count > len(data):
        raise ValueError('invalid soft-fp object section headers')
    sections = [struct.unpack_from('>IIQQQQIIQQ', data, offset + size * i) for i in range(count)]
    names_header = sections[names_index]
    names = data[names_header[4]:names_header[4] + names_header[5]]
    flags = []
    for section in sections:
        name_offset = section[0]
        if name_offset >= len(names) or b'\0' not in names[name_offset:]:
            raise ValueError('invalid soft-fp object section name')
        name = names[name_offset:].split(b'\0', 1)[0]
        if name == b'.MIPS.abiflags':
            if section[5] != 24 or section[4] + 24 > len(data):
                raise ValueError('invalid MIPS ABI flags section')
            flags.append(struct.unpack_from('>HBBBBBBIIII', data, section[4]))
    if flags != [(0, 64, 2, 2, 2, 0, 1, 0, 0, 1, 0)]:
        raise ValueError('soft-fp object register/FP ABI mismatch')
    return {'elf_class': 64, 'byte_order': 'big', 'type': 'ET_REL',
            'machine': 8, 'flags': 0x80000007, 'profile': PROFILE}


def inspect_library(root, pin):
    """Bind the actual GNU archive members and linker index to audited objects."""
    data = (root / LIBRARY).read_bytes()
    if not data.startswith(b'!<arch>\n'):
        raise ValueError('soft-fp library is not a regular GNU archive')
    offset, members, index = 8, {}, None
    while offset < len(data):
        header = data[offset:offset + 60]
        if len(header) != 60 or header[58:] != b'`\n' or not header[48:58].strip().isdigit():
            raise ValueError('invalid soft-fp archive header')
        name = header[:16].rstrip(b' ')
        size = int(header[48:58])
        body = data[offset + 60:offset + 60 + size]
        if len(body) != size:
            raise ValueError('truncated soft-fp archive member')
        if name == b'/':
            if index is not None or offset != 8:
                raise ValueError('duplicate or misplaced GNU archive index')
            index = body
        else:
            if not name.endswith(b'/'):
                raise ValueError('unsupported soft-fp archive member name')
            try:
                name = name[:-1].decode('ascii')
            except UnicodeDecodeError as exc:
                raise ValueError('non-ASCII soft-fp archive member name') from exc
            if name not in {n + '.o' for n in pin['functions']} or name in members:
                raise ValueError('unexpected or duplicate soft-fp archive member')
            if body != (root / 'objects' / name).read_bytes():
                raise ValueError('soft-fp archive member differs from audited object')
            members[name] = offset
        offset += 60 + size
        if size & 1:
            if data[offset:offset + 1] != b'\n':
                raise ValueError('invalid soft-fp archive padding')
            offset += 1
    if set(members) != {n + '.o' for n in pin['functions']} or index is None or len(index) < 4:
        raise ValueError('incomplete soft-fp archive or linker index')
    count = int.from_bytes(index[:4], 'big')
    if count != len(expected_symbols(pin)) or 4 + count * 4 > len(index):
        raise ValueError('invalid soft-fp archive symbol count')
    names = index[4 + count * 4:].split(b'\0')
    # GNU ar pads the symbol-name table with one NUL to an even byte size.
    if len(names) not in (count + 1, count + 2) or any(names[count:]):
        raise ValueError('invalid soft-fp archive symbol strings')
    expected = {'__' + n: members[n + '.o'] for n in pin['functions']}
    expected.update(__netf2=members['eqtf2.o'], __lttf2=members['letf2.o'], __gttf2=members['getf2.o'])
    symbols = {}
    for i in range(count):
        try:
            name = names[i].decode('ascii')
        except UnicodeDecodeError as exc:
            raise ValueError('invalid archive symbol encoding') from exc
        if name in symbols:
            raise ValueError('duplicate soft-fp archive symbol')
        symbols[name] = int.from_bytes(index[4 + i * 4:8 + i * 4], 'big')
    if symbols != expected:
        raise ValueError('soft-fp linker index does not name the audited members')
    return sorted(members)


def build(args):
    pin = json.loads(PIN.read_text())
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = clean_env()
    bindir = args.toolchain.resolve() / 'bin'
    compiler = bindir / 'mips64-elf-gcc'
    record = dict(schema_version=1, architecture='mips64', mode=args.mode, profile=PROFILE,
                  status='building', executed=False, source_pin_sha256=digest(PIN),
                  source_archive_sha256=pin['archive_sha256'], source_version=pin['version'],
                  library=LIBRARY, commands=[], files={}, tool_sha256={},
                  scope='Static user compiler-runtime supplement; no kernel, libm, pthread or execution qualification')
    def run(label, command):
        record['commands'].append(list(map(str, command)))
        with (output / (label + '.log')).open('xb') as log:
            subprocess.run(list(map(str, command)), env=env, check=True, stdout=log, stderr=subprocess.STDOUT)
    try:
        record['abi_macros'] = compiler_abi(compiler, env)
        for name in ('gcc', 'as', 'ar', 'nm', 'readelf'):
            record['tool_sha256'][str(bindir / ('mips64-elf-' + name))] = digest(bindir / ('mips64-elf-' + name))
        cc1 = Path(subprocess.check_output([str(compiler), '-print-prog-name=cc1'], env=env, text=True).strip()).resolve()
        record['tool_sha256'][str(cc1)] = digest(cc1)
        record['compiler_sha256'] = digest(compiler)
        record['compiler_version'] = subprocess.check_output([str(compiler), '-dumpfullversion'], env=env, text=True).strip()
        record['recipe_files'] = {}
        for name in ('mips64_softfp.py', 'musl_source.py', 'kernel_sdk.py', 'plan_ledger.py'):
            original = ROOT / 'tools' / name
            target = output / 'recipe' / name
            target.parent.mkdir(exist_ok=True)
            shutil.copyfile(original, target)
            record['recipe_files'][name] = digest(target)
        archive = output / ('gcc-' + pin['version'] + '.tar.xz')
        shutil.copyfile(args.archive, archive)
        source = output / 'source'
        extract_selected(archive, source, pin)
        shutil.copyfile(PIN, output / 'source-pin.json')
        obj = output / 'objects'
        obj.mkdir()
        flags = [*FLAGS['mips64'], '-std=gnu11', '-O2', '-fPIC', '-ffreestanding',
                 '-fno-stack-protector', '-nostdinc', '-fno-common',
                 f'-ffile-prefix-map={output}=/usr/src/mips64-softfp',
                 f'-fdebug-prefix-map={output}=/usr/src/mips64-softfp']
        if args.mode == 'debug':
            flags.append('-g')
        for folder in ('libgcc/soft-fp', 'libgcc/config/mips', 'include'):
            flags += ['-I', str(source / folder)]
        record['flags'] = flags
        for name in pin['functions']:
            run(name, [compiler, *flags, '-c', source / ('libgcc/soft-fp/' + name + '.c'), '-o', obj / (name + '.o')])
        record['object_abi'] = {name: inspect_object(obj / (name + '.o')) for name in pin['functions']}
        library = output / LIBRARY
        library.parent.mkdir(parents=True)
        objects = [obj / (name + '.o') for name in pin['functions']]
        run('archive', [bindir / 'mips64-elf-ar', 'rcsD', library, *objects])
        record['archive_members'] = inspect_library(output, pin)
        run('elf-attributes', [bindir / 'mips64-elf-readelf', '-h', '-A', *objects])
        defined = subprocess.check_output([str(bindir / 'mips64-elf-nm'), '-g', '--defined-only', str(library)], env=env, text=True)
        undefined = subprocess.check_output([str(bindir / 'mips64-elf-nm'), '-u', str(library)], env=env, text=True)
        (output / 'symbols-defined.log').write_text(defined)
        (output / 'symbols-undefined.log').write_text(undefined)
        symbols = sorted(line.split()[-1] for line in defined.splitlines() if len(line.split()) == 3)
        imports = sorted({line.split()[-1] for line in undefined.splitlines() if ' U ' in line})
        if symbols != expected_symbols(pin) or imports:
            raise ValueError('unexpected supplement export/import inventory: ' + repr((symbols, imports)))
        record['symbols'] = symbols
        record['undefined_symbols'] = imports
        licenses = output / 'sysroot/usr/share/licenses/gcc-soft-fp'
        licenses.mkdir(parents=True)
        for name in pin['files']:
            if name.startswith('COPYING'):
                shutil.copyfile(source / name, licenses / name)
        for path, expected in record['tool_sha256'].items():
            if digest(Path(path)) != expected:
                raise ValueError('compiler input changed during build: ' + path)
        record['status'] = 'built-not-executed'
    except (ValueError, OSError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        record['status'] = 'build-failed'
        record['failure'] = str(exc)
        raise
    finally:
        for path in sorted(output.rglob('*')):
            if path.is_file() and path.name != 'manifest.json':
                record['files'][path.relative_to(output).as_posix()] = digest(path)
        (output / 'manifest.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    return record


def admit(build_dir, manifest_sha256, arch, mode, compiler):
    root = build_dir.resolve()
    manifest_path = root / 'manifest.json'
    if not manifest_sha256 or digest(manifest_path) != manifest_sha256:
        raise ValueError('explicit soft-fp manifest checksum mismatch')
    record = json.loads(manifest_path.read_text())
    pin = json.loads(PIN.read_text())
    if (arch != 'mips64' or mode not in ('debug', 'release') or record.get('schema_version') != 1
            or record.get('architecture') != arch or record.get('mode') != mode
            or record.get('profile') != PROFILE or record.get('status') != 'built-not-executed'
            or record.get('executed') is not False or record.get('source_pin_sha256') != digest(PIN)
            or record.get('source_archive_sha256') != pin['archive_sha256']
            or record.get('source_version') != pin['version'] or record.get('library') != LIBRARY
            or record.get('compiler_sha256') != digest(compiler)
            or record.get('abi_macros') != ABI_MACROS or record.get('symbols') != expected_symbols(pin)
            or record.get('undefined_symbols') != []):
        raise ValueError('soft-fp build source/profile/mode/compiler contract mismatch')
    files = record.get('files')
    required = {LIBRARY, 'source-pin.json', 'symbols-defined.log', 'symbols-undefined.log', 'elf-attributes.log'}
    required.update('source/' + name for name in pin['files'])
    required.update('objects/' + name + '.o' for name in pin['functions'])
    required.update('sysroot/usr/share/licenses/gcc-soft-fp/' + name for name in pin['files'] if name.startswith('COPYING'))
    if not isinstance(files, dict) or not required.issubset(files):
        raise ValueError('soft-fp artifact inventory incomplete')
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != manifest_path}
    if actual != set(files):
        raise ValueError('soft-fp artifact inventory differs from retained files')
    for name, expected in files.items():
        path = member_path(root, name)
        if not path.is_file() or digest(path) != expected:
            raise ValueError('soft-fp retained artifact checksum mismatch: ' + name)
    for name, expected in pin['files'].items():
        if files['source/' + name] != expected:
            raise ValueError('soft-fp upstream source checksum mismatch')
    if files['source-pin.json'] != digest(PIN):
        raise ValueError('soft-fp retained source pin mismatch')
    objects = {name: inspect_object(root / ('objects/' + name + '.o')) for name in pin['functions']}
    if record.get('object_abi') != objects:
        raise ValueError('soft-fp object ABI inventory mismatch')
    if record.get('archive_members') != inspect_library(root, pin):
        raise ValueError('soft-fp archive member inventory mismatch')
    return root / LIBRARY, record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--toolchain', type=Path, required=True)
    parser.add_argument('--mode', choices=('debug', 'release'), required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    record = build(args)
    print(json.dumps({k: record[k] for k in ('status', 'profile', 'mode', 'executed')}, indent=2))


if __name__ == '__main__':
    main()

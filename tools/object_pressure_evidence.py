"""Strict SDK77 admission and serial evidence for object-pressure guests."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath

from kernel_sdk import ARCH_TRIPLES, validate_sdk

SOURCE_ROOTS = ('apps', 'compat', 'config', 'docs', 'drivers', 'lib', 'modules', 'scripts',
                'sdk', 'tests', 'tools', 'xmake')
SOURCE_FILES = ('AGENTS.md', 'xmake.lua')
FRAME_FIELDS = ('used', 'total', 'allocations', 'releases', 'pinned', 'user',
                'objects', 'free', 'pending', 'reserve', 'user_limit')
NUMBER = rb'(0|[1-9][0-9]{0,19})'
FRAME = re.compile(rb'OK_NATIVE_FRAMES version=([23]) source=(firmware|linker)' +
                   b''.join(b' ' + key.encode() + b'=' + NUMBER for key in FRAME_FIELDS) + rb'(?: object_quarantine=' + NUMBER + rb')?\r?\n')
PRESSURE = re.compile(rb'OK_MUSL_OBJECT_PRESSURE children=' + NUMBER + rb' pages=' + NUMBER +
                      rb' first=' + NUMBER + rb' last=' + NUMBER +
                      rb' poll=pass reclaim=pass reuse=pass\r?\n')


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(data)
    return result.hexdigest()


def require_hash(path, expected, label):
    if not isinstance(expected, str) or not re.fullmatch('[0-9a-f]{64}', expected) or sha(path) != expected:
        raise ValueError(label + ' hash mismatch')


def relative_file(root, name):
    if not isinstance(name, str):
        raise ValueError('artifact path must be a string')
    relative = PurePosixPath(name)
    if (relative.is_absolute() or '..' in relative.parts or
            str(relative) != name or not relative.parts or '\\' in name):
        raise ValueError('unsafe artifact path: ' + str(name))
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('artifact missing or outside input root: ' + name)
    return path


def source_files(root):
    files = {}
    paths = [root / name for name in SOURCE_FILES]
    for name in SOURCE_ROOTS:
        directory = root / name
        if directory.is_symlink():
            raise ValueError('source directory may not be a symlink')
        if directory.exists():
            paths.extend(directory.rglob('*'))
    for path in sorted(paths):
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        if path.is_symlink():
            raise ValueError('source snapshot may not follow symlinks: ' + str(path))
        if path.is_file():
            files[str(path.relative_to(root))] = sha(path)
    if not all(name in files for name in SOURCE_FILES):
        raise ValueError('missing OS source root files')
    return files


def admit_sources(root, manifest, expected, *, scope='object-pressure-os-sources'):
    require_hash(manifest, expected, 'source inventory')
    data = json.loads(manifest.read_text())
    if (not isinstance(data, dict) or type(data.get('schema')) is not int or
            data['schema'] != 1 or data.get('scope') != scope):
        raise ValueError('source inventory schema/scope mismatch')
    files = data.get('files')
    if not isinstance(files, dict) or not files or files != source_files(root):
        raise ValueError('OS source inventory missing, extra or changed files')
    return data


def admit_sdk(sdk, expected, arch, mode, compiler, compiler_hash):
    require_hash(sdk / 'manifest.json', expected, 'SDK manifest')
    require_hash(compiler, compiler_hash, 'SDK compiler')
    # Validate paths before the shared SDK validator opens its inventory.
    manifest = json.loads((sdk / 'manifest.json').read_text())
    if not isinstance(manifest.get('files'), dict):
        raise ValueError('SDK missing artifact inventory')
    for name in manifest['files']:
        relative_file(sdk, name)
    manifest = validate_sdk(sdk, arch, mode, compiler)
    if manifest['abi_version'] != 77 or manifest['compiler'].get('family') != 'gcc':
        raise ValueError('object pressure requires SDK77 GCC ABI77')
    return manifest


def failure_line(serial):
    for line in serial.splitlines():
        if any(token in line for token in (b'OBJECT_PRESSURE_FAIL', b'OK_TEST_FAIL',
                b'POSIX_CHECK failed:', b'MUSL_CHECK failed:', b'acceptance=FAIL',
                b'boot=degraded', b'boot=failed')):
            return line.decode(errors='replace')
    return None


def frame_source(arch, version):
    # SDK <= 74 (version 2) kept linker backing on three profiles; SDK 75
    # (version 3) discovers boot memory on every profile.
    if version == 3:
        return 'firmware'
    return 'linker' if arch in ('loongarch64', 'mips', 'mips64') else 'firmware'


def frame_version(serial):
    match = re.search(rb'OK_NATIVE_FRAMES version=([23]) ', serial)
    if not match:
        raise ValueError('missing frame records')
    return int(match[1])


def decode_frames(serial, arch, *, require_quarantine=False):
    if arch not in ARCH_TRIPLES:
        raise ValueError('unknown architecture')
    rows = []
    version = None
    for line in serial.splitlines(keepends=True):
        if b'OK_NATIVE_FRAMES' not in line:
            continue
        match = FRAME.fullmatch(line)
        if not match or (version is not None and int(match[1]) != version) or \
                match[2].decode() != frame_source(arch, int(match[1])):
            raise ValueError('incomplete, malformed, mixed-version or wrong-source frame record')
        version = int(match[1])
        if require_quarantine and match.groups()[-1] is None:
            raise ValueError('missing current mapping quarantine accounting')
        row = dict(zip(FRAME_FIELDS, map(int, match.groups()[2:-1])))
        row['object_quarantine'] = int(match.groups()[-1] or 0)
        # Version 2 owned a dedicated allocator; version 3 is a quota over the
        # shared kernel allocator, whose other owners hold the remaining frames.
        exclusive = version == 2
        if (any(value > 0xffffffffffffffff for value in row.values()) or
                not 0 < row['reserve'] < row['total'] or
                (row['user_limit'] != row['total'] - row['reserve'] if exclusive else
                 row['user_limit'] + row['reserve'] > row['total']) or
                row['user'] > row['user_limit'] or row['objects'] > row['reserve'] or
                row['used'] != row['user'] + row['objects'] or
                (row['used'] + row['free'] != row['total'] if exclusive else
                 row['used'] + row['free'] > row['total']) or
                row['allocations'] - row['releases'] != row['used'] or
                row['pinned'] or row['pending'] or row['object_quarantine']):
            raise ValueError('invalid frame ownership, purpose quota or reclamation accounting')
        if rows and (any(row[key] != rows[0][key] for key in ('total', 'reserve', 'user_limit')) or
                     row['allocations'] < rows[-1]['allocations'] or row['releases'] < rows[-1]['releases']):
            raise ValueError('frame capacity changed or lifetime counters moved backward')
        rows.append(row)
    if not rows:
        raise ValueError('missing frame records')
    return rows


def decode_pressure(serial):
    lines = [line for line in serial.splitlines(keepends=True) if b'OK_MUSL_OBJECT_PRESSURE' in line]
    if len(lines) != 1 or not (match := PRESSURE.fullmatch(lines[0])):
        raise ValueError('missing unique complete pressure success record')
    children, pages, first, last = map(int, match.groups())
    if not (1 < children < 12 and 0 < last < first == 256 and pages == first * (children - 1) + last):
        raise ValueError('shared user quota pressure was not demonstrated')
    return dict(children=children, pages=pages, first=first, last=last)


def validate_execution(serial, baseline_begin, pressure_begin, pressure_end, native_begin, arch):
    boundaries = (baseline_begin, pressure_begin, pressure_end, native_begin)
    if (any(type(offset) is not int for offset in boundaries) or
            not 0 < baseline_begin < pressure_begin < pressure_end <= native_begin < len(serial)):
        raise ValueError('invalid explicit guest command boundaries')
    if any(not serial[:offset].endswith(b'oksh> ') for offset in boundaries):
        raise ValueError('guest command boundary is not a completed shell prompt')
    if failure := failure_line(serial):
        raise ValueError('guest failure: ' + failure)
    boot, baseline_serial = serial[:baseline_begin], serial[baseline_begin:pressure_begin]
    pressure, native = serial[pressure_begin:pressure_end], serial[native_begin:]
    if b'OK_SYSTEM_GUI boot=complete' not in boot or b'OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw' not in boot:
        raise ValueError('missing ext4 distribution boot evidence')
    if b'hello from ObfuscationOS userland' not in baseline_serial.splitlines():
        raise ValueError('missing pre-pressure native pipeline baseline')
    if b'hello from ObfuscationOS userland' not in native:
        raise ValueError('native pipeline did not survive Linux execution')
    if any(b'OK_MUSL_OBJECT_PRESSURE' in span for span in (serial[:pressure_begin], serial[pressure_end:])):
        raise ValueError('pressure success outside the requested command')
    result = decode_pressure(pressure)
    rows = decode_frames(serial, arch, require_quarantine=True)
    during = decode_frames(pressure, arch, require_quarantine=True)
    boot_final = decode_frames(boot, arch, require_quarantine=True)[-1]
    baseline = decode_frames(baseline_serial, arch, require_quarantine=True)[-1]
    if baseline['allocations'] <= boot_final['allocations']:
        raise ValueError('pre-pressure native pipeline baseline has no fresh allocation')
    final = decode_frames(native, arch, require_quarantine=True)[-1]
    if (len(rows) < 4 or any(rows[0][key] for key in ('used', 'allocations', 'releases')) or
            baseline['objects'] < boot_final['objects'] or
            not any(row['objects'] > baseline['objects'] for row in during) or
            during[-1]['objects'] != baseline['objects'] or
            final['objects'] != baseline['objects'] or
            during[-1]['user'] != baseline['user'] or final['user'] != baseline['user'] or
            during[-1]['releases'] - baseline['releases'] < result['pages'] or
            result['pages'] >= rows[0]['user_limit'] or
            final['allocations'] <= during[-1]['allocations']):
        raise ValueError('missing actual object use, page reclamation or post-pressure allocation')
    version = frame_version(serial)
    return dict(pressure=result, accounting_version=version, source=frame_source(arch, version), total=final['total'],
                reserve=final['reserve'], user_limit=final['user_limit'], baseline=baseline, final=final,
                observed_object_pages=max(row['objects'] for row in during), records=len(rows))

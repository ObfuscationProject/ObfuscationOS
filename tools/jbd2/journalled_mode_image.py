#!/usr/bin/env python3
"""Prepare a disposable journalled chmod volume from the pinned Linux capture."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
from admit_linux_fixture import checksum, inspect
from test_completion import expected as recover_capture

CAPTURE_SHA256 = '50780dd20b69374a0da5a83725cbd83e4a2d263209d477f2388659abb7dd0457'
PAYLOAD = bytes((index * 17 + 29) & 255 for index in range(4096))
ORIGIN = 11
SUFFIX_SECTORS = 19


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inode_metadata(data, number):
    """Read one inode with independent libext2fs CRC32C verification."""
    per_group = struct.unpack_from('<I', data, 1064)[0]
    group, local = divmod(number - 1, per_group)
    table = struct.unpack_from('<I', data, 2048 + group * 32 + 8)[0]
    at = table * 1024 + local * 256
    raw = bytearray(data[at:at + 256])
    if len(raw) != 256 or struct.unpack_from('<H', raw, 128)[0] != 32:
        raise ValueError('unexpected inode size')
    recorded = struct.unpack_from('<H', raw, 124)[0] | (struct.unpack_from('<H', raw, 130)[0] << 16)
    raw[124:126] = raw[130:132] = bytes(2)
    seed = checksum(0xffffffff, data[1128:1144])
    state = checksum(checksum(seed, struct.pack('<I', number)), raw[100:104])
    if checksum(state, raw) != recorded:
        raise ValueError('invalid inode checksum: ' + str(number))
    def u16(offset): return struct.unpack_from('<H', raw, offset)[0]
    def u32(offset): return struct.unpack_from('<I', raw, offset)[0]
    times = {}
    for name, offset, extra in [('atime', 8, 140), ('ctime', 12, 132), ('mtime', 16, 136)]:
        extension = u32(extra)
        seconds = struct.unpack_from('<i', raw, offset)[0] + ((extension & 3) << 32)
        nanos = extension >> 2
        if nanos >= 1000000000:
            raise ValueError('invalid inode nanoseconds')
        times[name] = dict(seconds=seconds, nanoseconds=nanos)
    return dict(inode=number, byte_offset=at, block=at // 1024, offset=at % 1024,
                mode=u16(0), uid=u16(2) | (u16(120) << 16), gid=u16(24) | (u16(122) << 16),
                size=u32(4) | (u32(108) << 32), blocks512=u32(28) | (u16(116) << 32),
                links=u16(26), version=u32(36) | (u32(152) << 32), checksum=recorded, **times)


def extract_volume(data):
    prefix = bytes([0x9a]) * (ORIGIN * 512)
    suffix = bytes([0x9a]) * (SUFFIX_SECTORS * 512)
    if len(data) != len(prefix) + 32 * 1024 * 1024 + len(suffix):
        raise ValueError('unexpected guarded disk size')
    if data[:len(prefix)] != prefix or data[-len(suffix):] != suffix:
        raise ValueError('partition guard modified')
    return data[len(prefix):-len(suffix)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(status='running', scope='offline e2fsprogs fixture preparation; no native execution',
                  runner_sha256=sha(__file__), commands=[], tools={})
    def save():
        (out / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    def run(argv, label):
        argv = list(map(str, argv))
        log = out / (label + '.log')
        with log.open('xb') as stream:
            done = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT,
                                  env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TZ='UTC'))
        report['commands'].append(dict(argv=argv, returncode=done.returncode,
                                       log=log.name, log_sha256=sha(log)))
        save()
        if done.returncode:
            raise RuntimeError(label + ' failed')
        return log.read_text()
    save()
    try:
        capture_manifest = args.capture / 'capture-manifest.json'
        captured_path = args.capture / 'linux-dirty-capture.img'
        manifest = json.loads(capture_manifest.read_text())
        if sha(captured_path) != CAPTURE_SHA256 or manifest['capture_sha256'] != CAPTURE_SHA256:
            raise ValueError('capture identity mismatch')
        captured = captured_path.read_bytes()
        facts = inspect(captured, True)
        image = out / 'volume.img'
        image.write_bytes(recover_capture(captured, facts))
        shutil.copy2(capture_manifest, out / 'capture-manifest.json')
        report.update(capture_sha256=CAPTURE_SHA256, capture_manifest_sha256=sha(capture_manifest),
                      linux_image_sha256=manifest['linux_image_sha256'],
                      linux_source_provenance=manifest['linux_source_provenance'])
        tools = {}
        for name in ('debugfs', 'e2fsck'):
            tools[name] = str(Path(shutil.which(name)).resolve())
            report['tools'][tools[name]] = sha(tools[name])
        run([tools['e2fsck'], '-fn', image], 'recovered-fsck')
        seed_copy = out / 'original-seed.bin'
        run([tools['debugfs'], '-R', f'dump /seed {seed_copy}', image], 'original-seed')
        if seed_copy.read_bytes() != PAYLOAD:
            raise ValueError('unexpected pinned seed bytes')
        payload = out / 'other-payload.bin'
        payload.write_bytes(b'other owner metadata fixture\n')
        script = out / 'seed.debugfs'
        requests = [f'write {payload} /other-owner', 'mkdir /child', 'symlink /seed-link seed']
        for path, uid, gid, mode in [('/seed', 1000, 1001, 0o100600),
                                    ('/other-owner', 2000, 2000, 0o100644),
                                    ('/child', 1000, 1000, 0o40755),
                                    ('/seed-link', 1000, 1001, 0o120777)]:
            for field, value in [('uid', uid), ('gid', gid), ('mode', mode),
                                 ('atime', '@1600000001'), ('atime_extra', 246913576),
                                 ('mtime', '@1600000002'), ('mtime_extra', 938271560),
                                 ('ctime', '@1600000003'), ('ctime_extra', 493827156)]:
                requests.append(f'set_inode_field {path} {field} {value}')
        script.write_text('\n'.join(requests) + '\n')
        run([tools['debugfs'], '-w', '-f', script, image], 'seed')
        run([tools['e2fsck'], '-fn', image], 'seed-fsck')
        volume = image.read_bytes()
        nodes = {}
        for label, path in [('root', '/'), ('seed', '/seed'), ('other_owner', '/other-owner'),
                            ('child', '/child'), ('seed_link', '/seed-link')]:
            text = run([tools['debugfs'], '-R', 'stat ' + path, image], 'stat-' + label)
            match = re.search(r'^Inode: (\d+)\s', text, re.MULTILINE)
            if not match:
                raise ValueError('missing path from seeded image: ' + path)
            nodes[label] = inode_metadata(volume, int(match.group(1)))
        seed = nodes['seed']
        if (seed['inode'], seed['mode'], seed['uid'], seed['gid'], seed['size'], seed['blocks512'], seed['links']) != \
                (12, 0o100600, 1000, 1001, 4096, 8, 1):
            raise ValueError('seed metadata mismatch')
        for label in ('seed', 'other_owner', 'child', 'seed_link'):
            node = nodes[label]
            for name, seconds, nanos in [('atime', 1600000001, 61728394),
                                         ('mtime', 1600000002, 234567890), ('ctime', 1600000003, 123456789)]:
                if node[name] != dict(seconds=seconds, nanoseconds=nanos):
                    raise ValueError('seeded timestamp mismatch: ' + label + '/' + name)
        if nodes['other_owner']['uid'] != 2000 or nodes['other_owner']['gid'] != 2000 or \
                nodes['other_owner']['mode'] != 0o100644 or nodes['seed_link']['blocks512'] != 0:
            raise ValueError('other-owner or fast symlink mismatch')
        final_seed = out / 'seed.bin'
        run([tools['debugfs'], '-R', f'dump /seed {final_seed}', image], 'final-seed')
        if final_seed.read_bytes() != PAYLOAD:
            raise ValueError('seed payload modified')
        guarded = out / 'guarded.img'
        guarded.write_bytes(bytes([0x9a]) * (ORIGIN * 512) + volume + bytes([0x9a]) * (SUFFIX_SECTORS * 512))
        if extract_volume(guarded.read_bytes()) != volume:
            raise ValueError('guarded image extraction mismatch')
        header = ['#pragma once', 'namespace journalled_fixture {',
                  f'inline constexpr ok::u64 origin = {ORIGIN}, sectors = {len(volume) // 512};',
                  f'inline constexpr ok::u64 journal_first = {facts["journal_first"]};',
                  'struct Inode { ok::u32 number; ok::u64 block; ok::usize offset; };']
        for label, node in nodes.items():
            header.append(f'inline constexpr Inode {label}{{{node["inode"]}, {node["block"]}, {node["offset"]}}};')
        header += ['}', '']
        (out / 'journalled_mode_fixture.hpp').write_text('\n'.join(header))
        current_facts = dict(facts, nodes=nodes, origin=ORIGIN, sectors=len(volume) // 512,
                             suffix_sectors=SUFFIX_SECTORS, captured_facts=facts)
        current_facts['feature_masks'] = [struct.unpack_from('<I', volume, 1024 + offset)[0]
                                          for offset in (92, 96, 100)]
        journal_offset = facts['journal_first'] * 1024
        current_facts['journal_sequence'] = struct.unpack_from('>I', volume, journal_offset + 24)[0]
        current_facts['journal_start'] = struct.unpack_from('>I', volume, journal_offset + 28)[0]
        current_facts['seed_inode_sha256'] = hashlib.sha256(volume[seed['byte_offset']:seed['byte_offset'] + 256]).hexdigest()
        if current_facts['feature_masks'] != [4, 0x42, 0x400] or current_facts['journal_start'] != 0:
            raise ValueError('prepared image is not clean')
        (out / 'facts.json').write_text(json.dumps(current_facts, indent=2, sort_keys=True) + '\n')
        report.update(status='passed', volume_sha256=sha(image), guarded_sha256=sha(guarded),
                      facts_sha256=sha(out / 'facts.json'), header_sha256=sha(out / 'journalled_mode_fixture.hpp'))
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        save()
        raise
    save()
    print('PASS journalled mode image; offline preparation only', flush=True)


if __name__ == '__main__':
    main()

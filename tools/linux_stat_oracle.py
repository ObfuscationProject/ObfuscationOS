"""Independent raw ext4/statx oracle for explicit SDK31 user fixture policies."""
import re
import struct
from linux_stat_image import ABSENT_PATHS, CONTENT, EPOCHS, HOLE_SIZE, Image, NANOSECONDS, PATHS


ARCH_ENDIAN = {'i386': '<', 'x86_64': '<', 'aarch64': '<', 'arm32': '<', 'rv32': '<',
               'rv64': '<', 'loongarch64': '<', 'mips': '>', 'mips64': '>', 'ppc': '>'}
SNAPSHOT = re.compile(r'LINUX_STAT_SNAPSHOT name=([a-z]+) hex=([0-9a-f]{512})')


def decode_statx(data, arch):
    if arch not in ARCH_ENDIAN or len(data) != 256:
        raise ValueError('statx architecture/size mismatch')
    endian = ARCH_ENDIAN[arch]
    def u16(at): return struct.unpack_from(endian + 'H', data, at)[0]
    def u32(at): return struct.unpack_from(endian + 'I', data, at)[0]
    def u64(at): return struct.unpack_from(endian + 'Q', data, at)[0]
    def time(at):
        seconds, nanos, padding = struct.unpack_from(endian + 'qII', data, at)
        if nanos >= 1000000000 or padding:
            raise ValueError('invalid statx timestamp')
        return seconds, nanos
    if (u32(0) != 0x7ff or u64(8) or data[30:32] != bytes(2) or u64(56) or
            data[80:96] != bytes(16) or u32(128) or u32(132) or data[144:] != bytes(112)):
        raise ValueError('statx capability/padding contract mismatch')
    device = u32(136), u32(140)
    if device == (0, 0):
        raise ValueError('missing statx device identity')
    result = {'inode': u64(32), 'mode': u16(28), 'uid': u32(20), 'gid': u32(24),
              'nlink': u32(16), 'size': u64(40), 'blocks': u64(48), 'blksize': u32(4),
              'times': {'atime': time(64), 'mtime': time(112), 'ctime': time(96)}, 'device': device}
    if not result['inode'] or result['size'] > 0x7fffffffffffffff or result['blocks'] > 0x7fffffffffffffff:
        raise ValueError('invalid statx inode/size/blocks')
    return result


def fixture_nodes(raw, policy, epoch):
    nodes = {label: raw.fields(raw.lookup(path)) for label, path in PATHS.items()}
    if nodes['file']['inode'] != nodes['alias']['inode'] or len({n['inode'] for n in nodes.values()}) != 8:
        raise ValueError('unexpected fixture inode/hardlink identity')
    for label, node in nodes.items():
        mode = 0x4000 | 0o700 if label == 'directory' else (0xa000 | 0o777 if label in ('link', 'dangling', 'loop') else 0x8000 | 0o600)
        links = 2 if label in ('file', 'alias', 'directory') else 1
        if node['mode'] != mode or node['uid'] != 1000 or node['gid'] != 1000 or node['nlink'] != links:
            raise ValueError('raw fixture mode/owner/link mismatch: ' + label)
        if policy in ('readonly', 'unqualified'):
            if any(value != (epoch, NANOSECONDS) for value in node['times'].values()):
                raise ValueError('seeded timestamp changed: ' + label)
        else:
            if any(seconds < epoch or seconds > epoch + 300 for seconds, _ in node['times'].values()):
                raise ValueError('maintained timestamp outside execution epoch: ' + label)
    for label, expected in (('file', CONTENT), ('alias', CONTENT), ('empty', b''), ('child', b''),
                            ('hole', bytes(HOLE_SIZE)), ('link', b'stat-file'),
                            ('dangling', b'stat-missing'), ('loop', b'stat-loop')):
        if raw.content(nodes[label]['inode']) != expected:
            raise ValueError('raw fixture content mismatch: ' + label)
    for label in ('empty', 'hole', 'child', 'link', 'dangling', 'loop'):
        if nodes[label]['blocks'] != 0:
            raise ValueError('unexpected allocation in empty/hole/fast-link: ' + label)
    if nodes['file']['blocks'] != raw.block // 512 or nodes['directory']['blocks'] != raw.block // 512:
        raise ValueError('unexpected regular/directory allocation')
    entries = raw.children(nodes['directory']['inode'])
    if {name: number for name, number in entries.items() if name not in ('.', '..')} != {'child': nodes['child']['inode']}:
        raise ValueError('unexpected fixture directory entries')
    for path in ABSENT_PATHS:
        try: raw.lookup(path)
        except KeyError: pass
        else: raise ValueError('removed or missing pathname unexpectedly exists: ' + path)
    return nodes


def validate(text, initial_bytes, final_bytes, arch, policy, epoch):
    if arch not in ARCH_ENDIAN or policy not in ('maintained', 'readonly', 'unqualified') or epoch not in EPOCHS:
        raise ValueError('invalid explicit fixture identity')
    if '_FAIL' in text:
        raise ValueError('guest failure marker')
    initial, final = Image(initial_bytes), Image(final_bytes)
    if (initial.block, initial.stride, initial.blocks, initial.inodes) != (final.block, final.stride, final.blocks, final.inodes):
        raise ValueError('raw filesystem geometry changed')
    epoch_label = 'negative' if epoch < 0 else 'post2038'
    lines = text.splitlines()
    if policy in ('readonly', 'unqualified'):
        if initial_bytes != final_bytes:
            raise ValueError('control image bytes changed')
        marker = 'LINUX_STAT_CONTROLS_NATIVE_PASS authority=uid1000 native-stat=pass mutations=none'
        if lines.count(marker) != 1:
            raise ValueError('missing native control execution marker')
        pattern = re.compile(r'LINUX_STAT_CONTROLS_MUSL_PASS mode=' + policy + r' epoch=' + epoch_label + r' checks=([1-9][0-9]*)')
        if sum(bool(pattern.fullmatch(line)) for line in lines) != 1:
            raise ValueError('missing musl control execution marker')
    else:
        native = 'LINUX_STAT_NATIVE_PASS authority=uid1000 held-fd=10 renamed-dir-fd=11 cwd=detached'
        expected_kernel_stat = 1 if arch in ('x86_64', 'aarch64', 'rv64') else 0
        pattern = re.compile(r'LINUX_STAT_MUSL_PASS checks=([1-9][0-9]*) epoch=' + epoch_label +
                             r' kernel-stat=' + str(expected_kernel_stat) + r' statx-size=256')
        if lines.count(native) != 1 or sum(bool(pattern.fullmatch(line)) for line in lines) != 1:
            raise ValueError('missing dedicated user execution markers')
        for path in PATHS.values():
            try: initial.lookup(path)
            except KeyError: pass
            else: raise ValueError('maintained fixture was not initially absent')
    nodes = fixture_nodes(final, policy, epoch)
    snapshots = {}
    for line in lines:
        if not line.startswith('LINUX_STAT_SNAPSHOT'):
            continue
        match = SNAPSHOT.fullmatch(line)
        if match is None:
            raise ValueError('malformed statx snapshot log')
        name, encoded = match.groups()
        if name not in PATHS or name in snapshots:
            raise ValueError('unknown or duplicate statx snapshot')
        snapshots[name] = decode_statx(bytes.fromhex(encoded), arch)
    if policy == 'unqualified':
        if snapshots:
            raise ValueError('unqualified control unexpectedly projected statx')
    else:
        if set(snapshots) != set(PATHS):
            raise ValueError('incomplete final statx snapshot set')
        devices = {value['device'] for value in snapshots.values()}
        if len(devices) != 1:
            raise ValueError('same-filesystem device identity differs')
        for label, value in snapshots.items():
            expected = nodes[label]
            for key in ('inode', 'mode', 'uid', 'gid', 'nlink', 'size', 'blocks', 'blksize', 'times'):
                if value[key] != expected[key]:
                    raise ValueError('statx/raw inode mismatch: ' + label + '/' + key)
    return {'policy': policy, 'architecture': arch, 'epoch': epoch, 'snapshot_count': len(snapshots),
            'raw_nodes': nodes, 'device_identity_scope': 'nonzero and same across one mount; device identity is not stored by ext4',
            'linux_stat': 'refused-unqualified' if policy == 'unqualified' else 'qualified',
            'initial_image_unchanged': initial_bytes == final_bytes,
            'oracle': 'independent raw ext4 fields and exact target-endian statx bytes',
            'held_cwd_scope': 'dedicated user checks only; unlinked objects are released before final image inspection'}

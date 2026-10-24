"""Strict independent serial and raw-disk oracle for native maintained ext4."""
from __future__ import annotations
import struct

MARKER = 'EXT4_TIMESTAMPS_PASS scope=privileged-device-provider'
CREATES = ('create-left', 'create-right', 'create-file', 'create-inline', 'create-block-link',
           'create-victim', 'create-sub', 'create-dir-victim', 'create-orphan', 'create-rmdir')
EXPECTED = {name: {'parent': 6, 'child': 7} for name in CREATES}
EXPECTED.update({name: {'target': 6} for name in ('write', 'write-identical', 'write-sparse',
    'truncate-same', 'truncate-grow', 'truncate-shrink', 'truncate-zero', 'truncate-zero-again', 'write-restore')})
EXPECTED.update({name: {'target': 4} for name in ('chmod-equal', 'chmod', 'chown-equal', 'chown', 'backward')})
EXPECTED.update({name: {'target': 1} for name in ('read', 'read-eof', 'read-inline', 'read-block-link')})
EXPECTED.update({
    'write-empty': {'target': 0}, 'read-zero': {'target': 0},
    'link': {'parent': 6, 'source': 4}, 'unlink-retained': {'parent': 6, 'victim': 4},
    'rename-hardlink-noop': {'old': 0, 'new': 0, 'source': 0},
    'rename-same-inode': {'parent': 0, 'source': 0}, 'rename-same-parent': {'parent': 6, 'source': 4},
    'rename-cross-parent': {'old': 6, 'new': 6, 'source': 4},
    'rename-replace': {'parent': 6, 'source': 4, 'victim': 4},
    'release-replaced': {'parent': 0, 'source': 0},
    'move-directory': {'old': 6, 'new': 6, 'source': 4},
    'replace-directory': {'parent': 6, 'source': 4, 'victim': 4},
    'release-directory': {'parent': 0, 'source': 0},
    'list-access': {'directory': 1, 'child': 0}, 'list-inspection': {'directory': 0},
    'list-empty': {'directory': 1}, 'rmdir-nonempty': {'parent': 0, 'victim': 0},
    'metadata-lookup': {'parent': 0, 'target': 0}, 'remove-orphan': {'parent': 6, 'victim': 4},
    'close-orphan': {'parent': 0, 'file': 0}, 'rmdir-retained': {'parent': 6, 'victim': 4},
    'close-removed-directory': {'parent': 0}, 'close-linked': {'target': 0},
    'sync': {'root': 0, 'file': 0},
})
NO_WRITES = {'write-empty', 'read-zero', 'rename-hardlink-noop', 'rename-same-inode',
             'list-inspection', 'rmdir-nonempty', 'metadata-lookup', 'close-linked'}
FINAL_PATHS = {'/', '/left', '/right', '/right/victim', '/left/short', '/left/long', '/right/dst'}


def fields(line):
    output = {}
    for token in line.split()[1:]:
        if token.count('=') != 1:
            raise ValueError('malformed timestamp token')
        key, value = token.split('=')
        if not key or not value or key in output:
            raise ValueError('empty or duplicate timestamp field')
        output[key] = value
    return output


def integer(record, key):
    value = record[key]
    if not value.isascii() or not value.isdecimal() or (len(value) > 1 and value[0] == '0'):
        raise ValueError('noncanonical timestamp integer: ' + key)
    return int(value)


def triple(record, prefix, source):
    result = []
    for name in 'amc':
        seconds, nanos = integer(record, prefix + name + '_sec'), integer(record, prefix + name + '_ns')
        if nanos >= 1000000000 or integer(record, prefix + name + '_source') != source:
            raise ValueError('timestamp precision or provenance')
        result.append((seconds, nanos))
    return result


def validate_serial(text, inode_size):
    if inode_size not in (128, 256) or text.splitlines().count(MARKER) != 1 or 'EXT4_TIMESTAMPS_FAIL' in text:
        raise ValueError('failed/incomplete maintained native fixture')
    events, participants, finals, scopes = {}, {}, {}, []
    for line in text.splitlines():
        if line.startswith('EXT4_TIME_EVENT '):
            item = fields(line); name = item.pop('name')
            if name in events:
                raise ValueError('duplicate event')
            events[name] = item
        elif line.startswith('EXT4_TIME_INODE '):
            item = fields(line); key = item.pop('event'), item.pop('role')
            if key in participants:
                raise ValueError('duplicate participant')
            participants[key] = item
        elif line.startswith('EXT4_TIME_FINAL '):
            item = fields(line); name = item.pop('path')
            if name in finals:
                raise ValueError('duplicate final inode')
            finals[name] = item
        elif line.startswith('EXT4_TIME_SCOPE '):
            scopes.append(fields(line))
    expected = {**EXPECTED, 'post2038': {'target': 0 if inode_size == 128 else 6}}
    if set(events) != set(expected) or set(participants) != {(name, role) for name, roles in expected.items() for role in roles}:
        raise ValueError('incomplete event or participant inventory')
    if set(finals) != FINAL_PATHS or len(scopes) != 1:
        raise ValueError('final inode/scope inventory')
    scope = scopes[0]
    if any(scope.get(k) != v for k, v in {'origin': 'administrator-software', 'public-user': '0',
            'clock-loss': 'hosted-only', 'physical': '0', 'smp': '0'}.items()):
        raise ValueError('overstated native scope')
    if integer(scope, 'events') != len(expected) or not all(integer(scope, k) for k in ('reads', 'writes', 'flushes')):
        raise ValueError('event or device counts')
    previous_mono, previous_generation, mono_generation = -1, -1, None
    latest = {}
    changed = 0
    for name, event in events.items():
        keys = {'status', 'writes', 'no_writes', 'before_sec', 'before_ns', 'after_sec', 'after_ns',
                'before_mono', 'after_mono', 'wall_generation', 'mono_generation', 'origin'}
        if set(event) != keys or event['origin'] != 'administrator-software':
            raise ValueError('event record schema')
        wanted = 'busy' if name == 'rmdir-nonempty' else 'overflow' if name == 'post2038' and inode_size == 128 else 'ok'
        if event['status'] != wanted:
            raise ValueError('wrong event result')
        before_mono, after_mono = integer(event, 'before_mono'), integer(event, 'after_mono')
        if before_mono < previous_mono or after_mono < before_mono or integer(event, 'wall_generation') <= previous_generation:
            raise ValueError('clock bracket continuity')
        if previous_generation != -1 and integer(event, 'wall_generation') != previous_generation + 1:
            raise ValueError('unexpected extra software clock selection')
        previous_mono, previous_generation = after_mono, integer(event, 'wall_generation')
        if mono_generation is None: mono_generation = integer(event, 'mono_generation')
        elif mono_generation != integer(event, 'mono_generation'): raise ValueError('monotonic generation changed')
        if integer(event, 'mono_generation') <= 0:
            raise ValueError('invalid monotonic generation')
        low = integer(event, 'before_sec') * 10**9 + integer(event, 'before_ns')
        high = integer(event, 'after_sec') * 10**9 + integer(event, 'after_ns')
        if integer(event, 'before_ns') >= 10**9 or integer(event, 'after_ns') >= 10**9 or high - low != after_mono - before_mono:
            raise ValueError('software wall/monotonic equation')
        no_writes = name in NO_WRITES or (name == 'post2038' and inode_size == 128)
        if integer(event, 'no_writes') != no_writes or (no_writes and integer(event, 'writes')):
            raise ValueError('no-event/refused operation wrote')
        if inode_size == 128:
            low, high = low // 10**9 * 10**9, high // 10**9 * 10**9
        selected = set()
        for role, mask in expected[name].items():
            record = participants[name, role]
            wanted_keys = {'inode', 'mask', 'created'} | {prefix + f + '_' + suffix for prefix in ('before_', 'after_') for f in 'amc' for suffix in ('sec', 'ns', 'source')}
            if set(record) != wanted_keys: raise ValueError('participant record schema')
            created = name in CREATES and role == 'child'
            if integer(record, 'mask') != mask or integer(record, 'created') != created or not integer(record, 'inode'):
                raise ValueError('participant identity/mask')
            old = triple(record, 'before_', 0 if created else 2)
            new = triple(record, 'after_', 2)
            previous = latest.get(integer(record, 'inode'))
            if not created and previous is not None and old != previous:
                raise ValueError('participant history changed outside recorded events')
            if created and any(seconds or nanos for seconds, nanos in old):
                raise ValueError('new participant has invented prior times')
            for index in range(3):
                if mask & (1 << index):
                    ns = new[index][0] * 10**9 + new[index][1]
                    if not low <= ns <= high or (inode_size == 128 and new[index][1]):
                        raise ValueError('stored time outside actual clock bracket')
                    selected.add(new[index]); changed += 1
                elif new[index] != old[index]:
                    raise ValueError('unselected inode time changed')
            latest[integer(record, 'inode')] = new
        if len(selected) > 1:
            raise ValueError('multiple operation samples on equally precise fields')
    for path, record in finals.items():
        if set(record) != {'inode', 'reopened'} | {f + '_' + suffix for f in 'amc' for suffix in ('sec', 'ns', 'source')}:
            raise ValueError('final record schema')
        value = triple(record, '', 2)
        if integer(record, 'reopened') != 1 or latest.get(integer(record, 'inode')) != value:
            raise ValueError('final/reopened record differs from latest event')
    if sum(integer(e, 'writes') for e in events.values()) != integer(scope, 'writes'):
        raise ValueError('unaccounted device writes')
    if integer(events['post2038'], 'before_sec') < 2208988800 or integer(events['backward'], 'before_sec') >= 2147483648:
        raise ValueError('missing explicit 2040/backward transition')
    return {'events': events, 'participants': {name + '/' + role: row for (name, role), row in participants.items()},
            'finals': finals, 'scope': scope, 'event_count': len(events), 'selected_field_brackets': changed}


def inspect_image(raw, evidence, block_size, inode_size):
    def u16(at): return struct.unpack_from('<H', raw, at)[0]
    def u32(at): return struct.unpack_from('<I', raw, at)[0]
    if u16(1080) != 0xef53 or 1024 << u32(1048) != block_size or u16(1112) != inode_size or u16(1082) != 1:
        raise ValueError('final ext4 geometry or clean marker')
    def inode(number):
        group, index = divmod(number - 1, u32(1064))
        table = u32((u32(1044) + 1) * block_size + group * 32 + 8)
        at = table * block_size + index * inode_size
        if number <= 0 or at + inode_size > len(raw): raise ValueError('inode extent outside disk')
        return at
    def listing(number):
        at = inode(number)
        if u16(at) & 0xf000 != 0x4000 or u16(at + 40) != 0xf30a or u16(at + 46) != 0 or u16(at + 42) > 4:
            raise ValueError('unsupported native fixture directory')
        entries = {}
        for slot in range(u16(at + 42)):
            extent = at + 52 + slot * 12
            logical, length, high, physical = u32(extent), u16(extent + 4), u16(extent + 6), u32(extent + 8)
            if high or not length or length > 32768: raise ValueError('unsupported directory extent')
            for block in range(physical, physical + length):
                pos, end = block * block_size, (block + 1) * block_size
                if end > len(raw): raise ValueError('directory beyond disk')
                while pos < end:
                    number, size, namesize = u32(pos), u16(pos + 4), raw[pos + 6]
                    if size < 8 or size % 4 or pos + size > end or namesize > size - 8:
                        raise ValueError('malformed directory entry')
                    if number:
                        name = raw[pos + 8:pos + 8 + namesize].decode('ascii')
                        if name in entries: raise ValueError('duplicate directory entry')
                        entries[name] = number
                    pos += size
        return entries
    def resolve(path):
        number = 2
        for component in path.split('/'):
            if component: number = listing(number)[component]
        return number
    checked = {}
    for path, record in evidence['finals'].items():
        number = resolve(path)
        if number != integer(record, 'inode'): raise ValueError('final inode differs from namespace')
        at = inode(number); extra_size = u16(at + 128) if inode_size == 256 else 0
        if extra_size % 4 or extra_size > inode_size - 128 or (inode_size == 256 and path != '/' and extra_size != 16):
            raise ValueError('new inode extra extent is not exactly16')
        decoded = []
        for base, extra in ((8, 140), (16, 136), (12, 132)):
            seconds = struct.unpack_from('<i', raw, at + base)[0]
            extension = u32(at + extra) if extra + 4 <= 128 + extra_size else 0
            nanos = extension >> 2
            if nanos >= 10**9: raise ValueError('malformed stored nanoseconds')
            decoded.append((seconds + (extension & 3) * 4294967296, nanos))
        if decoded != triple(record, '', 2): raise ValueError('raw/provider timestamp mismatch')
        checked[path] = {'inode': number, 'offset': at, 'extra_isize': extra_size, 'times': decoded,
                         'mode': u16(at), 'uid': u16(at + 2) | u16(at + 120) << 16,
                         'gid': u16(at + 24) | u16(at + 122) << 16, 'links': u16(at + 26)}
    root, left, right, moved = (listing(resolve(p)) for p in ('/', '/left', '/right', '/right/dst'))
    if set(root) != {'.', '..', 'lost+found', 'left', 'right'} or set(left) != {'.', '..', 'short', 'long'} or set(right) != {'.', '..', 'victim', 'dst'} or set(moved) != {'.', '..'}:
        raise ValueError('final namespace/reclamation mismatch')
    if moved['..'] != resolve('/right') or checked['/']['links'] != 5 or checked['/left']['links'] != 2 or checked['/right']['links'] != 3:
        raise ValueError('directory move dotdot/link count mismatch')
    if (checked['/right/victim']['mode'], checked['/right/victim']['uid'], checked['/right/victim']['gid']) != (0o100600, 0x12345678, 0x87654321):
        raise ValueError('mode/owner persistence mismatch')
    def content(path):
        at = inode(resolve(path)); size = u32(at + 4)
        if u16(at) & 0xf000 == 0xa000 and size < 60: return raw[at + 40:at + 40 + size]
        if u16(at + 40) != 0xf30a or u16(at + 46): raise ValueError('unsupported final file extent')
        data = bytearray(size)
        for slot in range(u16(at + 42)):
            extent = at + 52 + slot * 12
            logical, length, high, physical = u32(extent), u16(extent + 4), u16(extent + 6), u32(extent + 8)
            if high or not length or length > 32768: raise ValueError('unsupported file extent')
            begin = logical * block_size
            amount = min(length * block_size, max(0, size - begin))
            data[begin:begin + amount] = raw[physical * block_size:physical * block_size + amount]
        return bytes(data)
    expected_data = {'/right/victim': b'abcdef', '/left/short': b'file',
                     '/left/long': b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-long-target'}
    for path, wanted in expected_data.items():
        if content(path) != wanted or checked[path]['links'] != 1: raise ValueError('persisted content/link mismatch')
    return checked

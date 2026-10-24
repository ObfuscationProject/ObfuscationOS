"""Verify actual guest operation records against independent complete disk oracles.

Calling this parser with synthetic records is a model test, not guest execution.
The outer runner must additionally bind SDK, ELF, QEMU process and final exit.
"""
import re
import struct
from admit_linux_fixture import checksum
from journalled_mode_image import extract_volume, inode_metadata
from journalled_directory_transaction import expected as transaction

NUMBER = r'(0|[1-9][0-9]*)'
PATTERNS = {
    'begin': re.compile(r'JDMODE_OP_BEGIN ordinal=' + NUMBER + r' name=([a-z0-9-]+)'),
    'end': re.compile(r'JDMODE_OP_END ordinal=' + NUMBER + r' mutation=([01])'),
    'write': re.compile(r'JDMODE_IO ordinal=' + NUMBER + r' kind=write sector=' + NUMBER +
                        r' bytes=' + NUMBER + r' crc32c=' + NUMBER + r' status=0'),
    'flush': re.compile(r'JDMODE_IO ordinal=' + NUMBER + r' kind=flush sector=0 bytes=0 crc32c=0 status=0'),
    'inode': re.compile(r'JDMODE_INODE io=' + NUMBER + r' inode=' + NUMBER + r' mode=' + NUMBER +
                        r' uid=' + NUMBER + r' gid=' + NUMBER + r' ctime_sec=' + NUMBER +
                        r' ctime_nsec=' + NUMBER + r' version=' + NUMBER),
    'fixture_begin': re.compile(r'JDMODE_FIXTURE_BEGIN scope=actual-musl-user-mode sdk=31 sdk-only=1 uid=' + NUMBER + r' clock=(in-range|negative)'),
    'storage': re.compile(r'JDMODE_STORAGE virtio=1 policy=maintained-noatime aliases=2 root=archive clock=administrator-software'),
    'credentials': re.compile(r'JDMODE_CREDENTIALS uid=' + NUMBER + r' euid=' + NUMBER + r' gid=' + NUMBER +
                              r' egid=' + NUMBER + r' before-entry=1 personality=linux'),
    'fixture_pass': re.compile(r'JDMODE_FIXTURE_PASS uid=' + NUMBER + r' exit=0 reaped=1 personality=linux epoch=' +
                               NUMBER + r' writes=' + NUMBER + r' flushes=' + NUMBER),
    'user_begin': re.compile(r'JDMODE_USER_BEGIN uid=' + NUMBER + r' sdk=31 scope=actual-musl-syscalls'),
    'user_pass': re.compile(r'JDMODE_USER_PASS uid=' + NUMBER + r' operations=' + NUMBER + r' checks=' + NUMBER),
    'snapshot': re.compile(r'LINUX_CHMOD_SNAPSHOT name=journal-child hex=([0-9a-f]{512})'),
}
ARCHES = {'x86_64', 'i386', 'aarch64', 'arm32', 'rv64', 'rv32', 'loongarch64', 'mips', 'mips64', 'ppc'}


def require(value, message):
    if not value:
        raise ValueError(message)


def expected_operations(uid, negative_clock=False):
    require(uid in (0, 1000), 'fixture credential domain')
    tail = [('unsupported-root', None, 0), ('unsupported-symlink', None, 0),
            ('fsync', None, 0), ('stale-fd', None, 0)]
    if uid:
        tail.insert(0, ('other-owner', None, 0))
    if negative_clock:
        require(uid == 0, 'negative fixture credential domain')
        return [('ctime-negative', None, 0)] + tail
    operations = [('chmod', 'child', 0o2750), ('same-mode', 'child', 0o2750),
                  ('remove-search', 'child', 0), ('search-permission', None, 0),
                  ('retained-fd-restore', 'child', 0o755),
                  ('fchmodat-relative', 'child', 0o1750),
                  ('fork-retained-fd', 'child', 0o700)]
    if not uid:
        operations += [('ctime-post2038', None, 0)]
    return operations + tail


def records(text):
    result = []
    if text and not text.endswith('\n'):
        tail = text.rsplit('\n', 1)[-1]
        require(not any(token in tail for token in ('JDMODE_', 'LINUX_CHMOD_SNAPSHOT')),
                'unterminated journalled protocol record')
    for position, line in enumerate(text.replace('\r\n', '\n').splitlines()):
        matched = False
        for kind, pattern in PATTERNS.items():
            match = pattern.fullmatch(line)
            if match:
                values = match.groups()
                if kind not in ('begin', 'fixture_begin', 'snapshot'):
                    values = tuple(map(int, values))
                elif kind in ('begin', 'fixture_begin'):
                    values = (int(values[0]), values[1])
                result.append(dict(kind=kind, values=values, position=position, raw=line))
                matched = True
                break
        if not matched:
            require(not any(token in line for token in ('JDMODE_', 'LINUX_CHMOD_SNAPSHOT')),
                    'unknown/malformed journalled record: ' + line)
    return result


def transaction_io(before, facts, number, mode, seconds, nanos):
    old = inode_metadata(before, number)
    published, complete = transaction(before, facts, number, old['uid'], old['gid'], seconds, nanos, mode)
    j, block = facts['journal_first'], old['block']
    def write(which, data):
        payload = data[which * 1024:(which + 1) * 1024]
        return ('write', facts['origin'] + which * 2, 1024, checksum(0xffffffff, payload))
    # Journal publication followed by recovery/checkpoint. Each FLUSH is an
    # actual transport completion; the phase split alone is not durability.
    io = [('flush',), write(j + 1, published), write(j + 2, published), write(j + 3, published),
          write(j + 5, published), ('flush',), write(j + 4, published), ('flush',),
          write(1, published), ('flush',), write(j, published), ('flush',), ('flush',),
          write(1, published), write(block, complete), ('flush',), write(j, complete),
          ('flush',), write(1, complete), ('flush',)]
    require(sum(item[0] == 'write' for item in io) == 11 and len(io) == 20, 'oracle transaction shape')
    return io, complete, inode_metadata(complete, number)


def verify_operations(text, initial, final_guarded, facts, uid, arch, negative_clock=False):
    require(arch in ARCHES, 'architecture domain')
    require(len(initial) == 32 * 1024 * 1024, 'initial image size')
    require(facts['journal_start'] == 0 and facts['feature_masks'] == [4, 0x42, 0x400], 'initial clean profile')
    # A private Linux ELF entry must have exactly one complete loader record.
    loader_pattern = re.compile(r'OK_NATIVE_IMAGE personality=linux source=(firmware|linker) pages=([1-9][0-9]*) physical_first=(0x[0-9a-f]{16}) physical_last=(0x[0-9a-f]{16}) owner=retained\r?\n')
    loader_lines = [line for line in text.splitlines(keepends=True) if 'OK_NATIVE_IMAGE' in line]
    require(len(loader_lines) == 1, 'unique Linux loader marker')
    loader = loader_pattern.fullmatch(loader_lines[0])
    require(loader is not None, 'complete Linux loader marker grammar')
    pages, first, last = int(loader[2]), int(loader[3], 16), int(loader[4], 16)
    require(loader[1] == ('linker' if arch in ('mips', 'mips64', 'loongarch64') else 'firmware') and
            pages > 0 and first % 4096 == last % 4096 == 0 and last >= first,
            'Linux loader page range')
    native_lines = text.splitlines(keepends=True)
    loaded = [i for i, line in enumerate(native_lines) if 'OK_NATIVE scope=hardware init=' in line]
    require(len(loaded) == 1 and re.fullmatch(r'OK_NATIVE scope=hardware init=loaded\r?\n',
            native_lines[loaded[0]]) is not None, 'complete Linux loaded marker')
    image_position = native_lines.index(loader_lines[0])
    rows = records(text)
    require(len(rows) >= 5 and [row['kind'] for row in rows[:4]] ==
            ['fixture_begin', 'storage', 'credentials', 'user_begin'], 'fixture/user entry order')
    require(rows[0]['values'] == (uid, 'negative' if negative_clock else 'in-range') and rows[2]['values'] == (uid, uid, uid, uid) and
            rows[3]['values'] == (uid,), 'fixture/user credential binding')
    require(sum(row['kind'] == 'user_begin' for row in rows) == 1, 'duplicate user begin')
    require(rows[1]['position'] < image_position < loaded[0] < rows[2]['position'], 'Linux entry ordering')
    operations = expected_operations(uid, negative_clock)
    cursor, io_ordinal, current = 4, 0, initial
    results = []
    total_writes = total_flushes = mutations = 0
    for ordinal, (name, label, mode) in enumerate(operations, 1):
        require(cursor < len(rows) and rows[cursor]['kind'] == 'begin' and
                rows[cursor]['values'] == (ordinal, name), 'operation start/order: ' + name)
        cursor += 1
        transport, inodes = [], []
        while cursor < len(rows) and rows[cursor]['kind'] != 'end':
            row = rows[cursor]
            require(row['kind'] in ('write', 'flush', 'inode'), 'unexpected event in operation: ' + name)
            values = row['values']
            if row['kind'] == 'inode':
                require(values[0] == io_ordinal and transport and transport[-1][0] == 'write', 'inode/write pairing')
                require(cursor and rows[cursor - 1]['kind'] == 'write' and
                        rows[cursor - 1]['position'] + 1 == row['position'], 'nonadjacent inode record')
                require(label is not None, 'unexpected inode for nonmutating operation')
                target = facts['nodes'][label]
                require(values[1] == target['inode'] and len(transport) == 15 and
                        transport[-1][1:3] == (facts['origin'] + target['block'] * 2, 1024),
                        'inode observation is not attached to its home write')
                inodes.append(values)
            else:
                io_ordinal += 1
                require(values[0] == io_ordinal, 'transport ordinal gap/reuse')
                transport.append((row['kind'], *values[1:]))
                if row['kind'] == 'write':
                    total_writes += 1
                    require(values[2] == 1024 and 0 <= values[3] < 2 ** 32, 'write/CRC domain')
                else:
                    total_flushes += 1
            cursor += 1
        require(cursor < len(rows) and rows[cursor]['values'] == (ordinal, int(label is not None)),
                'operation end/mutation: ' + name)
        cursor += 1
        if label:
            require(len(inodes) == 1, 'successful mutation needs one home inode record')
            _, number, actual_mode, owner, group, seconds, nanos, version = inodes[0]
            require(number == facts['nodes'][label]['inode'], 'wrong mutation target')
            require(1700000000 <= seconds < 1700003600 and 0 <= nanos < 1000000000, 'ctime outside guest clock window')
            expected_io, complete, metadata = transaction_io(current, facts, number, mode, seconds, nanos)
            require(transport == expected_io, 'write bytes/FLUSH ordering differs: ' + name)
            require((actual_mode, owner, group, version) ==
                    (metadata['mode'], metadata['uid'], metadata['gid'], metadata['version']), 'committed inode identity')
            current = complete
            mutations += 1
        else:
            require(not inodes, 'unexpected inode mutation')
            require(transport == ([('flush',), ('flush',)] if name == 'fsync' else []),
                    'unexpected I/O for nonmutating operation: ' + name)
        results.append(dict(ordinal=ordinal, name=name, mutation=label is not None,
                            writes=sum(item[0] == 'write' for item in transport),
                            flushes=sum(item[0] == 'flush' for item in transport)))
    require(cursor < len(rows) and rows[cursor]['kind'] == 'snapshot', 'final statx snapshot absent')
    snapshot = bytes.fromhex(rows[cursor]['values'][0])
    cursor += 1
    require(cursor < len(rows) and rows[cursor]['kind'] == 'user_pass', 'user pass absent')
    passed_uid, count, checks = rows[cursor]['values']
    require((passed_uid, count) == (uid, len(operations)) and checks >= (4100 if negative_clock else 16400), 'user pass accounting')
    cursor += 1
    require(cursor + 1 == len(rows) and rows[cursor]['kind'] == 'fixture_pass' and
            rows[cursor]['values'] == (uid, mutations + 1, total_writes, total_flushes),
            'final runtime exit/reap/mount/transport accounting')
    byte_order = '>' if arch in ('mips', 'mips64', 'ppc') else '<'
    seed = inode_metadata(current, facts['nodes']['child']['inode'])
    expected_snapshot = bytearray(256)
    for offset, fmt, value in [(0, 'I', 0x7ff), (4, 'I', 1024), (16, 'I', seed['links']),
                               (20, 'I', seed['uid']), (24, 'I', seed['gid']), (28, 'H', seed['mode']),
                               (32, 'Q', seed['inode']), (40, 'Q', seed['size']), (48, 'Q', seed['blocks512']),
                               (136, 'I', 0), (140, 'I', 2)]:
        struct.pack_into(byte_order + fmt, expected_snapshot, offset, value)
    for field, offset in [('atime', 64), ('ctime', 96), ('mtime', 112)]:
        struct.pack_into(byte_order + 'qI', expected_snapshot, offset,
                         seed[field]['seconds'], seed[field]['nanoseconds'])
    require(snapshot == expected_snapshot, 'complete statx wire image differs')
    require(extract_volume(final_guarded) == current, 'complete final disk differs from independent oracle')
    return dict(operations=results, mutations=mutations, writes=total_writes, flushes=total_flushes,
                checks=checks, final_volume=current, scope='parsed records and disk oracle; runner binds execution')

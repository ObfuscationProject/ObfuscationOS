"""Independent ext4/JBD2 oracle for one bounded ordered-data file update."""
import struct
from admit_linux_fixture import checksum
from journalled_mode_image import inode_metadata


def expected(clean, facts, operation, ctime_seconds, ctime_nanoseconds,
             mtime_seconds, mtime_nanoseconds):
    number = facts['nodes']['seed']['inode']
    original = inode_metadata(clean, number)
    if (original['mode'], original['uid'], original['gid'], original['blocks512']) != \
            (0o100600, 1000, 1001, 8):
        raise ValueError('ordered data seed inode identity changed')
    if not all(1700000000 <= seconds < 1700003600 and 0 <= nanos < 1000000000
               for seconds, nanos in ((ctime_seconds, ctime_nanoseconds),
                                      (mtime_seconds, mtime_nanoseconds))):
        raise ValueError('ordered data timestamp outside guest clock')
    at = original['byte_offset']
    if struct.unpack_from('<HHHHI', clean, at + 40) != (0xf30a, 1, 4, 0, 0):
        raise ValueError('seed has no single initialized inline extent')
    logical, extent_length, high, low = struct.unpack_from('<IHHI', clean, at + 52)
    if logical != 0 or extent_length != 4 or high:
        raise ValueError('seed extent does not cover exactly four logical blocks')
    if operation == 'overwrite' and original['size'] == 4096:
        logical, start, payload, size = 0, 100, b'CODE', 4096
    elif operation == 'truncate' and original['size'] == 4096:
        logical, start, payload, size = 3, 4000, bytes(96), 4000
    elif operation == 'append' and original['size'] == 4000:
        logical, start, payload, size = 3, 4000, b'APPEN', 4005
    else:
        raise ValueError('unexpected ordered-data operation or prior size')
    data_block = low + logical
    if data_block >= facts['filesystem_blocks'] or any(
            first <= data_block < first + count for first, count in facts['metadata_ranges']):
        raise ValueError('data block aliases ext4 metadata')
    data = bytearray(clean)
    data[data_block * 1024 + start % 1024:data_block * 1024 + start % 1024 + len(payload)] = payload
    j = facts['journal_first'] * 1024
    table = struct.unpack_from('<I', clean, 2056)[0]
    at = table * 1024 + (number - 1) * 256
    block, offset = divmod(at, 1024)
    sequence = struct.unpack_from('>I', clean, j + 24)[0] + 1
    seed = checksum(0xffffffff, bytes.fromhex(facts['uuid']))
    data[j + 1024:j + 6144] = bytes(5120)
    data[j + 2048:j + 3072] = clean[1024:2048]
    struct.pack_into('<I', data, j + 2048 + 96, struct.unpack_from('<I', data, j + 2048 + 96)[0] | 4)
    struct.pack_into('<I', data, j + 2048 + 1020, checksum(0xffffffff, data[j + 2048:j + 3068]))
    data[j + 3072:j + 4096] = clean[block * 1024:(block + 1) * 1024]
    inode = j + 3072 + offset
    for at, value in [(0, original['mode']), (2, original['uid'] & 0xffff),
                      (24, original['gid'] & 0xffff), (120, original['uid'] >> 16),
                      (122, original['gid'] >> 16), (124, 0), (130, 0)]:
        struct.pack_into('<H', data, inode + at, value)
    struct.pack_into('<I', data, inode + 4, size)
    struct.pack_into('<I', data, inode + 12, ctime_seconds)
    struct.pack_into('<I', data, inode + 132, ctime_nanoseconds << 2)
    struct.pack_into('<I', data, inode + 16, mtime_seconds)
    struct.pack_into('<I', data, inode + 136, mtime_nanoseconds << 2)
    version = struct.unpack_from('<I', data, inode + 36)[0] | (struct.unpack_from('<I', data, inode + 152)[0] << 32)
    struct.pack_into('<I', data, inode + 36, (version + 1) & 0xffffffff)
    struct.pack_into('<I', data, inode + 152, (version + 1) >> 32)
    crc = checksum(checksum(seed, struct.pack('<I', number)), data[inode + 100:inode + 104])
    crc = checksum(crc, data[inode:inode + 256])
    struct.pack_into('<H', data, inode + 124, crc & 0xffff)
    struct.pack_into('<H', data, inode + 130, crc >> 16)
    for index, kind in [(1, 1), (4, 2)]:
        struct.pack_into('>III', data, j + index * 1024, 0xc03b3998, kind, sequence)
    escaped = data[j + 3072:j + 3076] == bytes.fromhex('c03b3998')
    if escaped: data[j + 3072:j + 3076] = bytes(4)
    for at, target, flags, payload in [(12, 1, 0, 2), (44, block, 11 if escaped else 10, 3)]:
        crc = checksum(checksum(seed, struct.pack('>I', sequence)), data[j + payload * 1024:j + (payload + 1) * 1024])
        struct.pack_into('>IIII', data, j + 1024 + at, target, flags, 0, crc)
    struct.pack_into('>I', data, j + 2044, checksum(seed, data[j + 1024:j + 2048]))
    struct.pack_into('>QI', data, j + 4096 + 48, ctime_seconds, ctime_nanoseconds)
    struct.pack_into('>I', data, j + 4096 + 16, checksum(seed, data[j + 4096:j + 5120]))
    data[1024:2048] = data[j + 2048:j + 3072]
    struct.pack_into('>II', data, j + 24, sequence, 1)
    struct.pack_into('>I', data, j + 252, 0)
    struct.pack_into('>I', data, j + 252, checksum(0xffffffff, data[j:j + 1024]))
    published = bytes(data)
    data[block * 1024:(block + 1) * 1024] = data[j + 3072:j + 4096]
    if escaped: data[block * 1024:block * 1024 + 4] = bytes.fromhex('c03b3998')
    struct.pack_into('<I', data, 1120, struct.unpack_from('<I', data, 1120)[0] & ~4)
    struct.pack_into('<I', data, 2044, checksum(0xffffffff, data[1024:2044]))
    struct.pack_into('>II', data, j + 24, sequence + 2, 0)
    struct.pack_into('>I', data, j + 252, 0)
    struct.pack_into('>I', data, j + 252, checksum(0xffffffff, data[j:j + 1024]))
    return published, bytes(data), data_block

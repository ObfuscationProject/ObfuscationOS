"""Independent libext2fs CRC oracle for the bounded metadata transaction fixture."""
import struct
from admit_linux_fixture import checksum
from test_completion import expected as clean_capture


def expected(clean, facts):
    data = bytearray(clean)
    j = facts['journal_first'] * 1024
    block = facts['seed_block']
    offset = facts['seed_offset']
    sequence = struct.unpack_from('>I', clean, j + 24)[0] + 1
    seed = checksum(0xffffffff, bytes.fromhex(facts['uuid']))
    data[j + 1024:j + 6144] = bytes(5120)
    data[j + 2048:j + 3072] = clean[1024:2048]
    struct.pack_into('<I', data, j + 2048 + 96, struct.unpack_from('<I', data, j + 2048 + 96)[0] | 4)
    struct.pack_into('<I', data, j + 2048 + 1020, checksum(0xffffffff, data[j + 2048:j + 3068]))
    data[j + 3072:j + 4096] = clean[block * 1024:(block + 1) * 1024]
    inode = j + 3072 + offset
    for at, value in [(0, 0o100640), (2, 2000), (24, 2001), (120, 0), (122, 0), (124, 0), (130, 0)]:
        struct.pack_into('<H', data, inode + at, value)
    struct.pack_into('<I', data, inode + 12, 1700000000)
    struct.pack_into('<I', data, inode + 132, 123456789 << 2)
    version = struct.unpack_from('<I', data, inode + 36)[0] | (struct.unpack_from('<I', data, inode + 152)[0] << 32)
    struct.pack_into('<I', data, inode + 36, (version + 1) & 0xffffffff)
    struct.pack_into('<I', data, inode + 152, (version + 1) >> 32)
    crc = checksum(checksum(seed, struct.pack('<I', facts['seed_inode'])), data[inode + 100:inode + 104])
    crc = checksum(crc, data[inode:inode + 256])
    struct.pack_into('<H', data, inode + 124, crc & 0xffff)
    struct.pack_into('<H', data, inode + 130, crc >> 16)
    for index, kind in [(1, 1), (4, 2)]:
        struct.pack_into('>III', data, j + index * 1024, 0xc03b3998, kind, sequence)
    for at, target, flags, payload in [(12, 1, 0, 2), (44, block, 10, 3)]:
        crc = checksum(checksum(seed, struct.pack('>I', sequence)), data[j + payload * 1024:j + (payload + 1) * 1024])
        struct.pack_into('>IIII', data, j + 1024 + at, target, flags, 0, crc)
    struct.pack_into('>I', data, j + 2044, checksum(seed, data[j + 1024:j + 2048]))
    struct.pack_into('>QI', data, j + 4096 + 48, 1700000000, 123456789)
    struct.pack_into('>I', data, j + 4096 + 16, checksum(seed, data[j + 4096:j + 5120]))
    data[1024:2048] = data[j + 2048:j + 3072]
    struct.pack_into('>II', data, j + 24, sequence, 1)
    struct.pack_into('>I', data, j + 252, 0)
    struct.pack_into('>I', data, j + 252, checksum(0xffffffff, data[j:j + 1024]))
    published = bytes(data)
    data[block * 1024:(block + 1) * 1024] = data[j + 3072:j + 4096]
    struct.pack_into('<I', data, 1120, struct.unpack_from('<I', data, 1120)[0] & ~4)
    struct.pack_into('<I', data, 2044, checksum(0xffffffff, data[1024:2044]))
    struct.pack_into('>II', data, j + 24, sequence + 2, 0)
    struct.pack_into('>I', data, j + 252, 0)
    struct.pack_into('>I', data, j + 252, checksum(0xffffffff, data[j:j + 1024]))
    return published, bytes(data)

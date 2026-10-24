"""Independent bounded ext4 fixture preparation; no mounted filesystem writes."""
from pathlib import Path
import os
import struct


EPOCHS = (2208988800, -123456789)
NANOSECONDS = 123456789
CONTENT = b'linux-stat-fixture'
HOLE_SIZE = 12305
PATHS = {
    'file': '/home/stat-file', 'alias': '/home/stat-alias',
    'link': '/home/stat-link', 'dangling': '/home/stat-dangling',
    'loop': '/home/stat-loop', 'empty': '/home/stat-empty',
    'hole': '/home/stat-hole', 'directory': '/home/stat-renamed-dir',
    'child': '/home/stat-renamed-dir/child',
}
ABSENT_PATHS = ('/home/stat-missing', '/home/stat-held', '/home/stat-dir', '/home/stat-cwd')


class Image:
    """Read ext4 fields independently of the kernel and Linux stat codecs."""
    def __init__(self, data):
        self.data = data
        if len(data) < 2048 or self.u16(1080) != 0xef53:
            raise ValueError('invalid ext4 superblock')
        # Validate before shifting: an untrusted exponent can allocate gigabytes.
        if self.u32(1048) != 2:
            raise ValueError('unsupported explicit ext4 block-size exponent')
        self.block = 4096
        self.stride = self.u16(1112)
        self.inodes = self.u32(1024)
        self.blocks = self.u32(1028)
        self.first = self.u32(1044)
        self.blocks_per_group = self.u32(1056)
        self.inodes_per_group = self.u32(1064)
        # Match the explicit mkext4 geometry; reject journals/checksum/64-bit forms.
        if (self.block != 4096 or self.stride != 256 or self.first != 0 or
                self.u32(1116) != 0 or self.u32(1120) != 0x42 or
                self.u32(1124) != 3 or not self.inodes or not self.blocks_per_group or
                not self.inodes_per_group or self.blocks * self.block != len(data)):
            raise ValueError('unsupported explicit ext4 geometry/features')
        self.groups = (self.blocks - self.first + self.blocks_per_group - 1) // self.blocks_per_group

    def bytes(self, at, size):
        if at < 0 or size < 0 or at + size > len(self.data):
            raise ValueError('raw field outside image')
        return self.data[at:at + size]

    def u16(self, at): return struct.unpack('<H', self.bytes(at, 2))[0]
    def u32(self, at): return struct.unpack('<I', self.bytes(at, 4))[0]

    def inode(self, number):
        if not 0 < number <= self.inodes:
            raise ValueError('invalid raw inode number')
        group, index = divmod(number - 1, self.inodes_per_group)
        if group >= self.groups:
            raise ValueError('inode group outside filesystem')
        descriptor = (self.first + 1) * self.block + group * 32
        bitmap = self.u32(descriptor + 4)
        byte = self.bytes(bitmap * self.block + index // 8, 1)[0]
        if not byte & (1 << (index % 8)):
            raise ValueError('raw inode is not allocated')
        table = self.u32(descriptor + 8)
        at = table * self.block + index * self.stride
        self.bytes(at, self.stride)
        return at

    def extents(self, number):
        at = self.inode(number)
        if self.u32(at + 32) != 0x80000:
            raise ValueError('fixture inode requires only extent flag')
        if self.u16(at + 40) != 0xf30a or self.u16(at + 46) != 0 or self.u16(at + 44) != 4:
            raise ValueError('fixture requires inline extent tree')
        entries = self.u16(at + 42)
        if entries > 4:
            raise ValueError('too many inline extents')
        output, logical_end, physical_ranges = [], 0, []
        for index in range(entries):
            entry = at + 52 + index * 12
            logical, length = self.u32(entry), self.u16(entry + 4)
            physical = self.u32(entry + 8)
            if not 0 < length <= 32768 or self.u16(entry + 6) or logical < logical_end:
                raise ValueError('unsupported raw extent')
            if physical <= 0 or physical + length > self.blocks:
                raise ValueError('extent outside filesystem')
            if any(physical < high and physical + length > low for low, high in physical_ranges):
                raise ValueError('overlapping physical extents')
            physical_ranges.append((physical, physical + length))
            logical_end = logical + length
            output.append((logical, physical, length))
        return output

    def fields(self, number):
        at = self.inode(number)
        mode = self.u16(at)
        kind = mode & 0xf000
        if kind not in (0x8000, 0x4000, 0xa000):
            raise ValueError('unsupported fixture inode type')
        size = self.u32(at + 4) | self.u32(at + 108) << 32
        blocks = self.u32(at + 28) | self.u16(at + 116) << 32
        if size > 1024 * 1024 or self.u32(at + 104) or self.u16(at + 118):
            raise ValueError('unsupported fixture size or external attributes')
        extra = self.u16(at + 128)
        if extra < 16 or extra > 128 or extra % 4:
            raise ValueError('fixture needs complete extended timestamps')
        times = {}
        for name, base, extension in (('atime', 8, 140), ('mtime', 16, 136), ('ctime', 12, 132)):
            seconds = struct.unpack('<i', self.bytes(at + base, 4))[0]
            word = self.u32(at + extension)
            if word >> 2 >= 1000000000:
                raise ValueError('malformed raw nanoseconds')
            times[name] = (seconds + (word & 3) * 4294967296, word >> 2)
        fast = kind == 0xa000 and size <= 60 and blocks == 0
        if fast:
            if self.u32(at + 32) != 0:
                raise ValueError('fast symlink has inode flags')
        else:
            extents = self.extents(number)
            if blocks != sum(length for _, _, length in extents) * (self.block // 512):
                raise ValueError('raw block count disagrees with allocation')
        return {'inode': number, 'mode': mode, 'uid': self.u16(at + 2) | self.u16(at + 120) << 16,
                'gid': self.u16(at + 24) | self.u16(at + 122) << 16,
                'nlink': self.u16(at + 26), 'size': size, 'blocks': blocks,
                'blksize': self.block, 'times': times, 'extra_isize': extra, 'fast_symlink': fast}

    def content(self, number):
        fields = self.fields(number)
        size = fields['size']
        at = self.inode(number)
        if fields['fast_symlink']:
            return bytes(self.bytes(at + 40, size))
        result = bytearray(size)
        for logical, physical, length in self.extents(number):
            start = logical * self.block
            count = min(length * self.block, max(0, size - start))
            if count:
                result[start:start + count] = self.bytes(physical * self.block, count)
        return bytes(result)

    def children(self, number):
        at = self.inode(number)
        if self.u16(at) & 0xf000 != 0x4000:
            raise ValueError('raw path parent is not a directory')
        data = self.content(number)
        if len(data) % self.block:
            raise ValueError('partial directory block')
        result = {}
        for start in range(0, len(data), self.block):
            offset = start
            while offset < start + self.block:
                ino, length, name_length, _ = struct.unpack_from('<IHBB', data, offset)
                if length < 8 or length % 4 or offset + length > start + self.block or name_length > length - 8:
                    raise ValueError('malformed raw directory entry')
                if ino:
                    name = data[offset + 8:offset + 8 + name_length].decode('ascii')
                    if not name or '/' in name or '\0' in name or name in result:
                        raise ValueError('invalid or duplicate raw directory name')
                    self.inode(ino)
                    result[name] = ino
                offset += length
        return result

    def lookup(self, path):
        if not path.startswith('/'):
            raise ValueError('raw lookup requires absolute path')
        number = 2
        for name in path.strip('/').split('/'):
            if name:
                number = self.children(number)[name]
        return number


def prepare_root(root: Path):
    """Add fixture nodes to a disposable root without chown or replacing inputs."""
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError('fixture root must be an existing real directory')
    home = root / 'home'
    if home.is_symlink() or (home.exists() and not home.is_dir()):
        raise ValueError('fixture home must be a real directory')
    for path in (*PATHS.values(), *ABSENT_PATHS):
        target = root / path.lstrip('/')
        if target.exists() or target.is_symlink():
            raise ValueError('fixture path collision: ' + path)
    home.mkdir(mode=0o777, exist_ok=True)
    file = root / PATHS['file'].lstrip('/')
    file.write_bytes(CONTENT); file.chmod(0o600)
    os.link(file, root / PATHS['alias'].lstrip('/'))
    for label, target in (('link', 'stat-file'), ('dangling', 'stat-missing'), ('loop', 'stat-loop')):
        (root / PATHS[label].lstrip('/')).symlink_to(target)
    for label in ('empty', 'hole'):
        target = root / PATHS[label].lstrip('/')
        with target.open('xb') as stream:
            if label == 'hole': stream.truncate(HOLE_SIZE)
        target.chmod(0o600)
    (root / PATHS['directory'].lstrip('/')).mkdir(mode=0o700)
    child = root / PATHS['child'].lstrip('/')
    child.write_bytes(b''); child.chmod(0o600)


def seed_image(image: Path, epoch: int):
    """Patch exact fixture inode ownership/times in a newly packaged image."""
    if epoch not in EPOCHS:
        raise ValueError('unsupported fixture epoch')
    image = Path(image)
    original = image.read_bytes()
    raw = Image(original)
    numbers = {label: raw.lookup(path) for label, path in PATHS.items()}
    if numbers['file'] != numbers['alias'] or len(set(numbers.values())) != len(numbers) - 1:
        raise ValueError('fixture hardlink identity mismatch')
    # Encoding independently follows ext4's signed low seconds plus two epoch bits.
    low_unsigned = epoch & 0xffffffff
    low_signed = low_unsigned if low_unsigned < 0x80000000 else low_unsigned - 0x100000000
    epoch_bits = (epoch - low_signed) // 0x100000000
    if not 0 <= epoch_bits <= 3:
        raise ValueError('epoch not representable by ext4')
    data = bytearray(original)
    for number in set(numbers.values()):
        fields = raw.fields(number)
        at = raw.inode(number)
        for offset in (2, 24): struct.pack_into('<H', data, at + offset, 1000)
        for offset in (120, 122): struct.pack_into('<H', data, at + offset, 0)
        for base, extension in ((8, 140), (16, 136), (12, 132)):
            struct.pack_into('<I', data, at + base, low_unsigned)
            struct.pack_into('<I', data, at + extension, NANOSECONDS * 4 + epoch_bits)
    verified = Image(data)
    for number in set(numbers.values()):
        fields = verified.fields(number)
        if fields['uid'] != 1000 or fields['gid'] != 1000 or any(value != (epoch, NANOSECONDS) for value in fields['times'].values()):
            raise ValueError('seeded raw metadata did not round trip')
    image.write_bytes(data)
    return {'epoch': epoch, 'nanoseconds': NANOSECONDS, 'inodes': numbers,
            'uid': 1000, 'gid': 1000, 'host_chown': False, 'block_size': raw.block}

"""Explicit guest metadata for the native bootstrap root ext4 image profile."""
import os
import struct
from pathlib import Path

def require(value, message):
    if not value:
        raise ValueError(message)

class Ext4:
    """Bounded byte-level reader for the freshly composed supported ext4 subset."""

    def __init__(self, payload):
        self.data = bytearray(payload)
        require(len(self.data) >= 2048 and self.u16(1080) == 61267, 'ext4 superblock magic')
        exponent = self.u32(1048)
        require(exponent == 2, 'bounded supported raw ext4 block-size exponent before shifting')
        self.block = 1024 << exponent
        self.blocks = self.u32(1028)
        self.inodes = self.u32(1024)
        self.per_group = self.u32(1064)
        self.inode_size = self.u16(1112)
        require(self.block == 4096 and self.inode_size == 256 and (self.per_group > 0) and (self.blocks * self.block == len(self.data)), 'exact supported composed volume dimensions')
        require(self.u32(1116) == 0 and self.u32(1120) == 66 and (self.u32(1124) == 3), 'only explicit nonjournal extent/filetype/sparse-super/large-file feature set')
        self.descriptors = self.block

    def u16(self, offset):
        require(0 <= offset <= len(self.data) - 2, 'bounded uint16')
        return struct.unpack_from('<H', self.data, offset)[0]

    def u32(self, offset):
        require(0 <= offset <= len(self.data) - 4, 'bounded uint32')
        return struct.unpack_from('<I', self.data, offset)[0]

    def inode(self, number):
        require(type(number) is int and 1 <= number <= self.inodes, 'typed allocated inode number')
        group = (number - 1) // self.per_group
        slot = (number - 1) % self.per_group
        table = self.u32(self.descriptors + group * 32 + 8)
        offset = table * self.block + slot * self.inode_size
        require(table > 0 and 0 <= offset <= len(self.data) - self.inode_size, 'bounded explicit inode table')
        return offset

    def metadata(self, number):
        off = self.inode(number)
        return dict(inode=number, mode=self.u16(off), uid=self.u16(off + 2) | self.u16(off + 120) << 16, gid=self.u16(off + 24) | self.u16(off + 122) << 16, links=self.u16(off + 26), size=self.u32(off + 4) | self.u32(off + 108) << 32)

    def contents(self, number):
        off = self.inode(number)
        metadata = self.metadata(number)
        size = metadata['size']
        kind = metadata['mode'] & 61440
        if kind == 40960:
            require(0 < size < 60 and self.u32(off + 28) == 0 and
                    self.u16(off + 116) == 0 and not self.u32(off + 32) & 524288,
                    'bounded fast symlink with no allocated data blocks')
            return bytes(self.data[off + 40:off + 40 + size])
        require(kind in (16384, 32768), 'only dense directory or sparse regular-file contents')
        require(self.u32(off + 32) & 524288 and self.u16(off + 40) == 62218 and (self.u16(off + 46) == 0), 'fresh supported depth-zero initialized extents')
        count = self.u16(off + 42)
        capacity = self.u16(off + 44)
        require(count <= capacity <= 4 and size <= len(self.data), 'bounded plain extent count and file size')
        blocks = size // self.block + bool(size % self.block)
        if kind == 16384:
            require(size > 0 and size % self.block == 0, 'positive block-aligned dense directory size')
        extents = []
        logical = 0
        for index in range(count):
            pos = off + 52 + 12 * index
            start = self.u32(pos)
            length = self.u16(pos + 4)
            physical = self.u16(pos + 6) << 32 | self.u32(pos + 8)
            # ee_len == 32768 is initialized; larger values mark unwritten extents.
            require(0 < length <= 32768, 'bounded initialized extent length')
            require(start >= logical and length <= (1 << 32) - start,
                    'sorted nonoverlapping logical extents without overflow')
            require(start < blocks and length <= blocks - start,
                    'logical extent within rounded-up inode size')
            require(0 < physical < self.blocks and length <= self.blocks - physical,
                    'bounded physical extent without overflow')
            if kind == 16384:
                require(start == logical, 'dense directory extents without holes')
            extents.append((start, length, physical))
            logical = start + length
        if kind == 16384:
            require(logical == blocks, 'complete dense directory block coverage')
        # mke2fs may omit any zero block, including a short zero tail at EOF.
        value = bytearray(size)
        for start, length, physical in extents:
            begin = start * self.block
            copied = min(length * self.block, size - begin)
            value[begin:begin + copied] = self.data[physical * self.block:physical * self.block + copied]
        return bytes(value)

    def children(self, number):
        require(self.metadata(number)['mode'] & 61440 == 16384, 'directory traversal metadata type')
        data = self.contents(number)
        result = {}
        offset = 0
        while offset < len(data):
            require(offset + 8 <= len(data), 'complete directory header')
            inode, length, namesize, kind = struct.unpack_from('<IHBB', data, offset)
            require(length >= 8 and length % 4 == 0 and (offset + length <= len(data)) and (length <= self.block - offset % self.block) and (namesize <= length - 8), 'bounded aligned directory record')
            name = data[offset + 8:offset + 8 + namesize].decode('ascii')
            if inode:
                require(name and '/' not in name and ('\x00' not in name) and (name not in result), 'unique plain guest directory name')
                self.inode(inode)
                result[name] = (inode, kind)
            offset += length
        return result

    def paths(self):
        found = {'/': 2}
        visited = set()

        def visit(path, number):
            require(number not in visited, 'no aliased directory inode')
            visited.add(number)
            for name, (child, kind) in self.children(number).items():
                if name in ('.', '..'):
                    continue
                current = path.rstrip('/') + '/' + name
                require(current not in found, 'unique guest path')
                found[current] = child
                if self.metadata(child)['mode'] & 61440 == 16384:
                    visit(current, child)
        visit('/', 2)
        return found

    def verify_types(self, paths, files, symlinks=None):
        symlinks = {} if symlinks is None else symlinks
        require(type(paths) is dict and type(files) is dict and (set(files) <= set(paths)), 'exact intended regular-file paths within full guest inventory')
        require(type(symlinks) is dict and set(symlinks) <= set(paths) and
                not set(files) & set(symlinks), 'distinct intended fast-symlink paths within full guest inventory')
        for path, number in paths.items():
            expected = 40960 if path in symlinks else 32768 if path in files else 16384
            require(self.metadata(number)['mode'] & 61440 == expected, 'exact intended guest inode type: ' + path)

    def apply(self, paths, policy, files, symlinks=None, *, hardlink_groups=()):
        require(set(paths) == set(policy), 'exact inode path inventory for the intended rootfs policy')
        self.verify_types(paths, files, symlinks)
        groups = {}
        for path, number in paths.items():
            groups.setdefault(number, set()).add(path)
        aliases = {frozenset(names) for names in groups.values() if len(names) > 1}
        require(aliases == set(hardlink_groups), 'no unapproved aliased inode in composed rootfs')
        for number, names in groups.items():
            metadata = self.metadata(number)
            if len(names) > 1:
                require(names <= files.keys() and len({policy[name] for name in names}) == 1,
                        'fixture aliases require regular files with one metadata policy')
            if metadata['mode'] & 61440 == 32768:
                require(metadata['links'] == len(names), 'exact regular-file link inventory')
        for path, number in paths.items():
            off = self.inode(number)
            kind = self.u16(off) & 61440
            mode = policy[path]
            require(kind in (16384, 32768, 40960), 'only intended directories, regular files and fast symlinks')
            struct.pack_into('<H', self.data, off, kind | mode)
            for field in (2, 24, 120, 122):
                struct.pack_into('<H', self.data, off + field, 0)
        return bytes(self.data)

def linux_stat_fixture_policy(staging):
    """Admit only the named disposable stat fixture, never arbitrary hard links."""
    home = staging / 'home'
    require(not home.is_symlink() and home.is_dir(), 'stat fixture home is an ordinary directory')
    directory = home / 'stat-renamed-dir'
    require(not directory.is_symlink() and directory.is_dir(), 'stat fixture child directory is ordinary')
    contents = {'stat-file': b'linux-stat-fixture', 'stat-alias': b'linux-stat-fixture',
                'stat-empty': b'', 'stat-hole': bytes(12305), 'stat-renamed-dir/child': b''}
    for name, content in contents.items():
        path = home / name
        require(not path.is_symlink() and path.is_file() and path.stat().st_size == len(content) and
                path.read_bytes() == content,
                'exact ordinary stat fixture bytes: ' + name)
        require(path.stat().st_nlink == (2 if name in ('stat-file', 'stat-alias') else 1),
                'exact staged stat fixture link count: ' + name)
    first, alias = (home / 'stat-file').stat(), (home / 'stat-alias').stat()
    require((first.st_dev, first.st_ino) == (alias.st_dev, alias.st_ino), 'exact staged stat fixture hardlink identity')
    links = {'stat-link': 'stat-file', 'stat-dangling': 'stat-missing', 'stat-loop': 'stat-loop'}
    for name, target in links.items():
        path = home / name
        require(path.is_symlink() and os.readlink(path) == target, 'exact stat fixture symbolic link')
    for name in ('stat-missing', 'stat-held', 'stat-dir', 'stat-cwd'):
        path = home / name
        require(not path.exists() and not path.is_symlink(), 'absent reserved stat fixture path')
    modes = {'/home': 0o777, '/home/stat-renamed-dir': 0o700}
    modes.update(('/home/' + name, 0o600) for name in contents)
    modes.update(('/home/' + name, 0o777) for name in links)
    return modes, (frozenset(('/home/stat-file', '/home/stat-alias')),)


def normalize_bootstrap_root(payload, staging, *, profile='bootstrap'):
    staging = Path(staging)
    require(staging.is_dir() and (not staging.is_symlink()), 'ordinary staged root directory')
    require(profile in ('bootstrap', 'linux-stat-fixture-v1'), 'explicit supported rootfs metadata profile')
    overrides, hardlink_groups = (linux_stat_fixture_policy(staging)
                                  if profile == 'linux-stat-fixture-v1' else ({}, ()))
    expected = {'/': None, '/lost+found': None}
    policy = {'/': 493, '/lost+found': 448}
    symlinks = {}
    for path in sorted(staging.rglob('*')):
        name = '/' + path.relative_to(staging).as_posix()
        require(name not in expected, 'no staged path aliases reserved image directories')
        if name in ('/var', '/var/log'):
            require(not path.is_symlink() and path.is_dir(), 'log ancestry must be ordinary directories')
        if name in ('/var/log/system.log', '/var/log/system.prev'):
            require(not path.is_symlink() and path.is_file() and path.stat().st_nlink == 1 and
                    path.stat().st_size <= 8192, 'bounded ordinary single-link log file required')
        if name == '/root':
            require(not path.is_symlink() and path.is_dir(), 'administrator home must be an ordinary directory')
        if name == '/etc/accounts.db':
            require(not path.is_symlink() and path.is_file() and
                    path.read_bytes() == b'OKACCOUNTS 1\nstate unconfigured\n',
                    'bootstrap account database must be the explicit unconfigured seed')
        if path.is_symlink():
            # Read only the literal guest target, including dangling links.
            # Host targets never supply image bytes or traversal policy.
            target = os.fsencode(os.readlink(path))
            require(0 < len(target) < 60 and b'\x00' not in target,
                    'bounded staged fast symlink target')
            expected[name] = symlinks[name] = target
            policy[name] = 511
            continue
        require(path.is_file() or path.is_dir(), 'ordinary staged native image entry')
        expected[name] = None if path.is_dir() else path.read_bytes()
        if path.is_dir():
            policy[name] = 448 if name in ('/home', '/root', '/var/log') else 1023 if name == '/tmp' else 493
        else:
            policy[name] = 384 if name in ('/etc/accounts.db', '/var/log/system.log', '/var/log/system.prev') else 493 if path.stat().st_mode & 73 else 420
    image = Ext4(payload)
    paths = image.paths()
    require(set(paths) == set(expected), 'exact staged and image path inventory')
    for name, content in expected.items():
        metadata = image.metadata(paths[name])
        kind = 40960 if name in symlinks else 16384 if content is None else 32768
        require(metadata['mode'] & 61440 == kind, 'same staged/image inode type')
        if content is not None:
            require(image.contents(paths[name]) == content, 'exact staged bytes before guest metadata policy')
    files = {name: content for name, content in expected.items()
             if content is not None and name not in symlinks}
    policy.update(overrides)
    result = image.apply(paths, policy, files, symlinks, hardlink_groups=hardlink_groups)
    checked = Ext4(result)
    for name, number in paths.items():
        metadata = checked.metadata(number)
        require(metadata['uid'] == metadata['gid'] == 0 and metadata['mode'] & 4095 == policy[name], 'deterministic bootstrap guest owner and permission bytes')
        if expected[name] is not None:
            require(checked.contents(number) == expected[name], 'metadata policy preserves every native file byte')
    return result

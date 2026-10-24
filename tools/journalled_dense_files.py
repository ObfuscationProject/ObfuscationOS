"""Import bootstrap files as initialized extents without changing their bytes.

mke2fs -d omits zero blocks, which can turn ELF alignment padding into an
external extent tree. The selected native bootstrap reader accepts inline
extents. Only the private packaging copy receives temporary nonzero bytes;
debugfs restores original zero blocks before checksum and content admission.
"""
from pathlib import Path
import hashlib
import re
import struct
import subprocess

from journalled_rootfs_policy import inventory, metadata

BLOCK = 1024
PROFILE = 'initialized-1k-bootstrap-files-exact-bytes-v1'
INLINE_PROFILE = 'initialized-1k-inline-regular-files-v1'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(staging):
    staging = Path(staging)
    selected = inventory(staging)
    plan = {}
    for name, metadata in selected.items():
        if metadata['mode'] & 0o170000 != 0o100000:
            continue
        path = staging / name.lstrip('/')
        if path.stat().st_nlink != 1:
            raise ValueError('dense bootstrap requires unaliased temporary files')
        size, original = path.stat().st_size, digest(path)
        zeros = []
        with path.open('r+b') as stream:
            for index in range((size + BLOCK - 1) // BLOCK):
                at = index * BLOCK
                stream.seek(at)
                data = stream.read(min(BLOCK, size - at))
                if data and not any(data):
                    zeros.append(index)
                    stream.seek(at)
                    stream.write(b'\x01')
        if zeros:
            plan[name] = dict(size=size, original_sha256=original,
                              prepared_sha256=digest(path), zero_blocks=zeros)
    return plan


def restore(debugfs, image, staging, work, plan):
    image, staging, work = Path(image), Path(staging), Path(work).absolute()
    if not work.is_dir() or work.is_symlink() or not re.fullmatch(r'/[A-Za-z0-9_./+@=-]+', str(work)):
        raise ValueError('ordinary safe dense-file work directory required')
    selected = inventory(staging)
    commands = []
    for name, row in plan.items():
        path = staging / name.lstrip('/')
        blocks = row['zero_blocks']
        if (name not in selected or selected[name]['mode'] & 0o170000 != 0o100000 or
                path.stat().st_nlink != 1 or path.stat().st_size != row['size'] or
                digest(path) != row['prepared_sha256'] or not blocks or
                blocks != sorted(set(blocks)) or any(type(index) is not int or index < 0 or
                    index * BLOCK >= row['size'] for index in blocks)):
            raise ValueError('dense bootstrap preparation changed: ' + name)
        commands.extend('zap_block -f ' + name + ' ' + str(index) for index in blocks)
    script, log = work / 'dense-files.debugfs', work / 'dense-files.log'
    script.write_text('\n'.join(commands) + ('\n' if commands else ''))
    with log.open('x') as output:
        if commands:
            subprocess.run([str(debugfs), '-w', '-f', str(script), str(image)],
                           check=True, stdout=output, stderr=subprocess.STDOUT)
    for number, (name, row) in enumerate(plan.items()):
        path = staging / name.lstrip('/')
        with path.open('r+b') as stream:
            for index in row['zero_blocks']:
                at = index * BLOCK
                stream.seek(at)
                stream.write(bytes(min(BLOCK, row['size'] - at)))
        if digest(path) != row['original_sha256']:
            raise ValueError('dense bootstrap staging restoration differs: ' + name)
        captured = work / ('dense-file-' + str(number))
        subprocess.run([str(debugfs), '-R', 'dump ' + name + ' ' + str(captured), str(image)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not captured.is_file() or digest(captured) != row['original_sha256']:
            raise ValueError('dense bootstrap image restoration differs: ' + name)
    return dict(profile=PROFILE, block_size=BLOCK, files=plan,
                regular_file_bytes_preserved=True,
                debugfs_commands_sha256=digest(script), debugfs_log_sha256=digest(log))


def validate_initialized_inline(debugfs, image, staging):
    """Admit each regular file's final initialized inline extent representation.

    This read-only check shares the selected bootstrap policy's exact ext4
    geometry contract. It supplements byte comparison and the required fsck;
    neither zero bytes from sparse reads nor debugfs success admit a tree.
    """
    selected = inventory(staging)
    files = {}
    with Path(image).open('rb') as stream:
        stream.seek(0, 2)
        image_size = stream.tell()

        def read(at, count):
            if at < 0 or count < 0 or at + count > image_size:
                raise ValueError('inline regular-file storage outside image')
            stream.seek(at)
            data = stream.read(count)
            if len(data) != count:
                raise ValueError('short inline regular-file storage read')
            return data

        def u16(data, at): return struct.unpack_from('<H', data, at)[0]
        def u32(data, at): return struct.unpack_from('<I', data, at)[0]

        superblock = read(BLOCK, BLOCK)
        blocks = u32(superblock, 4)
        if (u16(superblock, 56) != 0xef53 or u32(superblock, 24) != 0 or
                u32(superblock, 20) != 1 or u16(superblock, 88) != 256 or
                [u32(superblock, at) for at in (92, 96, 100)] != [4, 0x42, 0x400] or
                blocks != 32768 or blocks * BLOCK != image_size):
            raise ValueError('unsupported inline regular-file image profile')
        per_group, blocks_per_group = u32(superblock, 40), u32(superblock, 32)
        if not 0 < per_group <= BLOCK * 8 or not 0 < blocks_per_group <= BLOCK * 8:
            raise ValueError('unsupported inline regular-file group geometry')
        groups = (blocks - 1 + blocks_per_group - 1) // blocks_per_group
        for name, expected in selected.items():
            if expected['mode'] & 0o170000 != 0o100000:
                continue
            number = metadata(debugfs, image, name)['inode']
            if not 1 <= number <= u32(superblock, 0):
                raise ValueError('inline regular-file inode outside image: ' + name)
            group, local = divmod(number - 1, per_group)
            if group >= groups:
                raise ValueError('inline regular-file inode group outside image: ' + name)
            descriptor = read(2048 + group * 32, 32)
            bitmap, table = u32(descriptor, 4), u32(descriptor, 8)
            if not 1 <= bitmap < blocks or not 1 <= table < blocks:
                raise ValueError('inline regular-file inode table outside image: ' + name)
            if not read(bitmap * BLOCK + local // 8, 1)[0] & (1 << (local % 8)):
                raise ValueError('inline regular-file inode is not allocated: ' + name)
            inode = read(table * BLOCK + local * 256, 256)
            size = (Path(staging) / name.lstrip('/')).stat().st_size
            if (u16(inode, 0) & 0o170000 != 0o100000 or not u16(inode, 26) or
                    u32(inode, 20) or u32(inode, 4) != size or
                    any(u32(inode, at) for at in (104, 108, 112)) or
                    u16(inode, 116) or u16(inode, 118)):
                raise ValueError('unsupported inline regular-file inode metadata: ' + name)
            count = u16(inode, 42)
            if (u32(inode, 32) != 0x80000 or u16(inode, 40) != 0xf30a or
                    count > 4 or u16(inode, 44) != 4 or u16(inode, 46)):
                raise ValueError('regular file requires initialized inline extents: ' + name)
            logical_end, extents = 0, []
            for index in range(count):
                logical, length, high, physical = struct.unpack_from('<IHHI', inode, 52 + index * 12)
                if (logical != logical_end or not 0 < length <= 32768 or high or
                        not 1 <= physical < blocks or physical + length > blocks):
                    raise ValueError('invalid initialized inline regular-file extent: ' + name)
                if any(physical < row['physical_block'] + row['block_count'] and
                       row['physical_block'] < physical + length for row in extents):
                    raise ValueError('overlapping inline regular-file physical extents: ' + name)
                extents.append(dict(logical_block=logical, block_count=length, physical_block=physical))
                logical_end += length
            if logical_end != (size + BLOCK - 1) // BLOCK or u32(inode, 28) != logical_end * 2:
                raise ValueError('inline regular-file coverage or sector accounting differs: ' + name)
            files[name] = dict(inode=number, size=size, initialized_blocks=logical_end, extents=extents)
    return dict(profile=INLINE_PROFILE, block_size=BLOCK, files=files,
                initialized_inline_regular_files=True,
                offline_checksum_validation='e2fsck -fn required by packaging caller')

"""Explicit checksum-aware guest bootstrap metadata for journalled ext4 packaging."""
from pathlib import Path
import hashlib
import os
import struct
import re
import subprocess

PROFILE = 'journalled-root-owned-bootstrap-v1'


def inventory(staging: Path) -> dict:
    staging = Path(staging)
    if not staging.is_dir() or staging.is_symlink():
        raise ValueError('ordinary staged journalled root required')
    result = {'/': {'mode': 0o40755, 'uid': 0, 'gid': 0},
              '/lost+found': {'mode': 0o40700, 'uid': 0, 'gid': 0}}
    for path in sorted(staging.rglob('*')):
        name = '/' + path.relative_to(staging).as_posix()
        # Literal debugfs command operands are deliberately bounded. Do not
        # approximate quoting, follow a host link, or accept injected commands.
        if not re.fullmatch(r'/[A-Za-z0-9_./+@=-]+', name) or name in result:
            raise ValueError('unsupported or reserved journalled guest pathname: ' + name)
        if name in ('/var', '/var/log') and (path.is_symlink() or not path.is_dir()):
            raise ValueError('log ancestry must be ordinary directories')
        if name in ('/var/log/system.log', '/var/log/system.prev') and (
                path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size > 8192):
            raise ValueError('bounded ordinary single-link log file required')
        if name == '/root' and (path.is_symlink() or not path.is_dir()):
            raise ValueError('administrator home must be an ordinary directory')
        if name == '/etc/accounts.db' and (path.is_symlink() or not path.is_file() or
                path.read_bytes() != b'OKACCOUNTS 1\nstate unconfigured\n'):
            raise ValueError('bootstrap account database must be the explicit unconfigured seed')
        owner = 0
        if path.is_symlink():
            mode = 0o120777
        elif path.is_dir():
            mode = 0o40700 if name in ('/home', '/root', '/var/log') else 0o41777 if name == '/tmp' else 0o40755
        elif path.is_file():
            mode = 0o100600 if name in ('/etc/accounts.db', '/var/log/system.log', '/var/log/system.prev') else 0o100755 if path.stat().st_mode & 0o111 else 0o100644
        else:
            raise ValueError('unsupported staged journalled inode type: ' + name)
        result[name] = {'mode': mode, 'uid': owner, 'gid': owner}
    if result.get('/etc', {}).get('mode') != 0o40755:
        raise ValueError('trusted ordinary /etc bootstrap directory required')
    if '/etc/services.conf' in result and result['/etc/services.conf']['mode'] & 0o170000 != 0o100000:
        raise ValueError('trusted bootstrap service manifest must be a regular file')
    return result


def metadata(debugfs: Path, image: Path, name: str) -> dict:
    observed = subprocess.run([str(debugfs), '-R', 'stat ' + name, str(image)],
                              check=True, capture_output=True, text=True)
    text = observed.stdout
    kind = re.search(r'Inode:\s*([0-9]+)\s+Type:\s*(\S+)\s+Mode:\s*0([0-7]+)', text)
    identity = re.search(r'User:\s*([0-9]+)\s+Group:\s*([0-9]+)', text)
    if not kind or not identity:
        raise ValueError('debugfs did not report exact inode metadata: ' + name)
    types = {'directory': 0o40000, 'regular': 0o100000, 'symlink': 0o120000}
    if kind[2] not in types:
        raise ValueError('unsupported actual journalled inode type: ' + name)
    return {'inode': int(kind[1]), 'mode': types[kind[2]] | int(kind[3], 8),
            'uid': int(identity[1]), 'gid': int(identity[2])}


def literal_symlink_bytes(image: Path, number: int) -> bytes:
    """Read the selected 1 KiB profile without resolving a link target."""
    with Path(image).open('rb') as stream:
        stream.seek(0, 2)
        length = stream.tell()

        def read(at, count):
            if at < 0 or count < 0 or at + count > length:
                raise ValueError('journalled symlink storage outside image')
            stream.seek(at)
            data = stream.read(count)
            if len(data) != count:
                raise ValueError('short journalled symlink storage read')
            return data

        superblock = read(1024, 1024)
        def u32(data, at): return struct.unpack_from('<I', data, at)[0]
        if (struct.unpack_from('<H', superblock, 56)[0] != 0xef53 or
                u32(superblock, 24) != 0 or u32(superblock, 20) != 1 or
                struct.unpack_from('<H', superblock, 88)[0] != 256 or
                [u32(superblock, at) for at in (92, 96, 100)] != [4, 0x42, 0x400] or
                u32(superblock, 4) * 1024 != length):
            raise ValueError('unsupported journalled symlink image profile')
        per_group = u32(superblock, 40)
        blocks_per_group = u32(superblock, 32)
        blocks = u32(superblock, 4)
        if not per_group or not blocks_per_group or not 1 <= number <= u32(superblock, 0):
            raise ValueError('journalled symlink inode outside image')
        group, local = divmod(number - 1, per_group)
        if group >= (blocks - 1 + blocks_per_group - 1) // blocks_per_group:
            raise ValueError('journalled symlink inode group outside image')
        descriptor = read(2048 + group * 32, 32)
        bitmap, table = u32(descriptor, 4), u32(descriptor, 8)
        if not 1 <= bitmap < blocks or not 1 <= table < blocks:
            raise ValueError('journalled symlink inode table outside image')
        if not read(bitmap * 1024 + local // 8, 1)[0] & (1 << (local % 8)):
            raise ValueError('journalled symlink inode is not allocated')
        raw = read(table * 1024 + local * 256, 256)
        size = u32(raw, 4) | (u32(raw, 108) << 32)
        flags = u32(raw, 32)
        sectors = u32(raw, 28) | (struct.unpack_from('<H', raw, 116)[0] << 32)
        if (struct.unpack_from('<H', raw, 0)[0] & 0o170000 != 0o120000 or
                not 0 < size <= 1024 or u32(raw, 104) or struct.unpack_from('<H', raw, 118)[0]):
            raise ValueError('unsupported journalled symlink inode')
        if flags == 0 and sectors == 0 and size <= 60:
            return raw[40:40 + size]
        if sectors != 2:
            raise ValueError('unsupported journalled symlink block accounting')
        if flags == 0x80000:
            if struct.unpack_from('<HHHH', raw, 40) != (0xf30a, 1, 4, 0):
                raise ValueError('unsupported journalled symlink extent tree')
            logical, count, high, block = struct.unpack_from('<IHHI', raw, 52)
            if logical != 0 or count != 1 or high != 0:
                raise ValueError('unsupported journalled symlink extent')
        elif flags == 0:
            pointers = struct.unpack_from('<15I', raw, 40)
            if any(pointers[1:]):
                raise ValueError('unsupported journalled symlink indirect blocks')
            block = pointers[0]
        else:
            raise ValueError('unsupported journalled symlink flags')
        if not 1 <= block < blocks:
            raise ValueError('journalled symlink block outside image')
        return read(block * 1024, size)


def normalize(debugfs: Path, image: Path, staging: Path, work: Path) -> dict:
    work = Path(work).absolute()
    # debugfs parses its own dump destination operand. Reject paths that need
    # shell-like quoting before any metadata command rather than guessing its
    # quoting rules or allowing a host path to inject another operand.
    if (not work.is_dir() or work.is_symlink() or
            not re.fullmatch(r'/[A-Za-z0-9_./+@=-]+', str(work))):
        raise ValueError('ordinary safe debugfs work directory required')
    selected = inventory(staging)
    before = {name: metadata(debugfs, image, name) for name in selected}
    if len({row['inode'] for row in before.values()}) != len(before):
        raise ValueError('aliased journalled bootstrap inode refused')
    for name, desired in selected.items():
        if before[name]['mode'] & 0o170000 != desired['mode'] & 0o170000:
            raise ValueError('staged and journalled image inode type differs: ' + name)
    symlinks = {}
    for name, desired in selected.items():
        if desired['mode'] & 0o170000 == 0o120000:
            expected = os.readlink(os.fsencode(Path(staging) / name.lstrip('/')))
            if literal_symlink_bytes(image, before[name]['inode']) != expected:
                raise ValueError('journalled symlink target differs from staging: ' + name)
            symlinks[name] = expected
    commands = []
    for name, desired in selected.items():
        for field in ('uid', 'gid'):
            commands.append('set_inode_field ' + name + ' ' + field + ' ' + str(desired[field]))
            commands.append('set_inode_field ' + name + ' ' + field + '_hi 0')
        commands.append('set_inode_field ' + name + ' mode 0' + format(desired['mode'], 'o'))
    script = Path(work) / 'bootstrap-metadata.debugfs'
    script.write_text('\n'.join(commands) + '\n')
    log = Path(work) / 'bootstrap-metadata.log'
    # libext2fs writes inode checksums for metadata_csum. Raw byte patches from
    # the separate nonjournalled 4 KiB bootstrap profile are not used here.
    with log.open('x') as output:
        subprocess.run([str(debugfs), '-w', '-f', str(script), str(image)], check=True,
                       stdout=output, stderr=subprocess.STDOUT)
    after = {name: metadata(debugfs, image, name) for name in selected}
    for name, desired in selected.items():
        if after[name]['inode'] != before[name]['inode']:
            raise ValueError('journalled bootstrap inode identity changed: ' + name)
        if any(after[name][field] != desired[field] for field in ('mode', 'uid', 'gid')):
            raise ValueError('journalled bootstrap metadata policy was not applied: ' + name)
    for name, expected in symlinks.items():
        if literal_symlink_bytes(image, after[name]['inode']) != expected:
            raise ValueError('journalled bootstrap metadata changed symlink target bytes: ' + name)
    for name in selected:
        source = Path(staging) / name.lstrip('/')
        if source.is_symlink() or not source.is_file():
            continue
        captured = Path(work) / ('metadata-file-' + str(after[name]['inode']))
        subprocess.run([str(debugfs), '-R', 'dump ' + name + ' ' + str(captured), str(image)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not captured.is_file() or captured.read_bytes() != source.read_bytes():
            raise ValueError('journalled bootstrap metadata changed staged file bytes: ' + name)
    return {'profile': PROFILE, 'inode_policy': selected, 'applied_inode_metadata': after,
            'debugfs_commands_sha256': hashlib.sha256(script.read_bytes()).hexdigest(),
            'debugfs_log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
            'regular_file_bytes_preserved': True, 'inode_identities_preserved': True,
            'literal_symlink_targets_preserved': True, 'literal_symlink_count': len(symlinks), 'checksum_writer': 'debugfs-libext2fs',
            'offline_checksum_validation': 'e2fsck -fn required by packaging caller'}

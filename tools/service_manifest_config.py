"""Bounded no-argument service configuration; no shell or native execution."""
from pathlib import Path
import os
import re
import stat

BYTE_LIMIT = 4096
CAPACITY = 8
NAME = re.compile(r"[A-Za-z0-9_-]{1,31}\Z")
MODES = {'simple': 0, 'notify': 1, 'oneshot': 2}
IDENTITY = re.compile(r"(?:0|[1-9][0-9]{0,9})\Z")


def parse(payload: bytes) -> list[dict]:
    if (type(payload) is not bytes or not payload or len(payload) > BYTE_LIMIT or
            not payload.startswith((b'OK_SERVICE_MANIFEST 1\n', b'OK_SERVICE_MANIFEST 2\n')) or
            not payload.endswith(b'\n') or
            any(byte != 10 and not 32 <= byte <= 126 for byte in payload)):
        raise ValueError('invalid service manifest bytes, header or size')
    version = payload.split(b'\n', 1)[0][-1:]
    field_count = 5 if version == b'1' else 7
    records = []
    for line in payload.decode('ascii').split('\n')[1:-1]:
        if not line or line.startswith('#'): continue
        fields = line.split(' ')
        if len(fields) != field_count or any(not field for field in fields) or fields[0] != 'service':
            raise ValueError(f'service record requires exactly {field_count} fields')
        _, name, mode, executable, dependencies = fields[:5]
        uid, gid = 0, 0
        if field_count == 7:
            if any(not IDENTITY.fullmatch(value) or int(value) >= 0xffffffff for value in fields[5:]):
                raise ValueError('service identity requires canonical decimal IDs below UINT32_MAX')
            uid, gid = (int(value) for value in fields[5:])
        if (not NAME.fullmatch(name) or name == '-' or mode not in MODES or
                not executable.startswith('/') or not 1 <= len(executable) <= 95 or
                len(records) == CAPACITY or any(record['name'] == name for record in records)):
            raise ValueError('invalid or duplicate service record')
        names = [] if dependencies == '-' else dependencies.split(',')
        if any(not NAME.fullmatch(item) or item == '-' for item in names) or len(set(names)) != len(names):
            raise ValueError('invalid or duplicate named dependency')
        records.append(dict(name=name, executable=executable, mode=MODES[mode], uid=uid, gid=gid,
                            dependency_names=names))
    if not records: raise ValueError('service manifest is empty')
    index = {record['name']: number for number, record in enumerate(records)}
    ancestors = []
    for record in records:
        if any(name not in index or name == record['name'] for name in record['dependency_names']):
            raise ValueError('unknown or self dependency')
        record['dependencies'] = sum(1 << index[name] for name in record.pop('dependency_names'))
        ancestors.append(record['dependencies'])
    for _ in records:
        for number in range(len(records)):
            for other in range(len(records)):
                if ancestors[number] & (1 << other): ancestors[number] |= ancestors[other]
    if any(mask & (1 << number) for number, mask in enumerate(ancestors)):
        raise ValueError('cyclic service dependency')
    return records


def _identity(metadata):
    return (metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_uid,
            metadata.st_gid, metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns)


def snapshot(path: Path) -> bytes:
    """Snapshot a trusted host packaging input; guest ownership is normalized separately."""
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(descriptor)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid not in (0, os.geteuid()) or
                before.st_mode & 0o022 or not 0 <= before.st_size <= BYTE_LIMIT):
            raise ValueError('unsafe service config packaging input')
        chunks, size = [], 0
        while True:
            try:
                chunk = os.read(descriptor, BYTE_LIMIT + 1 - size)
            except InterruptedError:
                continue
            if not chunk: break
            chunks.append(chunk); size += len(chunk)
            if size > BYTE_LIMIT: raise ValueError('service config packaging input exceeds limit')
        if _identity(before) != _identity(os.fstat(descriptor)) or size != before.st_size:
            raise ValueError('service config packaging input changed while reading')
        payload = b''.join(chunks)
        parse(payload)
    finally:
        os.close(descriptor)
    return payload

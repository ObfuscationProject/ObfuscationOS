#!/usr/bin/env python3
"""Admit the ordinary console-login disk before offline QEMU attachment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile

PROFILE = 'ordinary-native-console-login-logging-time-mount-resolver-v1'
SERVICES = (b'OK_SERVICE_MANIFEST 2\nservice console simple /bin/login - 0 0\n'
            b'service logd notify /bin/logd - 0 0\n'
            b'service timed notify /bin/timed - 0 0\n'
            b'service resolved notify /bin/resolved - 0 0\n')
HOSTS_LIMIT = 4096
HOSTS_SEED = b'127.0.0.1 localhost\n'
# Exact lg_base(0) bytes: fresh images allocate the first data block offline.
CHECKPOINT0 = b'OKLB1 0000000000000000 #077a2810\n'
PRODUCTS = ('/init', '/bin/login', '/bin/oksh', '/bin/logd', '/bin/logger',
            '/bin/timed', '/bin/timectl', '/bin/mountctl', '/bin/resolved', '/bin/resolvectl',
            '/etc/services.conf')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('console login requires a regular non-symlink file: ' + str(path))


def hosts_snapshot(path, *, exact_mode=False):
    """Bound trusted host input; guest root ownership is normalized separately."""
    path = Path(path).absolute()
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError('hosts path redirect is unsupported: ' + str(component))
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(descriptor)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid not in (0, os.geteuid()) or
                before.st_mode & 0o022 or before.st_nlink != 1 or
                not 0 <= before.st_size <= HOSTS_LIMIT or
                (exact_mode and stat.S_IMODE(before.st_mode) != 0o644)):
            raise ValueError('unsafe hosts packaging metadata or size')
        chunks, size = [], 0
        while True:
            try:
                chunk = os.read(descriptor, HOSTS_LIMIT + 1 - size)
            except InterruptedError:
                continue
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > HOSTS_LIMIT:
                raise ValueError('hosts packaging input exceeds limit')
        after = os.fstat(descriptor)
        fields = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink', 'st_size',
                  'st_mtime_ns', 'st_ctime_ns')
        if size != before.st_size or any(getattr(before, key) != getattr(after, key) for key in fields):
            raise ValueError('hosts packaging input changed while reading')
        return b''.join(chunks)
    finally:
        os.close(descriptor)


def product(root):
    files = {}
    for name in PRODUCTS:
        path = root / name[1:]
        regular(path)
        files[name] = sha(path)
    if (root / 'etc/services.conf').read_bytes() != SERVICES:
        raise ValueError('console login service configuration differs')
    regular(root / 'var/log/system.log')
    if (root / 'var/log/system.log').read_bytes() != CHECKPOINT0:
        raise ValueError('console login initial logging checkpoint differs')
    hosts_snapshot(root / 'etc/hosts', exact_mode=True)
    return dict(profile=PROFILE, files=files,
                mutable_configuration=dict(hosts=dict(path='/etc/hosts', max_bytes=HOSTS_LIMIT,
                    mode='0644', uid=0, gid=0, links=1, reload='service-restart')),
                initial_logging_checkpoint=dict(path='/var/log/system.log',
                    sha256=hashlib.sha256(CHECKPOINT0).hexdigest()))


def dump(debugfs, image, name, output):
    subprocess.run([str(debugfs), '-R', 'dump ' + name + ' ' + str(output), str(image)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    regular(output)
    return output.read_bytes()


def initial_seed(image, debugfs):
    """Check actual initial image bytes before publication, never on reuse."""
    with tempfile.TemporaryDirectory(prefix='console-login-seed-') as directory:
        work = Path(directory)
        if not re.fullmatch(r'/[A-Za-z0-9_./+-]+', str(work)):
            raise ValueError('literal-safe debugfs output directory required')
        if dump(debugfs, image, '/var/log/system.log', work / 'seed') != CHECKPOINT0:
            raise ValueError('persisted initial logging checkpoint differs')


def admit(image, root, debugfs):
    # Preserve final-component symlinks for rejection before any resolve().
    image = image.absolute()
    manifest_path = image.with_name(image.name + '.manifest.json')
    log = image.with_name(image.name + '.activation.log')
    for path in (image, manifest_path, log):
        regular(path)
    selected = product(root)
    manifest = json.loads(manifest_path.read_text())
    if (manifest.get('schema') != 1 or manifest.get('profile') !=
            'linux-activated-clean-1k-jbd2-crc32c-v3-normalized-head' or
            manifest.get('console_login') != selected or
            manifest.get('activation_log_sha256') != sha(log)):
        raise ValueError('console login image has no matching complete activation/product evidence')
    with tempfile.TemporaryDirectory(prefix='console-login-admit-') as directory:
        work = Path(directory)
        if not re.fullmatch(r'/[A-Za-z0-9_./+-]+', str(work)):
            raise ValueError('literal-safe debugfs output directory required')
        for index, name in enumerate(PRODUCTS):
            output = work / str(index)
            if hashlib.sha256(dump(debugfs, image, name, output)).hexdigest() != selected['files'][name]:
                raise ValueError('persisted console product differs from the selected build: ' + name)
        for name, kind, mode, single in (
                ('/', 'directory', 0o755, False), ('/etc', 'directory', 0o755, False),
                ('/bin', 'directory', 0o755, False), ('/var', 'directory', 0o755, False),
                ('/var/log', 'directory', 0o700, False),
                ('/root', 'directory', 0o700, False), ('/etc/accounts.db', 'regular', 0o600, True),
                ('/init', 'regular', 0o755, True), ('/bin/login', 'regular', 0o755, True),
                ('/bin/oksh', 'regular', 0o755, True), ('/bin/logd', 'regular', 0o755, True),
                ('/bin/logger', 'regular', 0o755, True), ('/bin/timed', 'regular', 0o755, True),
                ('/bin/timectl', 'regular', 0o755, True), ('/bin/mountctl', 'regular', 0o755, True),
                ('/bin/resolved', 'regular', 0o755, True), ('/bin/resolvectl', 'regular', 0o755, True),
                ('/etc/hosts', 'regular', 0o644, True), ('/etc/services.conf', 'regular', 0o644, True)):
            text = subprocess.run([str(debugfs), '-R', 'stat ' + name, str(image)], check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode('ascii', errors='replace')
            identity = re.search(r'Inode:\s*([0-9]+)\s+Type:\s*(\S+)\s+Mode:\s*0([0-7]+)', text)
            owner = re.search(r'User:\s*([0-9]+)\s+Group:\s*([0-9]+)', text)
            links = re.search(r'Links:\s*([0-9]+)', text)
            if (not identity or not owner or not links or identity[2] != kind or
                    int(identity[3], 8) != mode or int(owner[1]) or int(owner[2]) or
                    (single and int(links[1]) != 1)):
                raise ValueError('persisted console path metadata differs: ' + name)
            if name == '/etc/hosts':
                size = re.search(r'\bSize:\s*([0-9]+)', text)
                if not size or int(size[1]) > HOSTS_LIMIT:
                    raise ValueError('persisted console hosts metadata differs: ' + name)
        # Live logs are mutable and may need daemon archival recovery. Only
        # bounded protected metadata is admitted here; logd owns framing.
        for name in ('/var/log/system.log', '/var/log/system.prev'):
            result = subprocess.run([str(debugfs), '-R', 'stat ' + name, str(image)], check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            # A wrong-type inode can print arbitrary symlink target bytes.
            text = result.stdout.decode('ascii', errors='replace')
            if not text and b'File not found by ext2_lookup' in result.stderr:
                continue
            identity = re.search(r'Inode:\s*([0-9]+)\s+Type:\s*(\S+)\s+Mode:\s*0([0-7]+)', text)
            owner = re.search(r'User:\s*([0-9]+)\s+Group:\s*([0-9]+)', text)
            links = re.search(r'Links:\s*([0-9]+)', text)
            size = re.search(r'\bSize:\s*([0-9]+)', text)
            if (not identity or not owner or not links or not size or identity[2] != 'regular' or
                    int(identity[3], 8) != 0o600 or int(owner[1]) or int(owner[2]) or
                    int(links[1]) != 1 or int(size[1]) > 8192):
                raise ValueError('persisted console path metadata differs: ' + name)
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--debugfs', type=Path)
    args = parser.parse_args()
    debugfs = args.debugfs or Path(shutil.which('debugfs') or '/missing-debugfs')
    regular(debugfs)
    admit(args.image, args.root, debugfs)
    print('[console-login] persisted product and protected metadata admitted')


if __name__ == '__main__':
    main()

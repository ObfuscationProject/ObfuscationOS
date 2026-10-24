#!/usr/bin/env python3
"""Mount an exact journal-mode volume in pinned Linux and verify every fixture node."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import select
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())


def expected_header(data, facts, inode_metadata):
    fields = [('inode', 'unsigned long long'), ('mode', 'unsigned'), ('uid', 'unsigned'),
              ('gid', 'unsigned'), ('links', 'unsigned'), ('size', 'unsigned long long'),
              ('blocks512', 'unsigned long long')]
    times = [(name + suffix, 'long long') for name in ('atime', 'mtime', 'ctime') for suffix in ('_sec', '_nsec')]
    lines = ['struct expected_node { const char *path; ' +
             ' '.join(kind + ' ' + name + ';' for name, kind in fields + times) + ' };',
             'static const struct expected_node expected_nodes[] = {']
    for label, path in [('root', '/mnt'), ('seed', '/mnt/seed'), ('other_owner', '/mnt/other-owner'),
                        ('child', '/mnt/child'), ('seed_link', '/mnt/seed-link')]:
        node = inode_metadata(data, facts['nodes'][label]['inode'])
        values = [node[name] for name, _ in fields]
        values += [node[name][component] for name in ('atime', 'mtime', 'ctime') for component in ('seconds', 'nanoseconds')]
        lines.append('    {' + json.dumps(path) + ', ' + ', '.join(str(n) for n in values) + '},')
    lines.append('};\n')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--volume', type=Path, required=True)
    parser.add_argument('--volume-sha256', required=True)
    parser.add_argument('--facts', type=Path, required=True)
    parser.add_argument('--facts-sha256', required=True)
    parser.add_argument('--linux-image', type=Path, required=True)
    parser.add_argument('--linux-sha256', required=True)
    parser.add_argument('--oracle-source', type=Path, default=ROOT)
    parser.add_argument('--oracle-inventory', type=Path, required=True)
    parser.add_argument('--oracle-inventory-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert sys.dont_write_bytecode and os.environ['PYTHONDONTWRITEBYTECODE'] == '1'
    assert sha(args.volume) == args.volume_sha256 and sha(args.facts) == args.facts_sha256
    assert sha(args.linux_image) == args.linux_sha256
    assert sha(args.oracle_inventory) == args.oracle_inventory_sha256
    oracle_files = read(args.oracle_inventory)['files']
    for name, digest in oracle_files.items():
        assert sha(args.oracle_source / name) == digest
    sys.path.insert(0, str(args.oracle_source / 'tools/jbd2'))
    from journalled_mode_image import inode_metadata
    from create_linux_fixture import cpio
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    record = dict(status='running', scope='actual independent Linux readonly mount of supplied volume',
                  host_mounts=False, physical=False, linux_source_provenance='not-established',
                  volume_source=str(args.volume.resolve()), volume_sha256=args.volume_sha256,
                  facts_sha256=args.facts_sha256, linux_image_sha256=args.linux_sha256,
                  oracle_inventory_sha256=args.oracle_inventory_sha256, runner_sha256=sha(__file__), commands=[])

    def save():
        (out / 'result.json').write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')

    def run(argv, label):
        argv = list(map(str, argv)); log = out / (label + '.log')
        with log.open('xb') as stream:
            result = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT,
                                    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        record['commands'].append(dict(argv=argv, returncode=result.returncode, log_sha256=sha(log)))
        save(); assert result.returncode == 0, label

    save()
    try:
        volume = args.volume.read_bytes(); facts = read(args.facts)
        assert len(volume) == 32 * 1024 * 1024
        source = ROOT / 'tests/linux/journalled_mode_init.c'
        shutil.copy2(source, out / 'init.c')
        record['linux_init_source_sha256'] = sha(source)
        (out / 'journalled_linux_expected.h').write_text(expected_header(volume, facts, inode_metadata))
        compiler = Path(shutil.which('gcc')).resolve(); qemu = Path(shutil.which('qemu-system-x86_64')).resolve()
        fsck = Path(shutil.which('e2fsck')).resolve()
        record['tools'] = {str(p): sha(p) for p in (compiler, qemu, fsck)}
        run([compiler, '-static', '-O2', '-Wall', '-Wextra', '-Werror', out / 'init.c', '-o', out / 'init'], 'compile')
        entries = [(name, 0o040755, b'', 0, 0) for name in ('dev', 'proc', 'sys', 'mnt')]
        entries += [('dev/console', 0o020600, b'', 5, 1), ('init', 0o100755, (out / 'init').read_bytes(), 0, 0)]
        (out / 'initramfs.cpio').write_bytes(cpio(entries))
        shutil.copy2(args.linux_image, out / 'linux-bzImage')
        disk = out / 'volume.img'; disk.write_bytes(volume)
        command = [str(qemu), '-m', '512M', '-smp', '1', '-kernel', str(out / 'linux-bzImage'),
                   '-initrd', str(out / 'initramfs.cpio'), '-append',
                   'console=ttyS0 rdinit=/init loglevel=4 panic=-1 nokaslr', '-drive',
                   f'file={disk},format=raw,if=none,id=fixture,cache=writeback,readonly=on',
                   '-device', 'virtio-blk-pci,drive=fixture', '-display', 'none', '-serial', 'stdio',
                   '-monitor', 'none', '-no-reboot']
        record['qemu_argv'] = command; save()
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        serial = bytearray(); started = time.monotonic()
        marker = b'JMODE_LINUX_PASS nodes=5 payloads=2 symlink=1 mount=readonly unmount=pass\r\n'
        try:
            while time.monotonic() - started < 60:
                readable, _, _ = select.select([process.stdout], [], [], 0.1)
                if readable:
                    part = os.read(process.stdout.fileno(), 65536)
                    if part: serial.extend(part)
                    elif process.poll() is not None: break
                if marker in serial or b'JBD2_NATIVE_FAIL' in serial: break
        finally:
            if process.poll() is None: process.terminate()
            try: tail, _ = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); tail, _ = process.communicate()
            serial.extend(tail); (out / 'serial.log').write_bytes(serial)
            record.update(qemu_returncode=process.returncode, guest_seconds=time.monotonic() - started)
            save()
        assert serial.count(marker) == 1 and b'JBD2_NATIVE_FAIL' not in serial, 'Linux mount/metadata/payload validation'
        assert disk.read_bytes() == volume, 'readonly Linux guest modified input'
        run([fsck, '-fn', disk], 'readonly-e2fsck')
        assert sha(args.volume) == args.volume_sha256 and sha(args.linux_image) == args.linux_sha256
        record.update(status='passed', executed_linux=True, nodes=5, payloads=2, symlinks=1, readonly_unchanged=True)
    except BaseException as error:
        record.update(status='failed', error=repr(error)); save(); raise
    record['outputs'] = {str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'result.json'}
    save(); print('PASS independent Linux journalled mode readonly mount', sha(out / 'result.json'))


if __name__ == '__main__':
    main()

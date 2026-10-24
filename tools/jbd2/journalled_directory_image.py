#!/usr/bin/env python3
"""Add a nested payload to an explicitly pinned disposable chmod fixture."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from journalled_mode_image import extract_volume, inode_metadata


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--base-result-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert sys.dont_write_bytecode and os.environ['PYTHONDONTWRITEBYTECODE'] == '1'
    assert sha(args.base / 'result.json') == args.base_result_sha256
    base = json.loads((args.base / 'result.json').read_text())
    assert base['status'] == 'passed'
    for name, key in [('volume.img', 'volume_sha256'), ('guarded.img', 'guarded_sha256'),
                      ('facts.json', 'facts_sha256')]:
        assert sha(args.base / name) == base[key], name
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = dict(status='running', scope='offline disposable directory fixture; no native execution',
                  base_result_sha256=args.base_result_sha256, runner_sha256=sha(__file__), commands=[])

    def save():
        (out / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')

    def run(argv, label):
        argv = list(map(str, argv))
        log = out / (label + '.log')
        with log.open('xb') as stream:
            done = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT,
                                  env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TZ='UTC'))
        report['commands'].append(dict(argv=argv, returncode=done.returncode, log_sha256=sha(log)))
        save()
        assert done.returncode == 0, label

    save()
    try:
        tools = {name: str(Path(shutil.which(name)).resolve()) for name in ('debugfs', 'e2fsck')}
        report['tools'] = {path: sha(path) for path in tools.values()}
        image = out / 'volume.img'
        shutil.copy2(args.base / 'volume.img', image)
        payload = out / 'leaf.bin'
        payload.write_bytes(b'directory child payload\n')
        script = out / 'leaf.debugfs'
        script.write_text('\n'.join([
            f'write {payload} /child/leaf',
            'set_inode_field /child/leaf mode 33152',
            'set_inode_field /child/leaf uid 1000',
            'set_inode_field /child/leaf gid 1000',
            'set_inode_field /child/leaf atime @1600000001',
            'set_inode_field /child/leaf mtime @1600000002',
            'set_inode_field /child/leaf ctime @1600000003', '']))
        run([tools['debugfs'], '-w', '-f', script, image], 'seed-leaf')
        run([tools['e2fsck'], '-fn', image], 'seed-fsck')
        facts = json.loads((args.base / 'facts.json').read_text())
        data = image.read_bytes()
        for label, node in facts['nodes'].items():
            facts['nodes'][label] = inode_metadata(data, node['inode'])
        facts['nodes']['leaf'] = inode_metadata(data, 16)
        leaf = facts['nodes']['leaf']
        assert (leaf['mode'], leaf['uid'], leaf['gid'], leaf['size'], leaf['links']) == (0o100600, 1000, 1000, len(payload.read_bytes()), 1)
        actual = out / 'read-leaf.bin'
        run([tools['debugfs'], '-R', f'dump /child/leaf {actual}', image], 'read-leaf')
        assert actual.read_bytes() == payload.read_bytes()
        run([tools['debugfs'], '-R', 'stat /child/leaf', image], 'stat-leaf')
        assert 'Inode: 16 ' in (out / 'stat-leaf.log').read_text()
        seed = facts['nodes']['seed']
        facts['seed_inode_sha256'] = hashlib.sha256(data[seed['byte_offset']:seed['byte_offset'] + 256]).hexdigest()
        (out / 'facts.json').write_text(json.dumps(facts, indent=2, sort_keys=True) + '\n')
        guarded = bytes([0x9a]) * (facts['origin'] * 512) + data + bytes([0x9a]) * (facts['suffix_sectors'] * 512)
        assert extract_volume(guarded) == data
        (out / 'guarded.img').write_bytes(guarded)
        report.update(status='passed', volume_sha256=sha(image), guarded_sha256=sha(out / 'guarded.img'),
                      facts_sha256=sha(out / 'facts.json'), leaf_payload_sha256=sha(payload))
    except BaseException as error:
        report.update(status='failed', error=repr(error))
        save()
        raise
    save()


if __name__ == '__main__':
    main()

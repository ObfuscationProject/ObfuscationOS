#!/usr/bin/env python3
"""Put an exact static /init on a disposable, pinned bounded ext4 fixture."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True
from journalled_mode_image import extract_volume, inode_metadata


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--base-result-sha256', required=True)
    parser.add_argument('--init', type=Path, required=True)
    parser.add_argument('--init-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    base, init, out = args.base.resolve(), args.init.resolve(), args.output.resolve()
    if sha(base / 'result.json') != args.base_result_sha256 or sha(init) != args.init_sha256:
        raise ValueError('explicit base or /init pin mismatch')
    baseline = json.loads((base / 'result.json').read_text())
    if baseline.get('status') != 'passed':
        raise ValueError('base fixture did not pass')
    for name, key in [('volume.img', 'volume_sha256'), ('guarded.img', 'guarded_sha256'),
                      ('facts.json', 'facts_sha256')]:
        if sha(base / name) != baseline[key]:
            raise ValueError('base fixture artifact mismatch: ' + name)
    if init.read_bytes()[:4] != b'\x7fELF':
        raise ValueError('explicit /init is not an ELF file')
    out.mkdir(parents=True, exist_ok=False)
    report = {'status': 'running', 'scope': 'disposable offline image; no guest execution',
              'base_result_sha256': args.base_result_sha256, 'init_sha256': args.init_sha256,
              'runner_sha256': sha(Path(__file__)), 'commands': []}

    def save() -> None:
        (out / 'result.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')

    def run(argv: list[object], label: str) -> str:
        command = list(map(str, argv))
        done = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TZ='UTC'))
        (out / (label + '.log')).write_bytes(done.stdout)
        report['commands'].append({'argv': command, 'returncode': done.returncode,
                                   'log_sha256': sha(out / (label + '.log'))})
        save()
        if done.returncode:
            raise RuntimeError(label + ' failed')
        return done.stdout.decode(errors='replace')

    save()
    try:
        tools = {name: Path(shutil.which(name)).resolve() for name in ('debugfs', 'e2fsck')}
        report['tools'] = {str(path): sha(path) for path in tools.values()}
        image = out / 'volume.img'
        shutil.copy2(base / 'volume.img', image)
        script = out / 'install-init.debugfs'
        script.write_text('\n'.join([f'write {init} /init',
                                     'set_inode_field /init mode 33133',
                                     'set_inode_field /init uid 0',
                                     'set_inode_field /init gid 0', '']))
        run([tools['debugfs'], '-w', '-f', script, image], 'install-init')
        run([tools['e2fsck'], '-fn', image], 'post-install-fsck')
        stat = run([tools['debugfs'], '-R', 'stat /init', image], 'stat-init')
        match = re.search(r'^Inode: (\d+)\s', stat, re.MULTILINE)
        if not match:
            raise ValueError('/init missing from installed image')
        volume = image.read_bytes()
        facts = json.loads((base / 'facts.json').read_text())
        if (len(volume) != facts['sectors'] * 512 or
                [struct.unpack_from('<I', volume, 1024 + offset)[0] for offset in (92, 96, 100)] != [4, 0x42, 0x400] or
                struct.unpack_from('>I', volume, facts['journal_first'] * 1024 + 28)[0] != 0):
            raise ValueError('installed image changed journalled feature or clean-log profile')
        for label, node in facts['nodes'].items():
            facts['nodes'][label] = inode_metadata(volume, node['inode'])
        facts['nodes']['init'] = inode_metadata(volume, int(match.group(1)))
        node = facts['nodes']['init']
        if (node['mode'], node['uid'], node['gid'], node['size'], node['links']) != \
                (0o100555, 0, 0, init.stat().st_size, 1):
            raise ValueError('installed /init metadata differs from explicit ELF')
        dumped = out / 'readback-init.elf'
        run([tools['debugfs'], '-R', f'dump /init {dumped}', image], 'readback-init')
        if sha(dumped) != args.init_sha256:
            raise ValueError('on-disk /init differs from exact input ELF')
        guarded = out / 'guarded.img'
        guarded.write_bytes(bytes([0x9a]) * (facts['origin'] * 512) + volume +
                            bytes([0x9a]) * (facts['suffix_sectors'] * 512))
        if extract_volume(guarded.read_bytes()) != volume:
            raise ValueError('partition guards or volume changed')
        seed = facts['nodes']['seed']
        facts['seed_inode_sha256'] = hashlib.sha256(volume[seed['byte_offset']:seed['byte_offset'] + 256]).hexdigest()
        (out / 'facts.json').write_text(json.dumps(facts, indent=2, sort_keys=True) + '\n')
        report.update(status='passed', volume_sha256=sha(image), guarded_sha256=sha(guarded),
                      facts_sha256=sha(out / 'facts.json'), init_inode=node['inode'],
                      init_readback_sha256=sha(dumped), feature_masks=[4, 0x42, 0x400])
    except BaseException as exc:
        report.update(status='failed', error=repr(exc))
        save()
        raise
    save()


if __name__ == '__main__':
    main()

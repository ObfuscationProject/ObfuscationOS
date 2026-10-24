#!/usr/bin/env python3
"""Hosted raw-image/oracle regression tests; synthetic logs are not guest execution."""
import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

sys.dont_write_bytecode = True


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ModelChecks:
    def __init__(self, repository, output, image, oracle):
        self.repository = repository
        self.output = output
        self.image = image
        self.oracle = oracle
        self.checks = 0
        self.commands = []
        self.environment = dict(os.environ, LC_ALL='C', TZ='UTC', PYTHONDONTWRITEBYTECODE='1')
        self.host_tools = {}
        for name in ('e2fsck', 'debugfs', 'mke2fs'):
            path = shutil.which(name)
            if path is None:
                raise ValueError('required host tool not found: ' + name)
            self.host_tools[name] = Path(path).resolve()

    def check(self, value):
        self.checks += 1
        if not value:
            raise AssertionError('model check ' + str(self.checks))

    def reject(self, function):
        self.checks += 1
        try:
            function()
        except (ValueError, KeyError, struct.error):
            return
        raise AssertionError('model accepted invalid input at check ' + str(self.checks))

    def run(self, argv, name):
        argv = list(map(str, argv))
        result = subprocess.run(argv, capture_output=True, text=True, env=self.environment)
        path = self.output / (name + '.log')
        path.write_text(result.stdout + result.stderr)
        self.commands.append({'argv': argv, 'returncode': result.returncode,
                              'log': path.name, 'log_sha256': sha(path)})
        self.check(result.returncode == 0)
        return result.stdout

    def wire(self, fields, arch):
        # Independent construction uses Linux UAPI offsets, not the oracle codec.
        endian = self.oracle.ARCH_ENDIAN[arch]
        value = bytearray(256)
        for offset, key in ((4, 'blksize'), (16, 'nlink'), (20, 'uid'), (24, 'gid')):
            struct.pack_into(endian + 'I', value, offset, fields[key])
        struct.pack_into(endian + 'I', value, 0, 0x7ff)
        struct.pack_into(endian + 'H', value, 28, fields['mode'])
        for offset, key in ((32, 'inode'), (40, 'size'), (48, 'blocks')):
            struct.pack_into(endian + 'Q', value, offset, fields[key])
        for offset, key in ((64, 'atime'), (96, 'ctime'), (112, 'mtime')):
            struct.pack_into(endian + 'qI', value, offset, *fields['times'][key])
        struct.pack_into(endian + 'II', value, 136, 0, 1)
        return bytes(value)

    def synthetic_log(self, nodes, arch, policy, epoch):
        epoch_label = 'negative' if epoch < 0 else 'post2038'
        if policy == 'maintained':
            kind = int(arch in ('x86_64', 'aarch64', 'rv64'))
            lines = ['LINUX_STAT_NATIVE_PASS authority=uid1000 held-fd=10 renamed-dir-fd=11 cwd=detached',
                     f'LINUX_STAT_MUSL_PASS checks=100 epoch={epoch_label} kernel-stat={kind} statx-size=256']
        else:
            lines = ['LINUX_STAT_CONTROLS_NATIVE_PASS authority=uid1000 native-stat=pass mutations=none',
                     f'LINUX_STAT_CONTROLS_MUSL_PASS mode={policy} epoch={epoch_label} checks=100']
        if policy != 'unqualified':
            lines += ['LINUX_STAT_SNAPSHOT name=' + label + ' hex=' + self.wire(node, arch).hex()
                      for label, node in nodes.items()]
        return '\n'.join(lines) + '\n'

    def exercise(self, source_hashes):
        image_module = self.image
        validate = self.oracle.validate
        packager = self.repository / 'tools/mkext4.py'
        blank_root = self.output / 'blank-root'
        blank_root.mkdir()
        (blank_root / 'home').mkdir(mode=0o777)
        blank_image = self.output / 'blank.img'
        self.run([sys.executable, packager, '--root', blank_root, '--out', blank_image], 'blank-mkext4')
        for epoch in image_module.EPOCHS:
            label = 'post2038' if epoch > 0 else 'negative'
            root = self.output / (label + '-root')
            root.mkdir()
            (root / 'home').mkdir(mode=0o777)
            image_module.prepare_root(root)
            self.check((root / 'home/stat-file').stat().st_ino == (root / 'home/stat-alias').stat().st_ino)
            self.reject(lambda: image_module.prepare_root(root))
            image = self.output / (label + '.img')
            self.run([sys.executable, packager, '--root', root, '--out', image,
                      '--profile', 'linux-stat-fixture-v1'], label + '-mkext4')
            seed = image_module.seed_image(image, epoch)
            self.check(seed['epoch'] == epoch and seed['nanoseconds'] == 123456789)
            digest = sha(image)
            self.run([self.host_tools['e2fsck'], '-fn', image], label + '-fsck')
            self.check(sha(image) == digest)
            debug = self.run([self.host_tools['debugfs'], '-R', 'stat /home/stat-file', image],
                             label + '-debugfs-file')
            self.check('User:  1000' in debug and 'Group:  1000' in debug and 'Size: 18' in debug and
                       'Links: 2   Blockcount: 8' in debug)
            hole = self.run([self.host_tools['debugfs'], '-R', 'stat /home/stat-hole', image],
                            label + '-debugfs-hole')
            self.check('Size: 12305' in hole and 'Blockcount: 0' in hole)
            data = image.read_bytes()
            raw = image_module.Image(data)
            nodes = {name: raw.fields(raw.lookup(path)) for name, path in image_module.PATHS.items()}
            self.check(raw.content(nodes['file']['inode']) == image_module.CONTENT)
            self.check(raw.content(nodes['hole']['inode']) == bytes(image_module.HOLE_SIZE))
            for arch in self.oracle.ARCH_ENDIAN:
                for policy in ('readonly', 'unqualified', 'maintained'):
                    initial = blank_image.read_bytes() if policy == 'maintained' else data
                    text = self.synthetic_log(nodes, arch, policy, epoch)
                    result = validate(text, initial, data, arch, policy, epoch)
                    self.check(result['snapshot_count'] == (0 if policy == 'unqualified' else 9))
                    self.reject(lambda: validate(text + 'FIXTURE_FAIL\n', initial, data, arch, policy, epoch))
                    self.reject(lambda: validate(text.replace('PASS', 'MISSING'), initial, data, arch, policy, epoch))
            text = self.synthetic_log(nodes, 'x86_64', 'readonly', epoch)
            lines = text.splitlines()
            self.reject(lambda: validate('\n'.join(lines[:-1]), data, data, 'x86_64', 'readonly', epoch))
            self.reject(lambda: validate(text + lines[-1] + '\n', data, data, 'x86_64', 'readonly', epoch))
            self.reject(lambda: validate(text.replace('name=file', 'name=unknown'), data, data, 'x86_64', 'readonly', epoch))
            corrupt = bytearray(data)
            corrupt[-1] ^= 1
            self.reject(lambda: validate(text, data, bytes(corrupt), 'x86_64', 'readonly', epoch))
            self.reject(lambda: validate(text, data, data, 'mips64', 'readonly', epoch))
            unqualified = self.synthetic_log(nodes, 'x86_64', 'unqualified', epoch)
            self.reject(lambda: validate(unqualified + lines[-1] + '\n', data, data, 'x86_64', 'unqualified', epoch))
            # Every byte, in each byte order, is material to the full projection.
            for arch in ('x86_64', 'mips64'):
                text = self.synthetic_log(nodes, arch, 'readonly', epoch)
                original = self.wire(nodes['file'], arch)
                for index in range(256):
                    changed = bytearray(original)
                    changed[index] ^= 1
                    bad = text.replace('name=file hex=' + original.hex(), 'name=file hex=' + changed.hex())
                    self.reject(lambda: validate(bad, data, data, arch, 'readonly', epoch))
            at = raw.inode(nodes['file']['inode'])
            for offset, value in ((28, 16), (32, 0), (140, 4000000000)):
                damaged = bytearray(data)
                struct.pack_into('<I', damaged, at + offset, value)
                self.reject(lambda: image_module.Image(damaged).fields(nodes['file']['inode']))
            self.reject(lambda: image_module.seed_image(image, 0))
        self.check(source_hashes == {path: sha(path) for path in source_hashes})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2],
                        help='OS repository root; defaults to the root containing tests/tools')
    parser.add_argument('--output', type=Path, required=True,
                        help='New directory for disposable roots, images, command logs and result.json')
    args = parser.parse_args()
    repository = args.repo.resolve()
    output = args.output.resolve()
    tools = repository / 'tools'
    source_paths = [tools / 'linux_stat_image.py', tools / 'linux_stat_oracle.py',
                    tools / 'mkext4.py', tools / 'rootfs_policy.py', Path(__file__).resolve()]
    source_hashes = {str(path): sha(path) for path in source_paths}
    sys.path.insert(0, str(tools))
    image = importlib.import_module('linux_stat_image')
    oracle = importlib.import_module('linux_stat_oracle')
    for module in (image, oracle):
        if Path(module.__file__).resolve() != tools / (module.__name__ + '.py'):
            raise ValueError('module did not come from the explicit OS repository')
    expected_architectures = {'i386', 'x86_64', 'aarch64', 'arm32', 'rv32', 'rv64',
                              'loongarch64', 'mips', 'mips64', 'ppc'}
    if set(oracle.ARCH_ENDIAN) != expected_architectures or set(image.EPOCHS) != {2208988800, -123456789}:
        raise ValueError('the ten-profile, two-epoch model matrix must remain complete')
    output.mkdir(parents=True, exist_ok=False)
    model = ModelChecks(repository, output, image, oracle)
    report = {'status': 'running', 'checks': 0,
              'scope': 'hosted independent raw-image and synthetic-log oracle tests',
              'target_execution': False, 'qemu_execution': False, 'synthetic_logs': True,
              'repository': str(repository), 'source_sha256': source_hashes,
              'host_tool_sha256': {str(path): sha(path) for path in model.host_tools.values()},
              'commands': model.commands}
    result_path = output / 'result.json'
    def save():
        report['checks'] = model.checks
        result_path.write_text(json.dumps(report, indent=2) + '\n')
    save()
    try:
        model.exercise(source_hashes)
        report.update(status='passed', source_stable=True,
                      images={name: sha(output / name) for name in ('post2038.img', 'negative.img', 'blank.img')})
    except BaseException as error:
        report.update(status='failed', error=str(error))
        raise
    finally:
        save()
    print(json.dumps({'status': report['status'], 'checks': model.checks,
                      'scope': report['scope'], 'result': str(result_path),
                      'receipt_sha256': sha(result_path)}))


if __name__ == '__main__':
    main()

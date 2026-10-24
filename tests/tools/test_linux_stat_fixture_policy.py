"""Disposable stat fixture exceptions must not broaden bootstrap root policy."""
from pathlib import Path
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location('fixture_policy_' + name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policy, fixture = load('rootfs_policy'), load('linux_stat_image')


@unittest.skipUnless(shutil.which('mke2fs') and shutil.which('e2fsck'), 'ext4 fixture tools required')
class LinuxStatFixturePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='linux-stat-policy-')
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.root = self.work / 'root'
        self.root.mkdir()
        fixture.prepare_root(self.root)
        image = self.work / 'raw.img'
        subprocess.run(['mke2fs', '-q', '-t', 'ext4', '-b', '4096', '-I', '256',
                        '-O', 'none,extent,filetype,sparse_super,large_file',
                        '-E', 'lazy_itable_init=0', '-m', '0', '-d', str(self.root),
                        str(image), '16M'], check=True, capture_output=True)
        self.raw = image.read_bytes()

    def test_fixture_admits_only_exact_alias_and_modes(self):
        with self.assertRaisesRegex(ValueError, 'aliased inode'):
            policy.normalize_bootstrap_root(self.raw, self.root)
        data = policy.normalize_bootstrap_root(self.raw, self.root, profile='linux-stat-fixture-v1')
        image = policy.Ext4(data)
        paths = image.paths()
        self.assertEqual(paths['/home/stat-file'], paths['/home/stat-alias'])
        for name, mode in (('/home', 0o40777), ('/home/stat-file', 0o100600),
                           ('/home/stat-renamed-dir', 0o40700), ('/home/stat-link', 0o120777)):
            row = image.metadata(paths[name])
            self.assertEqual((row['mode'], row['uid'], row['gid']), (mode, 0, 0))
        output = self.work / 'normalized.img'
        output.write_bytes(data)
        subprocess.run(['e2fsck', '-fn', str(output)], check=True, capture_output=True)

    def test_frozen_fixture_retains_and_executes_the_metadata_policy(self):
        inventory = self.work / 'sources.json'
        subprocess.run([sys.executable, '-B', str(ROOT / 'tools/freeze_linux_stat_sources.py'),
                        '--output', str(inventory)], check=True, capture_output=True)
        files = json.loads(inventory.read_text())['files']
        retained = self.work / 'retained'
        for name in ('tools/mkext4.py', 'tools/rootfs_policy.py'):
            self.assertIn(name, files)
            target = retained / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        output = self.work / 'retained.img'
        subprocess.run([sys.executable, '-B', str(retained / 'tools/mkext4.py'),
                        '--root', str(self.root), '--out', str(output),
                        '--profile', 'linux-stat-fixture-v1'], check=True, capture_output=True)
        raw = fixture.Image(output.read_bytes())
        self.assertEqual(raw.lookup('/home/stat-file'), raw.lookup('/home/stat-alias'))

    def test_fixture_rejects_staged_third_link_and_wrong_identity(self):
        extra = self.work / 'extra'
        os.link(self.root / 'home/stat-file', extra)
        with self.assertRaisesRegex(ValueError, 'link count'):
            policy.normalize_bootstrap_root(self.raw, self.root, profile='linux-stat-fixture-v1')

        extra.unlink()
        alias = self.root / 'home/stat-alias'
        alias.unlink()
        alias.write_bytes(fixture.CONTENT)
        os.link(self.root / 'home/stat-file', self.work / 'file-spare')
        os.link(alias, self.work / 'alias-spare')
        with self.assertRaisesRegex(ValueError, 'hardlink identity'):
            policy.normalize_bootstrap_root(self.raw, self.root, profile='linux-stat-fixture-v1')

    def test_fixture_does_not_admit_unrelated_hardlinks(self):
        (self.root / 'unrelated').write_bytes(b'other')
        os.link(self.root / 'unrelated', self.root / 'unrelated-alias')
        output = self.work / 'unexpected.img'
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/mkext4.py'),
                                 '--root', str(self.root), '--out', str(output),
                                 '--profile', 'linux-stat-fixture-v1'], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('no unapproved aliased inode', result.stderr)
        self.assertFalse(output.exists())

    def test_fixture_rejects_symlink_parent_and_changed_contents(self):
        child = self.root / 'home/stat-renamed-dir'
        child.rename(self.work / 'outside')
        child.symlink_to(self.work / 'outside', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'ordinary'):
            policy.normalize_bootstrap_root(self.raw, self.root, profile='linux-stat-fixture-v1')
        child.unlink()
        (self.work / 'outside').rename(child)
        (self.root / 'home/stat-file').write_bytes(b'wrong')
        with self.assertRaisesRegex(ValueError, 'fixture bytes'):
            policy.normalize_bootstrap_root(self.raw, self.root, profile='linux-stat-fixture-v1')

    def test_raw_link_inventory_and_unbounded_block_exponent_are_rejected(self):
        image = policy.Ext4(self.raw)
        offset = image.inode(image.paths()['/home/stat-file'])
        changed = bytearray(self.raw)
        struct.pack_into('<H', changed, offset + 26, 3)
        with self.assertRaisesRegex(ValueError, 'link inventory'):
            policy.normalize_bootstrap_root(changed, self.root, profile='linux-stat-fixture-v1')
        for exponent in (0, 1, 3, 31, 0xffffffff):
            changed = bytearray(self.raw)
            struct.pack_into('<I', changed, 1048, exponent)
            with self.subTest(exponent=exponent), self.assertRaisesRegex(ValueError, 'block-size exponent'):
                fixture.Image(changed)

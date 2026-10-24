"""Protected first-boot seed packaging; no guest authentication or durability."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / ('tools/' + name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


legacy = module('rootfs_policy')
journalled = module('journalled_rootfs_policy')


class AccountPackagingTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory) / 'stage'
        (root / 'etc').mkdir(parents=True)
        (root / 'etc/accounts.db').write_bytes(b'OKACCOUNTS 1\nstate unconfigured\n')
        (root / 'root').mkdir()
        return root

    def test_rejects_nonseed_databases_before_image_access(self):
        for content in (b'', b'OKACCOUNTS 2\nstate unconfigured\n',
                        b'OKACCOUNTS 1\nstate active\n', b'OKACCOUNTS 1\nstate unconfigured\n\n'):
            with tempfile.TemporaryDirectory() as directory:
                root = self.fixture(directory)
                (root / 'etc/accounts.db').write_bytes(content)
                with self.assertRaisesRegex(ValueError, 'explicit unconfigured seed'):
                    legacy.normalize_bootstrap_root(b'', root)
                with self.assertRaisesRegex(ValueError, 'explicit unconfigured seed'):
                    journalled.inventory(root)

    def test_rejects_symlinks_and_wrong_types_for_protected_paths(self):
        for name in ('etc/accounts.db', 'root'):
            for kind in ('symlink', 'wrong-type'):
                with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory() as directory:
                    root = self.fixture(directory)
                    path = root / name
                    if path.is_dir():
                        path.rmdir()
                    else:
                        path.unlink()
                    if kind == 'symlink':
                        path.symlink_to('/outside-host-target')
                    elif name == 'root':
                        path.write_bytes(b'not a home directory')
                    else:
                        path.mkdir()
                    message = 'ordinary directory' if name == 'root' else 'explicit unconfigured seed'
                    with self.assertRaisesRegex(ValueError, message):
                        legacy.normalize_bootstrap_root(b'', root)
                    with self.assertRaisesRegex(ValueError, message):
                        journalled.inventory(root)


if __name__ == '__main__':
    unittest.main()

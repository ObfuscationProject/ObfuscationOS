import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tools'))
from qualification_artifacts import preserved_artifact_path


class ArtifactRetentionTests(unittest.TestCase):
    def path(self, source):
        return preserved_artifact_path(source, '/tmp/retention/Kernel', '/tmp/retention/OS',
                                       '/tmp/retention/output', '/tmp/retention/musl', '/tmp/retention/clock',
                                       '/tmp/retention/maintained')

    def test_same_basename_inputs_and_receipt_are_distinct(self):
        sources = ['/tmp/retention/musl/x86_64/bootstrap.elf', '/tmp/retention/clock/x86_64/bootstrap.elf',
                   '/tmp/retention/output/x86_64/debug/manifest.json',
                   '/tmp/retention/musl/x86_64/manifest.json', '/tmp/retention/clock/x86_64/manifest.json',
                   '/tmp/retention/maintained/x86_64/bootstrap.elf', '/tmp/retention/maintained/x86_64/manifest.json']
        self.assertEqual(len({self.path(path) for path in sources}), len(sources))
        self.assertEqual(self.path(sources[0]), Path('musl-probe/x86_64/bootstrap.elf'))
        self.assertEqual(self.path(sources[1]), Path('clock-set-probe/x86_64/bootstrap.elf'))
        self.assertEqual(self.path(sources[5]), Path('maintained-time-probe/x86_64/bootstrap.elf'))

    def test_repo_artifacts_keep_repository_identity(self):
        self.assertNotEqual(self.path('/tmp/retention/Kernel/build/kernel.bin'),
                            self.path('/tmp/retention/OS/build/kernel.bin'))

    def test_undeclared_external_root_is_rejected(self):
        with self.assertRaises(ValueError): self.path('/tmp/retention/unselected/bootstrap.elf')
        with self.assertRaises(ValueError): self.path('/tmp/retention/musl/../unselected/bootstrap.elf')


if __name__ == '__main__': unittest.main()

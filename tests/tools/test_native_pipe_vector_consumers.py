"""Inherited incidental diagnostics share scalar/vector live accounting."""
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_pipe_io_events as io
from test_native_pipe_io_events import ARCHES, writes
from test_native_child_consumers import collector

CONSUMERS = ('futex_signal', 'poll_signal', 'poll_temporary_mask', 'poll_mask_exec', 'child_wait')


def vectors(arch):
    scalar = writes(arch).replace(b'pid=900001 tid=900002', b'pid=900003 tid=900004')
    base = 0x10000000 if arch in ('aarch64', 'arm32') else 0x40000000
    scalar = scalar.replace(b'OK_NATIVE_PIPE_WRITE_', b'OK_NATIVE_PIPE_WRITEV_')
    scalar = scalar.replace(b'input=', b'array=')
    scalar = re.sub(rb'syscall=[0-9]+', b'syscall=' + str(io.vector.WRITEV[arch]).encode(), scalar)
    return scalar.replace(b'bytes=1', f'bytes=1 iovcnt=2 vectors=1:0,{base+8192}:1'.encode())


def overlap(arch):
    scalar = writes(arch).splitlines(keepends=True)
    vector = vectors(arch).replace(b'live=1', b'live=2').replace(b'live=0', b'live=1')
    return b''.join(scalar[:2]) + vector + scalar[2]


class VectorConsumerTests(unittest.TestCase):
    def test_combined_incidental_ownership_allten(self):
        for arch in ARCHES:
            self.assertEqual(len(io.native_events(overlap(arch), arch)), 6)
            for name in CONSUMERS:
                module = collector(name)
                original = module.fixture(arch)
                expected = module.validate(original, arch)
                for index in range(5):
                    modified = original.copy()
                    at = modified[index].rfind(b'OK_NATIVE_FRAMES ')
                    modified[index] = modified[index][:at] + overlap(arch) + modified[index][at:]
                    with self.subTest(arch=arch, consumer=name, span=index):
                        self.assertEqual(module.validate(modified, arch), expected)

    def test_combined_corruptions_allten(self):
        for arch in ARCHES:
            original = overlap(arch)
            corruptions = (
                original.replace(b'live=2', b'live=1'),
                original.replace(b'iovcnt=2', b'iovcnt=3', 1),
                original.replace(b'vectors=1:0', b'vectors=2:0', 1),
                original.replace(b'OK_NATIVE_PIPE_WRITEV_COMPLETE ', b'UNKNOWN_PIPE_COMPLETE ', 1),
                original.replace(b'pinned=0', b'pinned=1', 1),
            )
            for corrupt in corruptions:
                with self.subTest(arch=arch), self.assertRaises(ValueError):
                    io.native_events(corrupt, arch)
                for name in CONSUMERS:
                    module = collector(name)
                    modified = module.fixture(arch)
                    at = modified[2].rfind(b'OK_NATIVE_FRAMES ')
                    modified[2] = modified[2][:at] + corrupt + modified[2][at:]
                    with self.subTest(arch=arch, consumer=name), self.assertRaises(ValueError):
                        module.validate(modified, arch)

    def test_original_publication_adjacency(self):
        for arch in ARCHES:
            scalar = writes(arch).splitlines(keepends=True)
            corrupt = scalar[0] + vectors(arch) + b''.join(scalar[1:])
            with self.subTest(arch=arch), self.assertRaises(ValueError):
                io.native_events(corrupt, arch)


if __name__ == '__main__':
    unittest.main()

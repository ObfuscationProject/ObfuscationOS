"""Synthetic read/write ledger composition and inherited consumer regression."""
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import native_pipe_io_events as io
from test_native_child_consumers import collector

ARCHES = ('x86_64', 'i386', 'aarch64', 'arm32', 'rv32', 'rv64',
          'loongarch64', 'mips', 'mips64', 'ppc')
COLLECTORS = ('pipe_signal', 'futex_signal', 'poll_signal', 'poll_temporary_mask', 'poll_mask_exec', 'child_wait')


def writes(arch):
    base = 0x10000000 if arch in ('aarch64', 'arm32') else 0x40000000
    identity = f'pid=900001 tid=900002 wait=2 request=2 input={base+4096} fd=7 description=9 pipe=3 bytes=1'
    return (f'OK_NATIVE_PIPE_WRITE_WAIT {identity} stage=arm live=1\n'
            f'OK_NATIVE_PIPE_WRITE_ORIGIN pid=900001 tid=900002 request=2 wait=2 origin=88 pc={base+1024} syscall={io.write.WRITE[arch]} fd=7 input={base+4096} bytes=1\n'
            f'OK_NATIVE_PIPE_WRITE_COMPLETE {identity} result=1 outcome=ready pinned=0 live=0\n').encode()


class PipeIOComposition(unittest.TestCase):
    def test_complete_write_ledger_and_unmodified_read_cases(self):
        for arch in ARCHES:
            self.assertEqual(len(io.native_events(writes(arch), arch)), 3)
            for name in COLLECTORS:
                module = collector(name); original = module.fixture(arch)
                expected = module.validate(original, arch)
                parts = [span[:span.rfind(b'OK_NATIVE_FRAMES ')]+writes(arch)+span[span.rfind(b'OK_NATIVE_FRAMES '):] for span in original]
                with self.subTest(arch=arch, collector=name):
                    self.assertEqual(module.validate(parts, arch), expected)

    def test_mutated_write_records_are_never_hidden_from_inherited_consumers(self):
        for name in COLLECTORS:
            module = collector(name); original = module.fixture('x86_64')
            pair = writes('x86_64'); lines = pair.splitlines(keepends=True)
            replacements = (b''.join(lines[:-1]), lines[0]+pair, pair.replace(b'pinned=0', b'pinned=1'),
                            pair.replace(b'bytes=1', b'bytes=4098'), pair.replace(b'outcome=ready', b'outcome=unknown'),
                            b'junk'+pair, pair.replace(b'result=1 ', b'result=0 '))
            for span in range(5):
                for corrupt in replacements:
                    parts = original.copy(); at=parts[span].rfind(b'OK_NATIVE_FRAMES ');parts[span]=parts[span][:at]+corrupt+parts[span][at:]
                    with self.subTest(collector=name, span=span), self.assertRaises(ValueError):
                        module.validate(parts, 'x86_64')

    def test_write_filter_preserves_read_publication_adjacency(self):
        module = collector('pipe_signal'); parts = module.fixture('x86_64')
        body = parts[2]; lines = body.splitlines(keepends=True)
        # A balanced unrelated write must not make interrupted-read publication
        # or arm/origin pairs appear adjacent after namespace separation.
        for tag in (b'OK_NATIVE_PIPE_ORIGIN ', b'OK_NATIVE_PIPE_SIGNAL '):
            i = next(i for i, line in enumerate(lines) if line.startswith(tag))
            modified = b''.join(lines[:i]) + writes('x86_64') + b''.join(lines[i:])
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                io.native_events(modified, 'x86_64')
            import native_pipe_write_evidence as write_guest
            with self.subTest(tag=tag, consumer='write-guest'), self.assertRaises(ValueError):
                write_guest.pipe_events(modified, 'x86_64')

    def test_incidental_write_signals_cannot_claim_inherited_read_coverage(self):
        pair = writes('x86_64')
        pair = pair.replace(b'result=1 outcome=ready', b'result=-4 outcome=interrupted')
        pair += (b'OK_NATIVE_PIPE_WRITE_SIGNAL pid=900001 tid=900002 request=2 wait=2 origin=88 '
                 b'signal=10 outcome=eintr pc=1073742848 syscall=1 fd=7 input=1073745920 bytes=1 pinned=0 live=0\n')
        with self.assertRaises(ValueError):
            io.native_events(pair, 'x86_64')


if __name__ == '__main__':
    unittest.main()

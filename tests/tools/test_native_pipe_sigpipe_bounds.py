"""Native SIGPIPE descriptor admission; synthetic transcripts, not execution."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT / 'tests/tools')]
from test_native_pipe_sigpipe import transcript, validate
from native_pipe_vector_events import ARCHES


def descriptor_control(arch, field, value):
    parts = transcript(arch)
    case = b'resumed=0 case=0 ' if field == 'fd' else b'resumed=0 case=12 '
    line = next(line for line in parts[2].splitlines(keepends=True)
                if line.startswith(b'PIPE_SIGPIPE_CASE_BEGIN ') and case in line)
    original = b' fd=4 ' if field == 'fd' else b' readfd=3 '
    replacement = f' {field}={value} '.encode()
    if original not in line or original == replacement:
        raise AssertionError('descriptor control must change its intended bytes')
    altered = line.replace(original, replacement, 1)
    parts[2] = parts[2].replace(line, altered, 1)
    if altered == line or altered not in parts[2]:
        raise AssertionError('descriptor control was not inserted')
    return parts


class SigpipeDescriptorBoundsTests(unittest.TestCase):
    def test_out_of_table_slots_rejected_in_complete_wrapper(self):
        for arch in ARCHES:
            for field in ('fd', 'readfd'):
                for value in (32, 2147483647):
                    with self.subTest(arch=arch, field=field, value=value):
                        with self.assertRaisesRegex(ValueError, 'descriptor exceeds native SDK31 table'):
                            validate(descriptor_control(arch, field, value), arch)

    def test_last_valid_slot_accepted(self):
        for arch in ARCHES:
            for field in ('fd', 'readfd'):
                with self.subTest(arch=arch, field=field):
                    self.assertEqual(validate(descriptor_control(arch, field, 31), arch)['runs'], 2)

    def test_qualifier_scope_names_actual_probe(self):
        source = (ROOT / 'tools/qualify_native_pipe_sigpipe.py').read_text()
        self.assertIn('automatic SIGPIPE after immediate/resumed EPIPE', source)
        self.assertNotIn('nested/lifecycle/full ELF replacement', source)


if __name__ == '__main__':
    unittest.main()

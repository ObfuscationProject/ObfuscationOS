import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from entropy_observer import validate_complete
from dynamic_startup_observer import STATIC_MARKER, STATIC_RUNNER, STATIC_NO_ENTROPY, STATIC_NO_ENTROPY_RUNNER

def transcript(arch='x86_64', enabled=True):
    transport = 'mmio' if arch in {'aarch64', 'arm32', 'rv32', 'rv64'} else 'pci'
    source = 'virtio-rng-' + transport + ' state=ready' if enabled else 'none state=unavailable'
    serial = ('OK_ENTROPY source=' + source + '\noksh> ').encode()
    runs = []
    for _ in range(2):
        start = len(serial)
        records = (STATIC_MARKER, STATIC_RUNNER) if enabled else (STATIC_NO_ENTROPY, STATIC_NO_ENTROPY_RUNNER)
        serial += b'static-entropy-runner\n' + b'\n'.join(records) + b'\noksh> '
        runs.append((start, len(serial)))
    start = len(serial)
    serial += b'hello | cat\nhello from ObfuscationOS userland\noksh> '
    return serial, runs, (start, len(serial))

class EntropyObserverTests(unittest.TestCase):
    def test_all_profiles_and_controls(self):
        for arch in ('i386', 'x86_64', 'aarch64', 'arm32', 'rv64', 'rv32', 'loongarch64', 'mips', 'mips64', 'ppc'):
            for enabled in (False, True):
                self.assertEqual(validate_complete(*transcript(arch, enabled), architecture=arch, enabled=enabled)['executed'], enabled)

    def test_source_mismatch(self):
        with self.assertRaises(ValueError):
            validate_complete(*transcript(), architecture='aarch64', enabled=True)

    def test_negative_cannot_pass_positive(self):
        with self.assertRaises(ValueError):
            validate_complete(*transcript(enabled=False), architecture='x86_64', enabled=True)

    def test_wrapped_truncated_and_duplicate_records(self):
        serial, runs, pipeline = transcript()
        for changed in (serial.replace(STATIC_MARKER, b'x' + STATIC_MARKER, 1),
                        serial.replace(STATIC_MARKER, STATIC_MARKER[:-1], 1),
                        serial.replace(STATIC_MARKER, STATIC_MARKER + b'\n' + STATIC_MARKER, 1)):
            with self.assertRaises(ValueError):
                validate_complete(changed, runs, pipeline, architecture='x86_64', enabled=True)

    def test_no_gaps_or_tail(self):
        serial, runs, pipeline = transcript()
        for modified in ([(runs[0][0], runs[0][1]-1), runs[1]], [runs[0], (runs[1][0]+1, runs[1][1])]):
            with self.assertRaises(ValueError):
                validate_complete(serial, modified, pipeline, architecture='x86_64', enabled=True)
        with self.assertRaises(ValueError):
            validate_complete(serial + b'extra\noksh> ', runs, pipeline, architecture='x86_64', enabled=True)

    def test_extra_acceptance_or_failure(self):
        serial, runs, pipeline = transcript()
        for token in (STATIC_MARKER, b'OK_TEST_FAIL entropy', b'OK_ENTROPY source=none state=unavailable'):
            with self.assertRaises(ValueError):
                validate_complete(token + b'\n' + serial, runs, pipeline, architecture='x86_64', enabled=True)

if __name__ == '__main__':
    unittest.main()

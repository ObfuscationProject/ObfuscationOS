"""Reject contradictory guest receipts even after a successful final marker."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from native_removal_evidence import validate

IMAGE = b'OK_NATIVE_IMAGE personality=linux source=firmware pages=19 physical_first=0x0000000002000000 physical_last=0x0000000002012000 owner=retained\n'
RUN = (IMAGE + b'REMOVAL_BEGIN cases=8\n'
       b'REMOVAL_CASE index=0 name=flags pass=1\n'
       b'REMOVAL_CASE index=1 name=paths pass=1\n'
       b'REMOVAL_CASE index=2 name=retained pass=1\n'
       b'REMOVAL_CASE index=3 name=recreated pass=1\n'
       b'REMOVAL_CASE index=4 name=directories pass=1\n'
       b'REMOVAL_CASE index=5 name=libc_unlink pass=1\n'
       b'REMOVAL_CASE index=6 name=libc_rmdir pass=1\n'
       b'REMOVAL_CASE index=7 name=absolute pass=1\n'
       b'REMOVAL_PASS cases=8\n'
       b'oksh> ')
BOOT = b'OK_SYSTEM_GUI boot=complete\nOK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\noksh> '


class RemovalEvidenceTests(unittest.TestCase):
    def fixture(self, first=RUN, second=RUN, tail=b''):
        return BOOT + first + second + tail, (len(BOOT), len(BOOT + first), len(BOOT + first + second))

    def test_two_complete_guest_runs(self):
        serial, boundaries = self.fixture()
        self.assertEqual(validate(serial, boundaries)['runs'], 2)
        self.assertEqual(validate(serial.replace(b'\n', b'\r\n'),
            tuple(value + serial[:value].count(b'\n') for value in boundaries))['runs'], 2)

    def test_missing_duplicate_order_and_wrong_result(self):
        row = b'REMOVAL_CASE index=2 name=retained pass=1\n'
        for first in (RUN.replace(row, b''), RUN.replace(row, row + row),
                      RUN.replace(row, row.replace(b'pass=1', b'pass=0')),
                      RUN.replace(row, b'').replace(b'REMOVAL_PASS', row + b'REMOVAL_PASS')):
            with self.subTest(first=first), self.assertRaises(ValueError):
                validate(*self.fixture(first=first))

    def test_failure_and_incomplete_records_after_pass(self):
        for tail in (b'REMOVAL_FAIL code=126\n', b'REMOVAL_FAIL code=', b'OK_TEST_FAIL final\n',
                     b'REMOVAL_CASE index=0', b'REMOVAL_PASS cases=8\n'):
            with self.subTest(tail=tail), self.assertRaises(ValueError):
                validate(*self.fixture(tail=tail))

    def test_incomplete_and_prefixed_record(self):
        for first in (RUN.replace(b'REMOVAL_PASS cases=8\n', b'REMOVAL_PASS cases=8'),
                      RUN.replace(b'REMOVAL_BEGIN', b'extra REMOVAL_BEGIN')):
            with self.assertRaises(ValueError):
                validate(*self.fixture(first=first))

    def test_boundary_and_boot_failures(self):
        serial, boundaries = self.fixture()
        for values in ((True, boundaries[1], boundaries[2]),
                       (boundaries[0] - 1, boundaries[1], boundaries[2]),
                       (boundaries[1], boundaries[0], boundaries[2])):
            with self.assertRaises(ValueError):
                validate(serial, values)
        with self.assertRaises(ValueError):
            validate(serial.replace(b'boot=complete', b'boot=degraded'), boundaries)

    def test_linux_image_ownership_and_profile(self):
        for first in (RUN.replace(IMAGE, b''), RUN.replace(IMAGE, IMAGE + IMAGE),
                      RUN.replace(b'owner=retained', b'owner=lost'),
                      RUN.replace(b'source=firmware', b'source=linker')):
            with self.subTest(first=first), self.assertRaises(ValueError):
                validate(*self.fixture(first=first))
        with self.assertRaises(ValueError):
            validate(*self.fixture(tail=IMAGE))
        serial, boundaries = self.fixture()
        self.assertEqual(validate(serial.replace(b'source=firmware', b'source=linker'),
            tuple(value - serial[:value].count(b'source=firmware') * 2 for value in boundaries), 'mips')['runs'], 2)


if __name__ == '__main__':
    unittest.main()

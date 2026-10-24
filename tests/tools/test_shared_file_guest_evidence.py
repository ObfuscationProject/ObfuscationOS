"""Acceptance parser controls; these synthetic records are not guest execution."""
from pathlib import Path
import itertools
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from test_shared_files import MARKERS, run_evidence, stable_owners

FRAME = (b"OK_NATIVE_FRAMES version=2 source=firmware used=20 total=1024 allocations=120 releases=100 "
         b"pinned=0 user=17 objects=3 free=1004 pending=0 reserve=64 user_limit=960 object_quarantine=0\n")
FILE = (b"OK_NATIVE_SHARED_FILES_LEDGER version=1 files=0 aliases=0 retiring_files=0 retained_frames=0 reserved_cells=0\n")
OUTCOME = b"\n".join(MARKERS) + b"\n"


class SharedFileGuestEvidenceTests(unittest.TestCase):
    def test_completed_segment_binds_zero_shared_and_exact_physical_owners(self):
        evidence = run_evidence(OUTCOME + FRAME + FILE + b"oksh> ")
        self.assertEqual(evidence["ledger_serial_offset"], len(OUTCOME))
        self.assertEqual(evidence["shared_files"]["aliases"], 0)
        self.assertEqual(stable_owners(evidence)["used"], 20)

    def test_missing_or_duplicate_probe_markers_are_refused(self):
        for marker in MARKERS:
            for outcome in (OUTCOME.replace(marker + b"\n", b""), OUTCOME + marker + b"\n"):
                with self.subTest(marker=marker), self.assertRaises(ValueError):
                    run_evidence(outcome + FRAME + FILE)

    def test_marker_lines_require_exact_boundaries(self):
        for marker in MARKERS:
            for malformed in (b"INVALID_PREFIX_" + marker, b" " + marker, marker + b" suffix", marker + b" "):
                with self.subTest(marker=marker, malformed=malformed), self.assertRaises(ValueError):
                    run_evidence(OUTCOME.replace(marker + b"\n", malformed + b"\n") + FRAME + FILE)
        for prefix in (b"OK_NATIVE_FRAMES ", b"OK_NATIVE_SHARED_FILES_LEDGER "):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                run_evidence((OUTCOME + FRAME + FILE).replace(prefix, b"INVALID_PREFIX_" + prefix))
        run_evidence((OUTCOME + FRAME + FILE).replace(b"\n", b"\r\n"))

    def test_every_out_of_order_suite_is_refused(self):
        self.assertTrue(MARKERS[0].startswith(b"OK_NATIVE_SHARED_FILES "))
        self.assertTrue(MARKERS[1].startswith(b"OK_NATIVE_SHARED_RIGHTS "))
        self.assertTrue(MARKERS[2].startswith(b"OK_MUSL_SHARED_FILES "))
        self.assertTrue(MARKERS[3].startswith(b"OK_STATIC_SHARED_RIGHTS "))
        self.assertTrue(MARKERS[4].startswith(b"OK_SHARED_FILES_SUITE "))
        for order in itertools.permutations(MARKERS):
            if order == MARKERS:
                continue
            with self.subTest(order=order), self.assertRaisesRegex(ValueError, "runner order"):
                run_evidence(b"\n".join(order) + b"\n" + FRAME + FILE)

    def test_realistic_pool_capacity_and_quota_consistency_are_required(self):
        for frame in (FRAME.replace(b"free=1004", b"free=0"),
                      FRAME.replace(b"user_limit=960", b"user_limit=1024"),
                      FRAME.replace(b"reserve=64", b"reserve=1025"),
                      FRAME.replace(b"total=1024", b"total=1025").replace(b"free=1004", b"free=1005").replace(b"user_limit=960", b"user_limit=961"),
                      FRAME.replace(b"total=1024", b"total=0"),
                      FRAME.replace(b"used=20", b"used=65").replace(b"user=17", b"user=0").replace(b"objects=3", b"objects=65").replace(b"free=1004", b"free=959").replace(b"allocations=120", b"allocations=165"),
                      FRAME.replace(b"used=20", b"used=961").replace(b"user=17", b"user=961").replace(b"objects=3", b"objects=0").replace(b"free=1004", b"free=63").replace(b"allocations=120", b"allocations=1061")):
            with self.subTest(frame=frame), self.assertRaisesRegex(ValueError, "capacity or quota"):
                run_evidence(OUTCOME + frame + FILE)

    def test_smaller_realistic_pool_is_admitted(self):
        frame = FRAME.replace(b"total=1024", b"total=512").replace(b"free=1004", b"free=492").replace(b"user_limit=960", b"user_limit=448")
        self.assertEqual(run_evidence(OUTCOME + frame + FILE)["frames"]["total"], 512)

    def test_precompletion_or_unpaired_ledgers_are_refused(self):
        for serial in (FRAME + FILE + OUTCOME, OUTCOME + FRAME, OUTCOME + FILE,
                       OUTCOME + FRAME + b"unrelated record\n" + FILE):
            with self.subTest(serial=serial), self.assertRaises(ValueError):
                run_evidence(serial)

    def test_final_live_or_quarantined_owners_are_refused(self):
        for name in (b"files", b"aliases", b"retiring_files", b"retained_frames", b"reserved_cells"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "not fully reclaimed"):
                run_evidence(OUTCOME + FRAME + FILE.replace(name + b"=0", name + b"=1"))
        for name in (b"pinned", b"pending", b"object_quarantine"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "still pending"):
                run_evidence(OUTCOME + FRAME.replace(name + b"=0", name + b"=1") + FILE)

    def test_earlier_zero_cannot_hide_final_leak(self):
        with self.assertRaises(ValueError):
            run_evidence(OUTCOME + FRAME + FILE + FRAME + FILE.replace(b"aliases=0", b"aliases=1"))

    def test_newer_orphan_malformed_prefixed_or_truncated_ledgers_are_refused(self):
        candidates = (FRAME, FILE, FRAME.replace(b"used=20", b"used=invalid"),
                      FILE.replace(b"aliases=0", b"aliases=invalid"),
                      b"INVALID_PREFIX_" + FRAME, b"INVALID_PREFIX_" + FILE,
                      b"INVALID_PREFIX_" + FRAME + FILE,
                      FRAME + b"INVALID_PREFIX_" + FILE,
                      FRAME.rstrip(b"\n"), FILE.rstrip(b"\n"),
                      b"OK_NATIVE_FRAMES\n", b"OK_NATIVE_SHARED_FILES_LEDGER\n")
        for newer in candidates:
            with self.subTest(newer=newer), self.assertRaisesRegex(ValueError, "latest owner ledger"):
                run_evidence(OUTCOME + FRAME + FILE + newer)

    def test_latest_well_formed_zero_pair_is_selected(self):
        serial = OUTCOME + FRAME + FILE + b"unrelated record\n" + FRAME + FILE
        self.assertEqual(run_evidence(serial)["ledger_serial_offset"], len(serial) - len(FRAME + FILE))
        self.assertEqual(run_evidence(serial.replace(b"\n", b"\r\n"))["frames"]["used"], 20)

    def test_duplicate_missing_wrong_version_and_inconsistent_counts_are_refused(self):
        for frame in (FRAME.replace(b"used=20", b"used=20 used=20"), FRAME.replace(b"used=20 ", b""),
                      FRAME.replace(b"version=2", b"version=3"), FRAME.replace(b"releases=100", b"releases=99"),
                      FRAME.replace(b"objects=3", b"objects=4"), FRAME.replace(b"pinned=0", b"pinned=-1")):
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                run_evidence(OUTCOME + frame + FILE)

    def test_success_markers_cannot_hide_probe_failure(self):
        with self.assertRaisesRegex(ValueError, "probe or kernel failure"):
            run_evidence(OUTCOME + b"SHARED_FILES_FAIL reason=alias errno=14\n" + FRAME + FILE)


if __name__ == "__main__":
    unittest.main()

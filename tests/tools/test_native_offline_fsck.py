"""Injected offline failures must remain fatal after successful guest execution."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from native_offline_fsck import require_final_fsck


class OfflineFsckTests(unittest.TestCase):
    def test_final_fsck_failure_propagates_and_saves_failed_receipt(self):
        record = {"status": "guest-passed-awaiting-offline", "guest_executed": True}
        saved = []

        def failed_check():
            record["status"] = "failed"
            raise RuntimeError("final-fsck failed; retained log contains diagnostics")

        with self.assertRaisesRegex(RuntimeError, "final-fsck failed"):
            require_final_fsck(record, failed_check, lambda: saved.append(dict(record)))
        self.assertEqual(record["status"], "failed")
        self.assertIn("final-fsck failed", record["offline_error"])
        self.assertEqual(saved, [record])

    def test_success_restores_guest_state_without_resurrecting_guest_failure(self):
        for prior in ("guest-passed-awaiting-offline", "failed"):
            with self.subTest(prior=prior):
                record = {"status": prior}
                saved = []

                def passed_check():
                    record["status"] = "passed"

                require_final_fsck(record, passed_check, lambda: saved.append(dict(record)))
                self.assertEqual(saved, [{"status": prior}])
                self.assertNotIn("offline_error", record)


if __name__ == "__main__":
    unittest.main()

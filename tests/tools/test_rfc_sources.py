"""Negative controls for exact RFC reference byte readback."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / "tools"))
from check_rfc_sources import readback  # noqa: E402


class RfcSourceReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sources = self.root / "sources"
        self.sources.mkdir()
        self.plan = self.root / "NETWORK_SERVICES.md"
        self.manifest = self.root / "sources.json"
        original = json.loads((PROJECT / "docs/plans/contracts/drafts/internet_rfc_reference_sources.json").read_text())
        numbers = [row["number"] for row in original["rfc_sources"]]
        self.plan.write_text("# Network\n\n## 12. External reading and decision references\n\n" +
                             "\n".join(f"[RFC {n}](https://www.rfc-editor.org/rfc/rfc{n})" for n in numbers) + "\n")
        self.document = {
            "schema_version": 1,
            "scope": "NETWORK_SERVICES.md section 12 exact references",
            "qualification": "reference-bytes-only-unreviewed",
            "plan_sha256": hashlib.sha256(self.plan.read_bytes()).hexdigest(),
            "rfc_sources": [],
        }
        for number in numbers:
            name = f"rfc{number}.txt"
            payload = f"Request for Comments: {number}\nSynthetic fixture\n".encode()
            (self.sources / name).write_bytes(payload)
            self.document["rfc_sources"].append({
                "number": number, "file": name,
                "url": f"https://www.rfc-editor.org/rfc/rfc{number}.txt",
                "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
            })
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps(self.document))

    def check(self):
        return readback(self.manifest, self.plan, self.sources)

    def test_valid_byte_readback_retains_incomplete_qualification(self):
        result = self.check()
        self.assertEqual(result["rfc_count"], 47)
        self.assertFalse(result["clause_index_complete"])
        self.assertFalse(result["m0_complete"])

    def test_changed_source_bytes_fail(self):
        (self.sources / "rfc768.txt").write_bytes(b"Request for Comments: 768\nTampered\n")
        with self.assertRaisesRegex(ValueError, "source bytes differ"):
            self.check()

    def test_added_rfc_file_fails(self):
        (self.sources / "rfc9999.txt").write_bytes(b"Request for Comments: 9999\n")
        with self.assertRaisesRegex(ValueError, "extra or missing"):
            self.check()

    def test_plan_reference_change_fails(self):
        self.plan.write_text(self.plan.read_text().replace("rfc768)", "rfc769)"))
        with self.assertRaisesRegex(ValueError, "plan hash differs"):
            self.check()

    def test_duplicate_row_and_json_key_fail(self):
        self.document["rfc_sources"][1]["number"] = 768
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "duplicate RFC number"):
            self.check()
        self.manifest.write_text(self.manifest.read_text().replace('"schema_version": 1',
                                                            '"schema_version": 1, "schema_version": 1'))
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.check()

    def test_symlink_source_fails(self):
        source = self.sources / "rfc768.txt"
        source.unlink()
        source.symlink_to("/etc/hostname")
        with self.assertRaisesRegex(ValueError, "ordinary RFC file missing"):
            self.check()


if __name__ == "__main__":
    unittest.main()

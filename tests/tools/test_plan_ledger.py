"""Ledger admission tests: metadata never substitutes for executed evidence."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from plan_ledger import (CONTRACTS, load_json, m0_gaps, report, validate_inventory_coverage,
                         validate_ledger, validate_schema)


class PlanLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = load_json(CONTRACTS / "ledger.json")

    def setUp(self):
        self.ledger = copy.deepcopy(self.baseline)
        # Mutation tests own their synthetic artifacts; historical rows are
        # checked structurally below and by the separate receipt admission.
        self.ledger['evidence'] = []
        for requirement in self.ledger['requirements']:
            requirement['evidence_ids'] = []
            requirement['evidence_artifact_hash'] = None
        self.coverage = copy.deepcopy(load_json(CONTRACTS / "inventory_coverage.json"))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.artifacts = Path(self.temp.name)

    def validate(self):
        validate_ledger(self.ledger, evidence_root=self.artifacts)

    def requirement(self, name):
        return next(row for row in self.ledger["requirements"] if row["id"] == name)

    def add_evidence(self, test_id="T.sdk.artifacts", outcome="pass", arch="host", mode="host"):
        name = f"run-{len(self.ledger['evidence'])}"
        data = f"{name}: {test_id} {outcome}\n".encode()
        digest = hashlib.sha256(data).hexdigest()
        (self.artifacts / name).write_bytes(data)
        test = next(row for row in self.ledger["tests"] if row["id"] == test_id)
        evidence = {"id": name, "test_id": test_id, "architecture": arch, "mode": mode,
                    "execution": test["execution"], "outcome": outcome, "artifact": name, "sha256": digest}
        self.ledger["evidence"].append(evidence)
        return evidence

    def verified_sdk(self):
        req = self.requirement("A06.sdk")
        evidence = self.add_evidence()
        req.update(state="verified", limitations=[], evidence_ids=[evidence["id"]], evidence_artifact_hash=evidence["sha256"])
        return req, evidence

    def source_fixture_except(self, excluded_id):
        for row in self.ledger["references"]:
            if row["status"] != "source-pinned" or row["id"] == excluded_id:
                continue
            path = self.artifacts / row["archive_artifact"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((row["id"] + " source fixture").encode())
            row["archive_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()

    def coverage_link(self, req_id, source_id, source_section="fixture section"):
        req = self.requirement(req_id)
        return {"requirement_id": req_id, "source_id": source_id,
                "source_section": source_section,
                "ledger_source_version": req["source_version"],
                "ledger_source_section": req["source_section"],
                "relation": "Fixture mapping reviewed against the named normative unit and plan requirement.",
                "reviewer": "fixture reviewer", "reviewed_on": "2026-09-21"}

    def repin_index(self, indexes, name):
        index, path = indexes[name]
        data = (json.dumps(index, sort_keys=True) + "\n").encode()
        path.write_bytes(data)
        row = next(item for item in self.coverage["inventories"] if item["id"] == name)
        row["source_index"]["sha256"] = hashlib.sha256(data).hexdigest()

    def indexed_coverage(self):
        """Build small reviewed-index fixtures; they do not claim real source review."""
        associations = {
            "posix-clauses-options": ("P03.vm", "T.P03.vm"),
            "linux-abi-layouts": ("P01.bootstrap-codecs", "T.linux-abi-codecs"),
            "ext4-feature-combinations": ("S0.ext4-subset", "T.baseline.ext4"),
            "internet-rfc-clauses": ("N.internet-host", "T.N.internet-host"),
        }
        source_by_inventory = {row["id"]: row["source_ids"] for row in self.ledger["inventories"]}
        indexes = {}
        directory = self.artifacts / "docs/plans/contracts/indexes"
        directory.mkdir(parents=True)
        for row in self.coverage["inventories"]:
            name = row["id"]
            req_id, test_id = associations[name]
            index = {"schema_version": 1, "inventory_id": name,
                     "review_scope": "complete-selected-source-universe",
                     "source_ids": source_by_inventory[name],
                     "units": []}
            mappings = []
            for source_id in source_by_inventory[name]:
                unit_id = name + "." + source_id + ".fixture"
                index["units"].append({"id": unit_id, "source_id": source_id,
                                       "source_section": "fixture section", "obligation": "fixture obligation",
                                       "classification": "selected-profile",
                                       "architecture": list(self.requirement(req_id)["architecture"])})
                mappings.append({"unit_id": unit_id,
                                 "requirement_links": [self.coverage_link(req_id, source_id)],
                                 "test_ids": [test_id]})
            data = (json.dumps(index, sort_keys=True) + "\n").encode()
            path = directory / (name + ".json")
            path.write_bytes(data)
            row["source_index"] = {"artifact": "docs/plans/contracts/indexes/" + path.name,
                                   "sha256": hashlib.sha256(data).hexdigest(),
                                   "reviewer": "fixture reviewer", "reviewed_on": "2026-09-21"}
            row["mappings"] = mappings
            indexes[name] = (index, path)
        return indexes

    def test_seed_valid_but_m0_incomplete(self):
        self.validate()
        self.assertTrue(m0_gaps(self.ledger))
        self.assertIn("M0 incomplete", report(self.ledger))
        self.assertEqual({row["id"] for row in self.ledger["architectures"]},
                         {"i386", "x86_64", "aarch64", "arm32", "rv64", "rv32", "loongarch64", "mips", "mips64", "ppc"})

    def test_recorded_console_mappings_are_structurally_attached(self):
        # This checks schema/relationships only, with no artifact-byte claim.
        with mock.patch('plan_ledger.artifact') as artifacts:
            validate_ledger(copy.deepcopy(self.baseline), evidence_root=self.artifacts)
        self.assertEqual(artifacts.call_count, 11)
        rows = self.baseline['evidence']
        self.assertEqual(sum(row['execution'] == 'qemu-native' for row in rows), 2)
        self.assertEqual(sum(row['execution'].startswith('host-') for row in rows), 9)
        indexed = {row['id']: row for row in self.baseline['requirements']}
        self.assertEqual(set(indexed['P10.console-control']['architecture']),
                         {row['id'] for row in self.baseline['architectures']})
        self.assertEqual(indexed['P10.console-control-x86_64']['architecture'], ['x86_64'])
        self.assertEqual(indexed['N.console-login-pipeline-x86_64']['architecture'], ['x86_64'])
        for name in ('P10.console-control', 'P10.console-control-x86_64', 'N.console-login-pipeline-x86_64'):
            self.assertNotEqual(indexed[name]['state'], 'verified')
            self.assertTrue(indexed[name]['limitations'])
        self.assertTrue(m0_gaps(self.baseline))

    def test_reject_missing_architecture(self):
        self.ledger["architectures"].pop()
        with self.assertRaisesRegex(ValueError, "too few|ten"):
            self.validate()

    def test_reject_native_triple_drift(self):
        self.ledger["architectures"][0]["native_triple"] = "i386-linux-musl"
        with self.assertRaisesRegex(ValueError, "SDK contract"):
            self.validate()

    def test_reject_hidden_qualification_gap(self):
        self.ledger["architectures"][0]["qualification_gaps"] = []
        with self.assertRaisesRegex(ValueError, "explicit gaps"):
            self.validate()

    def test_reject_unsupported_abi_qualification(self):
        self.ledger["architectures"][0]["linux_qualification"] = "qualified"
        with self.assertRaisesRegex(ValueError, "qualification evidence protocol"):
            self.validate()

    def test_reject_unknown_state_and_fields(self):
        req = self.requirement("P03.vm")
        req["state"] = "mostly-verified"
        with self.assertRaisesRegex(ValueError, "enum"):
            self.validate()
        req["state"] = "planned"
        req["pretend_verified"] = True
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            self.validate()

    def test_reject_duplicate_identifiers(self):
        row = copy.deepcopy(self.ledger["requirements"][0])
        row["limitations"] = ["Different content must not disguise a duplicate identity."]
        self.ledger["requirements"].append(row)
        with self.assertRaisesRegex(ValueError, "duplicate id"):
            self.validate()

    def test_reject_unknown_and_cyclic_dependencies(self):
        req = self.requirement("P03.vm")
        req["dependencies"] = ["MISSING"]
        with self.assertRaisesRegex(ValueError, "unknown dependency"):
            self.validate()
        req["dependencies"] = ["P03.vm"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            self.validate()

    def test_reject_model_test_used_as_native(self):
        self.requirement("A04.native-baseline")["native_test_ids"] = ["T.baseline.models"]
        with self.assertRaisesRegex(ValueError, "wrong evidence layer"):
            self.validate()

    def test_reject_model_execution_labeled_native(self):
        self.ledger["tests"][0]["execution"] = "host-model"
        with self.assertRaisesRegex(ValueError, "layer and execution"):
            self.validate()

    def test_reject_missing_test_coverage(self):
        self.ledger["tests"][0]["architecture"].pop()
        with self.assertRaisesRegex(ValueError, "omits a required architecture"):
            self.validate()

    def test_reject_mandatory_waiver(self):
        req = self.requirement("P03.vm")
        req.update(state="not-applicable-with-rationale", requirement_level="mandatory")
        with self.assertRaisesRegex(ValueError, "cannot be waived"):
            self.validate()

    def test_verified_requires_real_artifact(self):
        req = self.requirement("A06.sdk")
        req.update(state="verified", limitations=[])
        with self.assertRaisesRegex(ValueError, "verified requires artifacts"):
            self.validate()
        self.verified_sdk()
        self.validate()

    def test_reject_failed_or_waived_evidence(self):
        _, row = self.verified_sdk()
        for outcome in ("fail", "waived"):
            with self.subTest(outcome=outcome):
                row["outcome"] = outcome
                with self.assertRaisesRegex(ValueError, "missing, failed or waived"):
                    self.validate()

    def test_reject_modified_and_missing_artifacts(self):
        _, row = self.verified_sdk()
        file = self.artifacts / row["artifact"]
        file.write_text("altered")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.validate()
        file.unlink()
        with self.assertRaisesRegex(ValueError, "artifact missing"):
            self.validate()

    def test_reject_evidence_without_root(self):
        self.verified_sdk()
        with self.assertRaisesRegex(ValueError, "requires --evidence-root"):
            validate_ledger(self.ledger)

    def test_reject_unsafe_and_symlink_artifacts(self):
        _, row = self.verified_sdk()
        row["artifact"] = "../outside"
        with self.assertRaisesRegex(ValueError, "unsafe relative path"):
            self.validate()
        row["artifact"] = "escape"
        (self.artifacts / "escape").symlink_to("/etc/hostname")
        with self.assertRaisesRegex(ValueError, "escapes root"):
            self.validate()

    def test_reject_bad_or_unattached_evidence_hash(self):
        req, _ = self.verified_sdk()
        req["evidence_artifact_hash"] = "invalid"
        with self.assertRaisesRegex(ValueError, "no allowed schema"):
            self.validate()
        req["evidence_artifact_hash"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "no linked artifact"):
            self.validate()

    def test_native_verification_needs_all_profiles_and_modes(self):
        req = self.requirement("A04.native-baseline")
        model = self.add_evidence("T.baseline.models")
        rows = [model]
        for arch in req["architecture"]:
            for mode in ("debug", "release"):
                if (arch, mode) != ("ppc", "release"):
                    rows.append(self.add_evidence("T.baseline.native", arch=arch, mode=mode))
        req.update(state="verified", limitations=[], evidence_ids=[row["id"] for row in rows], evidence_artifact_hash=rows[0]["sha256"])
        with self.assertRaisesRegex(ValueError, "ppc/release"):
            self.validate()
        req["evidence_ids"].append(self.add_evidence("T.baseline.native", arch="ppc", mode="release")["id"])
        self.validate()

    def test_reject_planned_test_evidence(self):
        self.add_evidence("T.P03.vm", arch="x86_64", mode="debug")
        with self.assertRaisesRegex(ValueError, "cannot execute a planned test"):
            self.validate()

    def test_reject_missing_pinned_archive_digest(self):
        row = self.ledger["references"][0]
        row["status"] = "source-pinned"
        with self.assertRaisesRegex(ValueError, "requires an archive checksum"):
            self.validate()

    def test_reject_pinned_source_without_archive_artifact(self):
        row = next(item for item in self.ledger["references"] if item["id"] == "musl")
        row["archive_artifact"] = None
        with self.assertRaisesRegex(ValueError, "requires an archive artifact"):
            self.validate()

    def test_source_pin_checks_exact_archive_bytes(self):
        self.source_fixture_except("musl")
        row = next(item for item in self.ledger["references"] if item["id"] == "musl")
        source = self.artifacts / row["archive_artifact"]
        source.write_bytes(b"source archive fixture")
        row["archive_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        validate_ledger(self.ledger, source_root=self.artifacts)
        source.write_bytes(b"altered source archive")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            validate_ledger(self.ledger, source_root=self.artifacts)
        source.unlink()
        with self.assertRaisesRegex(ValueError, "artifact missing"):
            validate_ledger(self.ledger, source_root=self.artifacts)

    def test_reject_source_archive_symlink_escape(self):
        self.source_fixture_except("musl")
        row = next(item for item in self.ledger["references"] if item["id"] == "musl")
        (self.artifacts / row["archive_artifact"]).symlink_to("/etc/hostname")
        with self.assertRaisesRegex(ValueError, "escapes root"):
            validate_ledger(self.ledger, source_root=self.artifacts)

    def test_m0_requires_checked_archive_bytes(self):
        self.assertIn("Pinned source archive bytes were not checked", " ".join(m0_gaps(self.ledger)))

    def test_reject_empty_inventory_gaps(self):
        self.ledger["inventories"][0]["gaps"] = []
        with self.assertRaisesRegex(ValueError, "contradicts its gaps"):
            self.validate()

    def test_seed_cannot_promote_with_status_strings(self):
        for row in self.ledger["inventories"]:
            row.update(state="complete", gaps=[])
        self.validate()
        self.assertIn("seed inventory", m0_gaps(self.ledger)[0])

    def test_coverage_baseline_retains_four_open_domains(self):
        status = validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)
        self.assertEqual(status, {name: False for name in status})
        self.assertEqual(len(status), 4)
        self.assertIn("reviewed source index", " ".join(m0_gaps(self.ledger, status)))

    def test_reviewed_index_fixture_maps_every_unit_but_does_not_pass_m0(self):
        self.indexed_coverage()
        status = validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)
        self.assertTrue(all(status.values()))
        self.assertTrue(m0_gaps(self.ledger, status))
        self.assertIn("seed inventory", m0_gaps(self.ledger, status)[0])

    def test_reject_missing_or_extra_source_unit_mapping(self):
        self.indexed_coverage()
        row = self.coverage["inventories"][0]
        row["mappings"] = []
        with self.assertRaisesRegex(ValueError, "source units and mappings differ"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)
        row["mappings"] = [{"unit_id": "invented", "requirement_links": [self.coverage_link("P03.vm", "posix-issue8")],
                            "test_ids": ["T.P03.vm"]}]
        with self.assertRaisesRegex(ValueError, "source units and mappings differ"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)

    def test_reject_declared_source_without_indexed_units(self):
        indexes = self.indexed_coverage()
        name = "ext4-feature-combinations"
        index, _ = indexes[name]
        omitted = index["source_ids"][-1]
        index["units"] = [unit for unit in index["units"] if unit["source_id"] != omitted]
        row = next(item for item in self.coverage["inventories"] if item["id"] == name)
        row["mappings"] = [mapping for mapping in row["mappings"]
                           if mapping["unit_id"] in {unit["id"] for unit in index["units"]}]
        self.repin_index(indexes, name)
        with self.assertRaisesRegex(ValueError, "source IDs without indexed units"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)

    def test_reject_linked_requirement_missing_indexed_architecture(self):
        indexes = self.indexed_coverage()
        name = "posix-clauses-options"
        indexes[name][0]["units"][0]["architecture"] = ["x86_64"]
        self.repin_index(indexes, name)
        with self.assertRaisesRegex(ValueError, "requirement P03.vm missing indexed architectures"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)

    def test_requirement_architectures_can_span_source_units(self):
        indexes = self.indexed_coverage()
        name = "linux-abi-layouts"
        first, second = indexes[name][0]["units"]
        arches = list(self.requirement("P01.bootstrap-codecs")["architecture"])
        first["architecture"] = arches[:5]
        second["architecture"] = arches[5:]
        self.repin_index(indexes, name)
        self.assertTrue(all(validate_inventory_coverage(self.ledger, self.coverage, self.artifacts).values()))

    def test_mismatched_unit_classification_cannot_cover_linked_requirement(self):
        self.indexed_coverage()
        extra = copy.deepcopy(self.requirement("P03.vm"))
        extra["id"] = "P03.extension-fixture"
        extra["requirement_level"] = "extension"
        self.ledger["requirements"].append(extra)
        row = next(item for item in self.coverage["inventories"] if item["id"] == "posix-clauses-options")
        row["mappings"][0]["requirement_links"].append(self.coverage_link(extra["id"], "posix-issue8"))
        with self.assertRaisesRegex(ValueError, "requirement P03.extension-fixture missing indexed architectures"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)

    def test_reject_unrelated_requirement_test_and_missing_architecture(self):
        self.indexed_coverage()
        row = self.coverage["inventories"][0]
        row["mappings"][0]["test_ids"] = ["T.sdk.artifacts"]
        with self.assertRaisesRegex(ValueError, "no mapped test"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)
        row["mappings"][0].update(requirement_links=[self.coverage_link("A06.sdk", "posix-issue8")],
                                  test_ids=["T.sdk.artifacts"])
        with self.assertRaisesRegex(ValueError, "outside the inventory plan section"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)

    def test_reject_mixed_levels_across_unit_architectures(self):
        indexes = self.indexed_coverage()
        name = "posix-clauses-options"
        indexes[name][0]["units"][0]["architecture"] = ["x86_64", "i386"]
        self.repin_index(indexes, name)
        self.requirement("P03.vm")["architecture"] = ["x86_64"]
        other = self.requirement("P01.bootstrap-codecs")
        other["requirement_level"] = "inventory"
        other["architecture"] = ["i386"]
        row = self.coverage["inventories"][0]["mappings"][0]
        row["requirement_links"].append(self.coverage_link(other["id"], "posix-issue8"))
        row["test_ids"].append("T.linux-abi-codecs")
        with self.assertRaisesRegex(ValueError, "matching normative requirement level omits i386"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)

    def test_reject_mapped_native_or_physical_test_missing_one_unit_architecture(self):
        indexes = self.indexed_coverage()
        name = "posix-clauses-options"
        indexes[name][0]["units"][0]["architecture"] = ["x86_64", "i386"]
        self.repin_index(indexes, name)
        test = next(item for item in self.ledger["tests"] if item["id"] == "T.P03.vm")
        self.assertEqual(test["execution"], "qemu-native")
        test["architecture"] = ["x86_64"]
        with self.assertRaisesRegex(ValueError, "mapped tests do not cover i386"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)
        test["execution"] = "physical"
        test["layer"] = "physical"
        req = self.requirement("P03.vm")
        req["native_test_ids"].remove("T.P03.vm")
        req["physical_test_ids"].append("T.P03.vm")
        with self.assertRaisesRegex(ValueError, "mapped tests do not cover i386"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)

    def test_hosted_mapping_is_architecture_independent(self):
        indexes = self.indexed_coverage()
        name = "linux-abi-layouts"
        indexes[name][0]["units"][0]["architecture"] = ["x86_64", "i386"]
        self.repin_index(indexes, name)
        self.assertEqual(next(item for item in self.ledger["tests"] if item["id"] == "T.linux-abi-codecs")["execution"],
                         "host-model")
        self.assertTrue(all(validate_inventory_coverage(self.ledger, self.coverage, self.artifacts).values()))

    def test_reject_forged_normative_or_ledger_source_attestation(self):
        self.indexed_coverage()
        link = self.coverage["inventories"][0]["mappings"][0]["requirement_links"][0]
        link["source_id"] = "internet-rfcs"
        with self.assertRaisesRegex(ValueError, "attested normative source differs"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)
        link["source_id"] = "posix-issue8"
        link["ledger_source_section"] = "ARCHITECTURE_SDK.md#A06"
        with self.assertRaisesRegex(ValueError, "attested ledger source differs"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)

    def test_reject_changed_index_bytes_and_bad_review_metadata(self):
        indexes = self.indexed_coverage()
        name = self.coverage["inventories"][0]["id"]
        row = self.coverage["inventories"][0]
        row["source_index"]["reviewed_on"] = "2026-02-30"
        with self.assertRaisesRegex(ValueError, "invalid review date"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)
        row["source_index"]["reviewed_on"] = "2026-09-21"
        indexes[name][1].write_text("{}")
        with self.assertRaisesRegex(ValueError, "source index checksum mismatch"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)

    def test_reject_coverage_revision_and_unreviewed_mapping(self):
        self.coverage["ledger_revision"] = "stale"
        with self.assertRaisesRegex(ValueError, "revision differs"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)
        self.coverage["ledger_revision"] = self.ledger["ledger_revision"]
        self.coverage["inventories"][0]["mappings"] = [
            {"unit_id": "pretend", "requirement_links": [self.coverage_link("P03.vm", "posix-issue8")],
             "test_ids": ["T.P03.vm"]}]
        with self.assertRaisesRegex(ValueError, "require a reviewed source index"):
            validate_inventory_coverage(self.ledger, self.coverage, self.artifacts)

    def test_strict_json_rejects_duplicate_keys_and_nan(self):
        file = self.artifacts / "invalid.json"
        for contents, reason in (('{"id": 1, "id": 2}', "duplicate JSON key"), ('{"id": NaN}', "non-JSON")):
            with self.subTest(contents=contents):
                file.write_text(contents)
                with self.assertRaisesRegex(ValueError, reason):
                    load_json(file)

    def test_schema_does_not_silently_ignore_new_constraints(self):
        with self.assertRaisesRegex(ValueError, "unsupported schema keywords"):
            validate_schema("test", {"type": "string", "format": "uri"})

    def test_cli_gate_failure_is_nonzero_and_report_deterministic(self):
        tool = Path(__file__).resolve().parents[2] / "tools/plan_ledger.py"
        fixture_manifest = self.artifacts / 'synthetic-ledger.json'
        fixture_manifest.write_text(json.dumps(self.ledger))
        result = subprocess.run([sys.executable, str(tool), "gate-m0", '--manifest', str(fixture_manifest),
                                 '--evidence-root', str(self.artifacts)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("M0 gate failed", result.stderr)
        self.assertEqual(report(self.ledger), report(copy.deepcopy(self.ledger)))


if __name__ == "__main__":
    unittest.main()

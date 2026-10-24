#!/usr/bin/env python3
"""Validate the workstation requirement/evidence ledger without executing its tests."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

from kernel_sdk import ARCH_TRIPLES

PROJECT = Path(__file__).resolve().parents[1]
CONTRACTS = PROJECT / "docs/plans/contracts"
COVERAGE = CONTRACTS / "inventory_coverage.json"
LAYERS = ("model", "native", "interop", "fault", "physical")
INVENTORIES = {"posix-clauses-options", "linux-abi-layouts", "ext4-feature-combinations", "internet-rfc-clauses"}
INVENTORY_PLAN_ANCHORS = {
    "posix-clauses-options": "POSIX_MUSL.md#",
    "linux-abi-layouts": "POSIX_MUSL.md#",
    "ext4-feature-combinations": "STORAGE_EXT4.md#",
    "internet-rfc-clauses": "NETWORK_SERVICES.md#",
}
SCHEMA_KEYS = {"$schema", "$id", "type", "properties", "additionalProperties", "required", "items",
               "minItems", "uniqueItems", "enum", "const", "pattern", "anyOf", "minLength"}


def load_json(path: Path, *, content: bytes | None = None) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"{path}: duplicate JSON key {key!r}")
            result[key] = value
        return result

    def invalid(value):
        raise ValueError(f"{path}: non-JSON numeric constant {value}")

    return json.loads((path.read_bytes() if content is None else content).decode("utf-8"),
                      object_pairs_hook=pairs, parse_constant=invalid)


def validate_schema(value, schema: dict, location: str = "ledger") -> None:
    """Evaluate only the documented schema vocabulary; unknown keywords fail closed.

    The checked-in schema is also usable by a full Draft 2020-12 validator. Keeping
    this small vocabulary avoids a downloaded Python dependency in OS builds.
    """
    unknown = set(schema) - SCHEMA_KEYS
    if unknown:
        raise ValueError(f"{location}: unsupported schema keywords {sorted(unknown)}")
    if "anyOf" in schema:
        for candidate in schema["anyOf"]:
            try:
                validate_schema(value, candidate, location)
                break
            except ValueError:
                pass
        else:
            raise ValueError(f"{location}: no allowed schema matches")
    kind = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "null": type(None)}
    if kind is not None and (kind not in types or type(value) is not types[kind]):
        raise ValueError(f"{location}: expected {kind}")
    if "enum" in schema and not any(type(value) is type(item) and value == item for item in schema["enum"]):
        raise ValueError(f"{location}: value is outside enum")
    if "const" in schema and (type(value) is not type(schema["const"]) or value != schema["const"]):
        raise ValueError(f"{location}: wrong schema constant")
    if isinstance(value, dict):
        missing = set(schema.get("required", ())) - value.keys()
        extra = value.keys() - schema.get("properties", {}).keys()
        if missing or (extra and schema.get("additionalProperties") is False):
            raise ValueError(f"{location}: missing fields {sorted(missing)}, unknown fields {sorted(extra)}")
        for key, child in value.items():
            if key in schema.get("properties", {}):
                validate_schema(child, schema["properties"][key], f"{location}.{key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValueError(f"{location}: too few entries")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            raise ValueError(f"{location}: duplicate entries")
        for index, item in enumerate(value):
            if "items" in schema:
                validate_schema(item, schema["items"], f"{location}[{index}]")
    if isinstance(value, str):
        if len(value.strip()) < schema.get("minLength", 0):
            raise ValueError(f"{location}: empty string")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            raise ValueError(f"{location}: string fails pattern")


def index_rows(rows: list[dict], name: str) -> dict:
    indexed = {}
    for row in rows:
        if row["id"] in indexed:
            raise ValueError(f"{name}: duplicate id {row['id']}")
        indexed[row["id"]] = row
    return indexed


def relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or str(path) != value or value == ".":
        raise ValueError(f"unsafe relative path: {value}")
    return path


def repository_path(value: str) -> None:
    path = relative_path(value)
    if len(path.parts) < 2 or path.parts[0] not in {"ObfuscationKernel", "ObfuscationOS"}:
        raise ValueError(f"path must name its owning repository: {value}")


def artifact(root: Path, name: str, digest: str) -> None:
    relative_path(name)
    root = root.resolve()
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"artifact escapes root: {name}")
    if not path.is_file():
        raise ValueError(f"artifact missing: {name}")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f"artifact checksum mismatch: {name}")


def validate_ledger(ledger: dict, schema: dict | None = None, evidence_root: Path | None = None,
                    source_root: Path | None = None) -> None:
    validate_schema(ledger, schema or load_json(CONTRACTS / "ledger.schema.json"))
    architectures = index_rows(ledger["architectures"], "architectures")
    if architectures.keys() != ARCH_TRIPLES.keys():
        raise ValueError("architecture matrix must preserve all ten native profiles")
    for name, row in architectures.items():
        if row["native_triple"] != ARCH_TRIPLES[name]:
            raise ValueError(f"{name}: native compiler triple differs from SDK contract")
        for source in row["source_paths"]:
            repository_path(source)
        if row["linux_qualification"] == "unqualified" and not row["qualification_gaps"]:
            raise ValueError(f"{name}: unqualified ABI needs explicit gaps")
        # ABI qualification is a separate gate that this initial ledger does not implement.
        if row["linux_qualification"] == "qualified":
            raise ValueError(f"{name}: schema v1 has no complete Linux ABI qualification evidence protocol")
    inventories = index_rows(ledger["inventories"], "inventories")
    if inventories.keys() != INVENTORIES:
        raise ValueError("required standards/ABI/format inventories must remain explicit")
    references = index_rows(ledger["references"], "references")
    for inventory in inventories.values():
        for source in inventory["source_ids"]:
            if source not in references:
                raise ValueError(f"{inventory['id']}: unknown source {source}")
        if (inventory["state"] == "partial") != bool(inventory["gaps"]):
            raise ValueError(f"{inventory['id']}: inventory status contradicts its gaps")
    for ref in references.values():
        if ref["status"] != "unpinned" and ref["version"] is None:
            raise ValueError(f"{ref['id']}: a selected/audited source requires a version")
        if ref["status"] == "source-pinned":
            if ref["archive_sha256"] is None:
                raise ValueError(f"{ref['id']}: source pin requires an archive checksum")
            if ref["archive_artifact"] is None:
                raise ValueError(f"{ref['id']}: source pin requires an archive artifact")
        elif ref["archive_sha256"] is not None or ref["archive_artifact"] is not None:
            raise ValueError(f"{ref['id']}: an unpinned/local-audit source cannot carry an archive pin")
        if ref["archive_artifact"] is not None:
            relative_path(ref["archive_artifact"])
            if source_root is not None:
                artifact(source_root, ref["archive_artifact"], ref["archive_sha256"])
        if ref["status"] != "source-pinned" and not ref["limitations"]:
            raise ValueError(f"{ref['id']}: unqualified source needs limitations")
        for audited in ref["audited_files"]:
            relative_path(audited["path"])
    tests = index_rows(ledger["tests"], "tests")
    allowed_execution = {"model": {"host-model", "host-tool"}, "native": {"qemu-native"},
                         "interop": {"host-tool", "qemu-native", "physical"},
                         "fault": {"host-model", "host-tool", "qemu-native", "physical"}, "physical": {"physical"}}
    for test in tests.values():
        if test["execution"] not in allowed_execution[test["layer"]]:
            raise ValueError(f"{test['id']}: test layer and execution disagree")
        host = test["execution"].startswith("host-")
        if (test["architecture"] == ["host"]) != host or (not host and "host" in test["architecture"]):
            raise ValueError(f"{test['id']}: test execution and architecture disagree")
        if (test["status"] == "available") != (test["entrypoint"] is not None):
            raise ValueError(f"{test['id']}: test availability needs an entrypoint")
        if test["entrypoint"] is not None:
            repository_path(test["entrypoint"])
            parts = PurePosixPath(test["entrypoint"]).parts
            if parts[0] == "ObfuscationOS" and not PROJECT.joinpath(*parts[1:]).is_file():
                raise ValueError(f"{test['id']}: OS test entrypoint does not exist")
    requirements = index_rows(ledger["requirements"], "requirements")
    used_tests = set()
    for req in requirements.values():
        for dependency in req["dependencies"]:
            if dependency not in requirements:
                raise ValueError(f"{req['id']}: unknown dependency {dependency}")
        for path in req["implementation_paths"]:
            repository_path(path)
        linked = []
        for layer in LAYERS:
            for test_id in req[layer + "_test_ids"]:
                if test_id not in tests:
                    raise ValueError(f"{req['id']}: unknown test {test_id}")
                test = tests[test_id]
                if test["layer"] != layer:
                    raise ValueError(f"{req['id']}: test {test_id} is in the wrong evidence layer")
                if not test["execution"].startswith("host-") and not set(req["architecture"]) <= set(test["architecture"]):
                    raise ValueError(f"{req['id']}: test {test_id} omits a required architecture")
                linked.append(test_id)
        if not linked and req["state"] != "not-applicable-with-rationale":
            raise ValueError(f"{req['id']}: requirement has no planned test")
        used_tests.update(linked)
        if req["state"] in {"model-only", "native-partial", "implemented", "verified"} and not req["implementation_paths"]:
            raise ValueError(f"{req['id']}: implemented state needs implementation paths")
        if req["state"] == "model-only" and not req["model_test_ids"]:
            raise ValueError(f"{req['id']}: model-only state needs a model test")
        if req["state"] == "native-partial" and not (req["native_test_ids"] or req["interop_test_ids"]):
            raise ValueError(f"{req['id']}: native-partial state needs native or interop tests")
        if req["state"] in {"planned", "model-only", "native-partial", "not-applicable-with-rationale"} and not req["limitations"]:
            raise ValueError(f"{req['id']}: incomplete/non-applicable state needs a rationale")
        if req["state"] == "not-applicable-with-rationale" and req["requirement_level"] in {"mandatory", "selected-profile"}:
            raise ValueError(f"{req['id']}: mandatory/selected requirements cannot be waived as non-applicable")
    if used_tests != tests.keys():
        raise ValueError(f"orphan tests: {sorted(tests.keys() - used_tests)}")
    visiting, complete = set(), set()

    def visit(name):
        if name in visiting:
            raise ValueError(f"requirement dependency cycle at {name}")
        if name in complete:
            return
        visiting.add(name)
        for dependency in requirements[name]["dependencies"]:
            visit(dependency)
        visiting.remove(name)
        complete.add(name)

    for name in requirements:
        visit(name)
    evidence = index_rows(ledger["evidence"], "evidence")
    for row in evidence.values():
        if row["test_id"] not in tests:
            raise ValueError(f"{row['id']}: unknown evidence test")
        test = tests[row["test_id"]]
        if test["status"] != "available":
            raise ValueError(f"{row['id']}: cannot execute a planned test")
        if row["execution"] != test["execution"] or row["architecture"] not in test["architecture"]:
            raise ValueError(f"{row['id']}: evidence does not match test execution/architecture")
        if (row["mode"] == "host") != row["execution"].startswith("host-"):
            raise ValueError(f"{row['id']}: evidence mode does not match execution")
        relative_path(row["artifact"])
        if evidence_root is None:
            raise ValueError("execution evidence requires --evidence-root for artifact verification")
        artifact(evidence_root, row["artifact"], row["sha256"])
    used_evidence = set()
    for req in requirements.values():
        linked_tests = {name for layer in LAYERS for name in req[layer + "_test_ids"]}
        rows = []
        for name in req["evidence_ids"]:
            if name not in evidence or evidence[name]["test_id"] not in linked_tests:
                raise ValueError(f"{req['id']}: unknown or unrelated evidence {name}")
            rows.append(evidence[name])
        used_evidence.update(req["evidence_ids"])
        if req["evidence_artifact_hash"] is not None and req["evidence_artifact_hash"] not in {row["sha256"] for row in rows}:
            raise ValueError(f"{req['id']}: evidence hash has no linked artifact")
        if req["state"] == "verified":
            if req["limitations"] or not rows or req["evidence_artifact_hash"] is None:
                raise ValueError(f"{req['id']}: verified requires artifacts and no outstanding limitations")
            for test_id in linked_tests:
                test = tests[test_id]
                needed_arches = ["host"] if test["execution"].startswith("host-") else req["architecture"]
                for arch in needed_arches:
                    modes = ["host"] if arch == "host" else ["debug", "release"]
                    for mode in modes:
                        matched = [row for row in rows if row["test_id"] == test_id and row["architecture"] == arch and row["mode"] == mode]
                        if not matched or any(row["outcome"] != "pass" for row in matched):
                            raise ValueError(f"{req['id']}: verified evidence missing, failed or waived for {test_id}/{arch}/{mode}")
            for dependency in req["dependencies"]:
                if requirements[dependency]["state"] != "verified":
                    raise ValueError(f"{req['id']}: verified requirement has unverified dependency {dependency}")
    if used_evidence != evidence.keys():
        raise ValueError("execution evidence must be attached to a requirement")


def validate_inventory_coverage(ledger: dict, coverage: dict, root: Path = PROJECT) -> dict[str, bool]:
    """Check reviewed source-universe indexes and their requirement/test mapping.

    The human review attests that an index enumerates the selected source universe.
    This validator checks its pinned bytes and internal completeness; it cannot
    discover clauses missing from an incorrectly reviewed source index.
    """
    validate_schema(coverage, load_json(CONTRACTS / "inventory_coverage.schema.json"), "coverage")
    if coverage["ledger_revision"] != ledger["ledger_revision"]:
        raise ValueError("coverage ledger revision differs from requirement ledger")
    inventories = index_rows(ledger["inventories"], "inventories")
    references = index_rows(ledger["references"], "references")
    requirements = index_rows(ledger["requirements"], "requirements")
    tests = index_rows(ledger["tests"], "tests")
    rows = index_rows(coverage["inventories"], "coverage inventories")
    if rows.keys() != inventories.keys():
        raise ValueError("coverage must retain exactly the four inventory domains")
    complete = {}
    for name, row in rows.items():
        source_index = row["source_index"]
        if source_index is None:
            if row["mappings"]:
                raise ValueError(f"{name}: mappings require a reviewed source index")
            complete[name] = False
            continue
        path = relative_path(source_index["artifact"])
        if path.parts[:4] != ("docs", "plans", "contracts", "indexes"):
            raise ValueError(f"{name}: source index must be in contracts/indexes")
        resolved_root = root.resolve()
        resolved_index = (resolved_root / path).resolve()
        if not resolved_index.is_relative_to(resolved_root):
            raise ValueError(f"{name}: source index escapes root")
        index_bytes = resolved_index.read_bytes()
        if hashlib.sha256(index_bytes).hexdigest() != source_index["sha256"]:
            raise ValueError(f"{name}: source index checksum mismatch")
        try:
            if date.fromisoformat(source_index["reviewed_on"]).isoformat() != source_index["reviewed_on"]:
                raise ValueError()
        except ValueError as exc:
            raise ValueError(f"{name}: invalid review date") from exc
        index = load_json(resolved_index, content=index_bytes)
        validate_schema(index, load_json(CONTRACTS / "inventory_index.schema.json"), f"{name} source index")
        if index["inventory_id"] != name:
            raise ValueError(f"{name}: source index names another inventory")
        if set(index["source_ids"]) != set(inventories[name]["source_ids"]):
            raise ValueError(f"{name}: source index omits or adds source references")
        if not set(index["source_ids"]) <= references.keys():
            raise ValueError(f"{name}: source index has an unknown source")
        units = index_rows(index["units"], f"{name} source units")
        mappings = index_rows([{"id": item["unit_id"], **item} for item in row["mappings"]],
                              f"{name} mappings")
        if units.keys() != mappings.keys():
            raise ValueError(f"{name}: source units and mappings differ")
        unrepresented_sources = set(index["source_ids"]) - {unit["source_id"] for unit in units.values()}
        if unrepresented_sources:
            raise ValueError(f"{name}: source IDs without indexed units: {sorted(unrepresented_sources)}")
        linked_architectures: dict[str, set[str]] = {}
        for unit_id, unit in units.items():
            if unit["source_id"] not in index["source_ids"]:
                raise ValueError(f"{name}/{unit_id}: source is outside the reviewed universe")
            mapping = mappings[unit_id]
            level = unit["classification"]
            required_level = {"mandatory": "mandatory", "selected-profile": "selected-profile"}.get(level)
            matching_levels = ({required_level} if required_level else {"extension", "inventory"})
            selected = []
            linked_tests = set()
            seen_requirements = set()
            for link in mapping["requirement_links"]:
                req_id = link["requirement_id"]
                if req_id in seen_requirements:
                    raise ValueError(f"{name}/{unit_id}: duplicate requirement link {req_id}")
                seen_requirements.add(req_id)
                if req_id not in requirements:
                    raise ValueError(f"{name}/{unit_id}: unknown requirement {req_id}")
                req = requirements[req_id]
                if link["source_id"] != unit["source_id"] or link["source_section"] != unit["source_section"]:
                    raise ValueError(f"{name}/{unit_id}: attested normative source differs from indexed unit")
                if (link["ledger_source_version"] != req["source_version"] or
                        link["ledger_source_section"] != req["source_section"]):
                    raise ValueError(f"{name}/{unit_id}: attested ledger source differs from requirement")
                if not req["source_section"].startswith(INVENTORY_PLAN_ANCHORS[name]):
                    raise ValueError(f"{name}/{unit_id}: requirement is outside the inventory plan section")
                covered = linked_architectures.setdefault(req_id, set())
                if req["requirement_level"] in matching_levels:
                    covered.update(set(unit["architecture"]) & set(req["architecture"]))
                try:
                    if date.fromisoformat(link["reviewed_on"]).isoformat() != link["reviewed_on"]:
                        raise ValueError()
                except ValueError as exc:
                    raise ValueError(f"{name}/{unit_id}: invalid mapping review date") from exc
                selected.append(req)
                linked = {test_id for layer in LAYERS for test_id in req[layer + "_test_ids"]}
                linked_tests.update(linked)
                if not linked.intersection(mapping["test_ids"]):
                    raise ValueError(f"{name}/{unit_id}: requirement {req_id} has no mapped test")
            for test_id in mapping["test_ids"]:
                if test_id not in tests or test_id not in linked_tests:
                    raise ValueError(f"{name}/{unit_id}: unknown or unrelated test {test_id}")
            for arch in unit["architecture"]:
                matching = [req for req in selected if arch in req["architecture"] and
                            req["requirement_level"] in matching_levels]
                if not matching:
                    raise ValueError(f"{name}/{unit_id}: matching normative requirement level omits {arch}")
                if not any(
                    test_id in {item for layer in LAYERS for item in req[layer + "_test_ids"]} and
                    (tests[test_id]["execution"].startswith("host-") or arch in tests[test_id]["architecture"])
                    for req in matching for test_id in mapping["test_ids"]
                ):
                    raise ValueError(f"{name}/{unit_id}: mapped tests do not cover {arch} through a matching requirement")
        for req_id, covered in linked_architectures.items():
            missing = set(requirements[req_id]["architecture"]) - covered
            if missing:
                raise ValueError(f"{name}: requirement {req_id} missing indexed architectures {sorted(missing)}")
        complete[name] = True
    return complete


def m0_gaps(ledger: dict, coverage: dict[str, bool] | None = None,
            source_artifacts_checked: bool = False) -> list[str]:
    gaps = []
    if ledger["scope"] != "reviewed-inventory":
        gaps.append("Requirement ledger remains a seed inventory; M0 is incomplete.")
    if coverage is None:
        gaps.append("No checked clause-level coverage certificate was supplied.")
    else:
        gaps.extend(f"{name}: reviewed source index and clause mapping absent" for name, done in coverage.items() if not done)
    gaps.extend(f"{row['id']}: {'; '.join(row['gaps'])}" for row in ledger["inventories"] if row["state"] != "complete")
    gaps.extend(f"{row['id']}: source status {row['status']}" for row in ledger["references"] if row["status"] != "source-pinned")
    if not source_artifacts_checked and any(row["status"] == "source-pinned" for row in ledger["references"]):
        gaps.append("Pinned source archive bytes were not checked; supply --source-root for M0 admission.")
    return gaps


def report(ledger: dict, coverage: dict[str, bool] | None = None,
           source_artifacts_checked: bool = False) -> str:
    states = Counter(row["state"] for row in ledger["requirements"])
    lines = ["# Workstation capability ledger", "", f"Revision: `{ledger['ledger_revision']}`. Scope: {ledger['scope']}; M0 {'incomplete' if m0_gaps(ledger, coverage, source_artifacts_checked) else 'passed'}.", "",
             "Source inspection and historical documentation are not new execution evidence.", "",
             "| Architecture | Native triple | Selected Linux target (unqualified) | ABI |",
             "| --- | --- | --- | --- |"]
    for row in ledger["architectures"]:
        lines.append(f"| {row['id']} | `{row['native_triple']}` | `{row['linux_target']}` | {row['linux_abi']} |")
    lines += ["", "All ten profiles retain their native bootstrap behavior. Linux ABI/musl, physical hardware and SMP qualification remain open.", "",
              "| Requirement state | Count |", "| --- | --- |"]
    lines += [f"| {state} | {count} |" for state, count in sorted(states.items())]
    lines += ["", "| Requirement | Owner | State | Limitations |", "| --- | --- | --- | --- |"]
    lines += [f"| {row['id']} | {row['owner_repository']} | {row['state']} | {' '.join(row['limitations']) or 'No recorded limitation; see tests and evidence.'} |" for row in ledger["requirements"]]
    lines += ["", "## M0 gaps", ""] + [f"- {gap}" for gap in m0_gaps(ledger, coverage, source_artifacts_checked)]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "report", "gate-m0"))
    parser.add_argument("--manifest", type=Path, default=CONTRACTS / "ledger.json")
    parser.add_argument("--coverage-manifest", type=Path, default=COVERAGE)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--source-root", type=Path,
                        help="Directory containing exact pinned source archives; required to pass M0")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        ledger = load_json(args.manifest)
        validate_ledger(ledger, evidence_root=args.evidence_root, source_root=args.source_root)
        coverage = validate_inventory_coverage(ledger, load_json(args.coverage_manifest))
        if args.command == "gate-m0":
            gaps = m0_gaps(ledger, coverage, args.source_root is not None)
            if gaps:
                raise ValueError("M0 gate failed:\n" + "\n".join(gaps))
        if args.command == "report":
            result = report(ledger, coverage, args.source_root is not None)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(result, encoding="utf-8")
            else:
                print(result, end="")
        else:
            state = "incomplete" if m0_gaps(ledger, coverage, args.source_root is not None) else "passed"
            print(f"[plan-ledger] schema/relationships valid: {len(ledger['requirements'])} requirements, {len(ledger['tests'])} tests, ten profiles; M0 {state}")
        return 0
    except (OSError, ValueError, RecursionError) as exc:
        print(f"plan ledger error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Read back the exact RFC texts cited by the network plan, without admitting clauses."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re


PROJECT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT / "docs/plans/contracts/drafts/internet_rfc_reference_sources.json"
DEFAULT_PLAN = PROJECT / "docs/plans/NETWORK_SERVICES.md"
SECTION = "## 12. External reading and decision references"
MAX_RFC_BYTES = 4 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
FILENAME = re.compile(r"rfc([1-9][0-9]*)\.txt\Z")
LINK = re.compile(r"\[RFC ([1-9][0-9]*)\]\(https://www\.rfc-editor\.org/rfc/rfc([1-9][0-9]*)\)")


def need(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        need(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def referenced_numbers(plan: bytes) -> set[int]:
    content = plan.decode("utf-8")
    need(content.count(SECTION) == 1, "network reference section missing or repeated")
    section = content.split(SECTION, 1)[1].split("\n## ", 1)[0]
    links = LINK.findall(section)
    need(len(links) == 47 and all(left == right for left, right in links),
         "network plan must retain 47 exact RFC Editor links")
    numbers = [int(left) for left, _ in links]
    need(len(set(numbers)) == len(numbers), "duplicate RFC reference in network plan")
    return set(numbers)


def readback(manifest_path: Path, plan_path: Path, source_dir: Path) -> dict:
    need(manifest_path.is_file() and not manifest_path.is_symlink(), "ordinary manifest required")
    need(plan_path.is_file() and not plan_path.is_symlink(), "ordinary plan required")
    need(source_dir.is_dir() and not source_dir.is_symlink(), "ordinary source directory required")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes, object_pairs_hook=unique_object)
    need(type(manifest) is dict and set(manifest) ==
         {"schema_version", "scope", "plan_sha256", "rfc_sources", "qualification"},
         "unexpected RFC manifest structure")
    need(manifest["schema_version"] == 1 and
         manifest["scope"] == "NETWORK_SERVICES.md section 12 exact references" and
         manifest["qualification"] == "reference-bytes-only-unreviewed",
         "RFC manifest scope or qualification changed")
    plan_bytes = plan_path.read_bytes()
    need(manifest["plan_sha256"] == digest(plan_bytes), "network plan hash differs")
    plan_numbers = referenced_numbers(plan_bytes)
    rows = manifest["rfc_sources"]
    need(type(rows) is list and len(rows) == 47, "RFC manifest needs 47 sources")
    observed = {}
    for row in rows:
        need(type(row) is dict and set(row) == {"number", "file", "url", "bytes", "sha256"},
             "unexpected RFC source row")
        number = row["number"]
        need(type(number) is int and number in plan_numbers and number not in observed,
             "unexpected or duplicate RFC number")
        name = row["file"]
        need(type(name) is str and FILENAME.fullmatch(name) is not None and
             name == f"rfc{number}.txt", "noncanonical RFC filename")
        need(row["url"] == f"https://www.rfc-editor.org/rfc/rfc{number}.txt",
             "noncanonical RFC Editor URL")
        need(type(row["bytes"]) is int and 0 < row["bytes"] <= MAX_RFC_BYTES and
             type(row["sha256"]) is str and SHA256.fullmatch(row["sha256"]) is not None,
             "invalid RFC byte pin")
        source = source_dir / name
        need(source.is_file() and not source.is_symlink(), "ordinary RFC file missing: " + name)
        payload = source.read_bytes()
        need(len(payload) == row["bytes"] and digest(payload) == row["sha256"],
             "RFC source bytes differ: " + name)
        header = payload[:4096]
        marker = re.compile(rb"(?:\bRFC:?\s+|Request for Comments:\s*)" +
                            str(number).encode() + rb"\b", re.IGNORECASE)
        need(marker.search(header) is not None, "RFC number absent from header: " + name)
        observed[number] = {"file": name, "bytes": len(payload), "sha256": row["sha256"]}
    need(set(observed) == plan_numbers, "RFC reference set differs")
    actual_names = {item.name for item in source_dir.iterdir() if FILENAME.fullmatch(item.name)}
    need(actual_names == {row["file"] for row in rows}, "extra or missing RFC source file")
    need(manifest_path.read_bytes() == manifest_bytes and plan_path.read_bytes() == plan_bytes,
         "manifest or plan changed during readback")
    return {
        "schema_version": 1,
        "status": "passed-rfc-reference-byte-readback-unreviewed",
        "manifest_sha256": digest(manifest_bytes),
        "plan_sha256": digest(plan_bytes),
        "rfc_count": len(observed),
        "total_bytes": sum(row["bytes"] for row in observed.values()),
        "sources": [observed[number] for number in sorted(observed)],
        "updates_obsoletes_errata_reviewed": False,
        "clause_index_complete": False,
        "m0_complete": False,
        "m0_m12_complete": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = readback(args.manifest, args.plan, args.source_dir)
    with args.output.open("x") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(result["status"], result["rfc_count"], result["total_bytes"])


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Copy an explicit Kernel Linux codec manifest into a partial M0 ABI inventory."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from kernel_sdk import ARCH_TRIPLES
from plan_ledger import CONTRACTS, load_json


OUTPUT = CONTRACTS / "drafts/linux_abi_bootstrap.json"


def build(kernel_manifest: Path, ledger_path: Path) -> dict:
    source_bytes = kernel_manifest.read_bytes()
    source = load_json(kernel_manifest, content=source_bytes)
    ledger = load_json(ledger_path)
    if source.get("scope") != "bootstrap-codec-model-only" or source.get("schema_version") != 1:
        raise ValueError("input is not the reviewed bootstrap codec model manifest")
    if source.get("linux_source_provenance") != "local inspected files; full upstream archive authenticity not established":
        raise ValueError("Linux source provenance changed; review before updating this draft")
    if source.get("musl_archive_sha256") != next(ref["archive_sha256"] for ref in ledger["references"] if ref["id"] == "musl"):
        raise ValueError("musl source pin differs from the OS ledger")
    linux_ref = next(ref for ref in ledger["references"] if ref["id"] == "linux-uapi-ext4")
    if linux_ref["status"] != "source-pinned" or linux_ref["archive_sha256"] is None:
        raise ValueError("Linux source archive must be pinned before regenerating the ABI draft")
    profiles = {row["architecture"]: row for row in source["profiles"]}
    architectures = {row["id"]: row for row in ledger["architectures"]}
    if len(profiles) != len(source["profiles"]):
        raise ValueError("bootstrap manifest repeats an architecture profile")
    if len(architectures) != len(ledger["architectures"]):
        raise ValueError("OS ledger repeats an architecture profile")
    if profiles.keys() != ARCH_TRIPLES.keys() or architectures.keys() != ARCH_TRIPLES.keys():
        raise ValueError("bootstrap draft must retain exactly all ten profiles")
    names = None
    result = []
    for arch in ARCH_TRIPLES:
        row = profiles[arch]
        os_row = architectures[arch]
        if row["word_bytes"] * 8 != os_row["elf_class"] or row["byte_order"] != os_row["byte_order"]:
            raise ValueError(f"{arch}: ABI width or endian differs from the OS profile")
        if row["linux_qualification"] != "unqualified" or row["execution"] != "host-codec-model-only":
            raise ValueError(f"{arch}: input overstates model qualification")
        numbers = row["syscall_numbers"]
        if names is None:
            names = list(numbers)
        elif list(numbers) != names:
            raise ValueError(f"{arch}: syscall name universe differs")
        if not set(row["linux_number_crosschecks"]) <= {name for name, value in numbers.items() if value is not None}:
            raise ValueError(f"{arch}: crosscheck names absent source numbers")
        if any(value is not None and (type(value) is not int or value < 0 or value >= 0xffffffff)
               for value in numbers.values()):
            raise ValueError(f"{arch}: invalid syscall number")
        result.append({
            "architecture": arch,
            "linux_target": os_row["linux_target"],
            "word_bytes": row["word_bytes"],
            "byte_order": row["byte_order"],
            "error_convention": row["error_convention"],
            "number_register": row["number_register"],
            "return_register": row["return_register"],
            "argument_registers": row["argument_registers"],
            "aligned_64bit_pairs": row["aligned_64bit_pairs"],
            "syscall_numbers": numbers,
            "errno_numbers": row["errno_numbers"],
            "linux_number_crosschecks": row["linux_number_crosschecks"],
            "qualification": "unqualified-model-data-only",
        })
    return {
        "schema_version": 1,
        "scope": "partial-linux-abi-bootstrap-number-inventory",
        "kernel_manifest_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "ledger_revision": ledger["ledger_revision"],
        "linux_reference_version": source["linux_reference_version"],
        "kernel_model_source_provenance": source["linux_source_provenance"],
        "linux_archive_artifact": linux_ref["archive_artifact"],
        "linux_archive_sha256": linux_ref["archive_sha256"],
        "musl_version": source["musl_version"],
        "musl_archive_sha256": source["musl_archive_sha256"],
        "source_file_sha256": source["source_file_sha256"],
        "limitations": [
            "Selected bootstrap syscall names and errno values only, not a complete Linux ABI universe.",
            "The Kernel model was generated from locally inspected files; verify the OS-pinned full archive separately with check_linux_source.py.",
            "No clause/structure/flag/signal/TLS/ELF layout coverage certificate or native execution claim.",
            "This draft cannot satisfy the M0 reviewed linux-abi-layouts index.",
        ],
        "architectures": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel-manifest", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, default=CONTRACTS / "ledger.json")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        data = json.dumps(build(args.kernel_manifest, args.ledger), indent=2, sort_keys=True) + "\n"
        if args.check:
            if args.output.read_text() != data:
                raise ValueError("bootstrap ABI draft differs from explicit source manifest or ledger")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(data)
        print("Linux ABI bootstrap draft: ten unqualified profiles; partial M0 inventory only")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ABI draft error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

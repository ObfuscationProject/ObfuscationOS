#!/usr/bin/env python3
"""Check explicitly pinned e2fsprogs archives without executing upstream code."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile


REFERENCES = ("e2fsprogs-primary", "e2fsprogs-secondary")
FILES = (
    "configure.ac", "version.h", "lib/ext2fs/ext2_fs.h",
    "lib/ext2fs/kernel-jbd.h", "lib/ext2fs/crc32c.c", "lib/ext2fs/csum.c",
    "e2fsck/journal.c", "misc/mke2fs.c",
)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "duplicate JSON key: " + key)
        result[key] = value
    return result


def regular(root, relative):
    parts = PurePosixPath(relative)
    need(relative and str(parts) == relative and not parts.is_absolute()
         and ".." not in parts.parts and "\\" not in relative,
         "noncanonical archive artifact")
    path = root
    for component in parts.parts:
        path = path / component
        need(not path.is_symlink(), "symlink archive component")
    need(path.is_file(), "missing ordinary archive: " + str(path))
    return path


def check_reference(reference, source_root):
    version = reference["version"]
    need(isinstance(version, str) and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version),
         "explicit three-component release required")
    need(reference["status"] == "source-pinned", "source reference is not pinned")
    prefix = "e2fsprogs-" + version
    artifact = prefix + "/" + prefix + ".tar.xz"
    need(reference["archive_artifact"] == artifact, "unexpected archive artifact")
    path = regular(source_root, artifact)
    archive_hash = digest(path.read_bytes())
    need(archive_hash == reference["archive_sha256"], "archive hash differs: " + version)
    records = reference["audited_files"]
    pins = {entry["path"]: entry["sha256"] for entry in records}
    need(len(records) == len(pins) and set(pins) == set(FILES), "exact audited file set required")
    observed = {}
    names = set()
    total = 0
    with tarfile.open(path, "r:xz") as archive:
        for member in archive:
            name = member.name.rstrip("/")
            normalized = PurePosixPath(name)
            need(str(normalized) == name and not normalized.is_absolute()
                 and ".." not in normalized.parts and "\\" not in name
                 and normalized.parts[0] == prefix, "unsafe archive namespace")
            need(name not in names, "duplicate archive member: " + name)
            names.add(name)
            need(len(names) <= 20000 and 0 <= member.size <= 64 * 1024 * 1024,
                 "archive member bound exceeded")
            total += member.size
            need(total <= 512 * 1024 * 1024, "archive expanded size bound exceeded")
            relative = "/".join(normalized.parts[1:])
            if relative not in pins:
                continue
            need(member.isfile(), "audited member must be a regular file")
            stream = archive.extractfile(member)
            need(stream is not None, "audited member has no contents")
            data = stream.read()
            need(len(data) == member.size and digest(data) == pins[relative],
                 "audited member hash differs: " + relative)
            observed[relative] = data
    need(set(observed) == set(FILES), "audited member missing")
    text = observed["version.h"].decode("ascii")
    matched = re.findall(r'^#define\s+E2FSPROGS_VERSION\s+"([^\"]+)"', text, re.MULTILINE)
    need(matched == [version], "release version header differs")
    need(digest(path.read_bytes()) == archive_hash, "archive changed during inspection")
    return {
        "reference": reference["id"], "version": version,
        "archive_artifact": artifact, "archive_sha256": archive_hash,
        "archive_member_count": len(names), "expanded_bytes": total,
        "audited_files": [{"path": name, "sha256": pins[name]} for name in FILES],
        "upstream_code_executed": False, "detached_signature_verified": False,
        "ext4_profile_qualified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    need(args.ledger.is_file() and not args.ledger.is_symlink(), "ordinary ledger required")
    need(args.source_root.is_dir() and not args.source_root.is_symlink(), "ordinary source root required")
    ledger_bytes = args.ledger.read_bytes()
    ledger = json.loads(ledger_bytes, object_pairs_hook=unique_object)
    references = [row for row in ledger["references"] if row["id"] in REFERENCES]
    need(len(references) == 2 and {row["id"] for row in references} == set(REFERENCES),
         "two distinct e2fsprogs references required")
    result = {
        "schema_version": 1, "status": "passed-pinned-e2fsprogs-source-readback",
        "ledger_sha256": digest(ledger_bytes),
        "source_root": str(args.source_root.resolve()),
        "references": [check_reference(row, args.source_root) for row in references],
        "full_ext4_inventory": False, "m0_complete": False, "tools_built": False,
    }
    need(args.ledger.read_bytes() == ledger_bytes, "ledger changed during inspection")
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(result["status"])


if __name__ == "__main__":
    main()

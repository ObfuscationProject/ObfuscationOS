#!/usr/bin/env python3
"""Authenticate the explicit Linux 6.13.4 archive and audited source files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

from plan_ledger import CONTRACTS, load_json


EXPECTED_FINGERPRINT = "647F28654894E3BD457199BE38DBBDC86092693E"
KEY_DOCUMENTATION = "https://www.kernel.org/signature.html"
ARCHIVE_NAME = "linux-6.13.4.tar.xz"


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def signed_tar(archive: Path, signature: Path, key: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="obf-linux-source-gpg-") as directory:
        home = Path(directory)
        home.chmod(0o700)
        details = subprocess.run(["gpg", "--batch", "--no-autostart", "--homedir", str(home),
                                  "--show-keys", "--with-colons", str(key)],
                                 capture_output=True, text=True, check=True)
        fingerprints = re.findall(r"^fpr:::::::::([0-9A-F]{40}):", details.stdout, re.M)
        if not fingerprints or fingerprints[0] != EXPECTED_FINGERPRINT:
            raise ValueError("release key primary fingerprint differs from kernel.org documentation")
        subprocess.run(["gpg", "--batch", "--no-autostart", "--homedir", str(home), "--import", str(key)],
                       capture_output=True, text=True, check=True)
        decompressor = subprocess.Popen(["xz", "-dc", str(archive)],
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            verified = subprocess.run(["gpg", "--batch", "--no-autostart", "--homedir", str(home),
                                       "--status-fd=1", "--verify", str(signature), "-"],
                                      stdin=decompressor.stdout, capture_output=True, text=True)
        finally:
            decompressor.stdout.close()
        decompressor_error = decompressor.stderr.read().decode("utf-8", errors="replace")
        decompressor_exit = decompressor.wait()
        if decompressor_exit != 0:
            raise ValueError(f"archive decompression failed: {decompressor_error.strip()}")
        if verified.returncode != 0:
            raise ValueError(f"release signature verification failed: {verified.stderr.strip()}")
        valid = re.findall(r"^\[GNUPG:\] VALIDSIG ([0-9A-F]{40})\b", verified.stdout, re.M)
        if valid != [EXPECTED_FINGERPRINT]:
            raise ValueError("release signature was not made by the pinned developer key")
        return {"signer_fingerprint": EXPECTED_FINGERPRINT,
                "signature_sha256": sha(signature), "public_key_sha256": sha(key),
                "key_documentation": KEY_DOCUMENTATION,
                "gpg_status": "valid-signature-and-matching-published-fingerprint"}


def audited_files(archive: Path, expected: dict[str, str]) -> dict[str, str]:
    actual = {}
    with tarfile.open(archive, mode="r|xz") as source:
        for member in source:
            if not member.isfile() or not member.name.startswith("linux-6.13.4/"):
                continue
            name = member.name.removeprefix("linux-6.13.4/")
            if name not in expected:
                continue
            if name in actual:
                raise ValueError(f"duplicate audited archive member: {name}")
            stream = source.extractfile(member)
            if stream is None:
                raise ValueError(f"cannot read audited archive member: {name}")
            h = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
            actual[name] = h.hexdigest()
            if actual[name] != expected[name]:
                raise ValueError(f"audited source hash mismatch: {name}")
    missing = expected.keys() - actual.keys()
    if missing:
        raise ValueError(f"audited source files absent from archive: {sorted(missing)}")
    return actual


def check(source_root: Path, signature: Path, key: Path, ledger_path: Path,
          kernel_manifest: Path | None) -> dict:
    ledger = load_json(ledger_path)
    reference = next(row for row in ledger["references"] if row["id"] == "linux-uapi-ext4")
    if reference["status"] != "source-pinned" or reference["version"] != "6.13.4":
        raise ValueError("Linux reference is not pinned to version 6.13.4 in the ledger")
    if reference["archive_artifact"] != "linux-6.13.4/" + ARCHIVE_NAME:
        raise ValueError("Linux source artifact path differs from explicit release archive")
    archive = source_root / reference["archive_artifact"]
    archive_digest = sha(archive)
    if archive_digest != reference["archive_sha256"]:
        raise ValueError("Linux source archive checksum differs from the ledger pin")
    expected = {row["path"]: row["sha256"] for row in reference["audited_files"]}
    if len(expected) != len(reference["audited_files"]):
        raise ValueError("duplicate audited Linux source path in ledger")
    model_count = 0
    if kernel_manifest is not None:
        model = load_json(kernel_manifest)
        if model["linux_reference_version"] != "6.13.4":
            raise ValueError("Kernel codec manifest names another Linux version")
        for name, digest in model["source_file_sha256"].items():
            if not name.startswith("linux/"):
                continue
            relative = name.removeprefix("linux/")
            if relative in expected and expected[relative] != digest:
                raise ValueError(f"ledger/model source digest conflict: {relative}")
            expected[relative] = digest
            model_count += 1
    signature_result = signed_tar(archive, signature, key)
    found = audited_files(archive, expected)
    return {"schema_version": 1, "status": "verified-source-archive",
            "scope": "Linux 6.13.4 source provenance and selected file hashes; M0 inventory still incomplete",
            "archive_artifact": reference["archive_artifact"],
            "archive_sha256": archive_digest,
            "signature": signature_result,
            "ledger_audited_file_count": len(reference["audited_files"]),
            "kernel_model_audited_file_count": model_count,
            "unique_audited_file_count": len(found),
            "audited_files": found}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--signature", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, default=CONTRACTS / "ledger.json")
    parser.add_argument("--kernel-manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = check(args.source_root, args.signature, args.key, args.ledger,
                       args.kernel_manifest)
        output = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output)
        else:
            print(output, end="")
        return 0
    except (OSError, ValueError, KeyError, StopIteration, subprocess.SubprocessError,
            tarfile.TarError) as exc:
        print(f"Linux source check error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

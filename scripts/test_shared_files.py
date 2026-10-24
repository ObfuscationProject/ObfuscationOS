#!/usr/bin/env python3
"""Execute paired volatile shared-file and rights aliases inside a real QEMU guest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import shutil
import subprocess
import sys
import time

from qemu_distro import command_for

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from build_musl_probe import admit_musl_build
from kernel_sdk import ARCH_TRIPLES, validate_sdk
from musl_source import inspect_elf

DETAILS = (b"acceptance=pass version=3 actual_native_alias=1 guest=1 physical_machine=0 english=1 "
           b"distinct_vas=1 canonical_io=1 vectors=1 vector_rollback=1 additive_seals=1 final_seals=1 "
           b"dup=1 fork=1 prot_none=1 offset_alias=1 partial_unmap=1 map_fixed=1 file_replacement=1 "
           b"file_capacity=1 descriptor_capacity=1 page_capacity=1 reclamation=40")
RIGHTS = b"queue_last_owner=pass roundtrip=pass cloexec=pass alias=pass discard=pass"
COMPLETE = b"OK_SHARED_FILES_SUITE native=2 static_musl=2 child_exit=0"
MARKERS = (b"OK_NATIVE_SHARED_FILES " + DETAILS, b"OK_NATIVE_SHARED_RIGHTS " + RIGHTS,
           b"OK_MUSL_SHARED_FILES " + DETAILS, b"OK_STATIC_SHARED_RIGHTS " + RIGHTS, COMPLETE)
# The bounded native provider exports at most 1024 allocator frames.
FRAME_CAPACITY = 1024
FRAME_FIELDS = {"version", "source", "used", "total", "allocations", "releases", "pinned", "user",
                "objects", "free", "pending", "reserve", "user_limit", "object_quarantine"}
FILE_FIELDS = {"version", "files", "aliases", "retiring_files", "retained_frames", "reserved_cells"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_fields(payload: bytes, expected: set[str]) -> dict:
    fields = {}
    for item in payload.decode("ascii").split():
        key, separator, value = item.partition("=")
        if not separator or key in fields or key not in expected:
            raise ValueError("ledger has malformed, duplicate or unexpected fields")
        if key == "source":
            if value not in ("firmware", "linker"):
                raise ValueError("ledger has invalid page source")
            fields[key] = value
        else:
            if not re.fullmatch(r"[0-9]+", value):
                raise ValueError("ledger has invalid nonnegative count")
            fields[key] = int(value)
    if set(fields) != expected:
        raise ValueError("ledger is missing required fields")
    return fields


def run_evidence(serial: bytes) -> dict:
    """Bind success and final reclamation to one completed shell command segment."""
    positions = []
    for marker in MARKERS:
        matches = list(re.finditer(rb"(?m)^" + re.escape(marker) + rb"\r?\n", serial))
        if len(matches) != 1:
            raise ValueError("guest outcome is missing, duplicated or malformed: " + marker.decode())
        positions.append(matches[0].start())
    if positions != sorted(positions):
        raise ValueError("guest outcomes disagree with the native suite runner order")
    if any(failure in serial for failure in (b"SHARED_FILES_FAIL", b"SHARED_RIGHTS_FAIL", b"KERNEL PANIC",
                                            b"ASSERTION FAILED", b"OK_TEST_FAIL", b"OK_SYSTEM_GUI boot=failed")):
        raise ValueError("guest reported a probe or kernel failure")
    completion = positions[-1]
    pairs = list(re.finditer(rb"(?m)^OK_NATIVE_FRAMES ([^\r\n]+)\r?\nOK_NATIVE_SHARED_FILES_LEDGER ([^\r\n]+)\r?\n", serial))
    if not pairs or pairs[-1].start() <= completion:
        raise ValueError("final paired owner ledgers are absent after suite completion")
    pair = pairs[-1]
    # A matching older zero pair cannot hide a later ledger-shaped record.
    # Include malformed and prefixed lines in this boundary check, then bind
    # the selected exact pair to the last two ledger-shaped lines.
    shaped = list(re.finditer(rb"(?m)^[^\r\n]*(?:OK_NATIVE_FRAMES|OK_NATIVE_SHARED_FILES_LEDGER)[^\r\n]*(?:\r?\n|$)", serial))
    if len(shaped) < 2 or pair.start() != shaped[-2].start() or pair.end() != shaped[-1].end():
        raise ValueError("latest owner ledger records are malformed, prefixed or unpaired")
    frames = parse_fields(pair[1], FRAME_FIELDS)
    files = parse_fields(pair[2], FILE_FIELDS)
    if frames["version"] != 2 or files["version"] != 1:
        raise ValueError("owner ledger version mismatch")
    if any(files[name] for name in FILE_FIELDS - {"version"}):
        raise ValueError("shared file ownership was not fully reclaimed")
    if any(frames[name] for name in ("pinned", "pending", "object_quarantine")):
        raise ValueError("physical ownership retirement is still pending")
    if frames["allocations"] - frames["releases"] != frames["used"] or \
            frames["used"] != frames["user"] + frames["objects"]:
        raise ValueError("physical owner counters disagree")
    if not 0 < frames["total"] <= FRAME_CAPACITY or frames["reserve"] > frames["total"] or \
            frames["free"] + frames["used"] != frames["total"] or \
            frames["reserve"] + frames["user_limit"] != frames["total"] or \
            frames["user"] > frames["user_limit"] or frames["objects"] > frames["reserve"]:
        raise ValueError("physical pool capacity or quota counters disagree")
    return {"shared_files": files, "frames": frames, "ledger_serial_offset": pair.start()}


def stable_owners(evidence: dict) -> dict:
    return {name: evidence["frames"][name] for name in
            ("source", "used", "total", "user", "objects", "free", "reserve", "user_limit")}


def receive(process: subprocess.Popen, serial: bytearray, marker: bytes, deadline: float, start: int = 0) -> None:
    while marker not in serial[start:]:
        if time.monotonic() > deadline:
            raise RuntimeError("guest did not print " + repr(marker))
        ready, _, _ = select.select([process.stdout], [], [], .1)
        if not ready:
            continue
        chunk = os.read(process.stdout.fileno(), 8192)
        if not chunk:
            raise RuntimeError("QEMU exited before command completion")
        serial.extend(chunk)
        if any(failure in serial for failure in (b"KERNEL PANIC", b"ASSERTION FAILED", b"OK_SYSTEM_GUI boot=failed")):
            raise RuntimeError("guest reported a kernel or boot failure")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", required=True, choices=ARCH_TRIPLES)
    parser.add_argument("--mode", required=True, choices=("debug", "release"))
    for name in ("qemu", "kernel", "kernel-sdk", "rootfs-tree", "files-probe", "rights-probe",
                 "native-files", "native-rights", "runner", "musl-build", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--expected-abi", type=int, required=True)
    args = parser.parse_args()
    if not __debug__ or not sys.dont_write_bytecode or os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ValueError("run with PYTHONDONTWRITEBYTECODE=1 python3 -B")
    sdk = validate_sdk(args.kernel_sdk.resolve(), args.arch, args.mode)
    if args.expected_abi != 65 or sdk["abi_version"] != args.expected_abi:
        raise ValueError("exact ABI65 shared-file SDK is required")
    musl = admit_musl_build(args.musl_build.resolve(), args.arch)
    if musl["mode"] != args.mode:
        raise ValueError("musl and SDK modes differ")
    inputs = {"kernel": args.kernel.resolve(), "sdk_manifest": args.kernel_sdk.resolve() / "manifest.json",
              "musl_manifest": args.musl_build.resolve() / "manifest.json", "qemu": args.qemu.resolve(),
              "script": Path(__file__).resolve(), "native_files": args.native_files.resolve(),
              "native_rights": args.native_rights.resolve(), "runner": args.runner.resolve()}
    for name, probe, source in (("files", args.files_probe, "shared_files_probe.c"),
                                ("rights", args.rights_probe, "shared_rights_probe.c")):
        probe = probe.resolve()
        manifest_path = probe.parent / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        source_path = TOOLS.parent / "tests/native" / source
        if (manifest.get("status") != "built-not-executed" or manifest.get("executed") is not False or
                manifest.get("architecture") != args.arch or manifest.get("mode") != args.mode or
                manifest.get("probe_sha256") != sha(source_path) or
                manifest.get("source_manifest_sha256") != sha(inputs["musl_manifest"]) or
                manifest.get("elf_sha256") != sha(probe)):
            raise ValueError("static probe source, binary or musl identity mismatch: " + name)
        inputs[name + "_source"] = source_path
        inputs[name + "_probe"] = probe
        inputs[name + "_manifest"] = manifest_path
    for name in ("native_files", "native_rights", "runner", "files_probe", "rights_probe"):
        inspect_elf(inputs[name], args.arch)
        if inputs[name].read_bytes()[7] != (3 if name.endswith("_probe") else 0):
            raise ValueError("probe/runner personality mismatch: " + name)
    input_hashes = {name: sha(path) for name, path in inputs.items()}
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = out / "root"
    shutil.copytree(args.rootfs_tree.resolve(), root, symlinks=True)
    for name, destination in (("native_files", "shared-files-native"), ("native_rights", "shared-rights-native"),
                              ("files_probe", "shared-files-static"), ("rights_probe", "shared-rights-static"),
                              ("runner", "shared-files-suite")):
        shutil.copy2(inputs[name], root / "bin" / destination)
        (root / "bin" / destination).chmod(0o755)
    disk = out / "rootfs.ext4.img"
    with (out / "package.log").open("x") as log:
        subprocess.run([sys.executable, "-B", str(TOOLS / "mkext4.py"), "--root", str(root), "--out", str(disk)],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    initial = out / "rootfs-input.ext4.img"
    shutil.copy2(disk, initial)
    kernel = out / "kernel-input.bin"
    shutil.copy2(inputs["kernel"], kernel)
    command = command_for(inputs["qemu"], args.arch, kernel, disk, "none", native_profile=True)
    record = {"schema": 1, "scope": "actual volatile shared-file native/static-musl aliases and UNIX rights",
              "expected_sdk_abi": args.expected_abi, "status": "running", "architecture": args.arch,
              "mode": args.mode, "physical": False, "runs": 0, "command": command,
              "inputs": {name: {"path": str(path), "sha256": input_hashes[name]} for name, path in inputs.items()},
              "input_disk_sha256": sha(initial), "owner_evidence": []}
    serial = bytearray()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        receive(process, serial, b"OK_SYSTEM_GUI boot=complete", time.monotonic() + args.timeout)
        receive(process, serial, b"oksh> ", time.monotonic() + args.timeout)
        if b"OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw" not in serial:
            raise RuntimeError("guest did not mount prepared ext4")
        for _ in range(2):
            start = len(serial)
            process.stdin.write(b"shared-files-suite\n")
            process.stdin.flush()
            receive(process, serial, b"oksh> ", time.monotonic() + args.timeout, start)
            run = bytes(serial[start:]).replace(b"\r\n", b"\n")
            evidence = run_evidence(run)
            if record["owner_evidence"] and stable_owners(evidence) != stable_owners(record["owner_evidence"][0]):
                raise RuntimeError("repeated suite did not restore the same physical owners")
            record["owner_evidence"].append(evidence)
            record["runs"] += 1
        record["status"] = "awaiting-offline"
    except BaseException as error:
        record.update(status="fail", failure=repr(error))
        raise
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()
        (out / "serial.log").write_bytes(serial)
        record.update(serial_sha256=sha(out / "serial.log"), input_disk_unchanged=sha(initial) == record["input_disk_sha256"])
        (out / "result.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    with (out / "fsck.log").open("x") as log:
        check = subprocess.run(["/usr/sbin/e2fsck", "-fn", str(disk)], stdout=log, stderr=subprocess.STDOUT)
    record.update(fsck_exit_code=check.returncode, fsck_log_sha256=sha(out / "fsck.log"), final_disk_sha256=sha(disk))
    record["inputs_unchanged"] = all(sha(path) == input_hashes[name] for name, path in inputs.items())
    record["status"] = "pass" if check.returncode == 0 and record["input_disk_unchanged"] and record["inputs_unchanged"] and record["runs"] == 2 else "fail"
    (out / "result.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    if record["status"] != "pass":
        raise RuntimeError("offline/input preservation checks failed")
    print(f"PASS {args.arch}/{args.mode}: paired native/static-musl aliases and exact final owner ledgers")


if __name__ == "__main__":
    main()

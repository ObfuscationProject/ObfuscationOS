#!/usr/bin/env python3
"""Reproduce admitted plan and independent e2fsprogs oracle on disposable copies."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
sys.dont_write_bytecode = True
from admit_linux_fixture import inspect
from native_support import validate_sdk, ARCH_TRIPLES

STAGE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--kernel-sdk", type=Path, required=True)
    parser.add_argument("--arch", choices=tuple(ARCH_TRIPLES), required=True)
    parser.add_argument("--mode", choices=("debug", "release"), default="debug")
    parser.add_argument("--candidate-headers", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source, sdk, root = args.fixture.resolve(), args.kernel_sdk.resolve(), args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    validate_sdk(sdk, args.arch, args.mode)
    for name in ("baseline-clean.img", "linux-dirty-capture.img", "capture-manifest.json"):
        shutil.copy2(source / name, root / name)
    (root / "sdk-manifest.json").write_bytes((sdk / "manifest.json").read_bytes())
    commands = []
    command = [sys.executable, str(STAGE / "admit_linux_fixture.py"), "--fixture", str(root)]
    commands.append(command); subprocess.run(command, check=True)
    capture = (root / "linux-dirty-capture.img").read_bytes()
    facts = inspect(capture, True)
    overlay = []
    candidate_hashes = {}
    if args.candidate_headers:
        for name in ("jbd2.hpp", "jbd2_replay.hpp"):
            data = (args.candidate_headers.resolve() / "ok/fs" / name).read_bytes()
            target = root / "candidate/ok/fs" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            candidate_hashes[name] = hashlib.sha256(data).hexdigest()
        overlay = ["-I" + str(root / "candidate")]
    audit_source = root / "jbd2_plan_audit.cpp"
    audit_source.write_bytes((STAGE.parents[1] / "tests/native/jbd2_plan_audit.cpp").read_bytes())
    for label, extra in [("production", ["-DOS_JBD2_AUDIT_STRICT"]), ("candidate", overlay)]:
        binary = root / ("audit-plan-" + label)
        command = ["g++", "-std=c++23", "-O2", "-Wall", "-Wextra", "-Werror", "-fno-exceptions", *extra,
                   "-I" + str(sdk / "include"), "-I" + str(root), str(audit_source), "-o", str(binary)]
        commands.append(command); subprocess.run(command, check=True)
        command = [str(binary), str(root / "linux-dirty-capture.img")]
        commands.append(command)
        result = subprocess.run(command, capture_output=True, text=True)
        (root / ("audit-" + label + ".log")).write_text(result.stdout + result.stderr)
        if label == "production":
            if result.returncode != 5 or "foreign JBD2 tag UUID" not in result.stderr:
                raise ValueError("expected unchanged production UUID admission failure")
        else:
            if result.returncode != 0: raise ValueError("candidate plan failed: " + result.stderr)
            plan = json.loads(result.stdout)
    (root / "replay-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    if plan["transactions"] != 1 or [(a["target"], a["source"]) for a in plan["actions"]] != [(1, 2), (7, 3)]:
        raise ValueError("the bounded qualified capture changed transaction shape")
    expected = bytearray(capture)
    for action in plan["actions"]:
        begin = (facts["journal_first"] + action["source"]) * 1024
        payload = bytearray(capture[begin:begin + 1024])
        if action["escape"]: payload[:4] = struct.pack(">I", 0xc03b3998)
        expected[action["target"] * 1024:(action["target"] + 1) * 1024] = payload
    (root / "native-expected.img").write_bytes(expected)
    control_path = root / "e2fsprogs-recovery.img"
    shutil.copyfile(root / "linux-dirty-capture.img", control_path)
    for label, options in [("journal-recovery", ["-fy", "-E", "journal_only"]), ("post-recovery-check", ["-fn"])]:
        command = ["e2fsck", *options, str(control_path)]
        commands.append(command)
        result = subprocess.run(command, capture_output=True, text=True)
        (root / ("e2fsprogs-" + label + ".log")).write_text(result.stdout + result.stderr)
        if result.returncode != 0: raise ValueError("independent e2fsprogs recovery/check failed")
    control = control_path.read_bytes()
    changed = [index for index in range(len(capture) // 1024)
               if expected[index * 1024:(index + 1) * 1024] != control[index * 1024:(index + 1) * 1024]]
    if changed != [1, facts["journal_first"]]:
        raise ValueError("independent control differs outside superblock cleanup state")
    allowed = set(range(48, 56)) | set(range(64, 68)) | set(range(96, 100)) | set(range(376, 384)) | set(range(1020, 1024))
    differences = [index for index in range(1024) if expected[1024 + index] != control[1024 + index]]
    if not set(differences).issubset(allowed): raise ValueError("unexpected filesystem superblock change")
    if struct.unpack_from("<I", expected, 1024 + 96)[0] != 0x46 or struct.unpack_from("<I", control, 1024 + 96)[0] != 0x42:
        raise ValueError("recovery flag distinction lost")
    if (root / "linux-dirty-capture.img").read_bytes() != capture:
        raise ValueError("raw source capture mutated")
    report = {"commands": commands, "home_blocks_equal_except_ext4_cleanup_superblock": True,
              "different_blocks": changed, "ext4_superblock_difference_offsets": differences,
              "native_expected_sha256": hashlib.sha256(expected).hexdigest(),
              "independent_control_sha256": hashlib.sha256(control).hexdigest(),
              "candidate_is_exported_sdk": args.candidate_headers is None,
              "candidate_header_sha256": candidate_hashes,
              "audit_source_sha256": hashlib.sha256(audit_source.read_bytes()).hexdigest(), "mount_admission": False, "checkpoint": False}
    validate_sdk(sdk, args.arch, args.mode)
    (root / "qualification.json").write_text(json.dumps(report, indent=2) + "\n")
    print("PASS Linux capture independent qualification " + str(root / "qualification.json"))


if __name__ == "__main__": main()

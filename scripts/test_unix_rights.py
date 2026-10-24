#!/usr/bin/env python3
"""Execute an exact static-musl bounded AF_UNIX descriptor transfer inside a real QEMU guest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
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


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def receive(process: subprocess.Popen, serial: bytearray, marker: bytes, deadline: float, start: int = 0) -> None:
    while marker not in serial[start:]:
        if time.monotonic() > deadline:
            raise RuntimeError(f"guest did not print {marker!r}")
        ready, _, _ = select.select([process.stdout], [], [], .1)
        if not ready:
            continue
        chunk = os.read(process.stdout.fileno(), 8192)
        if not chunk:
            raise RuntimeError("QEMU exited before the guest command completed")
        serial.extend(chunk)
        if any(failure in serial for failure in (b"KERNEL PANIC", b"ASSERTION FAILED", b"OK_SYSTEM_GUI boot=failed")):
            raise RuntimeError("guest reported a kernel or boot failure")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", required=True, choices=ARCH_TRIPLES)
    parser.add_argument("--mode", required=True, choices=("debug", "release"))
    for name in ("qemu", "kernel", "kernel-sdk", "rootfs-tree", "probe", "runner", "musl-build", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--expected-abi", type=int, required=True)
    args = parser.parse_args()
    if not __debug__ or not sys.dont_write_bytecode or os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ValueError("run with PYTHONDONTWRITEBYTECODE=1 python3 -B")
    sdk = validate_sdk(args.kernel_sdk.resolve(), args.arch, args.mode)
    if args.expected_abi <= 0 or json.loads((args.kernel_sdk / "manifest.json").read_text()).get("abi_version") != args.expected_abi:
        raise ValueError("the exact selected SDK ABI does not match acceptance")
    musl = admit_musl_build(args.musl_build.resolve(), args.arch)
    if musl["mode"] != args.mode:
        raise ValueError("musl mode does not match SDK mode")
    source = TOOLS.parent / "tests/musl/unix_rights_static.c"
    probe_manifest_path = args.probe.resolve().parent / "manifest.json"
    probe_manifest = json.loads(probe_manifest_path.read_text())
    if (probe_manifest.get("status") != "built-not-executed" or probe_manifest.get("executed") is not False or
            probe_manifest.get("probe_sha256") != sha(source) or
            probe_manifest.get("source_manifest_sha256") != sha(args.musl_build.resolve() / "manifest.json") or
            probe_manifest.get("elf_sha256") != sha(args.probe.resolve())):
        raise ValueError("static probe source or musl build identity mismatch")
    inspect_elf(args.probe.resolve(), args.arch)
    inspect_elf(args.runner.resolve(), args.arch)
    if args.probe.read_bytes()[7] != 3 or args.runner.read_bytes()[7] != 0:
        raise ValueError("probe and runner personalities are not Linux and native")

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = out / "root"
    shutil.copytree(args.rootfs_tree.resolve(), root, symlinks=True)
    for source_file, target in ((args.probe.resolve(), root / "bin/unix-rights-static"),
                                (args.runner.resolve(), root / "bin/unix-rights-runner")):
        shutil.copy2(source_file, target)
        target.chmod(0o755)
    disk = out / "rootfs.ext4.img"
    with (out / "package.log").open("x") as log:
        subprocess.run([sys.executable, "-B", str(TOOLS / "mkext4.py"), "--root", str(root), "--out", str(disk)],
                       check=True, stdout=log, stderr=subprocess.STDOUT,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    initial = out / "rootfs-input.ext4.img"
    shutil.copy2(disk, initial)
    kernel = out / "kernel-input.bin"
    shutil.copy2(args.kernel.resolve(), kernel)
    command = command_for(args.qemu.resolve(), args.arch, kernel, disk, "none", native_profile=True)
    record = {"schema": 1, "scope": "actual bounded static-musl AF_UNIX descriptor-transfer guest", "expected_sdk_abi": args.expected_abi, "status": "running",
              "architecture": args.arch, "mode": args.mode, "physical": False, "runs": 0, "command": command,
              "sdk_manifest_sha256": sha(args.kernel_sdk.resolve() / "manifest.json"),
              "musl_manifest_sha256": sha(args.musl_build.resolve() / "manifest.json"),
              "probe_manifest_sha256": sha(probe_manifest_path), "probe_sha256": sha(args.probe.resolve()),
              "runner_sha256": sha(args.runner.resolve()), "kernel_sha256": sha(kernel),
              "qemu_sha256": sha(args.qemu.resolve()), "input_disk_sha256": sha(initial),
              "script_sha256": sha(Path(__file__))}
    serial = bytearray()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        receive(process, serial, b"OK_SYSTEM_GUI boot=complete", time.monotonic() + args.timeout)
        receive(process, serial, b"oksh> ", time.monotonic() + args.timeout)
        if b"OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw" not in serial:
            raise RuntimeError("guest did not mount prepared ext4 storage")
        for _ in range(2):
            start = len(serial)
            process.stdin.write(b"unix-rights-runner\n")
            process.stdin.flush()
            receive(process, serial, b"oksh> ", time.monotonic() + args.timeout, start)
            run = bytes(serial[start:])
            if run.count(b"OK_NATIVE_UNIX_RIGHTS transfer=pass cloexec=pass file_reopen=pass") != 1 or \
                    run.count(b"OK_STATIC_UNIX_RIGHTS transfer=pass shared_offset=pass file_reopen=pass cloexec=pass peek=pass ctrunc=pass fault=pass read_discard=pass cycles=pass") != 1 or \
                    run.count(b"OK_STATIC_UNIX_RIGHTS_RUNNER child_exit=0") != 1:
                raise RuntimeError("static-musl rights guest markers are incomplete")
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
    record["status"] = "pass" if check.returncode == 0 and record["input_disk_unchanged"] and record["runs"] == 2 else "fail"
    (out / "result.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    if record["status"] != "pass":
        raise RuntimeError("offline filesystem check failed")
    print(f"PASS {args.arch}/{args.mode}: two static-musl AF_UNIX stream guest runs")


if __name__ == "__main__":
    main()

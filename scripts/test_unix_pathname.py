#!/usr/bin/env python3
"""Execute an exact static-musl bounded AF_UNIX pathname streams inside a real QEMU guest."""
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
from plan_ledger import load_json


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_entry(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("explicit regular admission artifact required: " + str(path))
    return {"sha256": sha(path), "mode": oct(path.stat().st_mode & 0o777)}


def admit_target_inputs(args: argparse.Namespace) -> dict:
    """Bind the launched image and runner to one actual SDK-only target result.

    This admission reads producing receipts. It does not execute code or turn a
    declaration, arbitrary ELF, or pathname match into a successful build.
    """
    receipt = args.target_result.absolute()
    if file_entry(receipt)["sha256"] != args.target_result_sha256:
        raise ValueError("explicit target result pin mismatch")
    result = load_json(receipt)
    observed = result.get("observations", {})
    if (result.get("passed") is not True or result.get("errors") != [] or
            (observed.get("arch"), observed.get("mode"), observed.get("private_SDK_ABI"),
             observed.get("Linux_UAPI")) != (args.arch, args.mode, 65, "0.7.0") or
            observed.get("official_SDK_export") is not True or
            observed.get("SDK_only_consumer") is not True or
            observed.get("complete_distro_image_linked") is not True or
            Path(observed.get("private_SDK_path", "")).resolve() != args.kernel_sdk.resolve()):
        raise ValueError("passing same-profile ABI65 SDK-only target receipt required")

    def artifact(name: str, path: Path) -> None:
        selected = result.get("artifacts", {}).get(name, {})
        if (selected.get("path") != str(path.resolve()) or
                selected.get("entry") != file_entry(path.resolve())):
            raise ValueError("target receipt does not bind supplied artifact: " + name)

    image_key = "distro_image" if args.arch in ("x86_64", "aarch64") else "distro_ELF"
    artifact(image_key, args.kernel)
    artifact("sdk_manifest", args.kernel_sdk / "manifest.json")
    artifact("native_unix_pathname_runner", args.runner)

    selected_source = result.get("source", {})
    source_directory = Path(selected_source.get("directory", ""))
    for name, key in (("RESULT.json", "result_sha256"), ("FREEZE.json", "freeze_sha256")):
        if file_entry(source_directory / name)["sha256"] != selected_source.get(key):
            raise ValueError("target selected source capsule pin mismatch")
    source_freeze = load_json(source_directory / "FREEZE.json")
    manifest_path = source_directory / "SOURCE_MANIFEST_V1.json"
    if file_entry(manifest_path) != source_freeze.get("files", {}).get("SOURCE_MANIFEST_V1.json"):
        raise ValueError("target selected source manifest is not frozen")
    manifest = load_json(manifest_path)
    unit = "tests/native/unix_pathname_runner.c"
    authored_source = TOOLS.parent / unit
    if manifest.get("ObfuscationOS", {}).get("files", {}).get(unit) != file_entry(authored_source):
        raise ValueError("runner source differs from exact target source selection")
    records = [row for row in result.get("actual_object_dependency_records", [])
               if row.get("owner") == "OS" and row.get("unit") == unit]
    if len(records) != 1:
        raise ValueError("unique actual native runner compilation receipt required")
    compiled = records[0]
    if (compiled.get("source", {}).get("entry") != file_entry(authored_source) or
            compiled.get("dependency_same_command_as_object") is not True or
            compiled.get("dependency_compiler_generated") is not True or
            compiled.get("object_compile_reused") is not False or
            compiled.get("fresh_SDK_only_consumer") is not True or
            "-fno-access-control" in compiled.get("actual_compiler_argv", [])):
        raise ValueError("native runner lacks its actual normal-access SDK-only source closure")
    runner_links = [row for row in result.get("actual_link_records", [])
                    if row.get("owner") == "OS" and row.get("output", {}).get("path") == str(args.runner.resolve())]
    if len(runner_links) != 1 or not any(
            saved.get("path") == compiled.get("object", {}).get("path") and
            saved.get("entry") == compiled.get("object", {}).get("entry")
            for saved in runner_links[0].get("inputs", [])):
        raise ValueError("native runner link lacks its admitted actual source object")
    for saved in (compiled["source"], compiled["object"], compiled["object_producing_dependency_capture"],
                  runner_links[0]["output"]):
        if file_entry(Path(saved["path"])) != saved["entry"]:
            raise ValueError("native runner producing artifact changed")
    return {"target_result_path": str(receipt), "target_result_sha256": args.target_result_sha256,
            "source_selection": selected_source, "native_runner_source_sha256": sha(authored_source),
            "native_runner_actual_compile_and_link_admitted": True,
            "distro_image_selected_SDK_binding_admitted": True}


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
    parser.add_argument("--target-result", type=Path, required=True)
    parser.add_argument("--target-result-sha256", required=True)
    args = parser.parse_args()
    if not __debug__ or not sys.dont_write_bytecode or os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        raise ValueError("run with PYTHONDONTWRITEBYTECODE=1 python3 -B")
    sdk = validate_sdk(args.kernel_sdk.resolve(), args.arch, args.mode)
    if args.expected_abi != 65 or json.loads((args.kernel_sdk / "manifest.json").read_text()).get("abi_version") != args.expected_abi:
        raise ValueError("the exact selected SDK ABI does not match acceptance")
    admission = admit_target_inputs(args)
    musl = admit_musl_build(args.musl_build.resolve(), args.arch)
    if musl["mode"] != args.mode:
        raise ValueError("musl mode does not match SDK mode")
    source = TOOLS.parent / "tests/musl/unix_pathname_static.c"
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
    for source_file, target in ((args.probe.resolve(), root / "bin/unix-pathname-static"),
                                (args.runner.resolve(), root / "bin/unix-pathname-runner")):
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
    record = {"schema": 1, "scope": "actual bounded static-musl pathname AF_UNIX stream guest", "expected_sdk_abi": args.expected_abi, "status": "running",
              "architecture": args.arch, "mode": args.mode, "physical": False, "runs": 0, "command": command,
              "sdk_manifest_sha256": sha(args.kernel_sdk.resolve() / "manifest.json"),
              "musl_manifest_sha256": sha(args.musl_build.resolve() / "manifest.json"),
              "probe_manifest_sha256": sha(probe_manifest_path), "probe_sha256": sha(args.probe.resolve()),
              "runner_sha256": sha(args.runner.resolve()), "kernel_sha256": sha(kernel),
              "qemu_sha256": sha(args.qemu.resolve()), "input_disk_sha256": sha(initial),
              "script_sha256": sha(Path(__file__)), "input_admission": admission}
    serial = bytearray()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        receive(process, serial, b"OK_SYSTEM_GUI boot=complete", time.monotonic() + args.timeout)
        receive(process, serial, b"oksh> ", time.monotonic() + args.timeout)
        if b"OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw" not in serial:
            raise RuntimeError("guest did not mount prepared ext4 storage")
        if b"OK_RUN source=ram mode=volatile pathname_sockets=bounded" not in serial:
            raise RuntimeError("guest did not attach its explicit volatile runtime namespace")
        record["runs_by_personality"] = {"native": 0, "musl": 0}
        for _ in range(2):
            for personality, program, marker in (
                    ("native", b"unix-pathname-runner", b"OK_NATIVE_UNIX_PATHNAME"),
                    ("musl", b"unix-pathname-static", b"OK_MUSL_UNIX_PATHNAME")):
                start = len(serial)
                process.stdin.write(program + b"\n")
                process.stdin.flush()
                receive(process, serial, b"oksh> ", time.monotonic() + args.timeout, start)
                run = bytes(serial[start:])
                expected = marker + b" processes=distinct exec=client credentials=kernel rights=preaccept shared_offset=pass cloexec=pass"
                if run.count(expected) != 1:
                    raise RuntimeError("pathname stream guest marker is incomplete: " + personality)
                record["runs"] += 1
                record["runs_by_personality"][personality] += 1
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
    record["status"] = "pass" if check.returncode == 0 and record["input_disk_unchanged"] and record["runs"] == 4 and record["runs_by_personality"] == {"native": 2, "musl": 2} else "fail"
    (out / "result.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    if record["status"] != "pass":
        raise RuntimeError("offline filesystem check failed")
    print(f"PASS {args.arch}/{args.mode}: two native and two static-musl pathname AF_UNIX stream guest runs")


if __name__ == "__main__":
    main()

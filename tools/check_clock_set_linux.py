#!/usr/bin/env python3
"""Check clock_settime only inside a disposable, binary-pinned x86 Linux guest."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/jbd2"))
from create_linux_fixture import cpio
from native_support import boot

MARKER = ("LINUX_CLOCK_SET_PASS root_sets=5 observations=6 root_errors=11 user_errors=7 "
          "shared=pass monotonic=pass credentials=actual")
TARGETS = {
    "ordinary": 1709210100123456789,
    "backwards": 1709210096234567890,
    "time2040": 2214176523345678901,
    "narrowed-realtime": 1709210096000000123,
    "child-global": 2214176530789012345,
    "parent-observes-child": 2214176530789012345,
}
ERRORS = {
    "root-monotonic-null": 22, "root-invalid-id-null": 22, "root-narrowed-id-null": 22,
    "root-null": 14, "root-unmapped": 14, "root-negative-seconds": 22,
    "root-negative-nanoseconds": 22, "root-high-nanoseconds": 22,
    "root-wide-nanoseconds": 22, "root-upper-range": 22, "root-monotonic-floor": 22,
    "user-valid": 1, "user-id-null": 22, "user-null": 14, "user-negative-seconds": 22,
    "user-nanoseconds": 22, "user-upper-range": 22, "user-floor-permission-first": 1,
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_serial(serial):
    lines = serial.decode("utf-8", errors="replace").splitlines()
    if lines.count(MARKER) != 1 or any("JBD2_NATIVE_FAIL" in line for line in lines):
        raise ValueError("Linux clock-setting success marker is missing or ambiguous")
    version = [line for line in lines if line.startswith("LINUX_CLOCK_SET_BEGIN ")]
    if len(version) != 1 or not version[0].endswith(" machine=x86_64"):
        raise ValueError("exactly one x86_64 Linux version record is required")
    for marker in (
        "LINUX_CLOCK_SET_CREDENTIALS role=parent uid=0 euid=0 cap_sys_time=1",
        "LINUX_CLOCK_SET_CREDENTIALS role=child uid=1000 euid=1000 gid=1000 egid=1000 cap_sys_time=0",
        "LINUX_CLOCK_SET_DENIAL_PASS cases=7 credentials=actual unchanged=elapsed-brackets",
    ):
        if lines.count(marker) != 1:
            raise ValueError("actual guest credential evidence is incomplete")
    samples, failures = {}, {}
    for line in lines:
        if line.startswith("LINUX_CLOCK_SET_SAMPLE "):
            match = re.fullmatch(r"LINUX_CLOCK_SET_SAMPLE case=([a-z0-9-]+) target=(\d+) before=(\d+) "
                                r"after=(\d+) read_before=(\d+) realtime=(\d+) read_after=(\d+)", line)
            if not match or match[1] not in TARGETS or match[1] in samples:
                raise ValueError("malformed, duplicate or unknown setting sample")
            target, before, after, c, real, d = map(int, match.groups()[1:])
            if target != TARGETS[match[1]] or not before <= after <= c <= d:
                raise ValueError("setting target or monotonic order mismatch")
            if not target + c - after <= real <= target + d - before:
                raise ValueError("Linux setting elapsed bracket mismatch")
            samples[match[1]] = dict(target=target, before=before, after=after,
                                     read_before=c, realtime=real, read_after=d)
        if line.startswith("LINUX_CLOCK_SET_ERROR "):
            match = re.fullmatch(r"LINUX_CLOCK_SET_ERROR case=([a-z0-9-]+) errno=(\d+) before=(\d+) first=(\d+) "
                                r"first_after=(\d+) second_before=(\d+) second=(\d+) after=(\d+)", line)
            if not match or match[1] not in ERRORS or match[1] in failures:
                raise ValueError("malformed, duplicate or unknown rejection sample")
            error, b, first, c, d, second, e = map(int, match.groups()[1:])
            if error != ERRORS[match[1]] or not b <= c <= d <= e:
                raise ValueError("Linux rejection errno or monotonic order mismatch")
            if not d - c <= second - first <= e - b:
                raise ValueError("failed setter changed a running clock")
            failures[match[1]] = dict(errno=error, before=b, first=first, first_after=c,
                                      second_before=d, second=second, after=e)
    if set(samples) != set(TARGETS) or set(failures) != set(ERRORS):
        raise ValueError("Linux clock-setting case inventory is incomplete")
    child, parent = samples["child-global"], samples["parent-observes-child"]
    if (child["before"], child["after"]) != (parent["before"], parent["after"]):
        raise ValueError("parent did not observe the exact child's setting bracket")
    return dict(version=version[0], samples=samples, errors=failures,
                root_sets=5, setting_observations=6, root_errors=11, user_errors=7)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    record = dict(status="running", scope="actual-linux-x86-clock-settime-reference", commands=[],
                  host_clock_setters=False, host_mounts=False, guest_block_devices=0,
                  linux_guest_boots=0, obfuscation_guest_boots=0,
                  linux_source_reference_version="6.13.4", linux_source_provenance="not-established",
                  libc_scope="Host compiler static libc init; raw Linux syscalls, not a musl wrapper gate.")

    def save():
        (out / "result.json").write_text(json.dumps(record, indent=2) + "\n")

    def run(command, label):
        item = dict(label=label, command=list(map(str, command)))
        record["commands"].append(item)
        save()
        environment = os.environ.copy()
        for name in ("CPATH", "C_INCLUDE_PATH", "LIBRARY_PATH", "GCC_EXEC_PREFIX", "COMPILER_PATH"):
            environment.pop(name, None)
        result = subprocess.run(item["command"], capture_output=True, env=environment)
        log = out / (label + ".log")
        log.write_bytes(result.stdout + result.stderr)
        item.update(returncode=result.returncode, log=log.name, log_sha256=sha(log))
        save()
        if result.returncode:
            raise RuntimeError(label + " failed; inspect retained log")
        return result.stdout

    save()
    try:
        fixture = args.fixture.resolve()
        capture_path = fixture / "capture-manifest.json"
        capture = json.loads(capture_path.read_text())
        source = fixture / "linux-bzImage"
        if capture.get("kind") != "linux-guest-created-dirty-journal" or sha(source) != capture["linux_image_sha256"]:
            raise ValueError("pinned fixture Linux binary mismatch")
        shutil.copy2(capture_path, out / "fixture-capture-manifest.json")
        kernel = out / "linux-bzImage"
        shutil.copy2(source, kernel)
        if sha(kernel) != capture["linux_image_sha256"]:
            raise ValueError("Linux binary changed during snapshot")
        record.update(fixture=str(fixture), fixture_capture_sha256=sha(capture_path), linux_image_sha256=sha(kernel))
        identities = {}
        for name in ("gcc", "as", "ld", "readelf", "qemu-system-x86_64"):
            executable = shutil.which(name)
            if executable is None:
                raise ValueError("required executable unavailable: " + name)
            path = Path(executable).resolve()
            identities[name] = dict(path=str(path), sha256=sha(path))
        record["tool_identities"] = identities
        names = ("tests/linux/clock_set_init.c", "tools/check_clock_set_linux.py",
                 "tools/jbd2/create_linux_fixture.py", "tools/jbd2/native_support.py", "tools/kernel_sdk.py")
        record["source_sha256"] = {}
        for name in names:
            target = out / "sources" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
            record["source_sha256"][name] = sha(target)
        record["compiler_version"] = run([identities["gcc"]["path"], "--version"], "compiler-version").decode().strip()
        record["qemu_version"] = run([identities["qemu-system-x86_64"]["path"], "--version"], "qemu-version").decode().strip()
        init = out / "init"
        run([identities["gcc"]["path"], "-static", "-O2", "-Wall", "-Wextra", "-Werror",
             out / "sources/tests/linux/clock_set_init.c", "-o", init], "compile-init")
        run([identities["readelf"]["path"], "-h", "-l", init], "inspect-static-init")
        elf = init.read_bytes()
        if elf[:6] != b"\x7fELF\x02\x01" or int.from_bytes(elf[18:20], "little") != 62:
            raise ValueError("init must be a little-endian ELF64 x86_64 executable")
        offset, entry_size, count = (int.from_bytes(elf[32:40], "little"),
                                     int.from_bytes(elf[54:56], "little"), int.from_bytes(elf[56:58], "little"))
        if not count or entry_size < 56 or offset + entry_size * count > len(elf):
            raise ValueError("invalid ELF program header extent")
        if any(int.from_bytes(elf[offset + i * entry_size:offset + i * entry_size + 4], "little") == 3 for i in range(count)):
            raise ValueError("init is dynamically interpreted")
        initrd = out / "initramfs.cpio"
        initrd.write_bytes(cpio([("dev", 0o040755, b"", 0, 0), ("dev/console", 0o020600, b"", 5, 1),
                                ("init", 0o100755, elf, 0, 0)]))
        command = [identities["qemu-system-x86_64"]["path"], "-accel", "tcg", "-smp", "1", "-m", "512M",
                   "-kernel", str(kernel), "-initrd", str(initrd), "-nic", "none",
                   "-rtc", "base=2024-02-29T12:34:56,clock=vm,driftfix=none",
                   "-append", "console=ttyS0 rdinit=/init loglevel=4 panic=-1 nokaslr",
                   "-display", "none", "-serial", "stdio", "-monitor", "none", "-no-reboot"]
        item = dict(label="linux-clock-reference", command=command, termination="own-QEMU-child-after-marker")
        record["commands"].append(item)
        save()
        item["qemu_returncode"] = boot(command, MARKER + "\r\n", out / "serial.log")
        record["guest"] = validate_serial((out / "serial.log").read_bytes())
        item.update(status="pass", log="serial.log", log_sha256=sha(out / "serial.log"))
        for name, identity in identities.items():
            if sha(Path(identity["path"])) != identity["sha256"]:
                raise ValueError("tool changed during reference gate: " + name)
        for name, digest in record["source_sha256"].items():
            if sha(ROOT / name) != digest:
                raise ValueError("source changed during reference gate: " + name)
        if sha(kernel) != record["linux_image_sha256"]:
            raise ValueError("retained Linux binary changed")
        record.update(status="pass", linux_guest_boots=1, init_sha256=sha(init), initramfs_sha256=sha(initrd),
                      serial_sha256=sha(out / "serial.log"),
                      scope_notes=["Only x86_64 Linux raw clock_settime is exercised; no ILP32 or musl wrapper claim.",
                                   "Linux version is guest-reported and binary-pinned; complete source provenance is not established.",
                                   "No ObfuscationOS capability, IRQ, SMP, RTC-write or physical hardware claim follows."])
    except Exception as error:
        record.update(status="failed", error=str(error))
        print(str(error), file=sys.stderr)
    finally:
        record["artifact_sha256"] = {str(path.relative_to(out)): sha(path) for path in sorted(out.rglob("*"))
                                     if path.is_file() and path.name != "result.json"}
        save()
    return 0 if record["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Type job-control commands at the maintenance `oksh> ` prompt of a QEMU guest.

The runner builds tests/native/oksh_job_probe.c, the root tree and the
distribution kernel for the configured profile, stages the probe as
/bin/oksh-jobs in a copy of the root tree, packs it with tools/mkext4.py and
boots it. It then checks a stop reported by WUNTRACED, `jobs`, the exit
warning, `fg` (SIGCONT and the job's status), `bg`, a trailing `&` with
completion reports, /dev/null input for background jobs without job control,
and `fg` of a running background job.

The maintenance console is not a pseudo-terminal and has ISIG off, so the
probe stops itself with SIGSTOP; ^Z on a pts belongs to the login lane. This
is guest execution in QEMU, not physical hardware.
"""
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

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))
from kernel_sdk import ARCH_TRIPLES  # noqa: E402
from musl_source import inspect_elf  # noqa: E402

PROMPT = b"oksh> "
FAILURES = (b"KERNEL PANIC", b"ASSERTION FAILED", b"OK_SYSTEM_GUI boot=failed")
ARCH_ALIASES = {"x64": "x86_64", "amd64": "x86_64", "arm64": "aarch64", "riscv64": "rv64",
                "loong64": "loongarch64", "loongarch": "loongarch64"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configured_profile(xmake: str) -> tuple[str, str]:
    """Reads the arch and mode the project is configured for."""
    shown = subprocess.run([xmake, "show", "-P", str(ROOT)], check=True, capture_output=True, text=True, cwd=ROOT).stdout
    shown = re.sub(r"\x1b\[[0-9;]*m", "", shown)
    fields = dict(re.findall(r"^\s*(arch|mode): (\S+)\s*$", shown.split("information of project", 1)[-1], re.M))
    if "arch" not in fields or "mode" not in fields:
        raise RuntimeError("xmake show did not report the configured arch and mode")
    return ARCH_ALIASES.get(fields["arch"], fields["arch"]), fields["mode"]


class Guest:
    def __init__(self, command: list[str], timeout: float):
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)
        self.serial = bytearray()
        self.offset = 0
        self.timeout = timeout

    def receive(self, done, timeout: float | None = None) -> None:
        deadline = time.monotonic() + (timeout or self.timeout)
        while not done():
            if time.monotonic() > deadline:
                raise RuntimeError("timeout waiting for the guest")
            ready, _, _ = select.select([self.process.stdout], [], [], .1)
            if not ready:
                continue
            chunk = os.read(self.process.stdout.fileno(), 8192)
            if not chunk:
                raise RuntimeError("QEMU exited before the check completed")
            self.serial.extend(chunk)
            if any(failure in self.serial for failure in FAILURES):
                raise RuntimeError("guest reported a kernel or boot failure")

    def boot(self) -> None:
        self.receive(lambda: b"OK_SYSTEM_GUI boot=complete" in self.serial and PROMPT in self.serial)
        self.offset = self.serial.rindex(PROMPT) + len(PROMPT)

    def step(self, line: str) -> bytes:
        """Type one line and return the output up to the next prompt."""
        start = self.offset
        self.process.stdin.write(line.encode() + b"\n")
        self.process.stdin.flush()
        self.receive(lambda: PROMPT in self.serial[start:])
        end = self.serial.index(PROMPT, start)
        self.offset = end + len(PROMPT)
        return bytes(self.serial[start:end]).replace(b"\r", b"")

    def until(self, expected: bytes, attempts: int = 50) -> bytes:
        """Type empty lines until a prompt is preceded by the expected report."""
        seen = b""
        for _ in range(attempts):
            seen += self.step("")
            if expected in seen:
                return seen
            time.sleep(.2)
        raise RuntimeError(f"no {expected!r} after {attempts} prompts")

    def close(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()


def require(output: bytes, *expected: bytes) -> None:
    for item in expected:
        if item not in output:
            raise RuntimeError(f"missing {item!r} in {output!r}")


def exercise(guest: Guest) -> dict:
    observed = {}
    out = guest.step("oksh-jobs stop 7")
    match = re.search(rb"OKSH_JOBS stop pid=(\d+)\n", out)
    group = re.search(rb"OKSH_JOBS group pgrp=(\d+)\n", out)
    if not match or not group:
        raise RuntimeError(f"probe did not start: {out!r}")
    pid = int(match.group(1))
    observed["job_process_group"] = "own" if int(group.group(1)) == pid else "shell"
    require(out, b"[1]+ Stopped oksh-jobs stop 7\n")
    require(guest.step("jobs"), b"[1]+ Stopped oksh-jobs stop 7\n")
    require(guest.step("exit"), b"oksh: there are stopped jobs\n")
    out = guest.step("fg || echo fg-status-nonzero")
    require(out, b"oksh-jobs stop 7\n", b"OKSH_JOBS continued pid=%d\n" % pid, b"fg-status-nonzero\n")
    if guest.step("jobs").strip():
        raise RuntimeError("fg left the finished job in the table")
    observed["stop_fg"] = "pass"

    require(guest.step("oksh-jobs stop 0"), b"[1]+ Stopped oksh-jobs stop 0\n")
    start = guest.offset
    require(guest.step("bg"), b"[1]+ oksh-jobs stop 0 &\n")
    guest.until(b"[1]+ Done oksh-jobs stop 0\n")
    require(bytes(guest.serial[start:]).replace(b"\r", b""), b"OKSH_JOBS continued pid=")
    observed["stop_bg"] = "pass"

    start = guest.offset
    if not re.match(rb"\[1\] \d+\n", guest.step("oksh-jobs stdin &")):
        raise RuntimeError("background launch was not reported")
    guest.until(b"[1]+ Done oksh-jobs stdin\n")
    require(bytes(guest.serial[start:]).replace(b"\r", b""), b"OKSH_JOBS stdin bytes=0\n")
    observed["background_done"] = "pass"

    if not re.match(rb"\[1\] \d+\n", guest.step("oksh-jobs sleep 3 &")):
        raise RuntimeError("background launch was not reported")
    require(guest.step("jobs"), b"[1]+ Running oksh-jobs sleep 3\n")
    out = guest.step("fg")
    require(out, b"oksh-jobs sleep 3\n", b"OKSH_JOBS slept seconds=3\n")
    if guest.step("jobs").strip():
        raise RuntimeError("fg left the finished job in the table")
    observed["running_fg"] = "pass"
    return observed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", required=True, choices=ARCH_TRIPLES)
    parser.add_argument("--mode", default="debug", choices=("debug", "release"))
    parser.add_argument("--qemu", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="new output directory")
    parser.add_argument("--xmake", default="xmake")
    parser.add_argument("--no-build", action="store_true", help="use the existing build outputs")
    parser.add_argument("--timeout", type=float, default=300, help="seconds for the boot and for each step")
    args = parser.parse_args()
    if configured_profile(args.xmake) != (args.arch, args.mode):
        raise ValueError(f"the project is not configured for {args.arch}/{args.mode}")
    if not args.no_build:
        for target in ("app-oksh-job-probe", "rootfs-stage", "distro_image"):
            subprocess.run([args.xmake, "-P", str(ROOT), "-y", "-b", target], check=True, cwd=ROOT)
    build = ROOT / "build" / args.arch / args.mode
    probe = build / "apps/oksh-jobs.elf"
    kernel_image = build / "distro/kernel.bin"
    tree = build / "rootfs"
    for path in (probe, kernel_image, args.qemu, tree / "bin/oksh"):
        if not path.is_file():
            raise FileNotFoundError(path)
    inspect_elf(probe, args.arch)
    if probe.read_bytes()[7] != 0:
        raise ValueError("the probe lacks the native ELF personality")

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = out / "root"
    shutil.copytree(tree, root, symlinks=True)
    shutil.copy2(probe, root / "bin/oksh-jobs")
    (root / "bin/oksh-jobs").chmod(0o755)
    disk = out / "rootfs.ext4.img"
    with (out / "package.log").open("xb") as log:
        subprocess.run([sys.executable, "-B", str(TOOLS / "mkext4.py"), "--root", str(root), "--out", str(disk)],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    kernel = out / "kernel-input.bin"
    shutil.copy2(kernel_image, kernel)
    # native_profile selects the single-CPU e500v2 profile that native PPC ELF
    # admission requires; other profiles ignore it.
    command = command_for(args.qemu.resolve(), args.arch, kernel, disk, "none", native_profile=True)
    record = {"schema": 1, "scope": "oksh-job-control-maintenance-console-qemu-guest", "architecture": args.arch,
              "mode": args.mode, "physical": False, "status": "running", "command": command,
              "probe_sha256": sha(probe), "probe_source_sha256": sha(ROOT / "tests/native/oksh_job_probe.c"),
              "oksh_sha256": sha(tree / "bin/oksh"), "kernel_sha256": sha(kernel),
              "qemu_sha256": sha(args.qemu.resolve()), "input_disk_sha256": sha(disk),
              "script_sha256": sha(Path(__file__))}
    guest = Guest(command, args.timeout)
    try:
        guest.boot()
        if b"OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw" not in guest.serial:
            raise RuntimeError("guest did not mount the prepared ext4 root")
        record.update(exercise(guest))
        record["status"] = "pass"
    except BaseException as error:
        record.update(status="fail", failure=repr(error))
        raise
    finally:
        guest.close()
        (out / "serial.log").write_bytes(guest.serial)
        record["serial_sha256"] = sha(out / "serial.log")
        (out / "result.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"PASS {args.arch}/{args.mode}: oksh job control at the maintenance console "
          f"(job groups: {record['job_process_group']})")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Execute the musl userland's sh acceptance and its own test suite in QEMU.

The image is the full-profile ext4 root staged with an admitted userland build
(`xmake f --userland_build=... && xmake -b rootfs-ext4`). The console shell
starts `/bin/sh` (BusyBox ash, decision 0004) on the acceptance script, then,
with --suite, BusyBox's own `testsuite/runtest` for the selected applets. The
result is a receipt in a new --out directory; it is evidence only for the exact
kernel, image and QEMU bytes it records.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import select
import shutil
import subprocess
import sys
import time
from pathlib import Path

from qemu_distro import command_for

PROMPT = b"oksh> "
SUITE_LINE = re.compile(rb"^(PASS|FAIL|SKIPPED|UNTESTED): ?(.*?)\r?$", re.M)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def suite_results(serial: bytes) -> dict[str, str]:
    """Map test name to its last reported outcome."""
    results = {}
    for outcome, name in SUITE_LINE.findall(serial):
        results[name.decode(errors="replace").strip()] = outcome.decode()
    return results


def suite_plan(path: Path) -> tuple[list[str], dict[str, str]]:
    """One `applets A B ...` line, then `test name<TAB>cause` reviewed failures."""
    applets, entries = None, {}
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("applets "):
            if applets is not None:
                raise ValueError("suite plan names its applets twice")
            applets = line.split()[1:]
            continue
        name, _, reason = line.partition("\t")
        if not name or not reason.strip() or name in entries:
            raise ValueError(f"reviewed failure needs one name and a cause: {line!r}")
        entries[name] = reason.strip()
    if not applets:
        raise ValueError("suite plan names no applets")
    return applets, entries


def judge_suite(results: dict[str, str], expected: dict[str, str]) -> dict:
    failed = sorted(name for name, outcome in results.items() if outcome == "FAIL")
    unexpected = sorted(set(failed) - set(expected))
    fixed = sorted(name for name in expected if results.get(name) == "PASS")
    return {"total": len(results), "passed": sum(outcome == "PASS" for outcome in results.values()),
            "failed": failed, "unexpected_failures": unexpected, "expected_failures_now_passing": fixed,
            "skipped": sorted(name for name, outcome in results.items() if outcome in ("SKIPPED", "UNTESTED")),
            "status": "pass" if results and not unexpected and not fixed else "fail"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arch", required=True)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--rootfs", type=Path, required=True, help="Full-profile ext4 image with the musl userland")
    parser.add_argument("--out", type=Path, required=True, help="New receipt directory")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--suite-plan", type=Path,
                        help="Run BusyBox testsuite/runtest for the plan's applets against its reviewed failures")
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    applets, expected = suite_plan(args.suite_plan) if args.suite_plan else (None, {})
    kernel, disk = output / "kernel-input.bin", output / "rootfs.ext4.img"
    shutil.copyfile(args.kernel, kernel)
    shutil.copyfile(args.rootfs, disk)
    # An image staged without the userland has the okcrt programs in /bin and no sh.
    inode = subprocess.run(["debugfs", "-R", "stat /bin/sh", str(disk)], capture_output=True, text=True)
    if "Type: symlink" not in inode.stdout:
        raise SystemExit("rootfs has no /bin/sh link: stage it with --userland_build")
    record = {"scope": "qemu-guest-execution", "architecture": args.arch, "status": "running",
              "inputs": {"kernel": digest(kernel), "rootfs": digest(disk), "qemu": digest(args.qemu.resolve()),
                         "acceptance_script": digest(Path(__file__).resolve().parents[1] / "tests/userland/sh-acceptance.sh"),
                         "runner": digest(Path(__file__).resolve())}}
    if args.suite_plan:
        record["inputs"]["suite_plan"] = digest(args.suite_plan)
    command = command_for(args.qemu.resolve(), args.arch, kernel, disk, "none", native_profile=args.arch == "ppc")
    record["command"] = command
    serial = bytearray()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert process.stdin is not None and process.stdout is not None

    def receive(predicate, budget):
        deadline = time.monotonic() + budget
        while not predicate():
            if time.monotonic() >= deadline:
                raise RuntimeError("timeout waiting for the guest")
            readable, _, _ = select.select([process.stdout], [], [], .1)
            if readable:
                chunk = os.read(process.stdout.fileno(), 8192)
                if not chunk:
                    raise RuntimeError("QEMU exited")
                serial.extend(chunk)

    def run(line: bytes, budget: float) -> bytes:
        start = len(serial)
        process.stdin.write(line + b"\n")
        process.stdin.flush()
        receive(lambda: PROMPT in serial[start + len(line):], budget)
        return bytes(serial[start:])

    try:
        receive(lambda: b"OK_SYSTEM_GUI boot=complete" in serial and PROMPT in serial, args.timeout)
        if b"OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw" not in serial:
            raise RuntimeError("root was not mounted read-write from ext4")
        # Linux stat, and with it PATH search, needs maintained root timestamps.
        policy = re.search(rb"OK_ROOT_TIMESTAMPS policy=(\S+)", serial)
        record["root_timestamps"] = policy.group(1).decode() if policy else None
        record["root_clock"] = "provisional" if b"OK_STORAGE_CLOCK source=ext4-last-write" in serial else "realtime"
        if record["root_timestamps"] != "maintained":
            raise RuntimeError("root timestamps are not maintained: build distro_image with --userland_build")
        shell = run(b"sh /usr/share/userland-tests/sh-acceptance.sh", args.timeout)
        record["sh_checks"] = sorted({name.decode() for name in re.findall(rb"OK_MUSL_SH_CHECK (\S+)=pass", shell)})
        if b"OK_MUSL_SH scope=hardware" not in shell:
            raise RuntimeError("sh acceptance failed: " + shell.decode(errors="replace")[-800:])
        record["sh_acceptance"] = "pass"
        # The native console shell must still run native programs afterwards.
        if b"hello from ObfuscationOS userland" not in run(b"hello | cat", 30):
            raise RuntimeError("native personality regression after musl execution")
        if applets:
            # The console shell has no quoting; the wrapper script enters the suite directory.
            suite = run(" ".join(["sh", "/usr/share/userland-tests/busybox-suite.sh", *applets]).encode(),
                        args.timeout * 20)
            record["suite"] = judge_suite(suite_results(suite), expected)
            record["suite"]["applets"] = applets
            if record["suite"]["status"] != "pass":
                raise RuntimeError("BusyBox testsuite: unexpected failures " + ", ".join(record["suite"]["unexpected_failures"]) +
                                   "; listed failures now passing " + ", ".join(record["suite"]["expected_failures_now_passing"]))
        record["status"] = "pass"
    except (RuntimeError, OSError) as error:
        record["status"] = "fail"
        record["failure"] = str(error)
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        (output / "serial.log").write_bytes(serial)
        record["serial_sha256"] = digest(output / "serial.log")
        (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"[musl-shell] {args.arch}: {record['status']} ({output})")
    return 0 if record["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Run the native TTY/session/job-control probe (tests/native/native_tty_sessions.c) in QEMU.

The probe opens its own /dev/ptmx pairs, so it runs from the maintenance
`oksh> ` prompt of an ordinary ext4 image; no login or journalled disk is
needed. The runner builds the probe, the root tree and the distribution
kernel for the configured profile, stages the probe as /bin/tty-sessions in a
copy of the root tree, packs it with tools/mkext4.py and boots it. Each run
must print one line per case and the exact PASS marker. This is guest
execution in QEMU, not physical hardware.
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
CASES = 20  # entries of cases[] in tests/native/native_tty_sessions.c
FAILURES = (b"KERNEL PANIC", b"ASSERTION FAILED", b"OK_SYSTEM_GUI boot=failed", b"OK_TEST_FAIL")
# init prints this only when it runs startup acceptance before the shell.
STARTUP_ACCEPTANCE = b"OK_USERLAND scope=hardware"
ACCEPTANCE_OPTIONS = ("native_init_acceptance", "native_vm_acceptance", "native_udp_probe")
RESULT = re.compile(rb"TTY_SESSIONS_PROBE stage=(PASS|FAIL)[^\r\n]*")
CASE_LINE = re.compile(rb"TTY_SESSIONS_CASE n=(\d+) name=([a-z_]+) result=pass")
ARCH_ALIASES = {"x64": "x86_64", "amd64": "x86_64", "arm64": "aarch64", "riscv64": "rv64",
                "loong64": "loongarch64", "loongarch": "loongarch64"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configured_profile(xmake: str) -> tuple[str, str, Path]:
    """Reads the arch, mode and configuration directory the project is configured for."""
    shown = subprocess.run([xmake, "show", "-P", str(ROOT)], check=True, capture_output=True, text=True, cwd=ROOT).stdout
    shown = re.sub(r"\x1b\[[0-9;]*m", "", shown)
    fields = dict(re.findall(r"^\s*(arch|mode|configdir): (\S+)\s*$", shown.split("information of project", 1)[-1],
                             re.M))
    if not {"arch", "mode", "configdir"} <= fields.keys():
        raise RuntimeError("xmake show did not report the configured arch, mode and configuration directory")
    return ARCH_ALIASES.get(fields["arch"], fields["arch"]), fields["mode"], Path(fields["configdir"])


def enabled_options(config: str) -> set[str]:
    """Names of the options a saved xmake.conf holds with a value other than false."""
    return {name for name, value in re.findall(r"^\s*([A-Za-z0-9_]+) = (.+?),?\s*$", config, re.M)
            if value != "false"}


def refuse_configuration(enabled: set[str]) -> None:
    """The probe is typed at the maintenance shell, so nothing may run before it."""
    if "native_console_login" in enabled:
        raise ValueError("native_console_login makes /bin/login the console service; the probe needs the "
                         "maintenance oksh console (reconfigure with --native_console_login=n)")
    acceptance = sorted(enabled.intersection(ACCEPTANCE_OPTIONS))
    if acceptance:
        raise ValueError("native startup acceptance runs before the maintenance shell; reconfigure without "
                         + ", ".join(acceptance) + " (xmake tty-sessions-test does this)")


def maintenance_console(services: str) -> bool:
    """Whether a staged services.conf runs the maintenance oksh as the console service."""
    consoles = [line.split() for line in services.splitlines() if line.split()[:2] == ["service", "console"]]
    return len(consoles) == 1 and consoles[0][3:4] == ["/bin/oksh"]


def receive(process: subprocess.Popen, serial: bytearray, done, deadline: float) -> None:
    while not done():
        if time.monotonic() > deadline:
            raise RuntimeError("timeout waiting for the guest")
        ready, _, _ = select.select([process.stdout], [], [], .1)
        if not ready:
            continue
        chunk = os.read(process.stdout.fileno(), 8192)
        if not chunk:
            raise RuntimeError("QEMU exited before the probe completed")
        serial.extend(chunk)
        if any(failure in serial for failure in FAILURES):
            raise RuntimeError("guest reported a kernel or boot failure")
        if STARTUP_ACCEPTANCE in serial:
            raise RuntimeError("guest ran native startup acceptance before the maintenance shell")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", required=True, choices=ARCH_TRIPLES)
    parser.add_argument("--mode", default="debug", choices=("debug", "release"))
    parser.add_argument("--qemu", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="new output directory")
    parser.add_argument("--xmake", default="xmake")
    parser.add_argument("--no-build", action="store_true", help="use the existing build outputs")
    parser.add_argument("--runs", type=int, default=2, help="probe runs in one boot")
    parser.add_argument("--timeout", type=float, default=300, help="seconds for the boot and for each run")
    args = parser.parse_args()
    if args.runs < 1:
        raise ValueError("--runs must be at least 1")
    arch, mode, configdir = configured_profile(args.xmake)
    if (arch, mode) != (args.arch, args.mode):
        raise ValueError(f"the project is not configured for {args.arch}/{args.mode}")
    refuse_configuration(enabled_options((configdir / "xmake.conf").read_text(encoding="utf-8")))
    if not args.no_build:
        for target in ("app-tty-sessions-probe", "rootfs-stage", "distro_image"):
            subprocess.run([args.xmake, "-P", str(ROOT), "-y", "-b", target], check=True, cwd=ROOT)
    build = ROOT / "build" / args.arch / args.mode
    probe = build / "apps/tty-sessions.elf"
    kernel_image = build / "distro/kernel.bin"
    tree = build / "rootfs"
    for path in (probe, kernel_image, args.qemu):
        if not path.is_file():
            raise FileNotFoundError(path)
    if not (tree / "bin/oksh").is_file():
        raise FileNotFoundError(tree / "bin/oksh")
    if not maintenance_console((tree / "etc/services.conf").read_text(encoding="utf-8")):
        raise ValueError(f"{tree / 'etc/services.conf'} does not run /bin/oksh as the console service")
    inspect_elf(probe, args.arch)
    if probe.read_bytes()[7] != 0:
        raise ValueError("the probe lacks the native ELF personality")

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = out / "root"
    shutil.copytree(tree, root, symlinks=True)
    shutil.copy2(probe, root / "bin/tty-sessions")
    (root / "bin/tty-sessions").chmod(0o755)
    disk = out / "rootfs.ext4.img"
    with (out / "package.log").open("xb") as log:
        subprocess.run([sys.executable, "-B", str(TOOLS / "mkext4.py"), "--root", str(root), "--out", str(disk)],
                       check=True, stdout=log, stderr=subprocess.STDOUT)
    kernel = out / "kernel-input.bin"
    shutil.copy2(kernel_image, kernel)
    # native_profile selects the measured single-CPU e500v2 profile that
    # native PPC ELF admission requires; other profiles ignore it.
    command = command_for(args.qemu.resolve(), args.arch, kernel, disk, "none", native_profile=True)
    record = {"schema": 1, "scope": "native-tty-sessions-qemu-guest", "architecture": args.arch, "mode": args.mode,
              "physical": False, "status": "running", "runs": [], "command": command,
              "probe_sha256": sha(probe), "probe_source_sha256": sha(ROOT / "tests/native/native_tty_sessions.c"),
              "kernel_sha256": sha(kernel), "qemu_sha256": sha(args.qemu.resolve()),
              "input_disk_sha256": sha(disk), "script_sha256": sha(Path(__file__))}
    serial = bytearray()
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        receive(process, serial, lambda: b"OK_SYSTEM_GUI boot=complete" in serial and PROMPT in serial,
                time.monotonic() + args.timeout)
        if b"OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw" not in serial:
            raise RuntimeError("guest did not mount the prepared ext4 root")
        expected = f"TTY_SESSIONS_PROBE stage=PASS cases={CASES} arch={args.arch}".encode()
        for _ in range(args.runs):
            start = len(serial)
            process.stdin.write(b"/bin/tty-sessions\n")
            process.stdin.flush()
            began = time.monotonic()

            def finished() -> bool:
                match = RESULT.search(serial, start)
                return match is not None and PROMPT in serial[match.end():]
            receive(process, serial, finished, time.monotonic() + args.timeout)
            run = bytes(serial[start:])
            result = RESULT.search(run).group(0).decode(errors="replace")
            record["runs"].append({"result": result, "seconds": round(time.monotonic() - began, 2)})
            print(result, flush=True)
            numbers = [int(match.group(1)) for match in CASE_LINE.finditer(run)]
            if run.count(expected) != 1 or result != expected.decode() or numbers != list(range(1, CASES + 1)):
                raise RuntimeError("TTY sessions probe failed: " + result)
        record["status"] = "pass"
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
        record["serial_sha256"] = sha(out / "serial.log")
        (out / "result.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"PASS {args.arch}/{args.mode}: {args.runs} TTY sessions probe runs, {CASES} cases each")


if __name__ == "__main__":
    main()

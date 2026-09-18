#!/usr/bin/env python3
"""Exercise real serial-shell commands and system apps in a debug or release image."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import time

from qemu_distro import command_for


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", required=True, choices=("x86_64", "aarch64", "rv64", "loongarch64"))
    parser.add_argument("--qemu", required=True, type=Path)
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--rootfs", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=40)
    args = parser.parse_args()
    serial = bytearray()
    with tempfile.TemporaryDirectory(prefix="ok-interactive-") as directory:
        disk = Path(directory) / "rootfs.img"
        shutil.copy2(args.rootfs, disk)
        process = subprocess.Popen(command_for(args.qemu.resolve(), args.arch, args.kernel.resolve(), disk, "none"),
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        assert process.stdout is not None and process.stdin is not None

        def receive_until(predicate):
            deadline = time.monotonic() + args.timeout
            while not predicate():
                if time.monotonic() >= deadline:
                    raise RuntimeError("timeout waiting for native shell response")
                readable, _, _ = select.select([process.stdout], [], [], 0.1)
                if not readable:
                    continue
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    raise RuntimeError("QEMU exited before native shell response")
                serial.extend(chunk)

        try:
            receive_until(lambda: b"OK_SYSTEM_GUI boot=complete" in serial and b"oksh> " in serial)
            for command, expected in (
                ("hello | cat", b"hello from ObfuscationOS userland"),
                ("echo OK_SERIAL_PIPE | cat", b"OK_SERIAL_PIPE"),
                ("notes /tmp/native-smoke.txt native-note-content", b"Saved /tmp/native-smoke.txt"),
                ("notes /tmp/native-smoke.txt", b"native-note-content"),
                ("tasks", b"System activity"),
                ("settings", b"Working directory:"),
                ("about", b"NAME=ObfuscationOS"),
            ):
                start = len(serial)
                process.stdin.write((command + "\n").encode())
                process.stdin.flush()
                receive_until(lambda: b"oksh> " in serial[start:])
                if expected not in serial[start:]:
                    raise RuntimeError(f"unexpected response to {command!r}: {serial[start:].decode(errors='replace')}")
                print(f"PASS scope=hardware serial command={command}", flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            args.log.parent.mkdir(parents=True, exist_ok=True)
            args.log.write_bytes(serial)
            process.stdin.close()
            process.stdout.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

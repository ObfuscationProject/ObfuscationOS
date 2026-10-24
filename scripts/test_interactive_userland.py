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
    parser.add_argument("--arch", required=True, choices=("i386", "x86_64", "aarch64", "arm32", "rv64", "rv32", "loongarch64", "mips", "mips64", "ppc"))
    parser.add_argument("--qemu", required=True, type=Path)
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--rootfs", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=40)
    parser.add_argument("--posix-check", action="store_true", help="Also execute native POSIX/path/VM acceptance from the shell")
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
                if b"POSIX_CHECK failed:" in serial or b"OK_TEST_FAIL " in serial:
                    raise RuntimeError("guest acceptance failed")

        try:
            receive_until(lambda: b"OK_SYSTEM_GUI boot=complete" in serial and b"oksh> " in serial)
            if args.posix_check:
                start = len(serial)
                process.stdin.write(b"posix-check\n")
                process.stdin.flush()
                receive_until(lambda: b"oksh> " in serial[start:])
                markers = [b"OK_POSIX scope=hardware fork=pass", b"OK_PATH scope=hardware relative_exec=pass symlink=pass",
                               b"OK_TIME_NATIVE scope=hardware monotonic=pass sleep=pass absolute=pass sibling=pass validation=pass",
                               b"OK_POLL_NATIVE scope=hardware nonblock=pass readiness=pass timeout=pass wake=pass peer_close=pass",
                               b"OK_VM_NATIVE scope=hardware map=pass zero=pass protect=pass unmap=pass fork=pass pressure=pass",
                               b"OK_VM_SHARED scope=hardware fork=pass private_isolation=pass protect=pass none=pass partial_unmap=pass fixed=pass exec_exit=pass pressure=pass cleanup=pass"]
                if b"OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw" in serial:
                    markers.append(b"OK_VM_FILE_PRIVATE scope=hardware ext4=pass offset=pass short_length=pass tail_zero=pass errno=pass unlink=pass private_write=pass fork=pass")
                for marker in markers:
                    if marker not in serial[start:]:
                        raise RuntimeError(f"missing acceptance marker: {marker!r}")
                print("PASS scope=hardware serial command=posix-check", flush=True)
            for command, expected in (
                ("hello | cat", b"hello from ObfuscationOS userland"),
                ("echo OK_SERIAL_PIPE | cat", b"OK_SERIAL_PIPE"),
                ("mkdir /home/native-notes", b""),
                ("notes /home/native-notes/native-smoke.txt native-note-content", b"Saved /home/native-notes/native-smoke.txt"),
                ("notes /home/native-notes/native-smoke.txt", b"native-note-content"),
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

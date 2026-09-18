#!/usr/bin/env python3
"""Capture the real QEMU desktop and check GUI/serial keyboard separation."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from qemu_distro import command_for
from render_workspace import png


class QmpConnection:
    """Read complete QMP messages with one deadline per greeting or command."""

    def __init__(self, reader, writer, timeout: float = 5.0):
        self.reader = reader
        self.writer = writer
        self.timeout = timeout
        self.pending = bytearray()

    def receive(self, deadline: float) -> dict:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("QMP response timed out")
            if b"\n" in self.pending:
                line, remainder = self.pending.split(b"\n", 1)
                self.pending = bytearray(remainder)
                response = json.loads(line)
                if not isinstance(response, dict):
                    raise RuntimeError("QMP response is not a JSON object")
                return response
            readable, _, _ = select.select([self.reader], [], [], remaining)
            if not readable:
                raise TimeoutError("QMP response timed out")
            chunk = os.read(self.reader.fileno(), 4096)
            if not chunk:
                raise RuntimeError("QMP connection closed before a complete response")
            self.pending.extend(chunk)
            if len(self.pending) > 1024 * 1024:
                raise RuntimeError("QMP response exceeds the message size limit")

    def greeting(self) -> None:
        if "QMP" not in self.receive(time.monotonic() + self.timeout):
            raise RuntimeError("QMP greeting was missing")

    def execute(self, name: str, arguments=None) -> dict:
        request = {"execute": name}
        if arguments:
            request["arguments"] = arguments
        deadline = time.monotonic() + self.timeout
        self.writer.write(json.dumps(request).encode() + b"\n")
        self.writer.flush()
        while True:
            response = self.receive(deadline)
            if "return" in response:
                return response
            if "error" in response:
                raise RuntimeError(response)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", required=True, choices=("x86_64", "aarch64", "rv64", "loongarch64"))
    parser.add_argument("--kernel", required=True, type=Path)
    parser.add_argument("--rootfs", required=True, type=Path)
    parser.add_argument("--qemu", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ok-gui-qmp-") as directory:
        serial = Path(directory) / "serial"
        command = command_for(args.qemu.resolve(), args.arch, args.kernel.resolve(), args.rootfs.resolve(), "none")
        command[command.index("-serial") + 1] = "file:" + str(serial)
        command += ["-qmp", "stdio"]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert process.stdin is not None and process.stdout is not None and process.stderr is not None
        try:
            deadline = time.monotonic() + 30
            while True:
                transcript = serial.read_bytes() if serial.exists() else b""
                if b"OK_SYSTEM_GUI boot=complete" in transcript and b"oksh> " in transcript:
                    break
                if process.poll() is not None:
                    raise RuntimeError(process.stderr.read().decode(errors="replace"))
                if time.monotonic() > deadline:
                    raise RuntimeError("desktop/native shell startup timed out")
                time.sleep(0.02)
            qmp = QmpConnection(process.stdout, process.stdin)
            qmp.greeting()
            execute = qmp.execute

            def capture(name: str):
                target = output / (name + ".ppm")
                execute("screendump", {"filename": str(target)})
                magic, dimensions, maximum, pixels = target.read_bytes().split(b"\n", 3)
                width, height = map(int, dimensions.split())
                if magic != b"P6" or maximum != b"255" or len(pixels) != width * height * 3:
                    raise ValueError("unexpected QEMU framebuffer format")
                png(target.with_suffix(".png"), width, height, pixels)

            execute("qmp_capabilities")
            capture("login")
            # Before input separation, these GUI key events also executed
            # 'hello' in the background root shell. The greeter ignores letters.
            offset = serial.stat().st_size
            for key in ("h", "e", "l", "l", "o", "ret"):
                execute("human-monitor-command", {"command-line": "sendkey " + key + " 10"})
                time.sleep(0.03)
            time.sleep(0.5)
            capture("desktop")
            transcript = serial.read_bytes()
            if b"hello from ObfuscationOS userland" in transcript[offset:]:
                raise RuntimeError("GUI keyboard leaked into native serial shell")
            print("PASS scope=hardware GUI keyboard is separate from native serial input")
        finally:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            (output / "serial.log").write_bytes(serial.read_bytes() if serial.exists() else b"")
            process.stdin.close()
            process.stdout.close()
            process.stderr.close()


if __name__ == "__main__":
    main()

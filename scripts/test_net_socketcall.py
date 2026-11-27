#!/usr/bin/env python3
"""Run the explicit net_socketcall fixture against the scripted peer.

The fixture (xmake net-socketcall-fixture-image, tools/package_net_socketcall_fixture.py)
is the net_probe distribution with /bin/socketcall-probe in its rescue root: a
freestanding Linux-personality program that drives TCP and UDP through legacy
socketcall(2). After the kernel link probe passes, the harness types the
program's path at the shell; the program connects to the peer's TCP echo
service (192.0.2.100:7) and prints OK_NET_SOCKETCALL. Only the profiles whose
Linux ABI has socketcall apply: i386, MIPS O32 and 32-bit PowerPC. This is
QEMU device execution, not physical hardware.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import select
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))
from net_probe_peer import Peer  # noqa: E402
from qemu_distro import command_for  # noqa: E402
from test_net_probe import network_args  # noqa: E402

PROFILES = ("i386", "mips", "ppc")
PROGRAM = "/bin/socketcall-probe"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=PROFILES, required=True)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True, help="fixtures/net-socketcall/distro/kernel.bin")
    parser.add_argument("--package", type=Path, required=True, help="fixtures/net-socketcall/package")
    parser.add_argument("--rootfs", type=Path, required=True, help="the build's SimpleFS image")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=240.0)
    args = parser.parse_args()
    manifest_path = args.package / "manifest.json"
    for path in (args.qemu, args.kernel, args.rootfs, manifest_path):
        if not path.is_file():
            raise SystemExit(f"missing input: {path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("fixture") != "net-socketcall" or manifest.get("architecture") != args.arch:
        raise SystemExit("the package is not this profile's net-socketcall fixture")
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = {"qemu": digest(args.qemu), "kernel": digest(args.kernel), "rootfs": digest(args.rootfs),
              "package_manifest": digest(manifest_path), "program": manifest["program_sha256"],
              "runner": digest(Path(__file__)), "peer": digest(ROOT / "tools/net_probe_peer.py")}
    peer = Peer(seed=0x534F43)
    serial = bytearray()
    markers: list[str] = []
    verdict, typed = "timeout", False
    host, backend = socket.socketpair()
    with tempfile.TemporaryDirectory(prefix="obfuscationos-socketcall-") as temp:
        rootfs = Path(temp) / args.rootfs.name
        shutil.copy2(args.rootfs, rootfs)
        # The probe runs in native userland, which the PPC kernel admits only
        # on its measured e500v2 single-CPU QEMU profile.
        command = command_for(args.qemu.resolve(), args.arch, args.kernel.resolve(), rootfs, "none",
                              native_profile=args.arch == "ppc")
        command += network_args(args.arch, backend.fileno())
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   pass_fds=(backend.fileno(),))
        backend.close()
        assert process.stdout is not None and process.stdin is not None
        frames, pending = bytearray(), b""
        probe_passed = False
        deadline = time.monotonic() + args.timeout
        try:
            while time.monotonic() < deadline and verdict == "timeout":
                readable, _, _ = select.select([process.stdout, host], [], [], 0.05)
                now = time.monotonic()
                if process.stdout in readable:
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        verdict = "qemu-exited"
                        break
                    serial += chunk
                    pending += chunk
                    while b"\n" in pending:
                        raw, pending = pending.split(b"\n", 1)
                        line = raw.decode(errors="replace").rstrip("\r")
                        at = line.find("OK_NET_")
                        if at >= 0:
                            line = line[at:]
                            markers.append(line)
                            print(line, flush=True)
                            if line.startswith("OK_NET_PROBE "):
                                probe_passed = " result=pass " in line + " "
                                if not probe_passed:
                                    verdict = "probe-failed"
                            if line.startswith("OK_NET_SOCKETCALL "):
                                verdict = "pass" if " result=pass " in line + " " else "fail"
                        if line.startswith("OK_TEST_FAIL ") or "boot=failed" in line:
                            verdict = "boot-failed"
                    # Type the path once the probe passed and the shell prompts.
                    if probe_passed and not typed and b"oksh> " in serial[-4096:]:
                        process.stdin.write(f"{PROGRAM}\n".encode())
                        process.stdin.flush()
                        typed = True
                if host in readable:
                    data = host.recv(65536)
                    if not data:
                        verdict = "netdev-closed"
                        break
                    frames += data
                    while len(frames) >= 4:
                        length = struct.unpack("!I", frames[:4])[0]
                        if len(frames) < 4 + length:
                            break
                        frame = bytes(frames[4:4 + length])
                        del frames[:4 + length]
                        for reply in peer.receive(frame, now):
                            host.sendall(struct.pack("!I", len(reply)) + reply)
                for reply in peer.tick(now):
                    host.sendall(struct.pack("!I", len(reply)) + reply)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            host.close()
    (args.output / "serial.log").write_bytes(bytes(serial))
    result = {"schema": 1, "scope": "qemu-device-execution", "architecture": args.arch, "verdict": verdict,
              "typed": typed, "markers": markers, "peer": peer.stats, "fixture": manifest,
              "command": command, "inputs": inputs, "serial_sha256": digest(args.output / "serial.log")}
    (args.output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"[net-socketcall] arch={args.arch} verdict={verdict}")
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

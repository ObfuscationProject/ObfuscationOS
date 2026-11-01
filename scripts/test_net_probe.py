#!/usr/bin/env python3
"""Run the kernel link probe of a net_probe distribution image against a
scripted Ethernet peer (tools/net_probe_peer.py) on a QEMU socket netdev.

The guest answers and resolves ARP, autoconfigures IPv6 from the peer's
router advertisement, pings the IPv4 gateway and the IPv6 router, and
exchanges bytes with the peer's TCP echo service; the probe's OK_NET_* serial
markers and the peer's frame counts are recorded. This is QEMU device
execution of the kernel network stack, not physical hardware.
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

PROFILES = ("i386", "x86_64", "aarch64", "arm32", "rv64", "rv32", "loongarch64", "mips", "mips64", "ppc")
MMIO = {"aarch64", "arm32", "rv64", "rv32"}
REQUIRED = ("OK_NET_LINK", "OK_NET_ARP", "OK_NET_PING scope=hardware family=4", "OK_NET_IPV6",
            "OK_NET_PING scope=hardware family=6", "OK_NET_TCP", "OK_NET_PROBE")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def network_args(arch: str, fd: int) -> list[str]:
    device = "virtio-net-device" if arch in MMIO else "virtio-net-pci"
    properties = "" if arch in MMIO else ",disable-legacy=on"
    return ["-nic", "none", "-netdev", f"socket,id=net0,fd={fd}",
            "-device", f"{device},netdev=net0,mac=02:11:22:33:44:55{properties}"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=PROFILES, required=True)
    parser.add_argument("--qemu", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--rootfs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tcp-loss", type=int, default=0, help="Percent of guest TCP segments the peer drops")
    parser.add_argument("--timeout", type=float, default=180.0)
    args = parser.parse_args()
    for path in (args.qemu, args.kernel, args.rootfs):
        if not path.is_file():
            raise SystemExit(f"missing input: {path}")
    args.output.mkdir(parents=True, exist_ok=False)
    inputs = {"qemu": digest(args.qemu), "kernel": digest(args.kernel), "rootfs": digest(args.rootfs),
              "runner": digest(Path(__file__)), "peer": digest(ROOT / "tools/net_probe_peer.py")}
    peer = Peer(seed=0x4E4554, tcp_loss_percent=args.tcp_loss)
    serial = bytearray()
    markers: list[str] = []
    verdict = "timeout"
    host, backend = socket.socketpair()
    with tempfile.TemporaryDirectory(prefix="obfuscationos-netprobe-") as temp:
        rootfs = Path(temp) / args.rootfs.name
        shutil.copy2(args.rootfs, rootfs)
        command = command_for(args.qemu.resolve(), args.arch, args.kernel.resolve(), rootfs, "none")
        command += network_args(args.arch, backend.fileno())
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   pass_fds=(backend.fileno(),))
        backend.close()
        assert process.stdout is not None
        frames = bytearray()
        pending = b""
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
                        if line.startswith("OK_NET_"):
                            markers.append(line)
                            print(line, flush=True)
                            if line.startswith("OK_NET_PROBE "):
                                verdict = "pass" if " result=pass " in line + " " else "fail"
                        if line.startswith("OK_TEST_FAIL ") or "boot=failed" in line:
                            verdict = "boot-failed"
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
    missing = [prefix for prefix in REQUIRED if not any(line.startswith(prefix) for line in markers)]
    if verdict == "pass" and missing:
        verdict = "incomplete"
    tcp = peer.tcp
    result = {"schema": 1, "scope": "qemu-device-execution", "architecture": args.arch, "verdict": verdict,
              "missing_markers": missing, "markers": markers, "peer": peer.stats,
              "tcp": {"received": tcp.received, "echoed_acked": tcp.echoed_acked, "retransmissions": tcp.retransmissions,
                      "duplicate_acks_sent": tcp.duplicate_acks_sent, "state": tcp.state},
              "tcp_loss_percent": args.tcp_loss, "command": command, "inputs": inputs,
              "serial_sha256": digest(args.output / "serial.log")}
    (args.output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"[net-probe] arch={args.arch} verdict={verdict} peer={json.dumps(peer.stats, sort_keys=True)}")
    return 0 if verdict == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

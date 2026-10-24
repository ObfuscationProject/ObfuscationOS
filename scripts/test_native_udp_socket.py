#!/usr/bin/env python3
"""Qualify an SDK33 native user UDP socket against an external QEMU Ethernet peer."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from kernel_sdk import validate_sdk  # noqa: E402
import static_udp_peer as peer_protocol  # noqa: E402
from native_udp_observer import observe, expected_markers  # noqa: E402

PROFILES = ("i386", "x86_64", "aarch64", "arm32", "rv64", "rv32", "loongarch64", "mips", "mips64", "ppc")
MMIO = {"aarch64", "arm32", "rv64", "rv32"}
QEMU = dict(zip(PROFILES, ("qemu-system-i386", "qemu-system-x86_64", "qemu-system-aarch64",
                           "qemu-system-arm", "qemu-system-riscv64", "qemu-system-riscv32",
                           "qemu-system-loongarch64", "qemu-system-mips", "qemu-system-mips64",
                           "qemu-system-ppc")))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_exact(stream: socket.socket, length: int) -> bytes:
    data = bytearray()
    while len(data) < length:
        part = stream.recv(length - len(data))
        if not part:
            raise RuntimeError("external Ethernet peer closed")
        data += part
    return bytes(data)


def receive_frame(stream: socket.socket, capture: bytearray) -> bytes:
    length = struct.unpack("!I", read_exact(stream, 4))[0]
    if not 14 <= length <= 1514:
        raise RuntimeError(f"invalid QEMU Ethernet frame length {length}")
    frame = read_exact(stream, length)
    capture.extend(struct.pack("!I", length) + frame)
    return frame


def send_frame(stream: socket.socket, frame: bytes, capture: bytearray) -> None:
    if not 14 <= len(frame) <= 1514:
        raise RuntimeError("invalid host Ethernet frame length")
    record = struct.pack("!I", len(frame)) + frame
    stream.sendall(record)
    capture.extend(record)


def wait_line(serial: Path, process: subprocess.Popen, expected: str,
              arch: str, mode: str, timeout: float = 25) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        data = serial.read_bytes() if serial.exists() else b""
        try:
            observed = observe(data, arch=arch, mode=mode)
        except ValueError as error:
            raise RuntimeError("guest rejected native UDP acceptance: " + str(error)) from error
        if expected.encode() in observed:
            return
        if process.poll() is not None:
            raise RuntimeError("QEMU exited before native UDP marker: " + expected + "\n" +
                               data[-4000:].decode("ascii", errors="replace"))
        time.sleep(0.01)
    raise RuntimeError("native UDP marker timed out: " + expected + "\n" +
                       data[-4000:].decode("ascii", errors="replace"))


def qemu_argv(arch: str, image: Path, backend: socket.socket, qemu: Path) -> list[str]:
    if arch in ("i386", "x86_64"):
        argv = [str(qemu), "-m", "128M", "-drive",
                f"file={image},format=raw,if=ide,snapshot=on", "-boot", "c"]
        if arch == "i386":
            argv += ["-cpu", "max"]
    elif arch in ("mips", "mips64", "ppc"):
        argv = [str(qemu), "-M", "ppce500" if arch == "ppc" else "malta",
                "-m", "256M", "-kernel", str(image)]
        if arch == "mips64":
            argv += ["-cpu", "MIPS64R2-generic"]
        if arch == "ppc":
            argv += ["-cpu", "e500v2_v22", "-smp", "1", "-accel", "tcg,thread=single"]
    else:
        argv = [str(qemu), "-M", "virt", "-m", "2G" if arch == "loongarch64" else "256M",
                "-kernel", str(image)]
        if arch in ("aarch64", "arm32"):
            argv += ["-cpu", "cortex-a57" if arch == "aarch64" else "cortex-a15"]
        if arch in ("rv64", "rv32"):
            argv += ["-bios", "none"]
    argv += ["-display", "none", "-serial", "stdio", "-monitor", "none", "-no-reboot", "-nic", "none"]
    if arch in MMIO:
        argv += ["-global", "virtio-mmio.force-legacy=false"]
    device = "virtio-net-device" if arch in MMIO else "virtio-net-pci"
    properties = "" if arch in MMIO else ",disable-legacy=on"
    argv += ["-netdev", f"socket,id=net0,fd={backend.fileno()}", "-device",
             f"{device},netdev=net0,mac=02:11:22:33:44:55{properties}"]
    return argv


def packet(port: int, data: bytes, identifier: int) -> bytes:
    return peer_protocol.datagram(peer_protocol.PEER_MAC, peer_protocol.LOCAL_MAC,
                                  peer_protocol.PEER_IP, peer_protocol.LOCAL_IP,
                                  12345, port, identifier, data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=PROFILES, required=True)
    parser.add_argument("--mode", choices=("debug", "release"), required=True)
    parser.add_argument("--kernel-sdk", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--qemu", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    qemu = args.qemu or Path("/usr/bin") / QEMU[args.arch]
    manifest = validate_sdk(args.kernel_sdk, args.arch, args.mode)
    if not args.image.is_file() or not qemu.is_file():
        raise RuntimeError("native UDP image or QEMU executable is missing")
    before = {"sdk_manifest": digest(args.kernel_sdk / "manifest.json"),
              "image": digest(args.image), "qemu": digest(qemu),
              "harness": digest(Path(__file__)),
              "observer": digest(ROOT / "tools" / "native_udp_observer.py")}
    args.output.mkdir(parents=True, exist_ok=False)
    serial = args.output / "serial.log"
    peer_rx, peer_tx = bytearray(), bytearray()
    host, backend = socket.socketpair()
    host.settimeout(25)
    command = qemu_argv(args.arch, args.image, backend, qemu)
    profile = f"OK_NATIVE_UDP profile={args.mode} arch={args.arch}"
    try:
        with serial.open("wb") as output:
            process = subprocess.Popen(command, stdout=output,
                                       stderr=subprocess.STDOUT, pass_fds=(backend.fileno(),),
                                       env=dict(os.environ, TMPDIR=str(args.output)))
            backend.close()
            try:
                wait_line(serial, process, profile, args.arch, args.mode)
                wait_line(serial, process, "OK_NATIVE_UDP parent=ready port=54321", args.arch, args.mode)
                wait_line(serial, process, "OK_NATIVE_UDP child=ready port=54320", args.arch, args.mode)
                frame = receive_frame(host, peer_rx)
                expected = peer_protocol.datagram(peer_protocol.LOCAL_MAC, peer_protocol.PEER_MAC,
                    peer_protocol.LOCAL_IP, peer_protocol.PEER_IP, 54321, 12345, 0x9000, b"HELLO")
                if frame != expected:
                    raise RuntimeError("user sendto frame differs from exact Ethernet/IP/UDP oracle")
                send_frame(host, packet(54321, b"RESPONSE", 0x1000), peer_tx)
                send_frame(host, packet(54320, b"C", 0x1001), peer_tx)
                wait_line(serial, process, "OK_NATIVE_UDP parent=trunc-ready", args.arch, args.mode)
                send_frame(host, packet(54321, b"ABCDEF", 0x1002), peer_tx)
                wait_line(serial, process, "OK_NATIVE_UDP parent=zero-ready", args.arch, args.mode)
                send_frame(host, packet(54321, b"Z", 0x1003), peer_tx)
                wait_line(serial, process, "OK_NATIVE_UDP parent=fault-ready", args.arch, args.mode)
                send_frame(host, packet(54321, b"Q", 0x1004), peer_tx)
                wait_line(serial, process, "OK_NATIVE_UDP parent=dup-ready", args.arch, args.mode)
                send_frame(host, packet(54321, b"D", 0x1005), peer_tx)
                wait_line(serial, process, "OK_NATIVE_UDP parent=reuse-ready", args.arch, args.mode)
                send_frame(host, packet(54321, b"R", 0x1006), peer_tx)
                wait_line(serial, process,
                          "OK_NATIVE_UDP scope=hardware acceptance=pass processes=2 ports=2",
                          args.arch, args.mode)
                wait_line(serial, process,
                          "OK_USERLAND scope=hardware acceptance=pass shell_pipeline=pass",
                          args.arch, args.mode)
                observed = observe(serial.read_bytes(), arch=args.arch, mode=args.mode, final=True)
                if observed != expected_markers(args.arch, args.mode):
                    raise RuntimeError("native UDP guest marker set is incomplete")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
    finally:
        host.close()
        backend.close()
    (args.output / "peer-rx.bin").write_bytes(peer_rx)
    (args.output / "peer-tx.bin").write_bytes(peer_tx)
    after = {"sdk_manifest": digest(args.kernel_sdk / "manifest.json"),
             "image": digest(args.image), "qemu": digest(qemu),
             "harness": digest(Path(__file__)),
             "observer": digest(ROOT / "tools" / "native_udp_observer.py")}
    if before != after:
        raise RuntimeError("native UDP execution inputs changed during QEMU run")
    receipt = {"schema": 2, "status": "passed-native-user-udp", "architecture": args.arch,
               "mode": args.mode, "guest_profile": profile,
               "transport": "mmio" if args.arch in MMIO else "pci",
               "sdk_abi": manifest["abi_version"], "sdk_manifest_sha256": before["sdk_manifest"],
               "image_sha256": before["image"], "serial_sha256": digest(serial),
               "peer_rx_sha256": digest(args.output / "peer-rx.bin"),
               "peer_tx_sha256": digest(args.output / "peer-tx.bin"),
               "processes": 2, "ports": [54320, 54321], "hardware_execution": True,
               "qemu_argv": command, "qemu_sha256": before["qemu"],
               "harness_sha256": before["harness"], "observer_sha256": before["observer"],
               "input_sha256_before": before, "input_sha256_after": after,
               "physical_acceptance": False, "irq_acceptance": False, "linux_socket_acceptance": False}
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("NATIVE_USER_UDP_PASS receipt=" + str(args.output / "receipt.json"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print("NATIVE_USER_UDP_FAIL " + str(exc), file=sys.stderr)
        raise SystemExit(1)

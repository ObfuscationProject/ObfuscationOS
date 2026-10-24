#!/usr/bin/env python3
"""Run the explicit public-libc UDP fixture over actual x86_64 QEMU Virtio PCI."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from kernel_sdk import validate_sdk
from musl_udp_observer import FrameCapture, RECORDS, WireObserver, observe, peer


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_child(child: bytes) -> None:
    if (len(child) < 64 or child[:9] != b"\x7fELF\x02\x01\x01\x03\x00" or
            struct.unpack_from("<HHI", child, 16) != (2, 62, 1)):
        raise ValueError("packaged child is not an explicit x86_64 Linux ELF")
    entry, phoff = struct.unpack_from("<QQ", child, 24)
    ehsize, phsize, count = struct.unpack_from("<HHH", child, 52)
    if ehsize != 64 or phsize != 56 or not 1 <= count <= 128 or phoff < 64 or phoff + count * phsize > len(child):
        raise ValueError("packaged child program-header table is invalid")
    executable = False
    for index in range(count):
        kind, flags, offset, address, _, filesz, memsz, alignment = struct.unpack_from(
            "<IIQQQQQQ", child, phoff + index * phsize)
        if kind in (2, 3):
            raise ValueError("packaged child must be static with no interpreter")
        if kind != 1:
            continue
        if (filesz > memsz or offset + filesz > len(child) or memsz > (1 << 64) - 1 - address or
                (alignment not in (0, 1) and
                 (alignment & (alignment - 1) or address % alignment != offset % alignment))):
            raise ValueError("packaged child load segment is invalid")
        executable |= bool(flags & 1 and address <= entry < address + filesz)
    if not executable:
        raise ValueError("packaged child has no loaded executable entry")


def qemu_argv(image: Path, backend_fd: int, qemu: Path) -> list[str]:
    return [str(qemu), "-m", "128M", "-drive",
            f"file={image},format=raw,if=ide,snapshot=on", "-boot", "c",
            "-display", "none", "-serial", "stdio", "-monitor", "none", "-no-reboot",
            "-nic", "none", "-netdev", f"socket,id=net0,fd={backend_fd}", "-device",
            "virtio-net-pci,netdev=net0,mac=02:11:22:33:44:55,disable-legacy=on",
            "-object", "rng-random,id=entropy0,filename=/dev/urandom",
            "-device", "virtio-rng-pci-non-transitional,rng=entropy0"]


class Coordinator:
    def __init__(self, stream: socket.socket, serial: Path, process: subprocess.Popen,
                 mode: str, timeout: float) -> None:
        self.stream, self.serial, self.process = stream, serial, process
        self.mode, self.timeout = mode, timeout
        self.rx, self.tx = FrameCapture(), bytearray()
        self.wire = WireObserver()
        self.sent: list[dict] = []
        self.identifier = 0x1000

    def records(self, final: bool = False) -> tuple[bytes, ...]:
        data = self.serial.read_bytes() if self.serial.exists() else b""
        return observe(data, arch="x86_64", mode=self.mode, final=final)

    def pump(self, timeout: float = 0.01) -> None:
        self.records()
        if select.select([self.stream], [], [], timeout)[0]:
            data = self.stream.recv(65536)
            if not data:
                raise RuntimeError("QEMU Ethernet transport closed")
            self.rx.feed(data)
        if self.process.poll() is not None:
            raise RuntimeError("QEMU exited before fixture completion")

    def wait(self, expected: bytes) -> None:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if expected in self.records():
                return
            self.pump()
        raise RuntimeError("musl UDP complete record timed out: " + expected.decode())

    def receive(self, event: str) -> int | None:
        deadline = time.monotonic() + self.timeout
        while not self.rx.frames:
            if time.monotonic() >= deadline:
                raise RuntimeError("musl UDP wire event timed out: " + event)
            self.pump()
        return self.wire.accept(self.rx.frames.pop(0), event)

    def send_frame(self, frame: bytes, event: str) -> None:
        record = struct.pack("!I", len(frame)) + frame
        deadline = time.monotonic() + self.timeout
        offset = 0
        while offset < len(record):
            if time.monotonic() >= deadline:
                raise RuntimeError("host Ethernet send timed out")
            self.records()
            if select.select([], [self.stream], [], 0.01)[1]:
                written = self.stream.send(record[offset:])
                if not written:
                    raise RuntimeError("host Ethernet send closed")
                self.tx.extend(record[offset:offset + written])
                offset += written
        self.sent.append({"event": event, "bytes": len(frame)})

    def send(self, port: int, payload: bytes, event: str) -> None:
        frame = peer.datagram(peer.PEER_MAC, peer.LOCAL_MAC, peer.PEER_IP,
                              peer.LOCAL_IP, 12345, port, self.identifier, payload)
        self.identifier += 1
        self.send_frame(frame, event)

    def phase(self, name: str) -> None:
        self.wait(("MUSL_UDP stage=" + name + "-ready" +
                   (" port=54322" if name == "basic" else "")).encode())

    def run(self) -> None:
        self.phase("basic")
        self.send_frame(peer.arp_request(), "arp-request")
        self.receive("arp")
        self.send(54322, b"GO:BASIC", "basic-start")
        self.receive("basic")
        self.send(54322, b"ACK:BASIC", "basic-ack")
        for name, payload in (("peek", b"PEEK-DATA"), ("short", b"SHORT-DATA"),
                              ("zero", b""), ("fault", b"F"), ("peekfault", b"P")):
            self.phase(name)
            self.send(54322, payload, name)
            if name == "zero":
                self.receive("zero")
        for phase, prefix in (("bind-zero", "BIND0"), ("implicit", "AUTO")):
            self.phase(phase)
            for number in (1, 2):
                port = self.receive(phase + "-" + str(number))
                if port is None:
                    raise RuntimeError("ephemeral phase has no UDP source port")
                self.send(port, ("ACK:" + prefix + ":" + str(number)).encode(),
                          phase + "-ack-" + str(number))
        self.wait(RECORDS[-1])
        self.records(final=True)
        self.wire.finish()
        # The interval is explicitly recorded; later traffic is not qualified.
        deadline = time.monotonic() + 0.1
        while time.monotonic() < deadline:
            self.pump(min(0.01, max(0, deadline - time.monotonic())))
        self.rx.finish()
        if self.rx.frames:
            raise RuntimeError("musl UDP guest emitted extra Ethernet frames")
        self.records(final=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=("x86_64",), required=True)
    parser.add_argument("--mode", choices=("debug", "release"), required=True)
    parser.add_argument("--kernel-sdk", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--packaged-child", type=Path, required=True)
    parser.add_argument("--qemu", type=Path, default=Path("/usr/bin/qemu-system-x86_64"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase-timeout", type=float, default=25)
    args = parser.parse_args()
    if not sys.dont_write_bytecode or os.environ.get("PYTHONDONTWRITEBYTECODE") != "1":
        parser.error("use PYTHONDONTWRITEBYTECODE=1 python3 -B")
    if not 1 <= args.phase_timeout <= 60:
        parser.error("phase timeout must be 1..60 seconds")
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=False)
    serial = args.output / "serial.log"
    serial.touch(exist_ok=False)
    paths = {"sdk_manifest": args.kernel_sdk / "manifest.json", "image": args.image,
             "packaged_child": args.packaged_child, "qemu": args.qemu,
             "harness": Path(__file__), "observer": ROOT / "tools/musl_udp_observer.py",
             "peer": ROOT / "scripts/static_udp_peer.py", "sdk_validator": ROOT / "tools/kernel_sdk.py"}
    receipt = {"schema": 1, "status": "failed", "architecture": args.arch, "mode": args.mode,
               "scope": "actual x86_64 guest static-peer nonblocking IPv4 UDP over polling Virtio PCI",
               "input_paths": {name: str(path.resolve()) for name, path in paths.items()},
               "physical_acceptance": False, "irq_acceptance": False, "smp_acceptance": False,
               "blocking_eintr_restart_acceptance": False,
               "linux_exec_entropy_device": "virtio-rng-pci-non-transitional",
               "host_entropy_backend": "rng-random:/dev/urandom",
               "cryptographic_entropy_quality_acceptance": False, "general_network_stack_acceptance": False,
               "full_m0_m12": False, "extra_frame_quiet_interval_seconds": 0.1,
               "endpoint_hashes_establish_immutable_history": False,
               "image_to_child_package_provenance_requires_external_admission": True,
               "cleanup": {"started": False, "reaped": False}}
    process, coordinator, host, backend = None, None, None, None
    error = None
    try:
        before = {name: digest(path) for name, path in paths.items()}
        receipt["input_sha256_before"] = before
        manifest = validate_sdk(args.kernel_sdk, args.arch, args.mode)
        receipt["sdk_abi"] = manifest["abi_version"]
        receipt["sdk_linux_udp_profile"] = manifest["linux_udp_profile"]
        receipt["sdk_files_before"] = manifest["files"]
        inspect_child(args.packaged_child.read_bytes())
        host, backend = socket.socketpair()
        host.setblocking(False)
        command = qemu_argv(args.image.resolve(), backend.fileno(), args.qemu.resolve())
        receipt["qemu_argv"] = command
        with serial.open("wb") as stream:
            process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                       pass_fds=(backend.fileno(),), env=dict(os.environ, TMPDIR=str(args.output)))
            receipt["cleanup"]["started"] = True
            backend.close()
            coordinator = Coordinator(host, serial, process, args.mode, args.phase_timeout)
            coordinator.run()
        receipt["guest_protocol_complete"] = True
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        error = str(exc)
    finally:
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
                    receipt["cleanup"]["termination_requested"] = True
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        receipt["cleanup"]["kill_requested"] = True
                        process.wait(timeout=2)
                receipt["cleanup"].update(reaped=True, qemu_returncode=process.returncode)
            except (OSError, subprocess.SubprocessError) as exc:
                receipt["cleanup"]["error"] = str(exc)
                error = error or "QEMU cleanup failed: " + str(exc)
        if coordinator is not None and host is not None and receipt["cleanup"]["reaped"]:
            try:
                # After reaping, drain only bytes already delivered by our owned
                # QEMU. Both success and refusal retain partial transport data.
                drain_deadline = time.monotonic() + 0.25
                drain_bytes = 0
                while select.select([host], [], [], 0)[0]:
                    if time.monotonic() >= drain_deadline or drain_bytes >= 1048576:
                        raise ValueError("final Ethernet evidence drain exceeded its bound")
                    data = host.recv(65536)
                    if not data:
                        break
                    drain_bytes += len(data)
                    coordinator.rx.feed(data)
                if receipt.get("guest_protocol_complete"):
                    coordinator.records(final=True)
                    coordinator.rx.finish()
                    if coordinator.rx.frames:
                        raise ValueError("musl UDP guest emitted extra Ethernet frames before cleanup")
            except (OSError, ValueError) as exc:
                error = error or "final evidence verification failed: " + str(exc)
        for stream in (host, backend):
            if stream is not None:
                stream.close()
        (args.output / "peer-rx.bin").write_bytes(bytes(coordinator.rx.raw) if coordinator else b"")
        (args.output / "peer-tx.bin").write_bytes(bytes(coordinator.tx) if coordinator else b"")
        receipt["wire_events"] = coordinator.wire.events if coordinator else []
        receipt["peer_sent_events"] = coordinator.sent if coordinator else []
        receipt["rx_partial_bytes"] = len(coordinator.rx.pending) if coordinator else 0
        receipt["rx_unaccepted_frames"] = len(coordinator.rx.frames) if coordinator else 0
        receipt["evidence_sha256"] = {name: digest(args.output / name)
                                      for name in ("serial.log", "peer-rx.bin", "peer-tx.bin")}
        try:
            after = {name: digest(path) for name, path in paths.items()}
            receipt["input_sha256_after"] = after
            final_manifest = validate_sdk(args.kernel_sdk, args.arch, args.mode)
            receipt["sdk_files_after"] = final_manifest["files"]
            if receipt.get("input_sha256_before") != after or receipt.get("sdk_files_before") != final_manifest["files"]:
                raise ValueError("musl UDP execution inputs changed at endpoint verification")
        except (OSError, ValueError) as exc:
            error = error or "input endpoint verification failed: " + str(exc)
        if error is None and receipt["cleanup"]["reaped"]:
            receipt["status"] = "passed-actual-musl-user-udp-nic"
            receipt["actual_guest_nic_execution"] = True
        else:
            receipt["error"] = error or "QEMU process was not reaped"
        (args.output / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(("MUSL_USER_UDP_NIC_PASS" if receipt["status"].startswith("passed") else
           "MUSL_USER_UDP_NIC_FAIL") + " receipt=" + str(args.output / "receipt.json"))
    return 0 if receipt["status"].startswith("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

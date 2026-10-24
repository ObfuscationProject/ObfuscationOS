#!/usr/bin/env python3
"""Execute the explicit public-libc name fixture on actual QEMU Virtio PCI."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from kernel_sdk import validate_sdk
from musl_udp_sockname_observer import FINAL_RECORD, WireObserver, name_reports, observe, peer, stage
from test_musl_udp_socket import Coordinator as BaseCoordinator, inspect_child, qemu_argv


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Coordinator(BaseCoordinator):
    """Gate host acknowledgements on exact parsed name and complete wire evidence."""
    ACKS = {
        "fixed-ack": ("fixed", b"ACK:NAME:FIXED"),
        "duplicate-ack": ("duplicate", b"ACK:NAME:DUP"),
        "bind-zero-ack-1": ("bind-zero-1", b"ACK:NAME:BIND0:1"),
        "bind-zero-ack-2": ("bind-zero-2", b"ACK:NAME:BIND0:2"),
        "implicit-ack-1": ("implicit-1", b"ACK:NAME:AUTO:1"),
        "implicit-ack-2": ("implicit-2", b"ACK:NAME:AUTO:2"),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.wire = WireObserver()

    def serial_bytes(self) -> bytes:
        return self.serial.read_bytes() if self.serial.exists() else b""

    def records(self, final: bool = False) -> tuple[bytes, ...]:
        return observe(self.serial_bytes(), arch="x86_64", mode=self.mode, final=final)

    def names(self, final: bool = False) -> tuple[dict, ...]:
        return name_reports(self.serial_bytes(), arch="x86_64", mode=self.mode, final=final)

    def wait_name(self, phase: str) -> dict:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            for row in self.names():
                if row["phase"] == phase:
                    return row
            self.pump()
        raise RuntimeError("musl UDP name report timed out: " + phase)

    def phase(self, name: str) -> None:
        self.wait(stage(name, ready=True))

    def receive(self, event: str) -> int | None:
        deadline = time.monotonic() + self.timeout
        while not self.rx.frames:
            if time.monotonic() >= deadline:
                raise RuntimeError("musl UDP name wire event timed out: " + event)
            self.pump()
        # Retain the candidate in the unaccepted queue until all checks pass.
        frame = self.rx.frames[0]
        self.wire.validate_frame(frame, event)
        for phase in self.wire.REQUIRED_NAMES.get(event, ()):
            self.wait_name(phase)
        port = self.wire.accept(frame, event, self.names())
        self.rx.frames.pop(0)
        return port

    def send_frame(self, frame: bytes, event: str) -> None:
        if (event != "arp-request" or frame != peer.arp_request() or self.wire.events or
                self.sent or stage("fixed", ready=True) not in self.records() or
                not any(row["phase"] == "fixed" for row in self.names())):
            raise ValueError("raw host frame lacks the fixed-phase ARP gate")
        super().send_frame(frame, event)

    def send_gate(self, port: int, payload: bytes, event: str) -> list[dict]:
        self.records()
        if any(row["event"] == event for row in self.sent):
            raise ValueError("duplicate host send gate is refused")
        if event == "fixed-start":
            if (port != 54322 or payload != b"GO:NAME:FIXED" or
                    tuple(row["event"] for row in self.wire.events) != ("arp",)):
                raise ValueError("fixed start lacks its ARP/wire gate")
            matched = [row for row in self.names() if row["phase"] == "fixed"]
            if len(matched) != 1 or matched[0]["port"] != port:
                raise ValueError("fixed start lacks its exact name gate")
            return [dict(row) for row in matched]
        if event not in self.ACKS or not self.wire.events:
            raise ValueError("ACK lacks an accepted name/wire gate")
        expected_event, expected_payload = self.ACKS[event]
        accepted = self.wire.events[-1]
        if (accepted["event"] != expected_event or accepted["source_port"] != port or
                payload != expected_payload or not accepted["matched_names"]):
            raise ValueError("ACK differs from its exact accepted name/wire gate")
        return [dict(row) for row in accepted["matched_names"]]

    def send(self, port: int, payload: bytes, event: str) -> None:
        matched = self.send_gate(port, payload, event)
        frame = peer.datagram(peer.PEER_MAC, peer.LOCAL_MAC, peer.PEER_IP,
                              peer.LOCAL_IP, 12345, port, self.identifier, payload)
        super().send_frame(frame, event)
        # A failed gate or transport does not consume the host IPv4 identifier.
        self.identifier += 1
        self.sent[-1]["matched_names"] = matched

    def run(self) -> None:
        self.phase("fixed")
        self.wait_name("fixed")
        self.send_frame(peer.arp_request(), "arp-request")
        self.receive("arp")
        self.send(54322, b"GO:NAME:FIXED", "fixed-start")
        self.receive("fixed")
        self.send(54322, b"ACK:NAME:FIXED", "fixed-ack")
        self.phase("capacity")
        self.wait(stage("capacity", ready=False))
        self.phase("duplicate")
        self.receive("duplicate")
        self.send(54322, b"ACK:NAME:DUP", "duplicate-ack")
        for phase, prefix in (("bind-zero", "BIND0"), ("implicit", "AUTO")):
            self.phase(phase)
            self.wait_name(phase + "-before")
            for number in (1, 2):
                port = self.receive(phase + "-" + str(number))
                if port is None:
                    raise RuntimeError("name phase has no UDP wire source port")
                self.send(port, ("ACK:NAME:" + prefix + ":" + str(number)).encode(),
                          phase + "-ack-" + str(number))
        self.wait(FINAL_RECORD)
        self.records(final=True)
        self.wire.finish()
        deadline = time.monotonic() + 0.1
        while time.monotonic() < deadline:
            self.pump(min(0.01, max(0, deadline - time.monotonic())))
        self.rx.finish()
        if self.rx.frames:
            raise RuntimeError("musl UDP name guest emitted extra Ethernet frames")
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
             "harness": Path(__file__), "observer": ROOT / "tools/musl_udp_sockname_observer.py",
             "base_harness": ROOT / "scripts/test_musl_udp_socket.py",
             "base_observer": ROOT / "tools/musl_udp_observer.py",
             "peer": ROOT / "scripts/static_udp_peer.py", "sdk_validator": ROOT / "tools/kernel_sdk.py"}
    receipt = {"schema": 1, "status": "failed", "architecture": args.arch, "mode": args.mode,
               "scope": "actual x86_64 public-libc getsockname and static-peer nonblocking IPv4 UDP over polling Virtio PCI",
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
        try:
            receipt["name_reports"] = list(coordinator.names()) if coordinator else []
        except (OSError, ValueError) as exc:
            receipt["name_reports"] = []
            receipt["name_report_error"] = str(exc)
            error = error or "final name evidence verification failed: " + str(exc)
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
                raise ValueError("musl UDP name execution inputs changed at endpoint verification")
        except (OSError, ValueError) as exc:
            error = error or "input endpoint verification failed: " + str(exc)
        if error is None and receipt["cleanup"]["reaped"]:
            receipt["status"] = "passed-actual-musl-user-udp-sockname-nic"
            receipt["actual_guest_nic_execution"] = True
        else:
            receipt["error"] = error or "QEMU process was not reaped"
        (args.output / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(("MUSL_USER_UDP_NAME_NIC_PASS" if receipt["status"].startswith("passed") else
           "MUSL_USER_UDP_NAME_NIC_FAIL") + " receipt=" + str(args.output / "receipt.json"))
    return 0 if receipt["status"].startswith("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

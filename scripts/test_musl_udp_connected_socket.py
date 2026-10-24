#!/usr/bin/env python3
"""Bounded public-libc association transactions over actual x86_64 QEMU Virtio PCI."""
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
from musl_udp_connected_observer import FINAL_RECORD, WireObserver, name_reports, observe, peer, stage
from test_musl_udp_socket import Coordinator as BaseCoordinator, inspect_child, qemu_argv


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Coordinator(BaseCoordinator):
    """Closed incoming events require preceding located name and complete wire evidence."""
    SENT_EVENTS = ("arp-request", "associated-start", "associated-wrong", "associated-ack", "duplicate-ack",
                   "zero-source", "zero-other", "disconnect-ack", "retained-ack", "reconnect-wrong", "reconnect-ack")
    INCOMING = {
        "associated-start": ("arp", "associated", 12345, b"GO:S6:ASSOC"),
        "associated-wrong": ("associated", "associated", 12346, b"BAD:S6:ASSOC"),
        "associated-ack": ("associated", "associated", 12345, b"ACK:S6:ASSOC"),
        "duplicate-ack": ("duplicate", "duplicate", 12345, b"ACK:S6:DUP"),
        "zero-source": ("zero", "zero", 0, b"ACK:S6:ZERO0"),
        "zero-other": ("zero", "zero", 12346, b"ACK:S6:ZEROOTHER"),
        "disconnect-ack": ("disconnect", "disconnect", 12346, b"ACK:S6:DISC"),
        "retained-ack": ("retained", "retained", 12345, b"ACK:S6:RETAIN"),
        "reconnect-wrong": ("reconnect", "reconnect", 12345, b"BAD:S6:RECONNECT"),
        "reconnect-ack": ("reconnect", "reconnect", 12346, b"ACK:S6:RECONNECT"),
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
        raise RuntimeError("connected UDP name report timed out: " + phase)

    def phase(self, name: str) -> None:
        self.wait(stage(name, ready=True))

    def receive(self, event: str) -> int | None:
        deadline = time.monotonic() + self.timeout
        while not self.rx.frames:
            if time.monotonic() >= deadline:
                raise RuntimeError("connected UDP wire event timed out: " + event)
            self.pump()
        frame = self.rx.frames[0]
        # Invalid queued frames cannot await future serial evidence or consume state.
        self.wire.validate_frame(frame, event)
        if event != "arp":
            self.phase(event)
        for phase in self.wire.REQUIRED_NAMES.get(event, ()):
            self.wait_name(phase)
        port = self.wire.accept(frame, event, self.names())
        self.rx.frames.pop(0)
        return port

    def next_send(self, event: str) -> None:
        index = len(self.sent)
        if index >= len(self.SENT_EVENTS) or event != self.SENT_EVENTS[index]:
            raise ValueError("host connected send event is duplicate, extra or out of order")

    def send_frame(self, frame: bytes, event: str) -> None:
        self.next_send(event)
        if (event != "arp-request" or frame != peer.arp_request() or self.wire.events or
                stage("associated", ready=True) not in self.records()):
            raise ValueError("raw host frame lacks the closed association ARP gate")
        names = self.names()
        local = [row for row in names if row["phase"] == "associated-local"]
        remote = [row for row in names if row["phase"] == "associated-peer"]
        if len(local) != 1 or len(remote) != 1 or local[0]["port"] != 54324 or remote[0]["port"] != 12345:
            raise ValueError("ARP request lacks exact associated names")
        super().send_frame(frame, event)
        self.sent[-1]["frame_sha256"] = hashlib.sha256(frame).hexdigest()

    def send_gate(self, event: str) -> tuple[int, int, bytes, list[dict]]:
        self.next_send(event)
        if event not in self.INCOMING or not self.wire.events:
            raise ValueError("incoming connected event lacks a closed wire gate")
        wire_event, phase, source, payload = self.INCOMING[event]
        if stage(phase, ready=True) not in self.records() or self.wire.events[-1]["event"] != wire_event:
            raise ValueError("incoming connected event differs from its exact serial/wire gate")
        if event == "associated-start":
            matched = [row for row in self.names() if row["phase"] in ("associated-local", "associated-peer")]
            if len(matched) != 2:
                raise ValueError("association start lacks its located names")
            port = 54324
        else:
            accepted = self.wire.events[-1]
            port, matched = accepted["source_port"], accepted["matched_names"]
            if port is None or not matched:
                raise ValueError("incoming connected event lacks accepted endpoint evidence")
        return port, source, payload, [dict(row) for row in matched]

    def send(self, event: str) -> None:
        port, source, payload, matched = self.send_gate(event)
        frame = peer.datagram(peer.PEER_MAC, peer.LOCAL_MAC, peer.PEER_IP, peer.LOCAL_IP,
                              source, port, self.identifier, payload)
        # The inherited framed transport is called only after this closed gate.
        super().send_frame(frame, event)
        self.sent[-1].update(source_port=source, destination_port=port,
                             frame_sha256=hashlib.sha256(frame).hexdigest(), matched_names=matched)
        self.identifier += 1

    def run(self) -> None:
        self.phase("associated")
        self.send_frame(peer.arp_request(), "arp-request")
        self.receive("arp")
        self.send("associated-start")
        self.receive("associated")
        self.send("associated-wrong"); self.send("associated-ack")
        self.phase("duplicate"); self.receive("duplicate"); self.send("duplicate-ack")
        self.phase("zero"); self.receive("zero"); self.send("zero-source"); self.send("zero-other")
        self.phase("disconnect"); self.receive("disconnect"); self.send("disconnect-ack")
        self.phase("retained"); self.receive("retained"); self.send("retained-ack")
        self.phase("reconnect"); self.receive("reconnect"); self.send("reconnect-wrong"); self.send("reconnect-ack")
        self.wait(FINAL_RECORD)
        self.records(final=True); self.wire.finish()
        if tuple(row["event"] for row in self.sent) != self.SENT_EVENTS:
            raise ValueError("connected UDP host protocol is incomplete")
        deadline = time.monotonic() + 0.1
        while time.monotonic() < deadline:
            self.pump(min(0.01, max(0, deadline - time.monotonic())))
        self.rx.finish()
        if self.rx.frames:
            raise ValueError("connected UDP guest emitted extra Ethernet frames")
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
    args.output = args.output.resolve(); args.output.mkdir(parents=True, exist_ok=False)
    serial = args.output / "serial.log"; serial.touch(exist_ok=False)
    paths = {"sdk_manifest": args.kernel_sdk / "manifest.json", "image": args.image,
             "packaged_child": args.packaged_child, "qemu": args.qemu, "harness": Path(__file__),
             "observer": ROOT / "tools/musl_udp_connected_observer.py",
             "base_harness": ROOT / "scripts/test_musl_udp_socket.py",
             "base_observer": ROOT / "tools/musl_udp_observer.py",
             "peer": ROOT / "scripts/static_udp_peer.py", "sdk_validator": ROOT / "tools/kernel_sdk.py"}
    receipt = {"schema": 1, "status": "failed", "architecture": args.arch, "mode": args.mode,
               "scope": "actual public-libc bounded IPv4 UDP association on x86_64 polling Virtio PCI",
               "input_paths": {name: str(path.resolve()) for name, path in paths.items()},
               "full_m0_m12": False, "hardware_SMP_IRQ_blocking_restart_general_network_desktop_acceptance": False,
               "clean_guest_shutdown": False, "associated_zero_default_send_required": True,
               "supplied_zero_sendto_EINVAL_required": True,
               "extra_frame_quiet_interval_seconds": 0.1, "endpoint_hashes_establish_immutable_history": False,
               "image_to_child_package_provenance_requires_external_admission": True,
               "nested_owned_session_retirement_requires_outer_campaign": True,
               "cleanup": {"started": False, "reaped": False}}
    process, coordinator, host, backend = None, None, None, None
    error = None
    try:
        before = {name: digest(path) for name, path in paths.items()}
        receipt["input_sha256_before"] = before
        manifest = validate_sdk(args.kernel_sdk, args.arch, args.mode)
        receipt.update(sdk_abi=manifest["abi_version"], sdk_linux_udp_profile=manifest["linux_udp_profile"],
                       sdk_connected_profile=manifest["native_udp_connected_profile"], sdk_files_before=manifest["files"])
        inspect_child(args.packaged_child.read_bytes())
        host, backend = socket.socketpair(); host.setblocking(False)
        command = qemu_argv(args.image.resolve(), backend.fileno(), args.qemu.resolve())
        receipt["qemu_argv"] = command
        with serial.open("wb") as stream:
            process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                       pass_fds=(backend.fileno(),), env=dict(os.environ, TMPDIR=str(args.output)))
            receipt["cleanup"]["started"] = True; backend.close()
            coordinator = Coordinator(host, serial, process, args.mode, args.phase_timeout)
            coordinator.run()
        receipt["guest_protocol_complete"] = True
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        error = str(exc)
    finally:
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate(); receipt["cleanup"]["termination_requested"] = True
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill(); receipt["cleanup"]["kill_requested"] = True; process.wait(timeout=2)
                receipt["cleanup"].update(reaped=True, qemu_returncode=process.returncode)
            except (OSError, subprocess.SubprocessError) as exc:
                receipt["cleanup"]["error"] = str(exc); error = error or "QEMU cleanup failed: " + str(exc)
        if coordinator is not None and host is not None and receipt["cleanup"]["reaped"]:
            try:
                deadline, count = time.monotonic() + 0.25, 0
                while select.select([host], [], [], 0)[0]:
                    if time.monotonic() >= deadline or count >= 1048576:
                        raise ValueError("final Ethernet evidence drain exceeded its bound")
                    data = host.recv(65536)
                    if not data:
                        break
                    count += len(data); coordinator.rx.feed(data)
                if receipt.get("guest_protocol_complete"):
                    coordinator.records(final=True); coordinator.rx.finish()
                    if coordinator.rx.frames:
                        raise ValueError("connected UDP guest emitted extra frames before cleanup")
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
            receipt["name_reports"] = []; error = error or "final name evidence failed: " + str(exc)
        receipt.update(wire_events=coordinator.wire.events if coordinator else [],
                       peer_sent_events=coordinator.sent if coordinator else [],
                       rx_partial_bytes=len(coordinator.rx.pending) if coordinator else 0,
                       rx_unaccepted_frames=len(coordinator.rx.frames) if coordinator else 0,
                       evidence_sha256={name: digest(args.output / name) for name in ("serial.log", "peer-rx.bin", "peer-tx.bin")})
        try:
            after = {name: digest(path) for name, path in paths.items()}
            receipt["input_sha256_after"] = after
            final_manifest = validate_sdk(args.kernel_sdk, args.arch, args.mode)
            receipt["sdk_files_after"] = final_manifest["files"]
            if receipt.get("input_sha256_before") != after or receipt.get("sdk_files_before") != final_manifest["files"]:
                raise ValueError("connected UDP execution inputs changed at endpoint verification")
        except (OSError, ValueError) as exc:
            error = error or "input endpoint verification failed: " + str(exc)
        if error is None and receipt["cleanup"]["reaped"]:
            receipt.update(status="passed-actual-musl-user-udp-connected-nic", actual_guest_nic_execution=True)
        else:
            receipt["error"] = error or "QEMU process was not reaped"
        (args.output / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(("MUSL_USER_UDP_CONNECTED_NIC_PASS" if receipt["status"].startswith("passed") else
           "MUSL_USER_UDP_CONNECTED_NIC_FAIL") + " receipt=" + str(args.output / "receipt.json"))
    return 0 if receipt["status"].startswith("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())

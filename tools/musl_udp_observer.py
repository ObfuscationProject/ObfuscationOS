"""Strict serial, wire and transport controls for the explicit musl UDP fixture."""
from __future__ import annotations

import struct
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import static_udp_peer as peer

PHASES = ("basic", "peek", "short", "zero", "fault", "peekfault", "bind-zero", "implicit")
RECORDS = (
    b"MUSL_UDP_RUNNER stage=start", b"MUSL_UDP stage=start",
    *(record for phase in PHASES for record in (
        ("MUSL_UDP stage=" + phase + "-ready" +
         (" port=54322" if phase == "basic" else "")).encode(),
        ("MUSL_UDP stage=" + phase + "-pass").encode())),
    b"MUSL_UDP stage=pass", b"MUSL_UDP_RUNNER stage=pass child_status=0",
)
FAILURES = (b"MUSL_UDP stage=fail", b"MUSL_UDP_RUNNER stage=fail", b"OK_TEST_FAIL",
            b"acceptance=FAIL", b"boot=failed", b"boot=degraded", b"panic", b"PANIC")


def observe(serial: bytes, *, arch: str, mode: str, final: bool = False) -> tuple[bytes, ...]:
    """Validate complete fixture records as one exact ordered prefix."""
    if arch != "x86_64" or mode not in ("debug", "release"):
        raise ValueError("this actual NIC fixture qualifies only x86_64 Debug/Release")
    if any(token in serial for token in FAILURES):
        raise ValueError("musl UDP serial contains a failure diagnostic")
    normalized = serial.replace(b"\r\n", b"\n")
    complete, fragment = normalized.rsplit(b"\n", 1) if b"\n" in normalized else (b"", normalized)
    if b"\r" in complete or (final and b"\r" in fragment):
        raise ValueError("musl UDP serial contains a bare carriage return")
    try:
        complete.decode("ascii")
        if final:
            fragment.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("musl UDP serial is not ASCII") from exc
    if final and any(token in fragment for token in
                     (b"MUSL_UDP", b"OK_MODE", b"OK_TEST_PASS", b"OK_KERNEL_BOOT", b"OK_ENTROPY")):
        raise ValueError("musl UDP serial contains an unterminated record")
    lines = complete.split(b"\n")
    records = tuple(line for line in lines if b"MUSL_UDP" in line)
    if any(line not in RECORDS for line in records):
        raise ValueError("musl UDP serial contains an unknown or wrapped record")
    if len(set(records)) != len(records):
        raise ValueError("musl UDP serial contains a duplicate record")
    if records != RECORDS[:len(records)]:
        raise ValueError("musl UDP serial phase order or prefix is invalid")
    modes = [line for line in lines if b"OK_MODE" in line]
    passes = [line for line in lines if b"OK_TEST_PASS" in line]
    boots = [line for line in lines if b"OK_KERNEL_BOOT" in line]
    entropies = [line for line in lines if b"OK_ENTROPY" in line]
    entropy_ready = b"OK_ENTROPY source=virtio-rng-pci state=ready"
    if len(entropies) > 1 or any(line != entropy_ready for line in entropies):
        raise ValueError("musl UDP Linux exec entropy diagnostic is invalid")
    if (final or records) and entropies != [entropy_ready]:
        raise ValueError("musl UDP Linux exec entropy ready record is missing")
    if mode == "release":
        expected = b"OK_KERNEL_BOOT scope=kernel mode=release arch=x86_64 status=ready"
        if modes or passes or any(line != expected for line in boots) or len(boots) > 1:
            raise ValueError("musl UDP release diagnostics are invalid")
        diagnostics = boots + entropies
        if final and boots != [expected]:
            raise ValueError("musl UDP release kernel boot record is missing")
    else:
        if (any(line != b"OK_MODE debug" for line in modes) or len(modes) > 1 or
                any(not re.fullmatch(rb"OK_TEST_PASS arch=x86_64(?: [a-z][a-z0-9_]*=[0-9]+)+", line)
                    or not re.search(rb" debug_test_points=[1-9][0-9]*(?: |$)", line)
                    for line in passes) or
                len(passes) > 1 or boots):
            raise ValueError("musl UDP debug diagnostics are invalid")
        diagnostics = modes + passes + entropies
        if final and (modes != [b"OK_MODE debug"] or len(passes) != 1):
            raise ValueError("musl UDP debug architecture diagnostics are missing")
        if modes and passes and lines.index(modes[0]) >= lines.index(passes[0]):
            raise ValueError("musl UDP debug diagnostic order is invalid")
    if records and any(lines.index(line) >= lines.index(records[0]) for line in diagnostics):
        raise ValueError("musl UDP kernel diagnostics follow fixture start")
    if final and records != RECORDS:
        raise ValueError("musl UDP serial required records are missing")
    return records


def decode_udp(frame: bytes) -> tuple[int, bytes]:
    """Validate the entire fixed-profile outgoing Ethernet/IPv4/UDP frame."""
    if not 60 <= len(frame) <= 1514:
        raise ValueError("outgoing Ethernet frame length is invalid")
    if frame[:14] != peer.PEER_MAC + peer.LOCAL_MAC + b"\x08\x00":
        raise ValueError("outgoing Ethernet identity is invalid")
    if frame[14:16] != b"\x45\x00" or frame[20:24] != b"\x40\x00\x40\x11":
        raise ValueError("outgoing IPv4 header shape is invalid")
    total = struct.unpack_from("!H", frame, 16)[0]
    if total < 28 or len(frame) != max(60, 14 + total):
        raise ValueError("outgoing IPv4 length is invalid")
    if frame[26:34] != peer.LOCAL_IP + peer.PEER_IP or peer.checksum(frame[14:34]):
        raise ValueError("outgoing IPv4 identity or checksum is invalid")
    udp = frame[34:14 + total]
    source, destination, length, checksum = struct.unpack_from("!HHHH", udp)
    if not source or destination != 12345 or length != len(udp) or not checksum:
        raise ValueError("outgoing UDP port, length or checksum policy is invalid")
    pseudo = peer.LOCAL_IP + peer.PEER_IP + b"\0\x11" + struct.pack("!H", length)
    if peer.checksum(pseudo + udp):
        raise ValueError("outgoing UDP checksum is invalid")
    if any(frame[14 + total:]):
        raise ValueError("outgoing Ethernet padding is invalid")
    return source, udp[8:]


class WireObserver:
    """Seven ordered guest wire events, independently of serial marker claims."""
    EVENTS = ("arp", "basic", "zero", "bind-zero-1", "bind-zero-2", "implicit-1", "implicit-2")
    PAYLOADS = (b"MUSL:BASIC", b"", b"MUSL:BIND0:1", b"MUSL:BIND0:2",
                b"MUSL:AUTO:1", b"MUSL:AUTO:2")

    def __init__(self) -> None:
        self.events: list[dict] = []
        self.ports: dict[str, int] = {}

    def accept(self, frame: bytes, event: str) -> int | None:
        index = len(self.events)
        if index >= len(self.EVENTS) or event != self.EVENTS[index]:
            raise ValueError("outgoing wire phase is extra or out of order")
        source = None
        if event == "arp":
            if frame != peer.arp_reply():
                raise ValueError("outgoing ARP reply differs from exact oracle")
        else:
            source, payload = decode_udp(frame)
            udp_index = index - 1
            if payload != self.PAYLOADS[udp_index]:
                raise ValueError("outgoing UDP payload is wrong for its phase")
            if event in ("basic", "zero"):
                if source != 54322:
                    raise ValueError("explicit socket source port changed")
            else:
                lifetime = "bind-zero" if event.startswith("bind-zero") else "implicit"
                if lifetime in self.ports and self.ports[lifetime] != source:
                    raise ValueError("ephemeral socket source port changed during its lifetime")
            expected = peer.datagram(peer.LOCAL_MAC, peer.PEER_MAC, peer.LOCAL_IP,
                                     peer.PEER_IP, source, 12345, 0x9000 + udp_index, payload)
            if frame != expected:
                raise ValueError("outgoing UDP frame differs from exact phase oracle")
            if event not in ("basic", "zero"):
                self.ports.setdefault(lifetime, source)
        self.events.append({"event": event, "source_port": source, "bytes": len(frame)})
        return source

    def finish(self) -> None:
        if tuple(row["event"] for row in self.events) != self.EVENTS:
            raise ValueError("outgoing wire events are missing")


class FrameCapture:
    """Retain every transport byte, including partial headers and payloads."""
    def __init__(self) -> None:
        self.raw = bytearray()
        self.pending = bytearray()
        self.frames: list[bytes] = []

    def feed(self, data: bytes) -> None:
        self.raw.extend(data)
        self.pending.extend(data)
        while len(self.pending) >= 4:
            length = struct.unpack_from("!I", self.pending)[0]
            if not 14 <= length <= 1514:
                raise ValueError("QEMU Ethernet transport frame length is invalid")
            if len(self.pending) < 4 + length:
                return
            self.frames.append(bytes(self.pending[4:4 + length]))
            del self.pending[:4 + length]

    def finish(self) -> None:
        if self.pending:
            raise ValueError("QEMU Ethernet transport contains a partial frame")

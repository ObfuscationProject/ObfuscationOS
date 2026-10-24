"""Strict public-libc UDP name records and complete report/wire agreement."""
from __future__ import annotations

from dataclasses import dataclass
import re

from musl_udp_observer import FrameCapture, decode_udp, peer

LOCAL_ADDRESS = 0xc0000202
PHASES = ("unbound", "fixed", "capacity", "duplicate", "bind-zero", "implicit")
PREFIX = b"MUSL_UDP_NAME"
NAME_PATTERN = re.compile(
    rb"MUSL_UDP_NAME stage=name phase=([a-z][a-z0-9-]*) family=2 "
    rb"address=(0|[1-9][0-9]*) port=(0|[1-9][0-9]*) length=16")
FAILURES = (b"MUSL_UDP_NAME stage=fail", b"MUSL_UDP_NAME_RUNNER stage=fail",
            b"MUSL_UDP stage=fail", b"MUSL_UDP_RUNNER stage=fail", b"OK_TEST_FAIL",
            b"acceptance=FAIL", b"boot=failed", b"boot=degraded", b"panic", b"PANIC")


@dataclass(frozen=True)
class NameSpec:
    phase: str
    address: int
    port: int | None


def stage(phase: str, *, ready: bool) -> bytes:
    return ("MUSL_UDP_NAME stage=" + phase + ("-ready" if ready else "-pass") +
            (" port=54322" if ready and phase in ("fixed", "duplicate") else "")).encode()


RECORD_SPECS = (
    b"MUSL_UDP_NAME_RUNNER stage=start", b"MUSL_UDP_NAME stage=start",
    stage("unbound", ready=True), NameSpec("unbound", 0, 0), stage("unbound", ready=False),
    stage("fixed", ready=True), NameSpec("fixed", LOCAL_ADDRESS, 54322), stage("fixed", ready=False),
    stage("capacity", ready=True), stage("capacity", ready=False),
    stage("duplicate", ready=True), NameSpec("duplicate", LOCAL_ADDRESS, 54322), stage("duplicate", ready=False),
    stage("bind-zero", ready=True), NameSpec("bind-zero-before", 0, None),
    NameSpec("bind-zero-after-first", 0, None), NameSpec("bind-zero-after-second", 0, None),
    stage("bind-zero", ready=False),
    stage("implicit", ready=True), NameSpec("implicit-before", 0, 0),
    NameSpec("implicit-after-first", 0, None), NameSpec("implicit-after-second", 0, None),
    stage("implicit", ready=False), b"MUSL_UDP_NAME stage=pass",
    b"MUSL_UDP_NAME_RUNNER stage=pass child_status=0",
)
FINAL_RECORD = RECORD_SPECS[-1]
NAME_SPECS = {row.phase: row for row in RECORD_SPECS if isinstance(row, NameSpec)}


def _inspect(serial: bytes, *, arch: str, mode: str, final: bool) -> tuple[tuple[bytes, ...], tuple[dict, ...]]:
    if arch != "x86_64" or mode not in ("debug", "release"):
        raise ValueError("this actual name fixture qualifies only x86_64 Debug/Release")
    if any(token in serial for token in FAILURES):
        raise ValueError("musl UDP name serial contains a failure diagnostic")
    normalized = serial.replace(b"\r\n", b"\n")
    complete, fragment = normalized.rsplit(b"\n", 1) if b"\n" in normalized else (b"", normalized)
    if b"\r" in complete or (final and b"\r" in fragment):
        raise ValueError("musl UDP name serial contains a bare carriage return")
    try:
        complete.decode("ascii")
        if final:
            fragment.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("musl UDP name serial is not ASCII") from error
    if final and any(token in fragment for token in
                     (b"MUSL_UDP", b"OK_MODE", b"OK_TEST_PASS", b"OK_KERNEL_BOOT", b"OK_ENTROPY")):
        raise ValueError("musl UDP name serial contains an unterminated record")
    lines = complete.split(b"\n")
    located = tuple((index, line) for index, line in enumerate(lines) if b"MUSL_UDP" in line)
    records = tuple(line for _, line in located)
    if len(records) > len(RECORD_SPECS):
        raise ValueError("musl UDP name serial contains extra records")
    names, ports = [], {}
    for (line_index, line), expected in zip(located, RECORD_SPECS):
        if isinstance(expected, bytes):
            if line != expected:
                raise ValueError("musl UDP name serial phase order or prefix is invalid")
            continue
        match = NAME_PATTERN.fullmatch(line)
        if not match or match[1].decode() != expected.phase:
            raise ValueError("musl UDP name record grammar, phase or order is invalid")
        # Bound decimal lengths before converting externally supplied serial text.
        if len(match[2]) > 10 or len(match[3]) > 5:
            raise ValueError("musl UDP name endpoint is outside bounded IPv4/port limits")
        address, port = int(match[2]), int(match[3])
        if address != expected.address or not 0 <= port <= 65535:
            raise ValueError("musl UDP name address or port is invalid")
        if expected.port is not None and port != expected.port or expected.port is None and not port:
            raise ValueError("musl UDP name port differs from its phase")
        lifetime = ("bind-zero" if expected.phase.startswith("bind-zero") else
                    "implicit" if expected.phase.startswith("implicit-after") else None)
        if lifetime:
            if lifetime in ports and ports[lifetime] != port:
                raise ValueError("musl UDP name port changed during its lifetime")
            ports[lifetime] = port
        names.append({"phase": expected.phase, "family": 2, "address": address, "port": port,
                      "length": 16, "serial_line_index": line_index, "serial_line": line.decode()})
    modes = [line for line in lines if b"OK_MODE" in line]
    passes = [line for line in lines if b"OK_TEST_PASS" in line]
    boots = [line for line in lines if b"OK_KERNEL_BOOT" in line]
    entropies = [line for line in lines if b"OK_ENTROPY" in line]
    entropy_ready = b"OK_ENTROPY source=virtio-rng-pci state=ready"
    if len(entropies) > 1 or any(line != entropy_ready for line in entropies):
        raise ValueError("musl UDP name Linux exec entropy diagnostic is invalid")
    if (final or records) and entropies != [entropy_ready]:
        raise ValueError("musl UDP name Linux exec entropy ready record is missing")
    if mode == "release":
        expected = b"OK_KERNEL_BOOT scope=kernel mode=release arch=x86_64 status=ready"
        if modes or passes or any(line != expected for line in boots) or len(boots) > 1:
            raise ValueError("musl UDP name release diagnostics are invalid")
        diagnostics = boots + entropies
        if final and boots != [expected]:
            raise ValueError("musl UDP name release kernel boot record is missing")
    else:
        if (any(line != b"OK_MODE debug" for line in modes) or len(modes) > 1 or
                any(not re.fullmatch(rb"OK_TEST_PASS arch=x86_64(?: [a-z][a-z0-9_]*=[0-9]+)+", line)
                    or not re.search(rb" debug_test_points=[1-9][0-9]*(?: |$)", line)
                    for line in passes) or len(passes) > 1 or boots):
            raise ValueError("musl UDP name debug diagnostics are invalid")
        diagnostics = modes + passes + entropies
        if final and (modes != [b"OK_MODE debug"] or len(passes) != 1):
            raise ValueError("musl UDP name debug architecture diagnostics are missing")
        if modes and passes and lines.index(modes[0]) >= lines.index(passes[0]):
            raise ValueError("musl UDP name debug diagnostic order is invalid")
    if records and any(lines.index(line) >= located[0][0] for line in diagnostics):
        raise ValueError("musl UDP name kernel diagnostics follow fixture start")
    if final and len(records) != len(RECORD_SPECS):
        raise ValueError("musl UDP name serial required records are missing")
    return records, tuple(names)


def observe(serial: bytes, *, arch: str, mode: str, final: bool = False) -> tuple[bytes, ...]:
    return _inspect(serial, arch=arch, mode=mode, final=final)[0]


def name_reports(serial: bytes, *, arch: str, mode: str, final: bool = False) -> tuple[dict, ...]:
    return _inspect(serial, arch=arch, mode=mode, final=final)[1]


class WireObserver:
    """Commit complete frames only after every required name agrees with wire."""
    EVENTS = ("arp", "fixed", "duplicate", "bind-zero-1", "bind-zero-2", "implicit-1", "implicit-2")
    PAYLOADS = (b"MUSL:NAME:FIXED", b"MUSL:NAME:DUP", b"MUSL:NAME:BIND0:1",
                b"MUSL:NAME:BIND0:2", b"MUSL:NAME:AUTO:1", b"MUSL:NAME:AUTO:2")
    REQUIRED_NAMES = {
        "fixed": ("fixed",), "duplicate": ("duplicate",),
        "bind-zero-1": ("bind-zero-before", "bind-zero-after-first"),
        "bind-zero-2": ("bind-zero-before", "bind-zero-after-first", "bind-zero-after-second"),
        "implicit-1": ("implicit-before", "implicit-after-first"),
        "implicit-2": ("implicit-before", "implicit-after-first", "implicit-after-second"),
    }

    def __init__(self) -> None:
        self.events: list[dict] = []
        self.ports: dict[str, int] = {}

    def validate_frame(self, frame: bytes, event: str) -> int | None:
        """Refuse a bad queued frame immediately, without committing any state."""
        index = len(self.events)
        if index >= len(self.EVENTS) or event != self.EVENTS[index]:
            raise ValueError("outgoing name wire event is extra or out of order")
        if event == "arp":
            if frame != peer.arp_reply():
                raise ValueError("outgoing ARP reply differs from exact oracle")
            return None
        source, payload = decode_udp(frame)
        udp_index = index - 1
        if payload != self.PAYLOADS[udp_index]:
            raise ValueError("outgoing name UDP payload differs from its phase")
        expected = peer.datagram(peer.LOCAL_MAC, peer.PEER_MAC, peer.LOCAL_IP,
                                 peer.PEER_IP, source, 12345, 0x9000 + udp_index, payload)
        if frame != expected:
            raise ValueError("outgoing name UDP frame differs from exact phase oracle")
        if event in ("fixed", "duplicate") and source != 54322:
            raise ValueError("fixed or duplicate wire source port changed")
        if event not in ("fixed", "duplicate"):
            lifetime = "bind-zero" if event.startswith("bind-zero") else "implicit"
            if lifetime in self.ports and self.ports[lifetime] != source:
                raise ValueError("ephemeral wire source port changed during its lifetime")
        return source

    def accept(self, frame: bytes, event: str, reports: tuple[dict, ...]) -> int | None:
        source = self.validate_frame(frame, event)
        matched, lifetime = [], None
        if event != "arp":
            by_phase = {row["phase"]: row for row in reports}
            if len(by_phase) != len(reports):
                raise ValueError("duplicate name evidence cannot authorize a wire event")
            for phase in self.REQUIRED_NAMES[event]:
                if phase not in by_phase:
                    raise ValueError("wire event is missing its required name report")
                name = by_phase[phase]
                wanted = 0 if phase == "implicit-before" else source
                if (name["family"] != 2 or name["address"] != NAME_SPECS[phase].address or
                        name["length"] != 16):
                    raise ValueError("wire gate name endpoint fields differ from the exact phase")
                if name["port"] != wanted:
                    raise ValueError("getsockname report differs from actual wire source port")
                matched.append(dict(name))
            if event not in ("fixed", "duplicate"):
                lifetime = "bind-zero" if event.startswith("bind-zero") else "implicit"
        # No accepted frame, port or evidence is published before all checks pass.
        if lifetime:
            self.ports.setdefault(lifetime, source)
        self.events.append({"event": event, "source_port": source, "bytes": len(frame),
                            "matched_names": matched})
        return source

    def finish(self) -> None:
        if tuple(row["event"] for row in self.events) != self.EVENTS:
            raise ValueError("outgoing name wire events are missing")

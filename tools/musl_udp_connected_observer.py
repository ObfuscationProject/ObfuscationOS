"""Exact connected UDP records, names and frame gates; parsing is not execution."""
from __future__ import annotations

from dataclasses import dataclass
import re
import struct

from musl_udp_observer import FrameCapture, peer

LOCAL_ADDRESS = 0xc0000202
PEER_ADDRESS = 0xc0000201
PHASES = ("associated", "duplicate", "zero", "disconnect", "retained", "reconnect")
NAME_PATTERN = re.compile(
    rb"MUSL_UDP_CONNECTED stage=name phase=([a-z][a-z0-9-]*) kind=(local|peer) "
    rb"family=2 address=(0|[1-9][0-9]*) port=(0|[1-9][0-9]*) length=16")
FAILURES = (b"stage=fail", b"OK_TEST_FAIL", b"acceptance=FAIL", b"boot=failed", b"boot=degraded",
            b"status=failed", b"panic", b"PANIC")


@dataclass(frozen=True)
class NameSpec:
    phase: str
    kind: str
    address: int
    port: int | None
    lifetime: str | None = None


def stage(phase: str, *, ready: bool) -> bytes:
    if phase not in PHASES:
        raise ValueError("unknown connected UDP phase")
    return ("MUSL_UDP_CONNECTED stage=" + phase + ("-ready" if ready else "-pass")).encode()


RECORD_SPECS = (
    b"MUSL_UDP_CONNECTED_RUNNER stage=start", b"MUSL_UDP_CONNECTED stage=start",
    NameSpec("unbound", "local", 0, 0),
    NameSpec("associated-local", "local", LOCAL_ADDRESS, 54324),
    NameSpec("associated-peer", "peer", PEER_ADDRESS, 12345),
    stage("associated", ready=True), stage("associated", ready=False),
    NameSpec("duplicate-local", "local", LOCAL_ADDRESS, 54324),
    NameSpec("duplicate-peer", "peer", PEER_ADDRESS, 12345),
    stage("duplicate", ready=True), stage("duplicate", ready=False),
    NameSpec("zero-before", "local", LOCAL_ADDRESS, 54325),
    NameSpec("zero-after-refusal", "local", LOCAL_ADDRESS, 54325),
    stage("zero", ready=True), stage("zero", ready=False),
    NameSpec("disconnected-fixed", "local", LOCAL_ADDRESS, 54325),
    stage("disconnect", ready=True), stage("disconnect", ready=False),
    NameSpec("retained-before", "local", LOCAL_ADDRESS, None, "retained-initial"),
    NameSpec("retained-connected", "local", LOCAL_ADDRESS, None, "retained-initial"),
    NameSpec("retained-peer", "peer", PEER_ADDRESS, 12345),
    NameSpec("retained-disconnected", "local", LOCAL_ADDRESS, 0),
    NameSpec("retained-autobind", "local", LOCAL_ADDRESS, None, "retained-rebound"),
    stage("retained", ready=True),
    NameSpec("retained-after-send", "local", LOCAL_ADDRESS, None, "retained-rebound"),
    stage("retained", ready=False),
    NameSpec("reconnected-local", "local", LOCAL_ADDRESS, None, "retained-rebound"),
    NameSpec("reconnected-peer", "peer", PEER_ADDRESS, 12346),
    stage("reconnect", ready=True), stage("reconnect", ready=False),
    b"MUSL_UDP_CONNECTED stage=pass", b"MUSL_UDP_CONNECTED_RUNNER stage=pass child_status=0",
)
FINAL_RECORD = RECORD_SPECS[-1]
NAME_SPECS = {row.phase: row for row in RECORD_SPECS if isinstance(row, NameSpec)}


def _inspect(serial: bytes, *, arch: str, mode: str, final: bool) -> tuple[tuple[bytes, ...], tuple[dict, ...]]:
    if arch != "x86_64" or mode not in ("debug", "release"):
        raise ValueError("actual connected fixture selects only x86_64 Debug/Release")
    if any(token in serial for token in FAILURES):
        raise ValueError("connected UDP serial contains a failure diagnostic")
    normalized = serial.replace(b"\r\n", b"\n")
    complete, fragment = normalized.rsplit(b"\n", 1) if b"\n" in normalized else (b"", normalized)
    if b"\r" in complete or final and b"\r" in fragment:
        raise ValueError("connected UDP serial contains a bare carriage return")
    try:
        complete.decode("ascii")
        if final:
            fragment.decode("ascii")
    except UnicodeDecodeError as error:
        raise ValueError("connected UDP serial is not ASCII") from error
    if final and any(token in fragment for token in (b"MUSL_UDP", b"OK_MODE", b"OK_TEST_PASS", b"OK_KERNEL_BOOT", b"OK_ENTROPY")):
        raise ValueError("connected UDP serial contains an unterminated record")
    lines = complete.split(b"\n")
    located = tuple((index, line) for index, line in enumerate(lines) if b"MUSL_UDP" in line)
    records = tuple(line for _, line in located)
    if len(records) > len(RECORD_SPECS):
        raise ValueError("connected UDP serial contains extra records")
    names, ports = [], {}
    for (line_index, line), expected in zip(located, RECORD_SPECS):
        if isinstance(expected, bytes):
            if line != expected:
                raise ValueError("connected UDP serial phase order or prefix is invalid")
            continue
        match = NAME_PATTERN.fullmatch(line)
        if not match or match[1].decode() != expected.phase or match[2].decode() != expected.kind:
            raise ValueError("connected UDP name grammar, phase or kind is invalid")
        if len(match[3]) > 10 or len(match[4]) > 5:
            raise ValueError("connected UDP endpoint is outside bounded IPv4/port limits")
        address, port = int(match[3]), int(match[4])
        if address != expected.address or not 0 <= port <= 65535:
            raise ValueError("connected UDP name address or port is invalid")
        if expected.port is not None and port != expected.port or expected.port is None and not port:
            raise ValueError("connected UDP name port differs from its phase")
        if expected.lifetime:
            if expected.lifetime in ports and ports[expected.lifetime] != port:
                raise ValueError("connected UDP local port changed during its retained lifetime")
            ports[expected.lifetime] = port
        names.append({"phase": expected.phase, "kind": expected.kind, "family": 2,
                      "address": address, "port": port, "length": 16,
                      "serial_line_index": line_index, "serial_line": line.decode()})
    modes = [line for line in lines if b"OK_MODE" in line]
    passes = [line for line in lines if b"OK_TEST_PASS" in line]
    boots = [line for line in lines if b"OK_KERNEL_BOOT" in line]
    entropies = [line for line in lines if b"OK_ENTROPY" in line]
    entropy_ready = b"OK_ENTROPY source=virtio-rng-pci state=ready"
    if len(entropies) > 1 or any(line != entropy_ready for line in entropies):
        raise ValueError("connected UDP Linux exec entropy diagnostic is invalid")
    if (final or records) and entropies != [entropy_ready]:
        raise ValueError("connected UDP Linux exec entropy ready record is missing")
    if mode == "release":
        expected = b"OK_KERNEL_BOOT scope=kernel mode=release arch=x86_64 status=ready"
        if modes or passes or any(line != expected for line in boots) or len(boots) > 1:
            raise ValueError("connected UDP release diagnostics are invalid")
        diagnostics = boots + entropies
        if final and boots != [expected]:
            raise ValueError("connected UDP release kernel boot record is missing")
    else:
        if (any(line != b"OK_MODE debug" for line in modes) or len(modes) > 1 or
                any(not re.fullmatch(rb"OK_TEST_PASS arch=x86_64(?: [a-z][a-z0-9_]*=[0-9]+)+", line)
                    or not re.search(rb" debug_test_points=[1-9][0-9]*(?: |$)", line) for line in passes) or
                len(passes) > 1 or boots):
            raise ValueError("connected UDP debug diagnostics are invalid")
        diagnostics = modes + passes + entropies
        if final and (modes != [b"OK_MODE debug"] or len(passes) != 1):
            raise ValueError("connected UDP debug architecture diagnostics are missing")
        if modes and passes and lines.index(modes[0]) >= lines.index(passes[0]):
            raise ValueError("connected UDP debug diagnostic order is invalid")
    if records and any(lines.index(line) >= located[0][0] for line in diagnostics):
        raise ValueError("connected UDP kernel diagnostics follow fixture start")
    if final and len(records) != len(RECORD_SPECS):
        raise ValueError("connected UDP serial required records are missing")
    return records, tuple(names)


def observe(serial: bytes, *, arch: str, mode: str, final: bool = False) -> tuple[bytes, ...]:
    return _inspect(serial, arch=arch, mode=mode, final=final)[0]


def name_reports(serial: bytes, *, arch: str, mode: str, final: bool = False) -> tuple[dict, ...]:
    return _inspect(serial, arch=arch, mode=mode, final=final)[1]


class WireObserver:
    """Commit a whole outgoing frame only after all located names agree."""
    EVENTS = ("arp", *PHASES)
    PAYLOADS = (b"MUSL:S6:ASSOC", b"MUSL:S6:DUP", b"MUSL:S6:ZERO", b"MUSL:S6:DISC",
                b"MUSL:S6:RETAIN", b"MUSL:S6:RECONNECT")
    DESTINATIONS = (12345, 12345, 0, 12345, 12345, 12346)
    REQUIRED_NAMES = {
        "associated": ("associated-local", "associated-peer"),
        "duplicate": ("duplicate-local", "duplicate-peer"),
        "zero": ("zero-before", "zero-after-refusal"),
        "disconnect": ("disconnected-fixed",),
        "retained": ("retained-disconnected", "retained-autobind", "retained-after-send"),
        "reconnect": ("retained-autobind", "retained-after-send", "reconnected-local", "reconnected-peer"),
    }

    def __init__(self) -> None:
        self.events: list[dict] = []
        self.retained_port: int | None = None

    def validate_frame(self, frame: bytes, event: str) -> int | None:
        index = len(self.events)
        if index >= len(self.EVENTS) or event != self.EVENTS[index]:
            raise ValueError("outgoing connected wire event is extra or out of order")
        if event == "arp":
            if frame != peer.arp_reply():
                raise ValueError("outgoing ARP reply differs from exact oracle")
            return None
        if len(frame) < 42:
            raise ValueError("outgoing connected UDP frame is truncated")
        source = struct.unpack_from("!H", frame, 34)[0]
        udp_index = index - 1
        if not source:
            raise ValueError("outgoing connected UDP source port is zero")
        expected = peer.datagram(peer.LOCAL_MAC, peer.PEER_MAC, peer.LOCAL_IP, peer.PEER_IP,
                                 source, self.DESTINATIONS[udp_index], 0x9000 + udp_index, self.PAYLOADS[udp_index])
        if frame != expected:
            raise ValueError("outgoing connected UDP frame differs from exact phase oracle")
        fixed = 54324 if event in ("associated", "duplicate") else 54325 if event in ("zero", "disconnect") else None
        if fixed is not None and source != fixed:
            raise ValueError("outgoing connected UDP fixed source port changed")
        if event == "reconnect" and self.retained_port != source:
            raise ValueError("outgoing reconnect wire source port changed")
        return source

    def accept(self, frame: bytes, event: str, reports: tuple[dict, ...]) -> int | None:
        source = self.validate_frame(frame, event)
        specifications = tuple(NAME_SPECS.values())
        if len(reports) > len(specifications):
            raise ValueError("extra located name reports cannot authorize a wire event")
        prior_line = -1
        lifetime_ports = {}
        for row, spec in zip(reports, specifications):
            if (not isinstance(row, dict) or not isinstance(row.get("phase"), str) or
                    not isinstance(row.get("kind"), str) or type(row.get("address")) is not int or
                    type(row.get("port")) is not int or not 0 <= row["port"] <= 65535):
                raise ValueError("located name report fields are invalid")
            text = ("MUSL_UDP_CONNECTED stage=name phase=" + row["phase"] + " kind=" + row["kind"] +
                    " family=2 address=" + str(row["address"]) + " port=" + str(row["port"]) + " length=16")
            if (row["phase"] != spec.phase or row["kind"] != spec.kind or row["address"] != spec.address or
                    row.get("family") != 2 or row.get("length") != 16 or
                    spec.port is not None and row["port"] != spec.port or
                    spec.port is None and not row["port"] or type(row.get("serial_line_index")) is not int or
                    row["serial_line_index"] <= prior_line or row.get("serial_line") != text):
                raise ValueError("located name reports are not an exact ordered serial prefix")
            if spec.lifetime:
                if spec.lifetime in lifetime_ports and lifetime_ports[spec.lifetime] != row["port"]:
                    raise ValueError("located name reports changed a retained lifetime port")
                lifetime_ports[spec.lifetime] = row["port"]
            prior_line = row["serial_line_index"]
        by_phase = {row["phase"]: row for row in reports}
        if len(by_phase) != len(reports):
            raise ValueError("duplicate name evidence cannot authorize a wire event")
        matched = []
        for phase in self.REQUIRED_NAMES.get(event, ()):
            if phase not in by_phase:
                raise ValueError("wire event is missing its required name report")
            row, spec = by_phase[phase], NAME_SPECS[phase]
            wanted = spec.port if spec.kind == "peer" or spec.port == 0 else source
            if (row["family"] != 2 or row["kind"] != spec.kind or row["address"] != spec.address or
                    row["length"] != 16 or row["port"] != wanted or
                    type(row.get("serial_line_index")) is not int or row["serial_line_index"] < 0 or
                    not isinstance(row.get("serial_line"), str)):
                raise ValueError("located name report differs from actual wire endpoint")
            matched.append(dict(row))
        if event == "retained":
            self.retained_port = source
        self.events.append({"event": event, "source_port": source, "destination_port": None if event == "arp" else
                            self.DESTINATIONS[len(self.events) - 1], "bytes": len(frame), "matched_names": matched})
        return source

    def finish(self) -> None:
        if tuple(row["event"] for row in self.events) != self.EVENTS:
            raise ValueError("outgoing connected wire events are missing")

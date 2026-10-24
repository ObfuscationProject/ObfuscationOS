"""Hosted name grammar/wire/gate controls; no guest, syscall or NIC execution."""
from __future__ import annotations

from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))
from musl_udp_sockname_observer import (FINAL_RECORD, LOCAL_ADDRESS, NameSpec, RECORD_SPECS,
                                       WireObserver, name_reports, observe, peer)
from musl_udp_observer import RECORDS as OLD_RECORDS
from test_musl_udp_sockname_socket import Coordinator


def rows(bind_port=49152, implicit_port=49153):
    result = []
    for expected in RECORD_SPECS:
        if isinstance(expected, bytes):
            result.append(expected)
        else:
            port = expected.port
            if port is None:
                port = bind_port if expected.phase.startswith("bind-zero") else implicit_port
            result.append(("MUSL_UDP_NAME stage=name phase=" + expected.phase +
                           " family=2 address=" + str(expected.address) + " port=" + str(port) +
                           " length=16").encode())
    return tuple(result)


def serial(mode="release", *, limit=None, bind_port=49152, implicit_port=49153):
    diagnostics = ((b"OK_MODE debug", b"OK_TEST_PASS arch=x86_64 ext4=1 debug_test_points=3")
                   if mode == "debug" else
                   (b"OK_KERNEL_BOOT scope=kernel mode=release arch=x86_64 status=ready",))
    selected = rows(bind_port, implicit_port)
    return b"\r\n".join((*diagnostics, b"OK_ENTROPY source=virtio-rng-pci state=ready",
                           *selected[:limit])) + b"\r\n"


def reports(data=None):
    return name_reports(data if data is not None else serial(), arch="x86_64", mode="release")


def frame(index, port=None):
    if port is None:
        port = 54322 if index < 2 else 49152 if index < 4 else 49153
    return peer.datagram(peer.LOCAL_MAC, peer.PEER_MAC, peer.LOCAL_IP, peer.PEER_IP,
                         port, 12345, 0x9000 + index, WireObserver.PAYLOADS[index])


def wire_prefix(count, names=None):
    wire = WireObserver()
    names = reports() if names is None else names
    if count:
        wire.accept(peer.arp_reply(), "arp", names)
    for index in range(max(0, count - 1)):
        wire.accept(frame(index), wire.EVENTS[index + 1], names)
    return wire


class SerialControls(unittest.TestCase):
    def test_complete_modes_and_nine_exact_located_names(self):
        for mode in ("debug", "release"):
            data = serial(mode)
            self.assertEqual(observe(data, arch="x86_64", mode=mode, final=True), rows())
            names = name_reports(data, arch="x86_64", mode=mode, final=True)
            self.assertEqual(len(names), 9)
            lines = data.replace(b"\r\n", b"\n").split(b"\n")
            for row in names:
                self.assertEqual(lines[row["serial_line_index"]].decode(), row["serial_line"])
            self.assertEqual(names[0]["port"], 0)
            self.assertEqual(names[1]["address"], LOCAL_ADDRESS)
            self.assertEqual(names[-1]["port"], 49153)

    def test_every_prefix_and_incomplete_record(self):
        for index, line in enumerate(rows()):
            prefix = serial(limit=index)
            self.assertEqual(observe(prefix + line, arch="x86_64", mode="release"), rows()[:index])
            with self.assertRaisesRegex(ValueError, "unterminated"):
                observe(prefix + line, arch="x86_64", mode="release", final=True)
        self.assertEqual(observe(b"", arch="x86_64", mode="release"), ())

    def test_every_missing_duplicate_wrapped_and_reordered_record(self):
        clean = rows()
        for index, row in enumerate(clean):
            samples = [serial().replace(row + b"\r\n", b""),
                       serial().replace(row, row + b"\r\n" + row),
                       serial().replace(row, b"prefix " + row),
                       serial().replace(row, row + b" suffix")]
            if index + 1 < len(clean):
                samples.append(serial().replace(row + b"\r\n" + clean[index + 1],
                                                clean[index + 1] + b"\r\n" + row))
            for sample in samples:
                with self.subTest(index=index), self.assertRaises(ValueError):
                    observe(sample, arch="x86_64", mode="release", final=True)

    def test_name_fields_are_canonical_bounded_and_exact(self):
        for row in rows():
            if b"stage=name " not in row:
                continue
            samples = [row.replace(b"family=2", b"family=1"),
                       row.replace(b"length=16", b"length=15"),
                       row.replace(b"stage=name", b"stage=wrong"),
                       row.replace(b" port=", b" extra=1 port="),
                       row.replace(b"address=0 ", b"address=3221225986 ") if b"address=0 " in row else
                           row.replace(b"address=3221225986 ", b"address=0 ")]
            for value in (b"-1", b"+1", b"00", b"01", b"0x10", b"65536", b"999999999999999999999"):
                samples.append(row[:row.index(b"port=") + 5] + value + b" length=16")
            for value in (b"-1", b"00", b"0x0", b"4294967296", b"999999999999999999999"):
                begin, end = row.index(b"address=") + 8, row.index(b" port=")
                samples.append(row[:begin] + value + row[end:])
            for sample in samples:
                with self.subTest(row=row, sample=sample), self.assertRaises(ValueError):
                    observe(serial().replace(row, sample), arch="x86_64", mode="release", final=True)

    def test_zero_fixed_and_dynamic_ports_and_lifetime_changes(self):
        for phase in ("fixed", "duplicate", "bind-zero-before", "bind-zero-after-first",
                      "bind-zero-after-second", "implicit-after-first", "implicit-after-second"):
            row = next(row for row in rows() if b"phase=" + phase.encode() + b" " in row)
            changed = row[:row.index(b"port=") + 5] + b"0 length=16"
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                observe(serial().replace(row, changed), arch="x86_64", mode="release", final=True)
        for phase in ("bind-zero-after-first", "bind-zero-after-second", "implicit-after-second"):
            row = next(row for row in rows() if b"phase=" + phase.encode() + b" " in row)
            changed = row[:row.index(b"port=") + 5] + b"50000 length=16"
            with self.subTest(phase=phase), self.assertRaisesRegex(ValueError, "lifetime"):
                observe(serial().replace(row, changed), arch="x86_64", mode="release", final=True)
        self.assertEqual(len(reports(serial(bind_port=50000, implicit_port=50000))), 9)

    def test_old_fixture_logs_unknown_failure_and_bad_encoding(self):
        old = serial(limit=0) + b"\r\n".join(OLD_RECORDS) + b"\r\n"
        for sample in (old, serial() + b"MUSL_UDP_NAME stage=unknown\n",
                       serial() + b"MUSL_UDP_NAME stage=fail reason=anything",
                       serial() + b"MUSL_UDP_NAME_RUNNER stage=fail reason=anything",
                       serial() + b"PANIC", serial() + b"\xff\n", serial().replace(b"length=16", b"length=16\r")):
            with self.subTest(sample=sample[-80:]), self.assertRaises(ValueError):
                observe(sample, arch="x86_64", mode="release", final=True)

    def test_diagnostics_entropy_identity_and_order(self):
        ready = b"OK_ENTROPY source=virtio-rng-pci state=ready"
        for mode in ("debug", "release"):
            clean = serial(mode)
            samples = [clean.replace(ready + b"\r\n", b""), clean + ready + b"\n",
                       clean.replace(ready, b"prefix " + ready),
                       clean.replace(ready, b"OK_ENTROPY source=none state=unavailable"),
                       clean.replace(ready + b"\r\n", b"") + ready + b"\n",
                       clean.replace(b"arch=x86_64", b"arch=aarch64")]
            if mode == "debug":
                samples += [clean.replace(b"debug_test_points=3", b"debug_test_points=0"),
                            clean.replace(b"ext4=1", b"Ext4=1"), clean.replace(b"OK_MODE debug\r\n", b"")]
            for sample in samples:
                with self.subTest(mode=mode), self.assertRaises(ValueError):
                    observe(sample, arch="x86_64", mode=mode, final=True)
            with self.assertRaises(ValueError):
                observe(clean, arch="x86_64", mode="release" if mode == "debug" else "debug", final=True)
        with self.assertRaises(ValueError):
            observe(serial(), arch="aarch64", mode="release", final=True)


class WireControls(unittest.TestCase):
    def test_frame_validation_alone_does_not_commit_evidence_or_ports(self):
        wire = wire_prefix(3)
        before = list(wire.events)
        self.assertEqual(wire.validate_frame(frame(2), "bind-zero-1"), 49152)
        self.assertEqual(wire.validate_frame(frame(2), "bind-zero-1"), 49152)
        self.assertEqual(wire.ports, {})
        self.assertEqual(wire.events, before)

    def test_all_seven_frames_have_matching_located_names(self):
        wire = wire_prefix(7)
        wire.finish()
        self.assertEqual(wire.ports, {"bind-zero": 49152, "implicit": 49153})
        self.assertEqual([len(row["matched_names"]) for row in wire.events], [0, 1, 1, 2, 3, 2, 3])
        original = reports()
        for row in wire.events:
            for name in row["matched_names"]:
                self.assertIn(name, original)

    def test_every_frame_byte_mutation_refuses_without_publication(self):
        names = reports()
        for index in range(6):
            clean = frame(index)
            for offset in range(len(clean)):
                wire = wire_prefix(index + 1)
                before_events, before_ports = list(wire.events), dict(wire.ports)
                changed = bytearray(clean); changed[offset] ^= 1
                with self.subTest(index=index, offset=offset), self.assertRaises(ValueError):
                    wire.accept(bytes(changed), wire.EVENTS[index + 1], names)
                self.assertEqual(wire.events, before_events)
                self.assertEqual(wire.ports, before_ports)
        for offset in range(60):
            changed = bytearray(peer.arp_reply()); changed[offset] ^= 1
            wire = WireObserver()
            with self.subTest(arp=offset), self.assertRaises(ValueError):
                wire.accept(bytes(changed), "arp", names)
            self.assertEqual(wire.events, [])

    def test_valid_but_false_reported_port_rejects_actual_wire(self):
        names = reports(serial(bind_port=50000))
        wire = wire_prefix(3, names)
        with self.assertRaisesRegex(ValueError, "actual wire"):
            wire.accept(frame(2), "bind-zero-1", names)
        self.assertEqual(wire.ports, {})
        self.assertEqual(len(wire.events), 3)
        names = reports(serial(implicit_port=50000))
        wire = wire_prefix(5, names)
        with self.assertRaisesRegex(ValueError, "actual wire"):
            wire.accept(frame(4), "implicit-1", names)
        self.assertEqual(wire.ports, {"bind-zero": 49152})

    def test_missing_duplicate_wrong_name_fields_and_extra_events(self):
        for names in ((), reports()[:-1] + (reports()[0],),
                      tuple(dict(row, address=LOCAL_ADDRESS) if row["phase"] == "bind-zero-before" else row
                            for row in reports())):
            wire = wire_prefix(3)
            with self.assertRaises(ValueError):
                wire.accept(frame(2), "bind-zero-1", names)
            self.assertEqual(wire.ports, {})
        wire = wire_prefix(7)
        with self.assertRaisesRegex(ValueError, "extra"):
            wire.accept(frame(5), "implicit-2", reports())
        with self.assertRaisesRegex(ValueError, "missing"):
            wire_prefix(6).finish()


class GateControls(unittest.TestCase):
    def coordinator(self, root, data=None):
        path = root / "serial.log"; path.write_bytes(serial() if data is None else data)
        stream = Mock(); stream.send.side_effect = lambda data: len(data)
        process = Mock(); process.poll.return_value = None
        return Coordinator(stream, path, process, "release", 1)

    def send(self, coordinator, port, payload, event):
        with patch("test_musl_udp_socket.select.select", return_value=([], [coordinator.stream], [])):
            coordinator.send(port, payload, event)

    def test_every_ack_rejects_before_matching_evidence_without_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for event, (_, payload) in Coordinator.ACKS.items():
                coordinator = self.coordinator(root)
                before = coordinator.identifier
                with self.subTest(event=event), self.assertRaisesRegex(ValueError, "gate"):
                    coordinator.send(49152, payload, event)
                self.assertEqual(bytes(coordinator.tx), b"")
                self.assertEqual(coordinator.sent, [])
                self.assertEqual(coordinator.identifier, before)
                coordinator.stream.send.assert_not_called()

    def test_exact_ack_and_duplicate_wrong_port_payload_stage_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self.coordinator(Path(directory))
            coordinator.wire = wire_prefix(4)
            for port, payload, event in ((49153, b"ACK:NAME:BIND0:1", "bind-zero-ack-1"),
                                         (49152, b"WRONG", "bind-zero-ack-1"),
                                         (49152, b"ACK:NAME:BIND0:2", "bind-zero-ack-2")):
                with self.subTest(event=event), self.assertRaises(ValueError):
                    coordinator.send(port, payload, event)
                self.assertEqual(coordinator.identifier, 0x1000)
                self.assertEqual(bytes(coordinator.tx), b"")
            self.send(coordinator, 49152, b"ACK:NAME:BIND0:1", "bind-zero-ack-1")
            self.assertEqual(coordinator.identifier, 0x1001)
            expected = peer.datagram(peer.PEER_MAC, peer.LOCAL_MAC, peer.PEER_IP, peer.LOCAL_IP,
                                     12345, 49152, 0x1000, b"ACK:NAME:BIND0:1")
            self.assertEqual(bytes(coordinator.tx), struct.pack("!I", len(expected)) + expected)
            self.assertEqual(len(coordinator.sent[0]["matched_names"]), 2)
            before = bytes(coordinator.tx)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                coordinator.send(49152, b"ACK:NAME:BIND0:1", "bind-zero-ack-1")
            self.assertEqual(bytes(coordinator.tx), before)
            self.assertEqual(coordinator.identifier, 0x1001)

    def test_report_first_and_frame_first_both_use_same_gate(self):
        after_index = next(index for index, row in enumerate(rows()) if b"phase=implicit-after-first " in row)
        for frame_first in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                coordinator = self.coordinator(Path(directory), serial(limit=after_index if frame_first else after_index + 1))
                coordinator.wire = wire_prefix(5)
                if frame_first:
                    coordinator.rx.frames.append(frame(4))
                    coordinator.pump = lambda: coordinator.serial.write_bytes(serial(limit=after_index + 1))
                else:
                    coordinator.pump = lambda: coordinator.rx.frames.append(frame(4))
                self.assertEqual(coordinator.receive("implicit-1"), 49153)
                self.assertEqual(coordinator.wire.ports["implicit"], 49153)
                self.assertEqual(coordinator.rx.frames, [])
                self.send(coordinator, 49153, b"ACK:NAME:AUTO:1", "implicit-ack-1")

    def test_failed_report_wire_gate_retains_candidate_and_no_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self.coordinator(Path(directory), serial(bind_port=50000))
            coordinator.wire = wire_prefix(3)
            coordinator.rx.frames.append(frame(2))
            with self.assertRaisesRegex(ValueError, "actual wire"):
                coordinator.receive("bind-zero-1")
            self.assertEqual(coordinator.rx.frames, [frame(2)])
            self.assertEqual(coordinator.wire.ports, {})
            with self.assertRaises(ValueError):
                coordinator.send(49152, b"ACK:NAME:BIND0:1", "bind-zero-ack-1")
            self.assertEqual(coordinator.sent, [])
            self.assertEqual(bytes(coordinator.tx), b"")
            self.assertEqual(coordinator.identifier, 0x1000)

    def test_bad_queued_frame_is_refused_before_awaiting_after_send_name(self):
        after_index = next(index for index, row in enumerate(rows()) if b"phase=bind-zero-after-first " in row)
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self.coordinator(Path(directory), serial(limit=after_index))
            coordinator.wire = wire_prefix(3)
            changed = bytearray(frame(2)); changed[14] ^= 1
            coordinator.rx.frames.append(bytes(changed))
            coordinator.pump = Mock(side_effect=AssertionError("bad frame cannot wait for a name"))
            coordinator.wait_name = Mock(side_effect=AssertionError("bad frame cannot wait for a name"))
            with self.assertRaises(ValueError):
                coordinator.receive("bind-zero-1")
            coordinator.wait_name.assert_not_called(); coordinator.pump.assert_not_called()
            self.assertEqual(coordinator.rx.frames, [bytes(changed)])
            self.assertEqual(coordinator.wire.ports, {})
            self.assertEqual(len(coordinator.wire.events), 3)
            self.assertEqual(bytes(coordinator.tx), b"")
            self.assertEqual(coordinator.identifier, 0x1000)

    def test_raw_frame_and_fixed_start_require_arp_name_and_no_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self.coordinator(Path(directory))
            with self.assertRaises(ValueError):
                coordinator.send(54322, b"GO:NAME:FIXED", "fixed-start")
            with self.assertRaises(ValueError):
                coordinator.send_frame(frame(0), "arp-request")
            coordinator.wire = wire_prefix(1)
            self.send(coordinator, 54322, b"GO:NAME:FIXED", "fixed-start")
            before = bytes(coordinator.tx)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                coordinator.send(54322, b"GO:NAME:FIXED", "fixed-start")
            self.assertEqual(bytes(coordinator.tx), before)


if __name__ == "__main__":
    unittest.main()

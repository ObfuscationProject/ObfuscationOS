"""Hosted serial/wire/transport controls; no guest, libc or NIC execution."""
from __future__ import annotations

from pathlib import Path
import hashlib
import struct
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))
from musl_udp_connected_observer import (FrameCapture, LOCAL_ADDRESS, PEER_ADDRESS, NameSpec,
                                         RECORD_SPECS, WireObserver, name_reports, observe, peer, stage)
from test_musl_udp_connected_socket import Coordinator


def rows(initial=49152, rebound=49153):
    result = []
    for spec in RECORD_SPECS:
        if isinstance(spec, bytes):
            result.append(spec)
            continue
        port = spec.port
        if port is None:
            port = initial if spec.lifetime == "retained-initial" else rebound
        result.append(("MUSL_UDP_CONNECTED stage=name phase=" + spec.phase + " kind=" + spec.kind +
                       " family=2 address=" + str(spec.address) + " port=" + str(port) + " length=16").encode())
    return tuple(result)


def serial(mode="release", *, limit=None, initial=49152, rebound=49153):
    diagnostics = ((b"OK_MODE debug", b"OK_TEST_PASS arch=x86_64 ext4=1 debug_test_points=3")
                   if mode == "debug" else
                   (b"OK_KERNEL_BOOT scope=kernel mode=release arch=x86_64 status=ready",))
    return b"\r\n".join((*diagnostics, b"OK_ENTROPY source=virtio-rng-pci state=ready",
                           *rows(initial, rebound)[:limit])) + b"\r\n"


def reports(data=None):
    return name_reports(serial() if data is None else data, arch="x86_64", mode="release")


def frame(index, port=None):
    if port is None:
        port = 54324 if index < 2 else 54325 if index < 4 else 49153
    return peer.datagram(peer.LOCAL_MAC, peer.PEER_MAC, peer.LOCAL_IP, peer.PEER_IP, port,
                         WireObserver.DESTINATIONS[index], 0x9000 + index, WireObserver.PAYLOADS[index])


def wire_prefix(count, names=None):
    wire = WireObserver()
    names = reports() if names is None else names
    if count:
        wire.accept(peer.arp_reply(), "arp", names)
    for index in range(max(0, count - 1)):
        wire.accept(frame(index), wire.EVENTS[index + 1], names)
    return wire


def changed_report(row, **changes):
    result = dict(row, **changes)
    result["serial_line"] = ("MUSL_UDP_CONNECTED stage=name phase=" + result["phase"] +
                             " kind=" + result["kind"] + " family=2 address=" + str(result["address"]) +
                             " port=" + str(result["port"]) + " length=16")
    return result


class SerialControls(unittest.TestCase):
    def test_both_modes_locate_sixteen_names_in_thirty_two_ordered_records(self):
        for mode in ("debug", "release"):
            data = serial(mode)
            self.assertEqual(observe(data, arch="x86_64", mode=mode, final=True), rows())
            names = name_reports(data, arch="x86_64", mode=mode, final=True)
            self.assertEqual(len(names), 16)
            self.assertEqual(len(rows()), 32)
            lines = data.replace(b"\r\n", b"\n").split(b"\n")
            for row in names:
                self.assertEqual(lines[row["serial_line_index"]].decode(), row["serial_line"])
            self.assertEqual(names[0]["port"], 0)
            self.assertEqual(names[-1]["port"], 12346)

    def test_legacy_zero_gap_name_cannot_authorize_default_zero_wire(self):
        legacy = serial().replace(b"phase=zero-after-refusal ", b"phase=zero-after-gap ")
        self.assertNotEqual(legacy, serial())
        with self.assertRaises(ValueError):
            observe(legacy, arch="x86_64", mode="release", final=True)
        with self.assertRaises(ValueError):
            reports(legacy)

    def test_every_prefix_and_unterminated_record(self):
        for index, line in enumerate(rows()):
            prefix = serial(limit=index)
            self.assertEqual(observe(prefix + line, arch="x86_64", mode="release"), rows()[:index])
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, "unterminated"):
                observe(prefix + line, arch="x86_64", mode="release", final=True)
        self.assertEqual(observe(b"", arch="x86_64", mode="release"), ())

    def test_every_missing_duplicate_wrapped_and_reordered_record(self):
        clean = rows()
        for index, row in enumerate(clean):
            samples = [serial().replace(row + b"\r\n", b""),
                       serial().replace(row, row + b"\r\n" + row),
                       serial().replace(row, b"prefix " + row), serial().replace(row, row + b" suffix")]
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
            samples = [row.replace(b"family=2", b"family=1"), row.replace(b"length=16", b"length=15"),
                       row.replace(b" kind=local ", b" kind=peer ") if b" kind=local " in row else
                           row.replace(b" kind=peer ", b" kind=local "),
                       row.replace(b" port=", b" extra=1 port=")]
            for value in (b"-1", b"+1", b"00", b"01", b"0x10", b"65536", b"999999999999999999999"):
                samples.append(row[:row.index(b"port=") + 5] + value + b" length=16")
            for value in (b"-1", b"00", b"0x0", b"4294967296", b"999999999999999999999"):
                begin, end = row.index(b"address=") + 8, row.index(b" port=")
                samples.append(row[:begin] + value + row[end:])
            begin, end = row.index(b"address=") + 8, row.index(b" port=")
            samples.append(row[:begin] + (b"1" if b"address=0 " in row else b"0") + row[end:])
            for sample in samples:
                with self.subTest(row=row, sample=sample), self.assertRaises(ValueError):
                    observe(serial().replace(row, sample), arch="x86_64", mode="release", final=True)

    def test_fixed_zero_dynamic_and_retained_lifetime_ports(self):
        for spec in RECORD_SPECS:
            if not isinstance(spec, NameSpec):
                continue
            row = next(row for row in rows() if b"phase=" + spec.phase.encode() + b" " in row)
            value = b"0" if spec.port != 0 else b"1"
            bad = row[:row.index(b"port=") + 5] + value + b" length=16"
            with self.subTest(phase=spec.phase), self.assertRaises(ValueError):
                observe(serial().replace(row, bad), arch="x86_64", mode="release", final=True)
        for phase in ("retained-connected", "retained-after-send", "reconnected-local"):
            row = next(row for row in rows() if b"phase=" + phase.encode() + b" " in row)
            bad = row[:row.index(b"port=") + 5] + b"50000 length=16"
            with self.subTest(phase=phase), self.assertRaisesRegex(ValueError, "lifetime"):
                observe(serial().replace(row, bad), arch="x86_64", mode="release", final=True)
        # Disconnect releases a reservation; it does not promise a different next port.
        self.assertEqual(len(reports(serial(initial=50000, rebound=50000))), 16)

    def test_unknown_old_failure_and_bad_encoding(self):
        for extra in (b"MUSL_UDP stage=start\n", b"MUSL_UDP_NAME stage=start\n",
                      b"MUSL_UDP_CONNECTED stage=unknown\n", b"MUSL_UDP_CONNECTED stage=fail reason=x",
                      b"MUSL_UDP_CONNECTED_RUNNER stage=fail reason=x", b"PANIC", b"\xff\n"):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                observe(serial() + extra, arch="x86_64", mode="release", final=True)
        with self.assertRaises(ValueError):
            observe(serial().replace(b"length=16", b"length=16\r"), arch="x86_64", mode="release", final=True)

    def test_diagnostics_entropy_mode_identity_and_order(self):
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
                            clean.replace(b"ext4=1", b"Ext4=1"), clean.replace(b"OK_MODE debug\r\n", b""),
                            clean.replace(b"OK_MODE debug\r\n", b"") + b"OK_MODE debug\n"]
            for sample in samples:
                with self.subTest(mode=mode), self.assertRaises(ValueError):
                    observe(sample, arch="x86_64", mode=mode, final=True)
            with self.assertRaises(ValueError):
                observe(clean, arch="x86_64", mode="debug" if mode == "release" else "release", final=True)
        for arch, mode in (("aarch64", "debug"), ("x86_64", "unknown")):
            with self.assertRaises(ValueError):
                observe(serial(), arch=arch, mode=mode, final=True)


class WireControls(unittest.TestCase):
    def test_all_events_match_located_names_and_exact_peer_destination(self):
        wire = wire_prefix(7)
        wire.finish()
        self.assertEqual(wire.retained_port, 49153)
        self.assertEqual([len(row["matched_names"]) for row in wire.events], [0, 2, 2, 2, 1, 3, 4])
        self.assertEqual([event["destination_port"] for event in wire.events],
                         [None, 12345, 12345, 0, 12345, 12345, 12346])
        for event in wire.events:
            for row in event["matched_names"]:
                self.assertIn(row, reports())

    def test_every_frame_byte_mutation_refuses_without_commit(self):
        for index in range(6):
            clean = frame(index)
            for offset in range(len(clean)):
                wire = wire_prefix(index + 1)
                before = list(wire.events), wire.retained_port
                bad = bytearray(clean); bad[offset] ^= 1
                with self.subTest(index=index, offset=offset), self.assertRaises(ValueError):
                    wire.accept(bytes(bad), wire.EVENTS[index + 1], reports())
                self.assertEqual((wire.events, wire.retained_port), before)
        for offset in range(len(peer.arp_reply())):
            bad = bytearray(peer.arp_reply()); bad[offset] ^= 1
            wire = WireObserver()
            with self.subTest(arp=offset), self.assertRaises(ValueError):
                wire.accept(bytes(bad), "arp", reports())
            self.assertEqual(wire.events, [])

    def test_complete_checksum_valid_wrong_ports_payloads_and_identifiers(self):
        for index in range(6):
            port = 54324 if index < 2 else 54325 if index < 4 else 49153
            destination = WireObserver.DESTINATIONS[index]
            candidates = [frame(index, port + 1), frame(index)[:-1], frame(index) + b"\0",
                          peer.datagram(peer.LOCAL_MAC, peer.PEER_MAC, peer.LOCAL_IP, peer.PEER_IP,
                                        port, destination ^ 1, 0x9000 + index, WireObserver.PAYLOADS[index]),
                          peer.datagram(peer.LOCAL_MAC, peer.PEER_MAC, peer.LOCAL_IP, peer.PEER_IP,
                                        port, destination, 0x9100 + index, WireObserver.PAYLOADS[index]),
                          peer.datagram(peer.LOCAL_MAC, peer.PEER_MAC, peer.LOCAL_IP, peer.PEER_IP,
                                        port, destination, 0x9000 + index, b"forbidden-zero")]
            for candidate in candidates:
                wire = wire_prefix(index + 1)
                with self.subTest(index=index), self.assertRaises(ValueError):
                    wire.accept(candidate, wire.EVENTS[index + 1], reports())
                self.assertEqual(len(wire.events), index + 1)

    def test_associated_zero_requires_default_wire_and_refused_sendto_emits_no_frame(self):
        old_explicit = peer.datagram(peer.LOCAL_MAC, peer.PEER_MAC, peer.LOCAL_IP, peer.PEER_IP,
                                    54325, 12345, 0x9002, b"MUSL:S6:ZERO")
        refused_payload = peer.datagram(peer.LOCAL_MAC, peer.PEER_MAC, peer.LOCAL_IP, peer.PEER_IP,
                                       54325, 0, 0x9002, b"forbidden-zero")
        for bad in (old_explicit, refused_payload):
            wire = wire_prefix(3)
            before = list(wire.events), wire.retained_port
            with self.assertRaises(ValueError):
                wire.accept(bad, "zero", reports())
            self.assertEqual((wire.events, wire.retained_port), before)
            wire.accept(frame(2), "zero", reports())
            self.assertEqual(wire.events[-1]["destination_port"], 0)
            for event in ("zero", "disconnect"):
                with self.assertRaises(ValueError):
                    wire.accept(bad, event, reports())
            self.assertEqual(len(wire.events), 4)

    def test_name_prefix_location_fields_missing_duplicate_and_order_refusals(self):
        original = reports()
        samples = [(), original[1:], original[:-1] + (original[0],),
                   (original[1], original[0], *original[2:]),
                   tuple(dict(row, serial_line_index=-1) if i == 1 else row for i, row in enumerate(original)),
                   tuple(dict(row, serial_line_index=original[0]["serial_line_index"]) if i == 1 else row
                         for i, row in enumerate(original)),
                   tuple(dict(row, serial_line="fabricated") if i == 1 else row for i, row in enumerate(original)),
                   tuple(changed_report(row, kind="peer") if i == 1 else row for i, row in enumerate(original)),
                   tuple(changed_report(row, address=0) if i == 1 else row for i, row in enumerate(original)),
                   tuple(changed_report(row, port=54325) if i == 1 else row for i, row in enumerate(original)),
                   tuple(dict(row, length=15) if i == 1 else row for i, row in enumerate(original)),
                   tuple(dict(row, port=None) if i == 1 else row for i, row in enumerate(original))]
        for names in samples:
            wire = wire_prefix(1)
            with self.subTest(names=names), self.assertRaises(ValueError):
                wire.accept(frame(0), "associated", names)
            self.assertEqual(len(wire.events), 1)
            self.assertIsNone(wire.retained_port)

    def test_valid_names_with_false_dynamic_wire_port_do_not_commit_lifetime(self):
        names = reports(serial(rebound=50000))
        wire = wire_prefix(5, names)
        self.assertEqual(wire.validate_frame(frame(4), "retained"), 49153)
        self.assertIsNone(wire.retained_port)
        with self.assertRaisesRegex(ValueError, "actual wire"):
            wire.accept(frame(4), "retained", names)
        self.assertIsNone(wire.retained_port)
        self.assertEqual(len(wire.events), 5)

    def test_event_order_extra_missing_and_validation_only(self):
        wire = wire_prefix(5)
        before = list(wire.events)
        for _ in range(2):
            self.assertEqual(wire.validate_frame(frame(4), "retained"), 49153)
        self.assertEqual(wire.events, before)
        self.assertIsNone(wire.retained_port)
        with self.assertRaises(ValueError):
            wire.accept(frame(5), "reconnect", reports())
        with self.assertRaisesRegex(ValueError, "missing"):
            wire.finish()
        wire = wire_prefix(7)
        with self.assertRaisesRegex(ValueError, "extra"):
            wire.accept(frame(5), "reconnect", reports())


class TransportControls(unittest.TestCase):
    def test_every_transport_prefix_preserves_partial_bytes_and_frames(self):
        frames = (peer.arp_reply(), *(frame(index) for index in range(6)))
        complete = b"".join(struct.pack("!I", len(row)) + row for row in frames)
        boundaries = {0}
        length = 0
        for row in frames:
            length += 4 + len(row); boundaries.add(length)
        for size in range(len(complete) + 1):
            capture = FrameCapture(); capture.feed(complete[:size])
            self.assertEqual(bytes(capture.raw), complete[:size])
            if size in boundaries:
                capture.finish()
            else:
                with self.assertRaises(ValueError): capture.finish()
            capture.feed(complete[size:]); capture.finish()
            self.assertEqual(tuple(capture.frames), frames)
            self.assertEqual(bytes(capture.raw), complete)

    def test_invalid_frame_length_is_retained(self):
        for length in (0, 13, 1515, 0xffffffff):
            capture = FrameCapture(); raw = struct.pack("!I", length) + b"bad"
            with self.assertRaises(ValueError): capture.feed(raw)
            self.assertEqual(bytes(capture.raw), raw)
            self.assertEqual(bytes(capture.pending), raw)


class GateControls(unittest.TestCase):
    def coordinator(self, root, data=None):
        path = root / "serial.log"; path.write_bytes(serial() if data is None else data)
        stream = Mock(); stream.send.side_effect = lambda data: len(data)
        process = Mock(); process.poll.return_value = None
        return Coordinator(stream, path, process, "release", 1)

    def send(self, coordinator, event):
        with patch("test_musl_udp_socket.select.select", return_value=([], [coordinator.stream], [])):
            coordinator.send(event)

    def state_for_send(self, coordinator, event):
        index = coordinator.SENT_EVENTS.index(event)
        coordinator.sent = [{"event": name} for name in coordinator.SENT_EVENTS[:index]]
        preceding = coordinator.INCOMING[event][0]
        coordinator.wire = wire_prefix(WireObserver.EVENTS.index(preceding) + 1)

    def assert_untouched(self, coordinator, sent, identifier):
        self.assertEqual(coordinator.sent, sent)
        self.assertEqual(coordinator.identifier, identifier)
        self.assertEqual(bytes(coordinator.tx), b"")
        coordinator.stream.send.assert_not_called()

    def test_every_incoming_event_refuses_missing_wire_or_serial_gate_transactionally(self):
        for event in Coordinator.INCOMING:
            for failure in ("wire", "serial"):
                with tempfile.TemporaryDirectory() as directory:
                    coordinator = self.coordinator(Path(directory))
                    self.state_for_send(coordinator, event)
                    if failure == "wire": coordinator.wire = WireObserver()
                    else: coordinator.serial.write_bytes(serial(limit=0))
                    before = list(coordinator.sent), coordinator.identifier
                    with self.subTest(event=event, failure=failure), self.assertRaisesRegex(ValueError, "gate"):
                        coordinator.send(event)
                    self.assert_untouched(coordinator, *before)

    def test_unknown_out_of_order_and_duplicate_events_refuse_before_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self.coordinator(Path(directory))
            self.state_for_send(coordinator, "zero-source")
            before = list(coordinator.sent), coordinator.identifier
            for event in ("unknown", "zero-other", "associated-ack", "arp-request"):
                with self.subTest(event=event), self.assertRaises(ValueError): coordinator.send(event)
                self.assert_untouched(coordinator, *before)
            self.send(coordinator, "zero-source")
            saved = bytes(coordinator.tx), list(coordinator.sent), coordinator.identifier
            with self.assertRaises(ValueError): coordinator.send("zero-source")
            self.assertEqual((bytes(coordinator.tx), coordinator.sent, coordinator.identifier), saved)

    def test_arbitrary_raw_host_frame_or_missing_association_cannot_send(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self.coordinator(Path(directory))
            for candidate, event in ((peer.arp_reply(), "arp-request"), (frame(0), "arp-request"),
                                     (peer.arp_request(), "associated-start")):
                with self.assertRaises(ValueError): coordinator.send_frame(candidate, event)
                self.assert_untouched(coordinator, [], 0x1000)
            coordinator.serial.write_bytes(serial(limit=5))
            with self.assertRaises(ValueError): coordinator.send_frame(peer.arp_request(), "arp-request")
            self.assert_untouched(coordinator, [], 0x1000)

    def test_report_first_and_frame_first_preserve_same_retained_gate(self):
        after = next(index for index, row in enumerate(rows()) if b"phase=retained-after-send " in row)
        for frame_first in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                coordinator = self.coordinator(Path(directory), serial(limit=after if frame_first else after + 1))
                coordinator.wire = wire_prefix(5)
                if frame_first:
                    coordinator.rx.frames.append(frame(4))
                    coordinator.pump = lambda: coordinator.serial.write_bytes(serial(limit=after + 1))
                else:
                    coordinator.pump = lambda: coordinator.rx.frames.append(frame(4))
                self.assertEqual(coordinator.receive("retained"), 49153)
                self.assertEqual(coordinator.wire.retained_port, 49153)
                self.assertEqual(coordinator.rx.frames, [])

    def test_failed_name_wire_match_retains_candidate_without_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self.coordinator(Path(directory), serial(rebound=50000))
            coordinator.wire = wire_prefix(5, reports(serial(rebound=50000)))
            coordinator.rx.frames.append(frame(4))
            coordinator.sent = [{"event": row} for row in Coordinator.SENT_EVENTS[:8]]
            with self.assertRaisesRegex(ValueError, "actual wire"): coordinator.receive("retained")
            self.assertEqual(coordinator.rx.frames, [frame(4)])
            self.assertIsNone(coordinator.wire.retained_port)
            with self.assertRaises(ValueError): coordinator.send("retained-ack")
            self.assertEqual(bytes(coordinator.tx), b"")
            self.assertEqual(coordinator.identifier, 0x1000)

    def test_bad_queued_frame_refuses_before_waiting_for_later_reports(self):
        after = next(index for index, row in enumerate(rows()) if b"phase=retained-after-send " in row)
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self.coordinator(Path(directory), serial(limit=after))
            coordinator.wire = wire_prefix(5)
            bad = bytearray(frame(4)); bad[14] ^= 1
            coordinator.rx.frames.append(bytes(bad))
            coordinator.pump = Mock(side_effect=AssertionError("invalid frame cannot await names"))
            coordinator.wait_name = Mock(side_effect=AssertionError("invalid frame cannot await names"))
            with self.assertRaises(ValueError): coordinator.receive("retained")
            coordinator.pump.assert_not_called(); coordinator.wait_name.assert_not_called()
            self.assertEqual(coordinator.rx.frames, [bytes(bad)])
            self.assertEqual(len(coordinator.wire.events), 5)
            self.assertIsNone(coordinator.wire.retained_port)

    def complete(self, coordinator):
        coordinator.rx.frames.extend((peer.arp_reply(), *(frame(index) for index in range(6))))
        coordinator.pump = Mock()
        with patch("test_musl_udp_socket.select.select", return_value=([], [coordinator.stream], [])):
            coordinator.run()

    def test_closed_full_host_protocol_keeps_valid_wrong_source_and_zero_source_bytes_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = self.coordinator(Path(directory))
            self.complete(coordinator)
            capture = FrameCapture(); capture.feed(bytes(coordinator.tx)); capture.finish()
            self.assertEqual(len(capture.frames), 11)
            self.assertEqual(capture.frames[0], peer.arp_request())
            self.assertEqual(tuple(row["event"] for row in coordinator.sent), Coordinator.SENT_EVENTS)
            for index, event in enumerate(Coordinator.SENT_EVENTS[1:]):
                raw = capture.frames[index + 1]
                _, _, source, payload = Coordinator.INCOMING[event]
                destination = 54324 if index < 4 else 54325 if index < 7 else 49153
                self.assertEqual(raw[:14], peer.LOCAL_MAC + peer.PEER_MAC + b"\x08\x00")
                self.assertEqual(raw[14:16], b"\x45\x00")
                total, ident = struct.unpack_from("!HH", raw, 16)
                self.assertEqual(ident, 0x1000 + index)
                self.assertEqual(raw[20:24], b"\x40\x00\x40\x11")
                self.assertEqual(raw[26:34], peer.PEER_IP + peer.LOCAL_IP)
                self.assertEqual(peer.checksum(raw[14:34]), 0)
                udp = raw[34:14 + total]
                src, dst, length, checksum = struct.unpack_from("!HHHH", udp)
                self.assertEqual((src, dst, length), (source, destination, len(udp)))
                self.assertNotEqual(checksum, 0)
                self.assertEqual(peer.checksum(peer.PEER_IP + peer.LOCAL_IP + b"\0\x11" +
                                               struct.pack("!H", length) + udp), 0)
                self.assertEqual(udp[8:], payload)
                self.assertFalse(any(raw[14 + total:]))
                self.assertEqual(coordinator.sent[index + 1]["frame_sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(struct.unpack_from("!H", capture.frames[5], 34)[0], 0)
            self.assertIn(b"BAD:S6:ASSOC", capture.frames[2])
            self.assertIn(b"ACK:S6:ASSOC", capture.frames[3])
            self.assertIn(b"BAD:S6:RECONNECT", capture.frames[9])
            self.assertIn(b"ACK:S6:RECONNECT", capture.frames[10])
            self.assertEqual(coordinator.identifier, 0x100a)
            self.assertEqual(coordinator.rx.frames, [])

    def test_completion_refuses_extra_frame_or_partial_transport(self):
        for partial in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                coordinator = self.coordinator(Path(directory))
                coordinator.rx.frames.extend((peer.arp_reply(), *(frame(index) for index in range(6))))
                if partial: coordinator.rx.feed(b"\0\0\0")
                else: coordinator.rx.frames.append(frame(5))
                coordinator.pump = Mock()
                with patch("test_musl_udp_socket.select.select", return_value=([], [coordinator.stream], [])), \
                        self.assertRaisesRegex(ValueError, "partial|extra"):
                    coordinator.run()
                self.assertEqual(bytes(coordinator.rx.raw), b"\0\0\0" if partial else b"")


if __name__ == "__main__":
    unittest.main()

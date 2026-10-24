"""Hosted protocol controls; these tests do not qualify guest or NIC execution."""
from __future__ import annotations
import struct
import sys
import unittest
import tempfile
import json
import subprocess
from unittest.mock import patch
from unittest.mock import Mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "scripts"))
from musl_udp_observer import FrameCapture, RECORDS, WireObserver, decode_udp, observe, peer
from test_musl_udp_socket import inspect_child, qemu_argv
import test_musl_udp_socket as runner


def serial(mode="release"):
    diagnostics = ((b"OK_MODE debug", b"OK_TEST_PASS arch=x86_64 processes=2 debug_test_points=3")
                   if mode == "debug" else
                   (b"OK_KERNEL_BOOT scope=kernel mode=release arch=x86_64 status=ready",))
    return b"\r\n".join((*diagnostics, b"OK_ENTROPY source=virtio-rng-pci state=ready", *RECORDS)) + b"\r\n"


def frame(index, port=54322):
    return peer.datagram(peer.LOCAL_MAC, peer.PEER_MAC, peer.LOCAL_IP, peer.PEER_IP,
                         port, 12345, 0x9000 + index, WireObserver.PAYLOADS[index])


def complete_wire():
    wire = WireObserver()
    wire.accept(peer.arp_reply(), "arp")
    for index, event in enumerate(WireObserver.EVENTS[1:]):
        wire.accept(frame(index, 54322 if index < 2 else 49152), event)
    wire.finish()
    return wire


class SerialTests(unittest.TestCase):
    def test_complete_both_modes(self):
        for mode in ("debug", "release"):
            self.assertEqual(observe(serial(mode), arch="x86_64", mode=mode, final=True), RECORDS)

    def test_all_valid_prefixes_and_incomplete_not_counted(self):
        prefix = (b"OK_KERNEL_BOOT scope=kernel mode=release arch=x86_64 status=ready\n"
                  b"OK_ENTROPY source=virtio-rng-pci state=ready\n")
        for index in range(len(RECORDS)):
            data = prefix + b"\n".join(RECORDS[:index]) + b"\n" + RECORDS[index]
            self.assertEqual(observe(data, arch="x86_64", mode="release"), RECORDS[:index])
            with self.assertRaisesRegex(ValueError, "unterminated"):
                observe(data, arch="x86_64", mode="release", final=True)

    def test_record_failures(self):
        samples = [serial().replace(RECORDS[2], b"prefix " + RECORDS[2]),
                   serial().replace(RECORDS[2], b"MUSL_UDP stage=unknown"),
                   serial().replace(RECORDS[2], RECORDS[2] + b"\r\n" + RECORDS[2]),
                   serial().replace(RECORDS[3], b""),
                   serial().replace(RECORDS[2], b"PLACEHOLDER").replace(RECORDS[4], RECORDS[2])
                           .replace(b"PLACEHOLDER", RECORDS[4]),
                   serial().replace(RECORDS[-1], b"MUSL_UDP_RUNNER stage=pass child_status=1"),
                   serial() + b"prefix MUSL_UDP stage=fail reason=anything",
                   serial() + b"boot=degraded", serial().replace(RECORDS[2], RECORDS[2] + b"\r"),
                   serial() + b"\xff\n"]
        for data in samples:
            with self.subTest(data=data), self.assertRaises(ValueError):
                observe(data, arch="x86_64", mode="release", final=True)

    def test_captured_actual_debug_record_and_invalid_identifiers(self):
        captured = b'OK_TEST_PASS arch=x86_64 processes=15 cpus=4 drivers=13 free_frames=16384 syscalls=92 debug_test_points=66 fs=1 simplefs=1 ext4=1 user=1 display=1 gpu=1 gui=1 input=1 posix=1 bus=1 usb=1 net=1 shell=1 modes=1 display_checksum=13395518439602740464'
        prefix = b"OK_MODE debug\r\n" + captured + b"\r\n"
        self.assertEqual(observe(prefix, arch="x86_64", mode="debug"), ())
        self.assertEqual(observe(prefix + b"OK_ENTROPY source=virtio-rng-pci state=ready\r\n" + b"\r\n".join(RECORDS) + b"\r\n",
                                 arch="x86_64", mode="debug", final=True), RECORDS)
        for invalid in (b"4ext", b"ext-4", b"_ext4", b"Ext4", b"ext4=1 junk!"):
            changed = prefix.replace(b"ext4=1", invalid + b"=1")
            with self.subTest(identifier=invalid), self.assertRaisesRegex(ValueError, "diagnostics"):
                observe(changed, arch="x86_64", mode="debug")

    def test_linux_exec_entropy_ready_missing_unavailable_wrapped_and_order(self):
        ready = b"OK_ENTROPY source=virtio-rng-pci state=ready"
        for mode in ("debug", "release"):
            good = serial(mode)
            samples = [good.replace(ready + b"\r\n", b""),
                       good.replace(ready, b"OK_ENTROPY source=none state=unavailable"),
                       good.replace(ready, b"OK_ENTROPY source=virtio-rng-pci state=failed"),
                       good.replace(ready, b"prefix " + ready),
                       good + ready + b"\n",
                       good.replace(ready + b"\r\n", b"") + ready + b"\r\n",
                       good.replace(ready + b"\r\n", b"") + ready]
            for changed in samples:
                with self.subTest(mode=mode), self.assertRaises(ValueError):
                    observe(changed, arch="x86_64", mode=mode, final=True)

    def test_diagnostics_profile_and_order(self):
        cases = [(serial("debug"), "release"), (serial(), "debug"),
                 (serial("debug").replace(b"arch=x86_64", b"arch=aarch64"), "debug"),
                 (serial("debug").replace(b"debug_test_points=3", b"debug_test_points=0"), "debug"),
                 (serial("debug").replace(b"OK_MODE debug\r\n", b""), "debug"),
                 (serial("debug") + b"OK_MODE debug\n", "debug"),
                 (b"\r\n".join((*RECORDS, b"OK_KERNEL_BOOT scope=kernel mode=release arch=x86_64 status=ready")) + b"\r\n", "release")]
        for data, mode in cases:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                observe(data, arch="x86_64", mode=mode, final=True)
        with self.assertRaises(ValueError):
            observe(serial(), arch="aarch64", mode="release", final=True)


class WireTests(unittest.TestCase):
    def test_exact_complete_oracle_and_shared_ephemeral_value_allowed(self):
        wire = complete_wire()
        self.assertEqual(wire.ports, {"bind-zero": 49152, "implicit": 49152})
        self.assertEqual(len(wire.events), 7)

    def test_every_byte_is_checked(self):
        clean = frame(0)
        for offset in range(len(clean)):
            changed = bytearray(clean)
            changed[offset] ^= 1
            wire = WireObserver()
            wire.accept(peer.arp_reply(), "arp")
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                wire.accept(bytes(changed), "basic")
            self.assertEqual(len(wire.events), 1)
        for offset in range(60):
            changed = bytearray(peer.arp_reply()); changed[offset] ^= 1
            with self.subTest(arp_offset=offset), self.assertRaises(ValueError):
                WireObserver().accept(bytes(changed), "arp")

    def test_lengths_missing_extra_phase_and_payload(self):
        for changed in (frame(0)[:40], frame(0)[:-1], frame(0) + b"\0", bytes(1515)):
            with self.subTest(length=len(changed)), self.assertRaises(ValueError):
                decode_udp(changed)
        wire = WireObserver()
        with self.assertRaisesRegex(ValueError, "missing"):
            wire.finish()
        with self.assertRaisesRegex(ValueError, "order"):
            wire.accept(frame(0), "basic")
        wire.accept(peer.arp_reply(), "arp")
        with self.assertRaisesRegex(ValueError, "order"):
            wire.accept(peer.arp_reply(), "arp")
        with self.assertRaisesRegex(ValueError, "payload"):
            wire.accept(frame(1), "basic")
        wire = complete_wire()
        with self.assertRaisesRegex(ValueError, "extra"):
            wire.accept(frame(5, 49152), "implicit-2")

    def test_ports_identifiers_and_failed_validation_do_not_publish(self):
        for port in (0, 54321):
            wire = WireObserver(); wire.accept(peer.arp_reply(), "arp")
            with self.assertRaises(ValueError):
                wire.accept(frame(0, port), "basic")
        wire = WireObserver(); wire.accept(peer.arp_reply(), "arp")
        wire.accept(frame(0), "basic"); wire.accept(frame(1), "zero")
        bad_id = peer.datagram(peer.LOCAL_MAC, peer.PEER_MAC, peer.LOCAL_IP, peer.PEER_IP,
                               50000, 12345, 0x9999, WireObserver.PAYLOADS[2])
        with self.assertRaisesRegex(ValueError, "oracle"):
            wire.accept(bad_id, "bind-zero-1")
        self.assertEqual(wire.ports, {})
        wire.accept(frame(2, 50000), "bind-zero-1")
        with self.assertRaisesRegex(ValueError, "lifetime"):
            wire.accept(frame(3, 50001), "bind-zero-2")
        wire.accept(frame(3, 50000), "bind-zero-2")
        wire.accept(frame(4, 60000), "implicit-1")
        with self.assertRaisesRegex(ValueError, "lifetime"):
            wire.accept(frame(5, 60001), "implicit-2")


class TransportTests(unittest.TestCase):
    def test_fragmented_header_payload_and_multiple_frames(self):
        records = b"".join(struct.pack("!I", len(packet)) + packet
                            for packet in (peer.arp_reply(), frame(0), frame(1)))
        for width in (1, 2, 3, 4, 7, len(records)):
            capture = FrameCapture()
            for offset in range(0, len(records), width):
                capture.feed(records[offset:offset + width])
            capture.finish()
            self.assertEqual(capture.raw, records)
            self.assertEqual(capture.frames, [peer.arp_reply(), frame(0), frame(1)])

    def test_every_partial_split_is_retained_and_refused(self):
        record = struct.pack("!I", 60) + peer.arp_reply()
        for offset in range(1, len(record)):
            capture = FrameCapture(); capture.feed(record[:offset])
            self.assertEqual(capture.raw, record[:offset])
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, "partial"):
                capture.finish()

    def test_invalid_frame_length_preserves_all_bytes(self):
        for length in (0, 13, 1515, 0xffffffff):
            data = struct.pack("!I", length) + b"payload"
            capture = FrameCapture()
            with self.assertRaisesRegex(ValueError, "length"):
                capture.feed(data)
            self.assertEqual(capture.raw, data)


class InputTests(unittest.TestCase):
    def test_exact_actual_nic_argv(self):
        argv = qemu_argv(Path("/explicit/image"), 9, Path("/explicit/qemu"))
        self.assertIn("socket,id=net0,fd=9", argv)
        self.assertIn("virtio-net-pci,netdev=net0,mac=02:11:22:33:44:55,disable-legacy=on", argv)
        self.assertIn("file=/explicit/image,format=raw,if=ide,snapshot=on", argv)
        self.assertIn("rng-random,id=entropy0,filename=/dev/urandom", argv)
        self.assertIn("virtio-rng-pci-non-transitional,rng=entropy0", argv)

    def test_elf_static_identity_and_load_bounds(self):
        child = bytearray(121)
        child[:9] = b"\x7fELF\x02\x01\x01\x03\x00"
        struct.pack_into("<HHIQQ", child, 16, 2, 62, 1, 0x1000, 64)
        struct.pack_into("<HHH", child, 52, 64, 56, 1)
        struct.pack_into("<IIQQQQQQ", child, 64, 1, 5, 120, 0x1000, 0, 1, 1, 1)
        inspect_child(bytes(child))
        changes = ((7, b"\0"), (18, b"\xb7\0"), (52, b"\0\0"), (64, b"\3\0\0\0"),
                   (96, struct.pack("<Q", 2)), (104, bytes(8)))
        for offset, value in changes:
            bad = bytearray(child); bad[offset:offset + len(value)] = value
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                inspect_child(bytes(bad))

    def test_precondition_failure_retains_receipt_without_starting_qemu(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            sdk = base / "sdk"; sdk.mkdir()
            image = base / "image"; image.write_bytes(b"image")
            child = base / "child"; child.write_bytes(b"not-an-elf")
            qemu = base / "qemu"; qemu.write_bytes(b"unexecuted")
            output = base / "evidence"
            argv = ["runner", "--arch=x86_64", "--mode=release", "--kernel-sdk", str(sdk),
                    "--image", str(image), "--packaged-child", str(child), "--qemu", str(qemu),
                    "--output", str(output)]
            with patch.object(sys, "argv", argv), patch.object(runner.subprocess, "Popen") as start:
                self.assertEqual(runner.main(), 1)
                start.assert_not_called()
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertEqual(receipt["status"], "failed")
            self.assertFalse(receipt["cleanup"]["started"])

            self.assertIn("manifest.json", receipt["error"])
            for name in ("serial.log", "peer-rx.bin", "peer-tx.bin"):
                self.assertEqual((output / name).read_bytes(), b"")
            (sdk / "manifest.json").write_text("{}")
            output = base / "malformed-child"
            argv[-1] = str(output)
            model_manifest = {"abi_version": 53, "linux_udp_profile": "model-only", "files": {}}
            with patch.object(sys, "argv", argv), patch.object(runner, "validate_sdk", return_value=model_manifest), \
                    patch.object(runner.subprocess, "Popen") as start:
                self.assertEqual(runner.main(), 1)
                start.assert_not_called()
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertIn("Linux ELF", receipt["error"])
            self.assertEqual(receipt["input_sha256_before"], receipt["input_sha256_after"])
            self.assertFalse(receipt["cleanup"]["started"])

    def test_unreaped_live_producer_cannot_enter_final_drain(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            sdk = base / "sdk"; sdk.mkdir(); (sdk / "manifest.json").write_text("{}")
            image = base / "image"; image.write_bytes(b"model-image")
            child = base / "child"; child.write_bytes(b"model-child")
            qemu = base / "qemu"; qemu.write_bytes(b"model-tool-never-executed")
            host, backend, process = Mock(), Mock(), Mock()
            host.recv.return_value = b"continuous-producer"
            process.poll.return_value = None
            process.wait.side_effect = subprocess.TimeoutExpired("model-qemu", 2)
            coordinator = Mock()
            coordinator.run.side_effect = RuntimeError("original-model-phase-failure")
            coordinator.rx = FrameCapture(); coordinator.rx.feed(b"\0\0")
            coordinator.tx = bytearray(b"partial-tx")
            coordinator.wire.events = []; coordinator.sent = []
            output = base / "evidence"
            argv = ["runner", "--arch=x86_64", "--mode=release", "--kernel-sdk", str(sdk),
                    "--image", str(image), "--packaged-child", str(child), "--qemu", str(qemu),
                    "--output", str(output)]
            model_manifest = {"abi_version": 53, "linux_udp_profile": "model-only", "files": {}}
            with patch.object(sys, "argv", argv), patch.object(runner, "inspect_child"), \
                    patch.object(runner, "validate_sdk", return_value=model_manifest), \
                    patch.object(runner.socket, "socketpair", return_value=(host, backend)), \
                    patch.object(runner.subprocess, "Popen", return_value=process), \
                    patch.object(runner, "Coordinator", return_value=coordinator), \
                    patch.object(runner.select, "select", return_value=([host], [], [])) as readiness:
                self.assertEqual(runner.main(), 1)
                readiness.assert_not_called()
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertFalse(receipt["cleanup"]["reaped"])
            self.assertIn("timed out", receipt["cleanup"]["error"])
            self.assertEqual(receipt["error"], "original-model-phase-failure")
            self.assertEqual((output / "peer-rx.bin").read_bytes(), b"\0\0")
            self.assertEqual(receipt["rx_partial_bytes"], 2)
            self.assertEqual((output / "peer-tx.bin").read_bytes(), b"partial-tx")
            host.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()

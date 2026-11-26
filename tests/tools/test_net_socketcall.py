"""Hosted controls for the net_socketcall fixture packaging and the scripted
peer's echo service, without a guest or a cross compiler."""
import json
import random
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import package_net_socketcall_fixture as package
from net_probe_peer import ECHO4, ECHO_PORT, TcpEcho, transport_checksum4

GUEST = bytes((192, 0, 2, 2))


def fake_compiler(directory: Path, identity: bytes, kind: int = 2) -> Path:
    """A compiler stand-in that writes a 32-bit ELF header to its -o output."""
    compiler = directory / "fake-gcc"
    order = "little" if identity[5] == 1 else "big"
    header = identity + bytes(16 - len(identity)) + kind.to_bytes(2, order) + bytes(34)
    compiler.write_text("#!/usr/bin/env python3\nimport sys\n"
                        f"open(sys.argv[sys.argv.index('-o') + 1], 'wb').write({header!r})\n")
    compiler.chmod(0o755)
    return compiler


class Packaging(unittest.TestCase):
    def test_marks_linux_personality_per_profile(self):
        for arch, (_, order, abi_version) in package.PROFILES.items():
            with self.subTest(arch=arch), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                compiler = fake_compiler(base, b"\x7fELF\x01" + bytes((order, 1)))
                out = base / "probe"
                command = package.build(arch, compiler, out)
                data = out.read_bytes()
                self.assertEqual((data[7], data[8]), (3, abi_version))
                self.assertIn("-Wl,--defsym,USER_BASE=0x40000000", command)
                self.assertIn(str(package.LINKER_SCRIPT), " ".join(command))

    def test_refuses_another_identity_or_type(self):
        cases = (b"\x7fELF\x02\x01\x01",          # ELFCLASS64
                 b"\x7fELF\x01\x02\x01",          # big endian on i386
                 b"\x7fELF\x01\x01\x01\x03")      # already marked
        for identity in cases:
            with self.subTest(identity=identity), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                with self.assertRaises(SystemExit):
                    package.build("i386", fake_compiler(base, identity), base / "probe")
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            with self.assertRaises(SystemExit):
                package.build("i386", fake_compiler(base, b"\x7fELF\x01\x01\x01", kind=3), base / "probe")

    def test_packages_root_archive_and_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            rescue = base / "rescue"
            (rescue / "bin").mkdir(parents=True)
            (rescue / "init").write_bytes(b"native-init"); (rescue / "init").chmod(0o755)
            (rescue / "bin/oksh").write_bytes(b"native-shell"); (rescue / "bin/oksh").chmod(0o755)
            compiler = fake_compiler(base, b"\x7fELF\x01\x02\x01")
            out = base / "package"
            argv = ["--arch", "mips", "--compiler", str(compiler), "--rescue-root", str(rescue), "--out", str(out)]
            old = sys.argv
            try:
                sys.argv = ["package_net_socketcall_fixture.py", *argv]
                self.assertEqual(package.main(), 0)
            finally:
                sys.argv = old
            program = out / "root/bin" / package.PROGRAM
            self.assertEqual(program.read_bytes()[7:9], bytes((3, 1)))
            self.assertTrue((out / "boot.okar").is_file() and (out / "boot.okar.inc").is_file())
            manifest = json.loads((out / "manifest.json").read_text())
            self.assertEqual((manifest["fixture"], manifest["architecture"], manifest["program"]),
                             ("net-socketcall", "mips", "/bin/socketcall-probe"))
            self.assertEqual(manifest["program_sha256"], package.digest(program))
            # The staged rescue root is copied, never modified.
            self.assertFalse((rescue / "bin" / package.PROGRAM).exists())

    def test_refuses_an_unstaged_root(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            compiler = fake_compiler(base, b"\x7fELF\x01\x01\x01")
            old = sys.argv
            try:
                sys.argv = ["x", "--arch", "i386", "--compiler", str(compiler), "--rescue-root", str(base / "none"),
                            "--out", str(base / "out")]
                with self.assertRaises(SystemExit):
                    package.main()
            finally:
                sys.argv = old


def segment(port: int, sequence: int, ack: int, flags: int, payload: bytes = b"") -> bytes:
    body = struct.pack("!HHIIBBHHH", port, ECHO_PORT, sequence, ack, 5 << 4, flags, 8192, 0, 0) + payload
    value = transport_checksum4(GUEST, ECHO4, 6, body)
    return body[:16] + struct.pack("!H", value) + body[18:]


class EchoClients(unittest.TestCase):
    def connect(self, echo: TcpEcho, port: int, now: float) -> tuple[int, int]:
        reply = echo.receive(GUEST, segment(port, 1000, 0, 0x02), now)
        self.assertEqual(len(reply), 1)
        server = struct.unpack("!I", reply[0][4:8])[0]
        self.assertEqual(echo.receive(GUEST, segment(port, 1001, server + 1, 0x10), now), [])
        self.assertEqual(echo.state, "established")
        return 1001, server + 1

    def test_second_client_after_the_first_finished(self):
        echo = TcpEcho(random.Random(1))
        sequence, ack = self.connect(echo, 40000, 0.0)
        # Data is echoed; a new SYN is ignored while echoed bytes are unacknowledged.
        out = echo.receive(GUEST, segment(40000, sequence, ack, 0x18, b"abc"), 0.1)
        echoed = [frame for frame in out if len(frame) > 20]
        self.assertEqual(echoed[0][20:], b"abc")
        self.assertEqual(echo.receive(GUEST, segment(40001, 5000, 0, 0x02), 0.2), [])
        # The first client acknowledges the echo and sends its FIN.
        echo.receive(GUEST, segment(40000, sequence + 3, ack + 3, 0x11), 0.3)
        self.assertTrue(echo.fin_received and not echo.pending)
        # Its own port cannot restart the session; another port can.
        self.assertEqual(echo.receive(GUEST, segment(40000, 9000, 0, 0x02), 0.4), [])
        self.connect(echo, 40001, 0.5)
        self.assertEqual(echo.peer, (GUEST, 40001))


if __name__ == "__main__":
    unittest.main()

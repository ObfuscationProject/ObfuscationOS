"""Negative controls for complete-line native UDP guest evidence."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from native_udp_observer import CHILD, PARENT, UDP_PASS, USER_PASS, expected_markers, observe


def good(arch: str = "i386", mode: str = "debug") -> bytes:
    diagnostics = ((b"OK_MODE debug", f"OK_TEST_PASS arch={arch} processes=2".encode())
                   if mode == "debug" else ())
    profile = f"OK_NATIVE_UDP profile={mode} arch={arch}".encode()
    rows = (*diagnostics, profile, PARENT[0], CHILD[0], PARENT[1], PARENT[2],
            PARENT[3], PARENT[4], CHILD[1], PARENT[5], UDP_PASS, USER_PASS)
    return b"\r\n".join(rows) + b"\r\n"


class NativeUdpObserverTests(unittest.TestCase):
    def test_complete_unique_guest(self):
        self.assertEqual(observe(good(), arch="i386", mode="debug", final=True),
                         expected_markers("i386", "debug"))
        self.assertEqual(observe(good(mode="release"), arch="i386", mode="release", final=True),
                         expected_markers("i386", "release"))
        self.assertIn(PARENT[0], observe(good().split(PARENT[1])[0], arch="i386", mode="debug"))

    def test_rejects_wrapped_marker(self):
        with self.assertRaisesRegex(ValueError, "wrapped"):
            observe(good().replace(PARENT[0], b"prefix " + PARENT[0]), arch="i386", mode="debug", final=True)

    def test_rejects_unknown_marker(self):
        with self.assertRaisesRegex(ValueError, "unknown"):
            observe(good().replace(PARENT[0], b"OK_NATIVE_UDP parent=unknown"), arch="i386", mode="debug", final=True)

    def test_rejects_duplicate_marker(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            observe(good().replace(PARENT[0] + b"\r\n", (PARENT[0] + b"\r\n") * 2), arch="i386", mode="debug", final=True)

    def test_rejects_unterminated_marker(self):
        with self.assertRaisesRegex(ValueError, "unterminated"):
            observe(good() + PARENT[0], arch="i386", mode="debug", final=True)

    def test_rejects_bare_carriage_return(self):
        with self.assertRaisesRegex(ValueError, "bare"):
            observe(good().replace(PARENT[0], PARENT[0] + b"\r"), arch="i386", mode="debug", final=True)

    def test_rejects_failure_even_when_wrapped_or_incomplete(self):
        for injected in (b"prefix acceptance=FAIL", b"OK_TEST_FAIL", b"boot=degraded",
                         b"OK_USERLAND scope=hardware shell_pipeline=FAIL"):
            with self.subTest(injected=injected), self.assertRaisesRegex(ValueError, "failure"):
                observe(good() + injected, arch="i386", mode="debug", final=True)

    def test_rejects_missing_and_out_of_order(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            observe(good().replace(CHILD[1] + b"\r\n", b""), arch="i386", mode="debug", final=True)
        with self.assertRaisesRegex(ValueError, "order"):
            observe(good().replace(PARENT[0], b"PLACEHOLDER").replace(PARENT[1], PARENT[0])
                    .replace(b"PLACEHOLDER", PARENT[1]), arch="i386", mode="debug", final=True)

    def test_partial_marker_does_not_pass(self):
        self.assertNotIn(PARENT[0], observe(b"boot\n" + PARENT[0], arch="i386", mode="debug"))
        with self.assertRaisesRegex(ValueError, "unterminated"):
            observe(b"boot\n" + PARENT[0], arch="i386", mode="debug", final=True)

    def test_rejects_wrong_or_missing_guest_profile(self):
        with self.assertRaisesRegex(ValueError, "unknown"):
            observe(good("aarch64", "release"), arch="i386", mode="release", final=True)
        with self.assertRaisesRegex(ValueError, "unknown"):
            observe(good(mode="release"), arch="i386", mode="debug", final=True)
        with self.assertRaisesRegex(ValueError, "missing"):
            observe(good().replace(b"OK_NATIVE_UDP profile=debug arch=i386\r\n", b""),
                    arch="i386", mode="debug", final=True)

    def test_rejects_debug_diagnostics_in_release(self):
        for marker in (b"OK_MODE debug\r\n", b"OK_TEST_PASS arch=i386 processes=2\r\n"):
            with self.subTest(marker=marker), self.assertRaisesRegex(ValueError, "unexpected"):
                observe(marker + good(mode="release"), arch="i386", mode="release", final=True)

    def test_requires_matching_debug_kernel_diagnostics(self):
        with self.assertRaisesRegex(ValueError, "architecture"):
            observe(good().replace(b"OK_TEST_PASS arch=i386 ", b"OK_TEST_PASS arch=arm32 "),
                    arch="i386", mode="debug", final=True)
        with self.assertRaisesRegex(ValueError, "missing debug"):
            observe(good().replace(b"OK_TEST_PASS arch=i386 processes=2\r\n", b""),
                    arch="i386", mode="debug", final=True)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            observe(good().replace(b"OK_MODE debug\r\n", b"OK_MODE debug\r\n" * 2),
                    arch="i386", mode="debug", final=True)


if __name__ == "__main__":
    unittest.main()

"""Reject altered static PID 1 ELF identities before rootfs installation."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from stage_rootfs import ELF_PROFILES, inspect_managed_init_elf


def static_elf(arch: str) -> bytearray:
    elf_class, byte_order, machine = ELF_PROFILES[arch]
    endian = "<" if byte_order == 1 else ">"
    header_size = 52 if elf_class == 1 else 64
    data = bytearray(256)
    data[:9] = b"\x7fELF" + bytes((elf_class, byte_order, 1, 3,
                                   1 if arch in ("mips", "mips64") else 0))
    struct.pack_into(endian + "HHI", data, 16, 2, machine, 1)
    if elf_class == 1:
        struct.pack_into(endian + "II", data, 24, 0x40000010, header_size)
        struct.pack_into(endian + "HHH", data, 40, header_size, 32, 1)
        struct.pack_into(endian + "IIIIIIII", data, header_size,
                         1, 0, 0x40000000, 0x40000000, len(data), len(data), 5, 1)
    else:
        struct.pack_into(endian + "QQ", data, 24, 0x40000010, header_size)
        struct.pack_into(endian + "HHH", data, 52, header_size, 56, 1)
        struct.pack_into(endian + "IIQQQQQQ", data, header_size,
                         1, 5, 0, 0x40000000, 0x40000000, len(data), len(data), 1)
    return data


class ManagedInitElfTests(unittest.TestCase):
    def test_all_ten_static_profiles(self):
        for arch, (elf_class, byte_order, machine) in ELF_PROFILES.items():
            with self.subTest(arch=arch):
                identity = inspect_managed_init_elf(static_elf(arch), arch)
                self.assertEqual(identity, {
                    "class": 32 if elf_class == 1 else 64,
                    "byte_order": "little" if byte_order == 1 else "big",
                    "machine": machine, "type": "ET_EXEC",
                    "interpreter": None, "executed": False,
                })

    def test_rejects_wrong_identity_and_truncated_header(self):
        original = static_elf("x86_64")
        for label, offset, value in (("class", 4, 1), ("endian", 5, 2),
                                     ("version", 6, 2), ("osabi", 7, 0),
                                     ("abi-version", 8, 1)):
            data = bytearray(original)
            data[offset] = value
            with self.subTest(label=label), self.assertRaises(ValueError):
                inspect_managed_init_elf(data, "x86_64")
        for size in (0, 15, 63):
            with self.subTest(size=size), self.assertRaises(ValueError):
                inspect_managed_init_elf(original[:size], "x86_64")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            inspect_managed_init_elf(original, "unknown")

    def test_rejects_rehashed_wrong_machine_and_nonstatic_load(self):
        original = static_elf("x86_64")
        for label, mutate in (
            ("wrong-machine", lambda data: struct.pack_into("<H", data, 18, 183)),
            ("shared-object", lambda data: struct.pack_into("<H", data, 16, 3)),
            ("dynamic", lambda data: struct.pack_into("<I", data, 64, 2)),
            ("interpreter", lambda data: struct.pack_into("<I", data, 64, 3)),
            ("nonexecutable-entry", lambda data: struct.pack_into("<I", data, 68, 4)),
            ("load-too-large", lambda data: struct.pack_into("<Q", data, 96, 257)),
            ("end-at-word-limit", lambda data: struct.pack_into("<Q", data, 104,
                                                                  (1 << 64) - 0x40000000)),
            ("no-program-headers", lambda data: struct.pack_into("<H", data, 56, 0)),
        ):
            data = bytearray(original)
            mutate(data)
            with self.subTest(label=label), self.assertRaises(ValueError):
                inspect_managed_init_elf(data, "x86_64")


if __name__ == "__main__":
    unittest.main()

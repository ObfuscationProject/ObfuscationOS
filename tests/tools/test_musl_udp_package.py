"""Hosted controls for exact embedded UDP fixture packaging, without a guest."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from mkarchive import pack
from package_musl_udp_fixture import archive_inventory, inventory, inspect_archive, inspect_static, manifest
import package_musl_udp_fixture as package


class ArchiveControls(unittest.TestCase):
    def root(self, base):
        root = base / "root"; root.mkdir(); (root / "bin").mkdir()
        (root / "init").write_bytes(b"native-parent")
        (root / "bin/musl-udp-probe").write_bytes(b"public-libc-child")
        (root / "init").chmod(0o755); (root / "bin/musl-udp-probe").chmod(0o755)
        return root

    def test_complete_record_payload_metadata_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(Path(directory))
            actual = inspect_archive(pack(root))
            self.assertEqual(actual, inventory(root))
            self.assertEqual(set(actual), {"/bin", "/bin/musl-udp-probe", "/init"})
            self.assertEqual(actual["/init"]["sha256"], hashlib.sha256(b"native-parent").hexdigest())

    def test_sticky_sgid_host_permissions_are_preserved_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(Path(directory))
            (root / "tmp").mkdir(); (root / "tmp").chmod(0o1777)
            (root / "group").mkdir(); (root / "group").chmod(0o2770)
            (root / "both").mkdir(); (root / "both").chmod(0o3777)
            before = inventory(root)
            expected = archive_inventory(root)
            self.assertEqual(before["/tmp"]["mode"], 0o041777)
            self.assertEqual(before["/group"]["mode"], 0o042770)
            self.assertEqual(expected["/tmp"]["mode"], 0o041777)
            self.assertEqual(expected["/group"]["mode"], 0o042770)
            self.assertEqual(expected["/both"]["mode"], 0o043777)
            self.assertEqual(expected, before)
            blob = pack(root)
            self.assertEqual(inspect_archive(blob), expected)
            self.assertEqual(inventory(root), before)
            self.assertEqual(blob, pack(root))

    def test_archive_inventory_rejects_special_files_and_suid_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(Path(directory))
            group = root / "group"; group.mkdir()
            for path, modes in ((root / "init", (0o1755, 0o2755, 0o4755, 0o7755)),
                                (group, (0o4755, 0o5777, 0o6770, 0o7777))):
                for mode in modes:
                    path.chmod(mode); before = inventory(root)
                    with self.subTest(path=path, mode=oct(mode)), self.assertRaisesRegex(ValueError, "permissions"):
                        archive_inventory(root)
                    self.assertEqual(inventory(root), before)
                path.chmod(0o755)

    def test_independent_reader_rejects_type_specific_special_and_unknown_bits(self):
        with tempfile.TemporaryDirectory() as directory:
            blob = pack(self.root(Path(directory)))
            # The first record is /bin; find /init's independent record header.
            directory_mode = 24
            regular_mode = blob.index(b"/init") - 8
            for offset, modes in ((directory_mode, (0o044755, 0o047777, 0o240755, 0o120755)),
                                  (regular_mode, (0o101755, 0o102755, 0o104755, 0o107755, 0o300755))):
                for mode in modes:
                    changed = bytearray(blob); struct.pack_into("<I", changed, offset, mode)
                    with self.subTest(offset=offset, mode=oct(mode)), self.assertRaisesRegex(ValueError, "mode"):
                        inspect_archive(bytes(changed))
            for mode in (0o041777, 0o042770, 0o043777):
                changed = bytearray(blob); struct.pack_into("<I", changed, directory_mode, mode)
                self.assertEqual(inspect_archive(bytes(changed))["/bin"]["mode"], mode)

    def test_archive_inventory_rejects_unknown_host_mode_bits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(Path(directory)); original = Path.lstat
            for entry in (root / "init", root / "bin"):
                def unknown(path, *args, **kwargs):
                    real = original(path, *args, **kwargs)
                    return SimpleNamespace(st_mode=real.st_mode | (0o200000 if path == entry else 0))

                with self.subTest(entry=entry), patch.object(Path, "lstat", unknown), self.assertRaisesRegex(ValueError, "permissions"):
                    archive_inventory(root)

    def test_header_record_lengths_paths_types_padding_and_trailing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            blob = pack(self.root(Path(directory)))
            samples = [blob[:15], blob[:-1], blob + b"\0"]
            for offset, data in ((0, b"FAIL"), (4, struct.pack("<I", 2)),
                                 (8, struct.pack("<I", 4097)), (12, struct.pack("<I", 1)),
                                 (16, struct.pack("<I", 128)), (20, struct.pack("<I", 0xffffffff)),
                                 (24, struct.pack("<I", 0o120755)), (28, struct.pack("<I", 1)),
                                 (32, b"../."), (36, b"\x01")):
                changed = bytearray(blob); changed[offset:offset + len(data)] = data
                samples.append(bytes(changed))
            for changed in samples:
                with self.subTest(changed=changed[:40]), self.assertRaises(ValueError):
                    inspect_archive(changed)
            changed = bytearray(blob)
            at = changed.find(b"/init")
            changed[at:at + 5] = b"/aaaa"
            with self.assertRaisesRegex(ValueError, "ordering"):
                inspect_archive(bytes(changed))

    def test_regular_input_inventory_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.root(Path(directory))
            (root / "alias").symlink_to(root / "init")
            with self.assertRaisesRegex(ValueError, "symlink"):
                inventory(root)

    def test_manifest_pin_and_static_elf_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            file = base / "manifest.json"; file.write_text('{"schema":1}')
            self.assertEqual(manifest(file, hashlib.sha256(file.read_bytes()).hexdigest()), {"schema": 1})
            for bad in ("f" * 64, "not-a-pin"):
                with self.assertRaises(ValueError):
                    manifest(file, bad)
            child = bytearray(121); child[:9] = b"\x7fELF\x02\x01\x01\x03\0"
            struct.pack_into("<HHIQQ", child, 16, 2, 62, 1, 0x1000, 64)
            struct.pack_into("<HHH", child, 52, 64, 56, 1)
            struct.pack_into("<IIQQQQQQ", child, 64, 1, 5, 120, 0x1000, 0, 1, 1, 1)
            elf = base / "child.elf"; elf.write_bytes(child)
            inspect_static(elf, "x86_64", 3)
            for offset, value in ((7, b"\0"), (64, struct.pack("<I", 2)), (96, struct.pack("<Q", 2)),
                                   (104, bytes(8)), (24, struct.pack("<Q", 0x2000))):
                changed = bytearray(child); changed[offset:offset + len(value)] = value; elf.write_bytes(changed)
                with self.subTest(offset=offset), self.assertRaises(ValueError):
                    inspect_static(elf, "x86_64", 3)

    def test_failure_receipt_preserves_normal_root(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); root = self.root(base); before = inventory(root)
            output = base / "package"
            argv = ["package", "--arch=x86_64", "--mode=debug", "--normal-root", str(root),
                    "--native-parent", str(root / "init"), "--child-build", str(base / "missing"),
                    "--child-manifest-sha256=" + "0" * 64, "--musl-build", str(base / "missing-musl"),
                    "--musl-manifest-sha256=" + "0" * 64, "--out", str(output)]
            with patch.object(sys, "argv", argv):
                self.assertEqual(package.main(), 1)
            receipt = json.loads((output / "receipt.json").read_text())
            self.assertEqual(receipt["status"], "failed")
            self.assertEqual(receipt["normal_root_before"], receipt["normal_root_after"])
            self.assertEqual(inventory(root), before)
            self.assertFalse((output / "root").exists())

    def package_fixture(self, base, root):
        parent = base / "parent.elf"; parent.write_bytes(b"native-parent")
        child_build = base / "child-build"; child_build.mkdir()
        (child_build / "bootstrap.elf").write_bytes(b"static-child")
        (child_build / "manifest.json").write_text("{}")
        musl_build = base / "musl-build"; musl_build.mkdir()
        (musl_build / "manifest.json").write_text("{}")
        output = base / "package"
        argv = ["package", "--arch=x86_64", "--mode=debug", "--normal-root", str(root),
                "--native-parent", str(parent), "--child-build", str(child_build),
                "--child-manifest-sha256=" + "0" * 64, "--musl-build", str(musl_build),
                "--musl-manifest-sha256=" + "0" * 64, "--out", str(output)]
        # ELF and compiler provenance have separate suites. This seam checks the
        # real archive/receipt path and exact preservation of the normal root.
        with patch.object(sys, "argv", argv), patch.object(package, "admit_child", return_value={"commands": []}), \
                patch.object(package, "inspect_static"):
            result = package.main()
        return result, output, json.loads((output / "receipt.json").read_text())

    def test_packaging_receipt_records_type_specific_modes_without_projection(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); root = self.root(base)
            (root / "tmp").mkdir(); (root / "tmp").chmod(0o1777)
            (root / "group").mkdir(); (root / "group").chmod(0o2770)
            before = inventory(root)
            result, output, receipt = self.package_fixture(base, root)
            self.assertEqual(result, 0)
            self.assertEqual(receipt["status"], "packaged-not-linked-or-executed")
            self.assertEqual(receipt["archive_mode_masks"], {"directory": "0o43777", "regular": "0o100777"})
            self.assertEqual(receipt["archive_entries"]["/tmp"]["mode"], 0o041777)
            self.assertEqual(receipt["archive_entries"]["/group"]["mode"], 0o042770)
            self.assertEqual(inspect_archive((output / "boot.okar").read_bytes()), receipt["archive_entries"])
            self.assertEqual(receipt["normal_root_before"], receipt["normal_root_after"])
            self.assertEqual(inventory(root), before)

    def test_permission_failure_receipt_preserves_normal_root_without_archive(self):
        for directory_entry in (False, True):
            with self.subTest(directory=directory_entry), tempfile.TemporaryDirectory() as directory:
                base = Path(directory); root = self.root(base); entry = root / "entry"
                entry.mkdir() if directory_entry else entry.write_bytes(b"payload")
                entry.chmod(0o4755); before = inventory(root)
                result, output, receipt = self.package_fixture(base, root)
                self.assertEqual(result, 1)
                self.assertEqual(receipt["status"], "failed")
                self.assertIn("permissions", receipt["error"])
                self.assertFalse((output / "boot.okar").exists())
                self.assertFalse((output / "boot.okar.inc").exists())
                self.assertEqual(receipt["normal_root_before"], receipt["normal_root_after"])
                self.assertEqual(inventory(root), before)


if __name__ == "__main__":
    unittest.main()

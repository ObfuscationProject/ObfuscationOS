"""Distribution archive reproducibility and boundary tests."""
import importlib.util
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

source = Path(__file__).resolve().parents[2] / "tools/mkarchive.py"
sys.path.insert(0, str(source.parent))
spec = importlib.util.spec_from_file_location("mkarchive", source)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)

class ArchiveTests(unittest.TestCase):
    def records(self, blob):
        magic, version, count, reserved = struct.unpack_from("<4sIII", blob)
        self.assertEqual((magic, version, reserved), (b"OKAR", 1, 0))
        cursor, rows = 16, {}
        for _ in range(count):
            namesz, size, mode, flags = struct.unpack_from("<IIII", blob, cursor)
            cursor += 16
            name = blob[cursor:cursor + namesz].decode("ascii")
            cursor += namesz
            rows[name] = (mode, flags, blob[cursor:cursor + size])
            cursor = (cursor + size + 7) & ~7
        self.assertEqual(cursor, len(blob))
        return rows

    def test_missing_or_file_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            file_root = work / "file"
            file_root.write_bytes(b"not a directory")
            for root in (work / "missing", file_root):
                with self.subTest(root=root), self.assertRaisesRegex(ValueError, "existing directory"):
                    archive.pack(root)

    def test_invalid_root_does_not_replace_existing_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            output = work / "boot.okar"
            include = work / "boot.okar.inc"
            output.write_bytes(b"previous archive")
            include.write_bytes(b"previous include")
            result = subprocess.run([sys.executable, "-B", str(source), "--root", str(work / "missing"),
                                     "--out", str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"existing directory", result.stderr)
            self.assertEqual(output.read_bytes(), b"previous archive")
            self.assertEqual(include.read_bytes(), b"previous include")

    def test_staged_init_packages_in_both_archive_and_flat_simplefs(self):
        project = source.parents[1]
        stage_spec = importlib.util.spec_from_file_location("stage_rootfs", project / "tools/stage_rootfs.py")
        stage = importlib.util.module_from_spec(stage_spec)
        stage_spec.loader.exec_module(stage)
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            apps = work / "apps"
            apps.mkdir()
            for name in stage.APPS:
                (apps / (name + ".elf")).write_bytes(b"ELF fixture: " + name.encode())
            root = work / "rootfs"
            subprocess.run([sys.executable, str(project / "tools/stage_rootfs.py"),
                            "--apps-dir", str(apps), "--out", str(root)], check=True, capture_output=True)
            self.assertEqual((root / "init").read_bytes(), (apps / "init.elf").read_bytes())
            self.assertFalse((root / "bin/init").exists())
            self.assertIn(b"/init", archive.pack(root))
            self.assertIn(b"/etc/hosts", archive.pack(root))
            self.assertIn(b"/bin/resolved", archive.pack(root))
            # The complete pre-resolver staged root already exceeds the
            # legacy flat SimpleFS format's 32-entry capacity. Keep testing
            # that format with an explicit bounded subset of staged bytes.
            flat = work / "flat-root"
            (flat / "etc").mkdir(parents=True)
            (flat / "bin").mkdir()
            for name in ("init", "etc/hosts", "bin/oksh"):
                shutil.copy2(root / name, flat / name)
            disk = work / "rootfs.img"
            subprocess.run([sys.executable, str(project / "tools/mksimplefs.py"), "pack",
                            "--root", str(flat), "--out", str(disk)], check=True, capture_output=True)
            subprocess.run([sys.executable, str(project / "tools/mksimplefs.py"), "verify",
                            str(disk), "--root", str(flat)], check=True, capture_output=True)
            rejected = subprocess.run([sys.executable, str(project / "tools/mksimplefs.py"), "pack",
                "--root", str(root), "--out", str(work / 'oversized.img')], capture_output=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn(b'at most 32 entries', rejected.stderr)
            self.assertFalse((work / 'oversized.img').exists())

    def test_order_modes_and_large_elf_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "bin").mkdir()
            content = bytes(range(256)) * 80
            (root / "bin/init").write_bytes(content)
            (root / "bin/init").chmod(0o755)
            first = archive.pack(root)
            self.assertEqual(first, archive.pack(root))
            self.assertEqual(struct.unpack_from("<4sIII", first), (b"OKAR", 1, 2, 0))
            path_size, size, mode, _ = struct.unpack_from("<IIII", first, 40)
            self.assertEqual((path_size, size, mode), (9, len(content), 0o100755))
            self.assertEqual(first[65:65 + len(content)], content)
            self.assertEqual(len(first) % 8, 0)

    def test_sticky_and_sgid_directory_modes_are_exact_and_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            modes = {"tmp": 0o1777, "group": 0o2770, "both": 0o3777, "private": 0o700}
            for name, mode in modes.items():
                (root / name).mkdir(); (root / name).chmod(mode)
            payload = root / "program"; payload.write_bytes(b"payload"); payload.chmod(0o777)
            first = archive.pack(root)
            for entry in root.iterdir():
                os.utime(entry, (12345, 12345))
            self.assertEqual(first, archive.pack(root))
            rows = self.records(first)
            for name, mode in modes.items():
                self.assertEqual(rows["/" + name], (0o040000 | mode, 0, b""))
            self.assertEqual(rows["/program"], (0o100777, 0, b"payload"))

    def test_regular_special_bits_and_directory_suid_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for directory_entry, modes in ((False, (0o1755, 0o2755, 0o4755, 0o7755)),
                                           (True, (0o4755, 0o5777, 0o6770, 0o7777))):
                entry = root / "entry"
                if directory_entry:
                    entry.mkdir()
                else:
                    entry.write_bytes(b"program")
                for mode in modes:
                    entry.chmod(mode)
                    with self.subTest(directory=directory_entry, mode=oct(mode)), self.assertRaisesRegex(ValueError, "permissions"):
                        archive.pack(root)
                if directory_entry:
                    entry.rmdir()
                else:
                    entry.unlink()

    def test_unknown_mode_bits_are_rejected_without_importing_host_owners(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "entry"; entry.write_bytes(b"program"); entry.chmod(0o755)
            before = archive.pack(root)
            original = Path.lstat

            def metadata(path, *args, **kwargs):
                real = original(path, *args, **kwargs)
                return SimpleNamespace(st_mode=real.st_mode, st_uid=12345, st_gid=54321)

            with patch.object(Path, "lstat", metadata):
                self.assertEqual(archive.pack(root), before)
            for directory_entry in (False, True):
                if directory_entry:
                    entry.unlink(); entry.mkdir()

                def unknown(path, *args, **kwargs):
                    real = original(path, *args, **kwargs)
                    return SimpleNamespace(st_mode=real.st_mode | (0o200000 if path == entry else 0))

                with self.subTest(directory=directory_entry), patch.object(Path, "lstat", unknown), self.assertRaisesRegex(ValueError, "permissions"):
                    archive.pack(root)

    def test_policy_failure_preserves_existing_archive_and_include(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory); root = work / "root"; root.mkdir()
            output, include = work / "boot.okar", work / "boot.okar.inc"
            output.write_bytes(b"previous archive"); include.write_bytes(b"previous include")
            entry = root / "entry"
            for kind in ("regular", "directory", "fifo"):
                if kind == "directory":
                    entry.mkdir(); entry.chmod(0o4755)
                elif kind == "fifo":
                    os.mkfifo(entry)
                else:
                    entry.write_bytes(b"program"); entry.chmod(0o4755)
                result = subprocess.run([sys.executable, "-B", str(source), "--root", str(root),
                                         "--out", str(output)], capture_output=True, timeout=5)
                with self.subTest(kind=kind):
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(b"unsupported archive", result.stderr)
                    self.assertEqual(output.read_bytes(), b"previous archive")
                    self.assertEqual(include.read_bytes(), b"previous include")
                entry.rmdir() if kind == "directory" else entry.unlink()

    def test_fifo_and_socket_types_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fifo = root / "fifo"; os.mkfifo(fifo)
            with self.assertRaisesRegex(ValueError, "unsupported archive entry"):
                archive.pack(root)
            fifo.unlink()
            entry = root / "socket"; entry.write_bytes(b"not a socket payload")
            original = Path.lstat

            def socket_type(path, *args, **kwargs):
                real = original(path, *args, **kwargs)
                return SimpleNamespace(st_mode=(stat.S_IFSOCK | 0o600) if path == entry else real.st_mode)

            # Socket bind is unavailable in some hosted sandboxes. Exercise its
            # lstat type boundary without opening any network endpoint.
            with patch.object(Path, "lstat", socket_type), self.assertRaisesRegex(ValueError, "unsupported archive entry"):
                archive.pack(root)

    def test_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "link").symlink_to("/etc/passwd")
            with self.assertRaises(ValueError):
                archive.pack(root)

    def test_symlink_root_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory); root = work / "root"; root.mkdir()
            (root / "program").write_bytes(b"payload")
            alias = work / "alias"; alias.symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "existing directory"):
                archive.pack(alias)

    def test_paths_respect_kernel_component_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ("a" * 32)).write_text("x")
            with self.assertRaises(ValueError):
                archive.pack(root)

if __name__ == "__main__":
    unittest.main()

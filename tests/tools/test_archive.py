"""Distribution archive reproducibility and boundary tests."""
import importlib.util
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

source = Path(__file__).resolve().parents[2] / "tools/mkarchive.py"
spec = importlib.util.spec_from_file_location("mkarchive", source)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)

class ArchiveTests(unittest.TestCase):
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
            disk = work / "rootfs.img"
            subprocess.run([sys.executable, str(project / "tools/mksimplefs.py"), "pack",
                            "--root", str(root), "--out", str(disk)], check=True, capture_output=True)
            subprocess.run([sys.executable, str(project / "tools/mksimplefs.py"), "verify",
                            str(disk), "--root", str(root)], check=True, capture_output=True)

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

    def test_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "link").symlink_to("/etc/passwd")
            with self.assertRaises(ValueError):
                archive.pack(root)

    def test_paths_respect_kernel_component_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ("a" * 32)).write_text("x")
            with self.assertRaises(ValueError):
                archive.pack(root)

if __name__ == "__main__":
    unittest.main()

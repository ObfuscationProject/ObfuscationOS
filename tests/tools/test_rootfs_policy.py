"""Host ext4 packaging checks; these do not execute a kernel or guest code."""
import importlib.util
import shutil
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

source = Path(__file__).resolve().parents[2] / "tools/rootfs_policy.py"
spec = importlib.util.spec_from_file_location("rootfs_policy", source)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


@unittest.skipUnless(shutil.which("mke2fs"), "ext4 fixture tool unavailable")
class BootstrapSymlinkPolicyTests(unittest.TestCase):
    def fixture(self, directory):
        work = Path(directory)
        root = work / "root"
        (root / "home").mkdir(parents=True)
        (root / "home/note").write_bytes(b"Guest text\n")
        (root / "root").mkdir()
        (root / "root").chmod(0o2777)
        (root / "etc").mkdir()
        (root / "etc/accounts.db").write_bytes(b"OKACCOUNTS 1\nstate unconfigured\n")
        (root / "etc/accounts.db").chmod(0o7777)
        (work / "outside").write_bytes(b"Host target must not enter the image\n")
        (root / "link").symlink_to("../outside")
        (root / "dangling").symlink_to("missing")
        (root / "directory-link").symlink_to("home", target_is_directory=True)
        image = work / "fixture.img"
        subprocess.run([
            "mke2fs", "-q", "-t", "ext4", "-b", "4096", "-I", "256",
            "-O", "none,extent,filetype,sparse_super,large_file",
            "-E", "lazy_itable_init=0", "-m", "0", "-d", str(root),
            str(image), "16M",
        ], check=True, capture_output=True)
        return root, image.read_bytes()

    def test_exact_targets_and_guest_metadata_without_host_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            root, raw = self.fixture(directory)
            normalized = policy.normalize_bootstrap_root(raw, root)
            image = policy.Ext4(normalized)
            paths = image.paths()
            self.assertEqual(set(paths), {"/", "/lost+found", "/home", "/home/note",
                                          "/link", "/dangling", "/directory-link",
                                          "/root", "/etc", "/etc/accounts.db"})
            for name, mode in (("/root", 0o40700), ("/etc/accounts.db", 0o100600)):
                metadata = image.metadata(paths[name])
                self.assertEqual((metadata['mode'], metadata['uid'], metadata['gid']), (mode, 0, 0))
            self.assertEqual(image.contents(paths['/etc/accounts.db']), b'OKACCOUNTS 1\nstate unconfigured\n')
            for name, target in (("/link", b"../outside"), ("/dangling", b"missing"),
                                 ("/directory-link", b"home")):
                with self.subTest(name=name):
                    self.assertEqual(image.contents(paths[name]), target)
                    metadata = image.metadata(paths[name])
                    self.assertEqual((metadata["mode"], metadata["uid"], metadata["gid"]),
                                     (0o120777, 0, 0))
            self.assertEqual(image.contents(paths["/home/note"]), b"Guest text\n")
            self.assertNotIn(b"Host target must not enter the image", normalized)

    def test_changed_target_type_or_block_claim_refuses_before_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            root, raw = self.fixture(directory)
            image = policy.Ext4(raw)
            offset = image.inode(image.paths()["/link"])
            changes = ((offset + 40, b"x", "exact staged bytes"),
                       (offset, struct.pack("<H", 0o100777), "same staged/image inode type"),
                       (offset + 28, struct.pack("<I", 8), "bounded fast symlink"))
            for position, value, message in changes:
                with self.subTest(message=message):
                    changed = bytearray(raw)
                    changed[position:position + len(value)] = value
                    with self.assertRaisesRegex(ValueError, message):
                        policy.normalize_bootstrap_root(changed, root)

    def test_long_staged_target_stays_outside_fast_symlink_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root, raw = self.fixture(directory)
            (root / "link").unlink()
            (root / "link").symlink_to("x" * 60)
            with self.assertRaisesRegex(ValueError, "bounded staged fast symlink"):
                policy.normalize_bootstrap_root(raw, root)


@unittest.skipUnless(shutil.which("mke2fs"), "ext4 fixture tool unavailable")
class BootstrapSparsePolicyTests(unittest.TestCase):
    block = 4096

    def fixture(self, directory):
        work = Path(directory)
        root = work / "root"
        root.mkdir()
        block = self.block
        files = {
            "leading": bytes(block) + b"L" * block,
            "middle": b"M" * block + bytes(block) + b"N" * block,
            "trailing": b"T" * block + bytes(block + 4),
            "allholes": bytes(block * 2 + 1),
            "empty": b"",
            "pwd-shape": b"P" * 45056 + bytes(4),
            "dense": b"D" * (block + 1),
            "four-extents": b"A" * block + bytes(block) + b"B" * block + bytes(block) +
                            b"C" * block + bytes(block) + b"D" * block,
        }
        for name, value in files.items():
            (root / name).write_bytes(value)
        image = work / "fixture.img"
        subprocess.run([
            "mke2fs", "-q", "-t", "ext4", "-b", "4096", "-I", "256",
            "-O", "none,extent,filetype,sparse_super,large_file",
            "-E", "lazy_itable_init=0", "-m", "0", "-d", str(root),
            str(image), "16M",
        ], check=True, capture_output=True)
        return root, image.read_bytes(), files

    def extent_offsets(self, raw, path):
        image = policy.Ext4(raw)
        number = image.paths()[path]
        offset = image.inode(number)
        return image, number, offset, offset + 52

    def refuse(self, raw, number, changes, message):
        changed = bytearray(raw)
        for position, value in changes:
            changed[position:position + len(value)] = value
        with self.assertRaisesRegex(ValueError, message):
            policy.Ext4(changed).contents(number)

    def test_actual_leading_middle_trailing_allholes_empty_and_dense_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root, raw, files = self.fixture(directory)
            image = policy.Ext4(raw)
            paths = image.paths()
            expected_extents = {
                "leading": [(1, 1)], "middle": [(0, 1), (2, 1)],
                "trailing": [(0, 1)], "allholes": [], "empty": [],
                "pwd-shape": [(0, 11)], "dense": [(0, 2)],
                "four-extents": [(0, 1), (2, 1), (4, 1), (6, 1)],
            }
            normalized = policy.Ext4(policy.normalize_bootstrap_root(raw, root))
            for name, content in files.items():
                with self.subTest(name=name):
                    number = paths["/" + name]
                    offset = image.inode(number)
                    extents = [(image.u32(offset + 52 + index * 12),
                                image.u16(offset + 56 + index * 12))
                               for index in range(image.u16(offset + 42))]
                    self.assertEqual(extents, expected_extents[name])
                    self.assertEqual(image.contents(number), content)
                    self.assertEqual(normalized.contents(number), content)
                    metadata = normalized.metadata(number)
                    self.assertEqual((metadata["mode"], metadata["uid"], metadata["gid"]),
                                     (0o100644, 0, 0))

    @unittest.skipUnless(shutil.which("e2fsck"), "ext4 consistency tool unavailable")
    def test_normalized_actual_sparse_image_passes_readonly_fsck(self):
        with tempfile.TemporaryDirectory() as directory:
            root, raw, _ = self.fixture(directory)
            image = Path(directory) / "normalized.img"
            image.write_bytes(policy.normalize_bootstrap_root(raw, root))
            subprocess.run(["e2fsck", "-fn", str(image)], check=True, capture_output=True)

    def test_unsorted_and_overlapping_logical_extents_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            _, raw, _ = self.fixture(directory)
            _, number, _, first = self.extent_offsets(raw, "/middle")
            changes = (
                ((first, raw[first + 12:first + 24]), (first + 12, raw[first:first + 12])),
                ((first + 12, struct.pack("<I", 0)),),
            )
            for change in changes:
                with self.subTest(changes=change):
                    self.refuse(raw, number, change, "sorted nonoverlapping logical extents")

    def test_logical_overflow_and_extent_past_eof_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            _, raw, _ = self.fixture(directory)
            _, number, _, first = self.extent_offsets(raw, "/dense")
            self.refuse(raw, number, [(first, struct.pack("<I", 0xffffffff))],
                        "logical extents without overflow")
            self.refuse(raw, number, [(first, struct.pack("<I", 1))],
                        "logical extent within rounded-up inode size")
            self.refuse(raw, number, [(first + 4, struct.pack("<H", 3))],
                        "logical extent within rounded-up inode size")

    def test_zero_and_unwritten_lengths_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            _, raw, _ = self.fixture(directory)
            _, number, _, first = self.extent_offsets(raw, "/dense")
            for length in (0, 32769, 65535):
                with self.subTest(length=length):
                    self.refuse(raw, number, [(first + 4, struct.pack("<H", length))],
                                "bounded initialized extent length")

    def test_initialized_32768_length_reaches_subsequent_file_range_check(self):
        with tempfile.TemporaryDirectory() as directory:
            _, raw, _ = self.fixture(directory)
            _, number, _, first = self.extent_offsets(raw, "/dense")
            # This length is initialized, but does not fit this small file.
            self.refuse(raw, number, [(first + 4, struct.pack("<H", 32768))],
                        "logical extent within rounded-up inode size")

    def test_physical_zero_outside_volume_and_end_overflow_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            _, raw, _ = self.fixture(directory)
            image, number, _, first = self.extent_offsets(raw, "/dense")
            changes = (
                [(first + 8, struct.pack("<I", 0))],
                [(first + 8, struct.pack("<I", image.blocks))],
                [(first + 8, struct.pack("<I", image.blocks - 1))],
                [(first + 6, struct.pack("<H", 65535)),
                 (first + 8, struct.pack("<I", 0xffffffff))],
            )
            for change in changes:
                with self.subTest(changes=change):
                    self.refuse(raw, number, change, "bounded physical extent without overflow")

    def test_file_size_high_bits_and_image_size_bound_refuse_before_allocation(self):
        with tempfile.TemporaryDirectory() as directory:
            _, raw, _ = self.fixture(directory)
            _, number, offset, _ = self.extent_offsets(raw, "/dense")
            for change in ([(offset + 4, struct.pack("<I", len(raw) + 1))],
                           [(offset + 108, struct.pack("<I", 0xffffffff))]):
                with self.subTest(changes=change):
                    self.refuse(raw, number, change, "bounded plain extent count and file size")

    def test_extent_header_capacity_depth_and_magic_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            _, raw, _ = self.fixture(directory)
            _, number, offset, _ = self.extent_offsets(raw, "/four-extents")
            changes = (
                (offset + 42, struct.pack("<H", 5), "bounded plain extent count"),
                (offset + 44, struct.pack("<H", 3), "bounded plain extent count"),
                (offset + 44, struct.pack("<H", 5), "bounded plain extent count"),
                (offset + 46, struct.pack("<H", 1), "depth-zero initialized extents"),
                (offset + 40, struct.pack("<H", 0), "depth-zero initialized extents"),
                (offset + 32, struct.pack("<I", 0), "depth-zero initialized extents"),
            )
            for position, value, message in changes:
                with self.subTest(position=position, value=value):
                    self.refuse(raw, number, [(position, value)], message)

    def test_unknown_inode_type_refuses_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            _, raw, _ = self.fixture(directory)
            _, number, offset, _ = self.extent_offsets(raw, "/dense")
            self.refuse(raw, number, [(offset, struct.pack("<H", 0o020644))],
                        "only dense directory or sparse regular-file contents")

    def test_allocated_extent_on_empty_file_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            _, raw, _ = self.fixture(directory)
            _, number, offset, first = self.extent_offsets(raw, "/empty")
            self.refuse(raw, number, [(offset + 42, struct.pack("<H", 1)),
                        (first, struct.pack("<IHHI", 0, 1, 0, 1))],
                        "logical extent within rounded-up inode size")

    def test_directory_zero_unaligned_leading_middle_and_trailing_holes_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            _, raw, _ = self.fixture(directory)
            image, number, offset, first = self.extent_offsets(raw, "/lost+found")
            self.assertEqual(image.metadata(number)["size"], self.block * 4)
            self.assertEqual(image.u16(first + 4), 4)
            physical = image.u32(first + 8)
            changes = (
                ([(offset + 4, struct.pack("<I", 0))], "positive block-aligned dense directory size"),
                ([(offset + 4, struct.pack("<I", self.block - 1))], "positive block-aligned dense directory size"),
                ([(first, struct.pack("<I", 1)), (first + 4, struct.pack("<H", 3))],
                 "dense directory extents without holes"),
                ([(offset + 42, struct.pack("<H", 2)), (first + 4, struct.pack("<H", 1)),
                  (first + 12, struct.pack("<IHHI", 2, 2, 0, physical + 2))],
                 "dense directory extents without holes"),
                ([(first + 4, struct.pack("<H", 3))], "complete dense directory block coverage"),
                ([(offset + 42, struct.pack("<H", 0))], "complete dense directory block coverage"),
            )
            for change, message in changes:
                with self.subTest(message=message):
                    self.refuse(raw, number, change, message)

    def test_missing_or_corrupted_nonzero_data_refuses_exact_staging_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            root, raw, _ = self.fixture(directory)
            image, _, offset, first = self.extent_offsets(raw, "/leading")
            physical = image.u32(first + 8)
            for position, value in ((offset + 42, struct.pack("<H", 0)),
                                    (physical * self.block, b"X")):
                with self.subTest(position=position):
                    changed = bytearray(raw)
                    changed[position:position + len(value)] = value
                    with self.assertRaisesRegex(ValueError, "exact staged bytes before guest metadata policy"):
                        policy.normalize_bootstrap_root(changed, root)

    def test_new_nonzero_staged_byte_in_hole_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            root, raw, files = self.fixture(directory)
            for name in ("leading", "middle", "trailing", "allholes", "pwd-shape"):
                with self.subTest(name=name):
                    original = files[name]
                    position = original.index(b"\x00")
                    changed = bytearray(original)
                    changed[position] = 1
                    (root / name).write_bytes(changed)
                    with self.assertRaisesRegex(ValueError, "exact staged bytes before guest metadata policy"):
                        policy.normalize_bootstrap_root(raw, root)
                    (root / name).write_bytes(original)


if __name__ == "__main__":
    unittest.main()

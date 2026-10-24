"""Reject incomplete guest claims and wrong independently read inode fields."""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from mkdir_evidence import GROUP_ID, check_metadata, creation_slots, expected_nodes


class CreationEvidenceTests(unittest.TestCase):
    def test_two_distinct_complete_ordered_runs(self):
        first = b"OK_MUSL_MKDIR slot=0 mkdir=pass mkdirat=pass modes=offline inheritance=offline copies=pass dirfd=pass errors=pass readdir=pass\n"
        second = first.replace(b"slot=0", b"slot=1")
        for value in (first + second, (first + second).replace(b"\n", b"\r\n")):
            self.assertEqual(creation_slots(value), [0, 1])
        for value in (first, first * 2, second + first, first + second + first,
                      first + second[:-1], (first + second).replace(b"copies=pass", b"copies=fail"),
                      first + second.replace(b"slot=1", b"slot=2")):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                creation_slots(value)

    def test_fields_are_verified_independently(self):
        record = f"Inode: 123 Type: directory Mode: 03750 Flags: 0x80000\nUser: 0 Group: {GROUP_ID} Size: 4096\nLinks: 3 Blockcount: 8\n"
        expected = ("directory", 0o3750, 0, GROUP_ID, 3)
        self.assertEqual(check_metadata(record, expected), 123)
        for old, new in (("123", "0"), ("directory", "regular"), ("03750", "01750"),
                         ("User: 0", "User: 1"), (str(GROUP_ID), str(GROUP_ID & 0xffff)),
                         ("Links: 3", "Links: 2"), ("Links:", "Missing:")):
            with self.subTest(old=old), self.assertRaises(RuntimeError):
                check_metadata(record.replace(old, new), expected)

    def test_expected_output_includes_files_and_directory_links(self):
        nodes = expected_nodes()
        self.assertEqual(len(nodes), 19)
        self.assertEqual(nodes["/home/musl-mkdir-sgid"][4], 4)
        self.assertEqual(nodes["/home/musl-mkdir-0"][4], 6)
        self.assertEqual(nodes["/home/musl-mkdir-sgid/run-1/data"],
                         ("regular", 0o640, 0, GROUP_ID, 1, b"group"))

    def test_debugfs_signed_owner_presentation_preserves_all_32_bits(self):
        record = "Inode: 25 Type: directory Mode: 02777 Flags: 0x80000\nUser: 0 Group: -2023406815 Project: 0 Size: 4096\nLinks: 4 Blockcount: 8\n"
        self.assertEqual(check_metadata(record, ("directory", 0o2777, 0, GROUP_ID, 4)), 25)
        for signed, unsigned in ((-2147483648, 2147483648), (-1, 4294967295),
                                 (0, 0), (2147483647, 2147483647), (4294967295, 4294967295)):
            for owner in ("User", "Group"):
                changed = record.replace("User: 0", f"User: {signed}") if owner == "User" else record.replace("Group: -2023406815", f"Group: {signed}")
                expected = ("directory", 0o2777, unsigned if owner == "User" else 0,
                            unsigned if owner == "Group" else GROUP_ID, 4)
                with self.subTest(owner=owner, signed=signed):
                    self.assertEqual(check_metadata(changed, expected), 25)
        for value in (-2147483649, 4294967296, 8589934591):
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, "exceeds 32 bits"):
                check_metadata(record.replace("Group: -2023406815", f"Group: {value}"),
                               ("directory", 0o2777, 0, value & 0xffffffff, 4))

    @unittest.skipUnless(all(shutil.which(tool) for tool in ("mke2fs", "e2fsck", "debugfs")),
                         "ext4 fixture tools unavailable")
    def test_old_and_new_gates_prepare_real_fixture_before_guest(self):
        # Exercise private image preparation, not ELF loading or guest execution.
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
        import test_musl_userland as runner
        original_popen = runner.subprocess.Popen
        class PreparedBeforeGuest(Exception):
            pass
        with tempfile.TemporaryDirectory(prefix="ok-mkdir-runner-fixture-") as directory:
            work = Path(directory)
            root = work / "root"
            (root / "bin").mkdir(parents=True)
            (root / "home").mkdir()
            probe = work / "probe"
            probe.mkdir()
            linux_elf = bytearray(16)
            linux_elf[7] = 3
            (probe / "bootstrap.elf").write_bytes(linux_elf)
            (probe / "manifest.json").write_text(json.dumps({
                "architecture": "x86_64", "musl": "1.2.5", "status": "built-not-executed",
                "elf_sha256": hashlib.sha256(linux_elf).hexdigest()}))
            native = work / "runner.elf"
            # Keep an allocated native-personality fixture: an all-zero file
            # becomes a sparse extent which the bootstrap image profile rejects.
            native.write_bytes(b"\x7fELF" + bytes(12))
            kernel = work / "kernel.bin"
            kernel.write_bytes(b"fixture preparation only")
            qemu = work / "never-executed-qemu"
            qemu.write_bytes(b"fixture preparation stops before execution")
            def stop_at_guest(command, *args, **kwargs):
                if str(command[0]) == str(qemu):
                    raise PreparedBeforeGuest()
                return original_popen(command, *args, **kwargs)
            for flag in ("--require-realtime", "--require-mkdir"):
                output = work / flag[2:]
                arguments = ["test_musl_userland.py", "--arch", "x86_64", "--qemu", str(qemu),
                             "--kernel", str(kernel), "--rootfs-tree", str(root), "--probe", str(probe),
                             "--runner", str(native), "--out", str(output), flag]
                with self.subTest(flag=flag), patch.object(sys, "argv", arguments), \
                        patch.object(runner, "inspect_elf"), \
                        patch.object(runner.subprocess, "Popen", side_effect=stop_at_guest), \
                        self.assertRaises(PreparedBeforeGuest):
                    runner.main()
                check_metadata((output / "mkdir-fixture.stat.log").read_text(),
                               ("directory", 0o2777, 0, GROUP_ID, 2))
                self.assertTrue((output / "kernel-input.bin").is_file())

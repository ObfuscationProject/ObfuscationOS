"""A kernel boot marker must not hide a failed distribution extension."""

import contextlib
import importlib.util
import io
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


source = Path(__file__).resolve().parents[2] / "scripts/qemu_distro.py"
spec = importlib.util.spec_from_file_location("qemu_distro", source)
distro = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distro)


class DistroMarkerTests(unittest.TestCase):
    def test_failure_preserves_guest_disk_without_mutating_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            qemu, kernel, disk = (root / name for name in ("qemu", "kernel.bin", "root.img"))
            for path in (qemu, kernel, disk):
                path.write_bytes(b"pristine")
            failed = root / "failure"

            def failed_guest(command, *args):
                attached = next(value for value in command if value.startswith("file=") and ",if=none" in value)
                Path(attached[5:].split(",")[0]).write_bytes(b"guest mutation")
                return 124

            argv = ["qemu_distro", "--arch", "loongarch64", "--qemu", str(qemu),
                    "--kernel", str(kernel), "--rootfs", str(disk), "--fs", "ext4",
                    "--failure-dir", str(failed)]
            with patch.object(sys, "argv", argv), patch.object(distro, "run_until_marker", failed_guest), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(distro.main(), 124)
            self.assertEqual(disk.read_bytes(), b"pristine")
            self.assertEqual((failed / "root.img").read_bytes(), b"guest mutation")
            result = json.loads((failed / "result.json").read_text())
            self.assertEqual(result["disk_sha256"], hashlib.sha256(b"guest mutation").hexdigest())
            self.assertEqual(result["exit_code"], 124)

    def run_guest_output(self, lines, native=False, storage=False, journalled=False):
        # The script deliberately uses real pipes/process exit, including the
        # case where a core marker is followed by an extension failure.
        code = "import os\n"
        code += "\n".join(f"os.write(1, {line.encode()!r})" for line in lines)
        with contextlib.redirect_stdout(io.StringIO()):
            return distro.run_until_marker([sys.executable, "-u", "-c", code], 1.0,
                                           native, storage, journalled)

    def test_native_run_requires_actual_userland_and_preemption(self):
        gui = "OK_SYSTEM_GUI boot=complete\n"
        user = "OK_USERLAND scope=hardware acceptance=pass shell_pipeline=pass\n"
        timer = "OK_NATIVE scope=hardware timer=preempted\n"
        paths = "OK_PATH scope=hardware relative_exec=pass symlink=pass\n"
        vm = "OK_VM_NATIVE scope=hardware map=pass zero=pass protect=pass unmap=pass fork=pass pressure=pass\n"
        paged_vm = "OK_VM_PAGED scope=hardware pages=192 fork=pass none=pass remap=pass rollback=pass cleanup=pass\n"
        shared_vm = "OK_VM_SHARED scope=hardware fork=pass private_isolation=pass protect=pass none=pass partial_unmap=pass fixed=pass exec_exit=pass pressure=pass cleanup=pass\n"
        clock = "OK_TIME_NATIVE scope=hardware monotonic=pass sleep=pass absolute=pass sibling=pass validation=pass\n"
        sleep = "OK_SLEEP_NATIVE scope=hardware sole_sleeper=pass\n"
        poll = "OK_POLL_NATIVE scope=hardware nonblock=pass readiness=pass timeout=pass wake=pass peer_close=pass\n"
        quota = "OK_VM_QUOTA scope=hardware resource=address-space refused=enomem restored=pass\n"
        fork_copy = ("OK_VM_FORK_COPY scope=hardware parent_store=pass parent_kernel_copy=pass "
                     "child_kernel_copy=pass child_store=pass\n")
        self.assertEqual(self.run_guest_output([gui], native=True), 124)
        self.assertEqual(self.run_guest_output([gui, user], native=True), 124)
        self.assertEqual(self.run_guest_output([gui, timer, user], native=True), 124)
        self.assertEqual(self.run_guest_output([gui, paths, timer, user], native=True), 124)
        self.assertEqual(self.run_guest_output([gui, paths, vm, timer, user], native=True), 124)
        self.assertEqual(self.run_guest_output([gui, paths, vm, timer, user, clock], native=True), 124)
        self.assertEqual(self.run_guest_output([gui, paths, vm, timer, user, clock, sleep], native=True), 124)
        self.assertEqual(self.run_guest_output([gui, paths, vm, timer, user, clock, sleep, poll], native=True), 124)
        self.assertEqual(self.run_guest_output([gui, paths, vm, paged_vm, timer, user, clock, sleep, poll], native=True), 124)
        # The pressure phase must have run against a real per-process quota.
        self.assertEqual(self.run_guest_output([gui, paths, vm, paged_vm, shared_vm, timer, user, clock, sleep, poll], native=True), 124)
        self.assertEqual(self.run_guest_output([gui, paths, vm, paged_vm, shared_vm, quota, timer, user, clock, sleep, poll], native=True), 124)
        # Both directions of fork private-page isolation must have been observed.
        self.assertEqual(self.run_guest_output([gui, paths, vm, paged_vm, shared_vm, quota, fork_copy, timer, user, clock, sleep, poll], native=True), 0)
        self.assertEqual(self.run_guest_output([gui, "POSIX_CHECK failed: fork\n"], native=True), 1)

    def test_symlink_gap_is_rejected_on_every_filesystem(self):
        lines = ["OK_SYSTEM_GUI boot=complete\n",
                 "OK_USERLAND scope=hardware acceptance=pass shell_pipeline=pass\n",
                 "OK_NATIVE scope=hardware timer=preempted\n",
                 "OK_TIME_NATIVE scope=hardware monotonic=pass sleep=pass absolute=pass sibling=pass validation=pass\n",
                 "OK_SLEEP_NATIVE scope=hardware sole_sleeper=pass\n",
                 "OK_POLL_NATIVE scope=hardware nonblock=pass readiness=pass timeout=pass wake=pass peer_close=pass\n",
                 "OK_VM_NATIVE scope=hardware map=pass zero=pass protect=pass unmap=pass fork=pass pressure=pass\n",
                 "OK_PATH scope=hardware relative_exec=pass symlink=unsupported-filesystem\n",
                 "OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\n"]
        self.assertEqual(self.run_guest_output(lines, native=True), 124)
        self.assertEqual(self.run_guest_output(lines, native=True, storage=True), 124)

    def test_ext4_requires_a_real_storage_mount(self):
        gui = "OK_SYSTEM_GUI boot=complete\n"
        mounted = "OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\n"
        file_private = "OK_VM_FILE_PRIVATE scope=hardware ext4=pass offset=pass short_length=pass tail_zero=pass errno=pass unlink=pass private_write=pass fork=pass\n"
        self.assertEqual(self.run_guest_output([gui], storage=True), 124)
        self.assertEqual(self.run_guest_output([gui, mounted], storage=True), 124)
        self.assertEqual(self.run_guest_output([gui, mounted, file_private], storage=True), 0)
        self.assertEqual(self.run_guest_output([gui, "OK_STORAGE source=archive reason=non-ext4-media\n"], storage=True), 1)

    def test_journalled_profile_requires_its_exact_mount_marker(self):
        gui = "OK_SYSTEM_GUI boot=complete\n"
        legacy = "OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\n"
        journalled = "OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=ordered-data\n"
        file_private = "OK_VM_FILE_PRIVATE scope=hardware ext4=pass offset=pass short_length=pass tail_zero=pass errno=pass unlink=pass private_write=pass fork=pass\n"
        self.assertEqual(self.run_guest_output([gui, legacy, file_private], storage=True, journalled=True), 124)
        self.assertEqual(self.run_guest_output([gui, journalled, file_private], storage=True, journalled=True), 0)

    def test_all_profiles_have_native_qemu_commands(self):
        arches = ("i386", "x86_64", "arm32", "aarch64", "rv32", "rv64", "loongarch64", "mips", "mips64", "ppc")
        for arch in arches:
            command = distro.command_for(Path("qemu"), arch, Path("kernel.bin"), Path("root.img"), "none")
            self.assertIn("stdio", command)
            self.assertEqual(command.count("rng-random,id=entropy0,filename=/dev/urandom"), 1)
            self.assertEqual(command.count("-object"), 1)
            if arch in {"arm32", "aarch64", "rv32", "rv64"}:
                self.assertIn("virtio-blk-device,drive=fsdisk", command)
                self.assertEqual(command.count("virtio-mmio.force-legacy=false"), 1)
                self.assertEqual(command.count("virtio-rng-device,rng=entropy0"), 1)
            else:
                self.assertNotIn("virtio-mmio.force-legacy=false", command)
                self.assertEqual(command.count("virtio-rng-pci-non-transitional,rng=entropy0"), 1)
            if arch == "i386":
                self.assertIn("max", command)
            if arch == "ppc":
                self.assertNotIn("-cpu", command)
                self.assertNotIn("-smp", command)
                self.assertNotIn("-accel", command)

    def test_explicit_no_entropy_controls_have_no_rng_device(self):
        arches = ("i386", "x86_64", "arm32", "aarch64", "rv32", "rv64", "loongarch64", "mips", "mips64", "ppc")
        for arch in arches:
            with self.subTest(arch=arch):
                command = distro.command_for(Path("qemu"), arch, Path("kernel.bin"), Path("root.img"), "none",
                                             entropy="none")
                self.assertNotIn("-object", command)
                self.assertFalse(any("virtio-rng" in item for item in command))
                self.assertEqual(command.count("virtio-mmio.force-legacy=false"),
                                 int(arch in {"arm32", "aarch64", "rv32", "rv64"}))
        with self.assertRaisesRegex(ValueError, "entropy"):
            distro.command_for(Path("qemu"), "ppc", Path("kernel.bin"), Path("root.img"), "none",
                               entropy="invalid")

    def test_explicit_native_ppc_profile_has_one_cpu_selection(self):
        command = distro.command_for(Path("qemu"), "ppc", Path("kernel.bin"), Path("root.img"), "none",
                                     native_profile=True)
        self.assertEqual(command.count("-cpu"), 1)
        self.assertEqual(command[command.index("-cpu") + 1], "e500v2_v22")
        self.assertEqual(command.count("-smp"), 1)
        self.assertEqual(command[command.index("-smp") + 1], "1")
        self.assertEqual(command.count("-accel"), 1)
        self.assertEqual(command[command.index("-accel") + 1], "tcg,thread=single")

    def test_core_boot_does_not_complete_distro_validation(self):
        self.assertEqual(self.run_guest_output(["OK_DEBUG boot=complete\n"]), 124)

    def test_core_test_pass_does_not_complete_distro_validation(self):
        self.assertEqual(self.run_guest_output(["OK_TEST_PASS arch=x86_64\n"]), 124)

    def test_extension_failure_is_not_reported_as_success(self):
        self.assertEqual(self.run_guest_output(["OK_TEST_FAIL extension-start=failed\n"]), 1)

    def test_release_extension_failure_is_detected(self):
        self.assertEqual(self.run_guest_output(["OK_BOOT_EXTENSION boot=failed\n"]), 1)

    def test_os_completion_marker_passes(self):
        self.assertEqual(self.run_guest_output(["OK_SYSTEM_GUI boot=complete\n"]), 0)

    def test_markers_in_one_pipe_chunk_are_drained(self):
        self.assertEqual(self.run_guest_output([
            "OK_DEBUG boot=complete\nOK_TEST_PASS arch=x86_64\nOK_SYSTEM_GUI boot=complete\n"
        ]), 0)

    def test_failure_after_core_boot_is_detected(self):
        self.assertEqual(self.run_guest_output([
            "OK_DEBUG boot=complete\nOK_TEST_PASS arch=x86_64\nOK_TEST_FAIL extension-start=failed\n"
        ]), 1)


if __name__ == "__main__":
    unittest.main()

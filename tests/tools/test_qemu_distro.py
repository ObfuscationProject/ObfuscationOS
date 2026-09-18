"""A kernel boot marker must not hide a failed distribution extension."""

import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest


source = Path(__file__).resolve().parents[2] / "scripts/qemu_distro.py"
spec = importlib.util.spec_from_file_location("qemu_distro", source)
distro = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distro)


class DistroMarkerTests(unittest.TestCase):
    def run_guest_output(self, lines):
        # The script deliberately uses real pipes/process exit, including the
        # case where a core marker is followed by an extension failure.
        code = "import os\n"
        code += "\n".join(f"os.write(1, {line.encode()!r})" for line in lines)
        with contextlib.redirect_stdout(io.StringIO()):
            return distro.run_until_marker([sys.executable, "-u", "-c", code], 1.0)

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

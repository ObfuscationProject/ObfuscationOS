"""Closed connected fixture selector controls with synthetic ELF; no build or guest."""
from pathlib import Path
import json
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests/tools"))
import package_musl_udp_fixture as package
import test_musl_udp_sockname_package as reference
from build_musl_probe import capture_compile_dependencies


class ConnectedSelectorControls(unittest.TestCase):
    def helper(self):
        # Keep the inherited test class inside its defining module so unittest
        # discovery does not collect its tests a second time from this module.
        return reference.SelectorControls(methodName="runTest")

    def test_connected_selector_admits_only_its_unchanged_source(self):
        helper = self.helper()
        with tempfile.TemporaryDirectory() as directory:
            build, musl, value, musl_value = helper.inputs(Path(directory), "udp-connected")
            self.assertEqual(helper.admit(build, musl, musl_value, "udp-connected"), value)
            for fixture in (None, "udp", "udp-sockname"):
                with self.subTest(fixture=fixture), self.assertRaisesRegex(ValueError, "manifest differs"):
                    helper.admit(build, musl, musl_value, fixture)
        for old in ("udp", "udp-sockname"):
            with tempfile.TemporaryDirectory() as directory:
                build, musl, _, musl_value = helper.inputs(Path(directory), old)
                with self.assertRaisesRegex(ValueError, "manifest differs"):
                    helper.admit(build, musl, musl_value, "udp-connected")

    def test_actual_dependency_and_producing_command_must_select_connected_source(self):
        helper = self.helper()
        for old in ("tests/musl/udp.c", "tests/musl/udp_sockname.c"):
            with tempfile.TemporaryDirectory() as directory:
                build, musl, value, musl_value = helper.inputs(Path(directory), "udp-connected")
                source = ROOT / old
                depfile = build / "probe.d"; depfile.write_text("musl-probe-object: " + str(source.resolve()) + "\n")
                value["compile_dependencies"] = capture_compile_dependencies(depfile, source, build)
                helper.write_manifest(build, value)
                with self.subTest(old=old), self.assertRaisesRegex(ValueError, "dependencies omit"):
                    helper.admit(build, musl, musl_value, "udp-connected")
        with tempfile.TemporaryDirectory() as directory:
            build, musl, value, musl_value = helper.inputs(Path(directory), "udp-connected")
            value["commands"][0] = ["synthetic-compiler", "-MD", str(ROOT / "tests/musl/udp.c")]
            helper.write_manifest(build, value)
            with self.assertRaisesRegex(ValueError, "producing command"):
                helper.admit(build, musl, musl_value, "udp-connected")

    def test_manifest_source_mode_linker_capture_and_elf_hash_refusals(self):
        helper = self.helper()
        for mutation in ("source", "mode", "architecture", "linker", "musl", "status", "executed",
                         "dependencies", "same-command", "command-index", "command-count", "no-MD",
                         "elf-hash", "changed-depfile"):
            with tempfile.TemporaryDirectory() as directory:
                build, musl, value, musl_value = helper.inputs(Path(directory), "udp-connected")
                if mutation == "source": value["probe_sha256"] = "0" * 64
                elif mutation == "mode": value["mode"] = "release"
                elif mutation == "architecture": value["architecture"] = "aarch64"
                elif mutation == "linker": value["linker_script_sha256"] = "0" * 64
                elif mutation == "musl": value["source_manifest_sha256"] = "0" * 64
                elif mutation == "status": value["status"] = "executed"
                elif mutation == "executed": value["executed"] = True
                elif mutation == "dependencies": del value["compile_dependencies"]
                elif mutation == "same-command": value["compile_dependencies"]["same_command_as_object"] = False
                elif mutation == "command-index": value["compile_dependencies"]["command_index"] = 1
                elif mutation == "command-count": value["commands"].pop()
                elif mutation == "no-MD": value["commands"][0].remove("-MD")
                elif mutation == "elf-hash": value["elf_sha256"] = "0" * 64
                elif mutation == "changed-depfile": (build / "probe.d").write_text("changed.o: changed.c\n")
                helper.write_manifest(build, value)
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    helper.admit(build, musl, musl_value, "udp-connected")

    def test_selected_manifest_pin_cannot_be_substituted(self):
        helper = self.helper()
        with tempfile.TemporaryDirectory() as directory:
            build, musl, _, musl_value = helper.inputs(Path(directory), "udp-connected")
            for child_pin, musl_pin in (("0" * 64, package.sha(musl / "manifest.json")),
                                        (package.sha(build / "manifest.json"), "0" * 64)):
                with patch.object(package, "admit_musl_build", return_value=musl_value), self.assertRaises(ValueError):
                    package.admit_child(build, child_pin, musl, musl_pin, "x86_64", "debug", "udp-connected")

    def test_static_elf_personality_machine_dynamic_extent_and_entry_refusals(self):
        helper = self.helper()
        for mutation in ("native-personality", "wrong-machine", "dynamic", "interpreter", "extent", "entry"):
            with tempfile.TemporaryDirectory() as directory:
                build, musl, value, musl_value = helper.inputs(Path(directory), "udp-connected")
                blob = bytearray((build / "bootstrap.elf").read_bytes())
                if mutation == "native-personality": blob[7] = 0
                elif mutation == "wrong-machine": struct.pack_into("<H", blob, 18, 183)
                elif mutation == "dynamic": struct.pack_into("<I", blob, 64, 2)
                elif mutation == "interpreter": struct.pack_into("<I", blob, 64, 3)
                elif mutation == "extent": struct.pack_into("<Q", blob, 96, 2)
                elif mutation == "entry": struct.pack_into("<Q", blob, 24, 0x2000)
                (build / "bootstrap.elf").write_bytes(blob)
                value["elf_sha256"] = package.sha(build / "bootstrap.elf")
                helper.write_manifest(build, value)
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    helper.admit(build, musl, musl_value, "udp-connected")

    def test_connected_archive_changes_only_init_and_explicit_child(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            output, receipt = self.helper().package_fixture(base, "udp-connected")
            self.assertEqual(receipt["fixture"], "udp-connected")
            self.assertEqual(receipt["inputs_before"]["probe_source"]["path"], str(ROOT / "tests/musl/udp_connected.c"))
            self.assertEqual(receipt["inputs_before"]["native_parent_source"]["path"],
                             str(ROOT / "tests/native/musl_udp_connected_runner.c"))
            self.assertEqual(Path(receipt["copied_child"]["path"]).name, "musl-udp-connected-probe")
            archived = package.inspect_archive((output / "boot.okar").read_bytes())
            self.assertEqual(archived, receipt["archive_entries"])
            self.assertEqual(set(archived), {"/bin", "/bin/keep", "/bin/musl-udp-connected-probe", "/init", "/tmp"})
            self.assertEqual(archived["/bin/keep"]["sha256"], package.sha(base / "normal/bin/keep"))
            self.assertEqual(archived["/init"]["sha256"], package.sha(base / "parent.elf"))
            self.assertEqual(archived["/bin/musl-udp-connected-probe"]["sha256"], package.sha(base / "child/bootstrap.elf"))
            self.assertEqual(archived["/tmp"]["mode"], 0o041777)
            self.assertEqual(receipt["root_entries"]["/tmp"]["mode"], 0o041777)
            self.assertEqual(receipt["inputs_before"], receipt["inputs_after"])
            self.assertFalse(receipt["guest_executed"])

    def test_default_original_and_explicit_original_archives_remain_equal(self):
        blobs = []
        for explicit in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                output, receipt = self.helper().package_fixture(Path(directory), "udp", explicit=explicit)
                self.assertNotIn("fixture", receipt)
                self.assertEqual(Path(receipt["copied_child"]["path"]).name, "musl-udp-probe")
                blobs.append((output / "boot.okar").read_bytes())
        self.assertEqual(*blobs)

    def test_unknown_or_path_substitution_refuses_before_output(self):
        for fixture in ("../udp-connected", "/tmp/udp_connected.c", "udp-connected-extra", "UDP-CONNECTED"):
            with self.subTest(fixture=fixture), self.assertRaises(ValueError): package.fixture_spec(fixture)
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "out"
                argv = ["package", "--fixture", fixture, "--arch=x86_64", "--mode=debug",
                        "--normal-root=missing", "--native-parent=missing", "--child-build=missing",
                        "--child-manifest-sha256=" + "0" * 64, "--musl-build=missing",
                        "--musl-manifest-sha256=" + "0" * 64, "--out", str(output)]
                with patch.object(sys, "argv", argv), patch("sys.stderr"), self.assertRaises(SystemExit) as refused:
                    package.main()
                self.assertEqual(refused.exception.code, 2)
                self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()

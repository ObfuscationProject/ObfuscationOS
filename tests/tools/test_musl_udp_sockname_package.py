"""Hosted closed-selector controls with synthetic ELF/manifests, no compilation."""
from pathlib import Path
import json
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import package_musl_udp_fixture as package
from build_musl_probe import capture_compile_dependencies


def static_elf(osabi):
    blob = bytearray(121); blob[:9] = b"\x7fELF\x02\x01\x01" + bytes((osabi, 0))
    struct.pack_into("<HHIQQ", blob, 16, 2, 62, 1, 0x1000, 64)
    struct.pack_into("<HHH", blob, 52, 64, 56, 1)
    struct.pack_into("<IIQQQQQQ", blob, 64, 1, 5, 120, 0x1000, 0, 1, 1, 1)
    return bytes(blob)


class SelectorControls(unittest.TestCase):
    def inputs(self, base, fixture):
        source = ROOT / package.fixture_spec(fixture)[0]
        build, musl = base / "child", base / "musl"
        build.mkdir(); musl.mkdir()
        child = build / "bootstrap.elf"; child.write_bytes(static_elf(3))
        musl_manifest = {"mode": "debug"}
        (musl / "manifest.json").write_text(json.dumps(musl_manifest))
        depfile = build / "probe.d"; depfile.write_text("musl-probe-object: " + str(source.resolve()) + "\n")
        dependencies = capture_compile_dependencies(depfile, source, build)
        manifest = {
            "schema_version": 1, "architecture": "x86_64", "mode": "debug",
            "status": "built-not-executed", "executed": False,
            "source_manifest_sha256": package.sha(musl / "manifest.json"),
            "probe_sha256": package.sha(source), "linker_script_sha256": package.sha(ROOT / "tests/musl/bootstrap.ld"),
            "elf_sha256": package.sha(child), "compile_dependencies": dependencies,
            "commands": [["synthetic-compiler", "-MD", str(source.resolve())], ["synthetic-link"], ["synthetic-stamp"]],
        }
        self.write_manifest(build, manifest)
        return build, musl, manifest, musl_manifest

    def write_manifest(self, build, manifest):
        (build / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))

    def admit(self, build, musl, musl_manifest, fixture=None):
        with patch.object(package, "admit_musl_build", return_value=musl_manifest):
            args = (build, package.sha(build / "manifest.json"), musl,
                    package.sha(musl / "manifest.json"), "x86_64", "debug")
            return package.admit_child(*args) if fixture is None else package.admit_child(*args, fixture)

    def test_default_and_explicit_predecessor_both_admit_only_original_source(self):
        with tempfile.TemporaryDirectory() as directory:
            build, musl, value, musl_value = self.inputs(Path(directory), "udp")
            self.assertEqual(self.admit(build, musl, musl_value), value)
            self.assertEqual(self.admit(build, musl, musl_value, "udp"), value)
            with self.assertRaisesRegex(ValueError, "manifest differs"):
                self.admit(build, musl, musl_value, "udp-sockname")

    def test_new_selector_admits_only_new_source_and_requires_its_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            build, musl, value, musl_value = self.inputs(base, "udp-sockname")
            self.assertEqual(self.admit(build, musl, musl_value, "udp-sockname"), value)
            with self.assertRaisesRegex(ValueError, "manifest differs"):
                self.admit(build, musl, musl_value)
            # A manifest can claim the new hash while its retained producing
            # dependency file describes the original child. It must be refused.
            old_source = ROOT / "tests/musl/udp.c"
            depfile = build / "probe.d"; depfile.write_text("musl-probe-object: " + str(old_source.resolve()) + "\n")
            value["compile_dependencies"] = capture_compile_dependencies(depfile, old_source, build)
            self.write_manifest(build, value)
            with self.assertRaisesRegex(ValueError, "dependencies omit"):
                self.admit(build, musl, musl_value, "udp-sockname")

    def test_source_dependency_command_mode_and_elf_refusals(self):
        for mutation in ("source", "missing-dependencies", "not-same-command", "wrong-command-index",
                         "wrong-producing-command", "wrong-mode", "wrong-elf-hash", "changed-depfile"):
            with tempfile.TemporaryDirectory() as directory:
                build, musl, value, musl_value = self.inputs(Path(directory), "udp-sockname")
                if mutation == "source": value["probe_sha256"] = "0" * 64
                elif mutation == "missing-dependencies": del value["compile_dependencies"]
                elif mutation == "not-same-command": value["compile_dependencies"]["same_command_as_object"] = False
                elif mutation == "wrong-command-index": value["compile_dependencies"]["command_index"] = 1
                elif mutation == "wrong-producing-command": value["commands"][0] = ["synthetic-compiler", "-MD", str(ROOT / "tests/musl/udp.c")]
                elif mutation == "wrong-mode": value["mode"] = "release"
                elif mutation == "wrong-elf-hash": value["elf_sha256"] = "0" * 64
                elif mutation == "changed-depfile": (build / "probe.d").write_text("changed.o: changed.c\n")
                self.write_manifest(build, value)
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    self.admit(build, musl, musl_value, "udp-sockname")

    def package_fixture(self, base, fixture, *, explicit=True):
        build, musl, _, musl_value = self.inputs(base, fixture)
        normal = base / "normal"; normal.mkdir(); (normal / "bin").mkdir(); (normal / "tmp").mkdir()
        (normal / "tmp").chmod(0o1777); (normal / "init").write_bytes(b"normal-init")
        (normal / "bin/keep").write_bytes(b"normal-data")
        parent = base / "parent.elf"; parent.write_bytes(static_elf(0))
        output = base / "package"
        argv = ["package", "--arch=x86_64", "--mode=debug", "--normal-root", str(normal),
                "--native-parent", str(parent), "--child-build", str(build),
                "--child-manifest-sha256", package.sha(build / "manifest.json"), "--musl-build", str(musl),
                "--musl-manifest-sha256", package.sha(musl / "manifest.json"), "--out", str(output)]
        if explicit: argv.extend(("--fixture", fixture))
        before = package.inventory(normal)
        with patch.object(sys, "argv", argv), patch.object(package, "admit_musl_build", return_value=musl_value):
            self.assertEqual(package.main(), 0)
        record = json.loads((output / "receipt.json").read_bytes())
        self.assertEqual(package.inventory(normal), before)
        self.assertEqual(record["normal_root_before"], before)
        self.assertEqual(record["normal_root_after"], before)
        self.assertEqual(record["status"], "packaged-not-linked-or-executed")
        self.assertFalse(record["guest_executed"])
        return output, record

    def test_new_selector_packages_only_exact_two_payload_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            output, record = self.package_fixture(Path(directory), "udp-sockname")
            self.assertEqual(record["fixture"], "udp-sockname")
            self.assertEqual(record["inputs_before"]["probe_source"]["path"], str(ROOT / "tests/musl/udp_sockname.c"))
            self.assertEqual(record["inputs_before"]["native_parent_source"]["path"], str(ROOT / "tests/native/musl_udp_sockname_runner.c"))
            self.assertEqual(Path(record["copied_child"]["path"]).name, "musl-udp-sockname-probe")
            archived = package.inspect_archive((output / "boot.okar").read_bytes())
            self.assertEqual(archived, record["archive_entries"])
            self.assertEqual(set(archived), {"/bin", "/bin/keep", "/bin/musl-udp-sockname-probe", "/init", "/tmp"})
            self.assertEqual(archived["/tmp"]["mode"], 0o041777)
            self.assertEqual(record["root_entries"]["/tmp"]["mode"], 0o041777)

    def test_omitted_selector_retains_original_archive_and_receipt_fields(self):
        blobs = []
        for explicit in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                output, record = self.package_fixture(Path(directory), "udp", explicit=explicit)
                self.assertNotIn("fixture", record)
                self.assertEqual(record["inputs_before"]["probe_source"]["path"], str(ROOT / "tests/musl/udp.c"))
                self.assertEqual(record["inputs_before"]["native_parent_source"]["path"], str(ROOT / "tests/native/musl_udp_runner.c"))
                self.assertEqual(Path(record["copied_child"]["path"]).name, "musl-udp-probe")
                blobs.append((output / "boot.okar").read_bytes())
        self.assertEqual(blobs[0], blobs[1])

    def test_unknown_or_arbitrary_path_selector_is_refused_before_output(self):
        for fixture in ("unknown", "../udp", "/tmp/udp.c", "udp-sockname-extra"):
            with self.subTest(fixture=fixture), self.assertRaises(ValueError):
                package.fixture_spec(fixture)
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

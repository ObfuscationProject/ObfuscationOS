"""Rootfs profiles (full, rescue, release) and musl userland staging."""
import hashlib
import importlib.util
import json
import os
import stat
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import ports  # noqa: E402

spec = importlib.util.spec_from_file_location("stage_rootfs_profiles", ROOT / "tools/stage_rootfs.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def static_elf() -> bytes:
    """Minimal x86_64 ET_EXEC with one PT_LOAD, marked with the Linux personality."""
    header = bytearray(64 + 56)
    header[:9] = b"\x7fELF\x02\x01\x01\x03\x00"
    struct.pack_into("<HHIQQQIHHHHHH", header, 16, 2, 62, 1, 0x40000078, 64, 0, 0, 64, 56, 1, 64, 0, 0)
    struct.pack_into("<IIQQQQQQ", header, 64, 1, 5, 0, 0x40000000, 0x40000000, len(header), len(header), 4096)
    return bytes(header)


def userland_build(directory: Path, applets=("cat", "ls", "sh", "[")) -> tuple[Path, str]:
    from musl_source import inspect_elf
    busybox = ports.load()["busybox"]
    build = directory / "busybox-build"
    (build / "stage/bin").mkdir(parents=True)
    program = build / "stage/bin/busybox"
    program.write_bytes(static_elf())
    share = build / "stage/share/busybox"
    (share / "testsuite").mkdir(parents=True)
    (share / "testsuite/runtest").write_text("#!/bin/sh\n")
    (share / "testsuite/runtest").chmod(0o755)
    (share / ".config").write_text("CONFIG_ASH=y\n")
    (build / "stage/share/licenses/busybox").mkdir(parents=True)
    (build / "stage/share/licenses/busybox/LICENSE").write_text("GPL-2.0-only\n")
    files = {path.relative_to(build).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(build.rglob("*")) if path.is_file()}
    manifest = {"schema_version": 1, "name": "busybox", "version": busybox["version"],
                "archive_sha256": busybox["sha256"], "architecture": "x86_64", "mode": "debug",
                "status": "built-not-executed", "executed": False, "applets": sorted(applets),
                "elf": inspect_elf(program, "x86_64"), "elf_sha256": files["stage/bin/busybox"], "files": files}
    (build / "manifest.json").write_text(json.dumps(manifest))
    return build, hashlib.sha256((build / "manifest.json").read_bytes()).hexdigest()


class RootfsProfileTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        work = Path(self.scratch.name)
        self.project = work / "project"
        (self.project / "config").mkdir(parents=True)
        (self.project / "config/services.conf").write_bytes(b"OK_SERVICE_MANIFEST 1\nservice console simple /bin/oksh -\n")
        (self.project / "config/hosts").write_bytes(b"127.0.0.1 localhost\n")
        (self.project / "tests/userland").mkdir(parents=True)
        for script in stage.USERLAND_SCRIPTS:
            (self.project / "tests/userland" / script).write_text("echo " + script + "\n")
        module = self.project / "modules/system-gui/system-gui.okmod"
        module.parent.mkdir(parents=True)
        module.write_bytes(b"module fixture")
        self.apps = work / "apps"
        self.apps.mkdir()
        for app in stage.APPS:
            (self.apps / (app + ".elf")).write_bytes(b"okcrt " + app.encode())
        self.work = work

    def tearDown(self):
        self.scratch.cleanup()

    def run_stage(self, name, *extra):
        out = self.work / name
        argv = ["stage_rootfs", "--apps-dir", str(self.apps), "--out", str(out), *extra]
        with patch.object(stage, "__file__", str(self.project / "tools/stage_rootfs.py")), patch.object(sys, "argv", argv):
            stage.main()
        return out

    def test_rescue_and_full_without_userland_carry_every_okcrt_program(self):
        for profile in ("rescue", "full"):
            out = self.run_stage(profile, "--profile", profile)
            self.assertEqual(sorted(os.listdir(out / "bin")), sorted(app for app in stage.APPS if app != "init"))
            self.assertFalse((out / "rescue").exists())
            self.assertFalse((out / "etc/passwd").exists())

    def test_release_omits_acceptance_programs_and_refuses_acceptance(self):
        out = self.run_stage("release", "--profile", "release")
        for app in stage.ACCEPTANCE_APPS:
            self.assertFalse((out / "bin" / app).exists(), app)
        self.assertTrue((out / "bin/oksh").is_file())
        with self.assertRaisesRegex(SystemExit, "acceptance"):
            self.run_stage("release-acceptance", "--profile", "release", "--acceptance")

    def test_full_profile_makes_musl_applets_the_default_bin(self):
        build, sha = userland_build(self.work)
        out = self.run_stage("full-userland", "--userland-build", str(build), "--userland-manifest-sha256", sha,
                             "--arch", "x86_64")
        self.assertEqual((out / "bin/busybox").read_bytes(), static_elf())
        self.assertEqual(stat.S_IMODE((out / "bin/busybox").stat().st_mode), 0o755)
        for applet in ("cat", "ls", "sh", "["):
            self.assertEqual(os.readlink(out / "bin" / applet), "busybox", applet)
        # Displaced okcrt tools stay reachable; others keep their /bin entry.
        self.assertEqual((out / "rescue/cat").read_bytes(), b"okcrt cat")
        self.assertEqual((out / "rescue/ls").read_bytes(), b"okcrt ls")
        self.assertEqual((out / "bin/oksh").read_bytes(), b"okcrt oksh")
        self.assertEqual((out / "bin/stat").read_bytes(), b"okcrt stat")
        self.assertEqual((out / "etc/passwd").read_text(), stage.PASSWD)
        self.assertNotIn(":$", (out / "etc/passwd").read_text())
        self.assertEqual(os.readlink(out / "usr/share/busybox/busybox"), "/bin/busybox")
        self.assertEqual(stat.S_IMODE((out / "usr/share/busybox/testsuite/runtest").stat().st_mode), 0o755)
        self.assertEqual(sorted(os.listdir(out / "usr/share/userland-tests")), sorted(stage.USERLAND_SCRIPTS))
        for script in stage.USERLAND_SCRIPTS:
            self.assertTrue((ROOT / "tests/userland" / script).is_file(), script)
        self.assertTrue((out / "usr/share/licenses/busybox/LICENSE").is_file())

    def test_release_profile_ships_userland_without_tests(self):
        build, sha = userland_build(self.work)
        out = self.run_stage("release-userland", "--profile", "release", "--userland-build", str(build),
                             "--userland-manifest-sha256", sha, "--arch", "x86_64")
        self.assertEqual(os.readlink(out / "bin/sh"), "busybox")
        self.assertTrue((out / "usr/share/licenses/busybox/LICENSE").is_file())
        self.assertFalse((out / "usr/share/busybox").exists())
        self.assertFalse((out / "usr/share/userland-tests").exists())

    def test_userland_refusals(self):
        build, sha = userland_build(self.work)
        with self.assertRaisesRegex(SystemExit, "rescue"):
            self.run_stage("r", "--profile", "rescue", "--userland-build", str(build),
                           "--userland-manifest-sha256", sha, "--arch", "x86_64")
        with self.assertRaisesRegex(SystemExit, "together"):
            self.run_stage("p", "--userland-build", str(build))
        with self.assertRaisesRegex(SystemExit, "hash"):
            self.run_stage("h", "--userland-build", str(build), "--userland-manifest-sha256", "0" * 64, "--arch", "x86_64")
        with self.assertRaisesRegex(SystemExit, "finished build"):
            self.run_stage("a", "--userland-build", str(build), "--userland-manifest-sha256", sha, "--arch", "arm32")
        reserved, reserved_sha = userland_build(self.work / "reserved", applets=("cat", "sync"))
        with self.assertRaisesRegex(SystemExit, "decision 0001"):
            self.run_stage("s", "--userland-build", str(reserved), "--userland-manifest-sha256", reserved_sha,
                           "--arch", "x86_64")
        (build / "stage/share/busybox/.config").write_text("CONFIG_ASH=n\n")
        with self.assertRaisesRegex(SystemExit, "artifact mismatch"):
            self.run_stage("t", "--userland-build", str(build), "--userland-manifest-sha256", sha, "--arch", "x86_64")

    def test_xmake_profiles_stage_separate_trees(self):
        targets = (ROOT / "xmake/targets.lua").read_text()
        self.assertIn('stage_rootfs(batchcmds, "full", "rootfs")', targets)
        self.assertIn('stage_rootfs(batchcmds, "rescue", "rootfs-rescue")', targets)
        self.assertIn('stage_rootfs(batchcmds, "release", "rootfs-release")', targets)
        simplefs = targets[targets.index('target("rootfs-simplefs")'):targets.index('target("boot-archive")')]
        self.assertIn('add_deps("rootfs-rescue-stage")', simplefs)


if __name__ == "__main__":
    unittest.main()

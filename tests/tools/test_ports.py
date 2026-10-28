import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import ports  # noqa: E402


def archive(directory: Path, members: dict, *, top="demo-1") -> Path:
    path = directory / f"{top}.tar.gz"
    with tarfile.open(path, "w:gz") as stream:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            if data is None:
                info.type = tarfile.DIRTYPE
                stream.addfile(info)
            elif isinstance(data, str):
                info.type, info.linkname = tarfile.SYMTYPE, data
                stream.addfile(info)
            else:
                info.size = len(data)
                stream.addfile(info, io.BytesIO(data))
    return path


class PortsFrameworkTests(unittest.TestCase):
    def test_repository_descriptors_validate(self):
        loaded = ports.load()
        self.assertEqual(sorted(loaded), ["busybox", "musl"])
        self.assertEqual(ports.validate(loaded), [])
        self.assertEqual(ports.order(loaded, ["busybox"]), ["musl", "busybox"])

    def test_musl_descriptor_is_the_ledger_pin(self):
        from musl_source import source_pin
        musl = ports.load()["musl"]
        self.assertEqual(musl["sha256"], source_pin()["archive_sha256"])
        self.assertEqual(musl["version"], source_pin()["version"])

    def test_busybox_patches_are_gpl2_and_listed(self):
        patches = ports.load()["busybox"]["build"]["patches"]
        self.assertEqual(sorted(p.relative_to(ROOT / "ports/busybox").as_posix()
                                for p in (ROOT / "ports/busybox/patches").glob("*.patch")), sorted(patches))
        for patch in patches:
            self.assertTrue((ROOT / "ports/busybox" / patch).read_text().startswith("SPDX-License-Identifier: GPL-2.0-only\n"))

    def test_busybox_fragment_holds_back_unrouted_applets(self):
        requested = ports.config_lines((ROOT / "ports/busybox/busybox.config").read_text())
        names = {line.split("=", 1)[0] for line in requested}
        self.assertIn("CONFIG_ASH", names)
        self.assertIn("CONFIG_STATIC", names)
        # Decision 0001 keeps sync on okcrt; the others need unrouted syscalls.
        for held in ("SYNC", "LN", "TOUCH", "UNAME", "UPTIME", "DF", "MKFIFO", "CHOWN", "PS", "ASH_JOB_CONTROL"):
            self.assertNotIn("CONFIG_" + held, names)

    def test_cli_validate(self):
        result = subprocess.run([sys.executable, "-B", str(ROOT / "tools/ports.py"), "validate"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejections(self):
        base = {"name": "x", "version": "1", "archive": "x.tar", "sha256": "", "license": "MIT",
                "depends": [], "profiles": [], "state": "planned", "build": {"system": "make"}}
        self.assertEqual(ports.validate({"x": dict(base)}), [])
        self.assertTrue(ports.validate({"x": dict(base, state="builds")}))          # no hash
        self.assertTrue(ports.validate({"x": dict(base, sha256="ab")}))             # bad hash
        self.assertTrue(ports.validate({"x": dict(base, license="review", state="builds", sha256="0" * 64)}))
        self.assertTrue(ports.validate({"x": dict(base, depends=["nope"])}))
        self.assertTrue(ports.validate({"x": dict(base, profiles=["sparc"])}))
        self.assertTrue(ports.validate({"x": dict(base, state="executes", sha256="0" * 64)}))  # no profiles
        self.assertTrue(ports.validate({"x": dict(base, build={"system": "kconfig", "config": "absent"})}))
        for patch in ("../musl/port.json", "busybox.config", "patches/absent.patch"):
            self.assertTrue(ports.validate({"busybox": dict(ports.load()["busybox"], build=dict(
                ports.load()["busybox"]["build"], patches=[patch]))}), patch)
        with self.assertRaises(SystemExit):
            ports.order({"a": dict(base, name="a", depends=["b"]), "b": dict(base, name="b", depends=["a"])}, ["a"])


class KconfigRecipeTests(unittest.TestCase):
    def test_config_lines(self):
        text = "# comment\nCONFIG_A=y\n\nCONFIG_B=4\nCONFIG_C=\"/bin/busybox\"\n"
        self.assertEqual(ports.config_lines(text), ["CONFIG_A=y", "CONFIG_B=4", 'CONFIG_C="/bin/busybox"'])
        for bad in ("CONFIG_A=n", "CONFIG_A=y\nCONFIG_A=y", "CONFIG_a=y", 'CONFIG_A="x\\"y"', "A=y",
                    'CONFIG_EXTRA_CFLAGS="-O0"', "CONFIG_DEBUG=y"):
            with self.assertRaises(ValueError, msg=bad):
                ports.config_lines(bad)

    def test_unmet_config(self):
        resolved = "CONFIG_A=y\n# CONFIG_B is not set\nCONFIG_C=\"x\"\n"
        self.assertEqual(ports.unmet_config(["CONFIG_A=y", 'CONFIG_C="x"'], resolved), [])
        self.assertEqual(ports.unmet_config(["CONFIG_B=y", 'CONFIG_C="y"'], resolved), ["CONFIG_B=y", 'CONFIG_C="y"'])

    def test_resolve_config_turns_off_unrequested_defaults_but_keeps_selected(self):
        # Fake kconfig: ASH brings JOB_CONTROL (default y) and selects MATH; MATH alone is off.
        def oldconfig():
            lines = path.read_text().splitlines()
            values = {ports.config_symbol(line): line for line in lines if ports.config_symbol(line)}
            if values.get("CONFIG_ASH") == "CONFIG_ASH=y":
                values.setdefault("CONFIG_ASH_JOB_CONTROL", "CONFIG_ASH_JOB_CONTROL=y")
                values["CONFIG_MATH"] = "CONFIG_MATH=y"
            calls.append(1)
            path.write_text("".join(line + "\n" for line in values.values()))
        with tempfile.TemporaryDirectory() as scratch:
            path, calls = Path(scratch) / ".config", []
            base = "# CONFIG_ASH is not set\n# CONFIG_MATH is not set\nCONFIG_PREFIX=\"./_install\"\n"
            resolved = ports.resolve_config(path, base, ["CONFIG_ASH=y", 'CONFIG_X="v"'], oldconfig)
        self.assertEqual(resolved.splitlines(), ["CONFIG_ASH=y", "CONFIG_MATH=y", 'CONFIG_PREFIX="./_install"',
                                                 'CONFIG_X="v"', "# CONFIG_ASH_JOB_CONTROL is not set"])
        self.assertLessEqual(len(calls), 4)
        self.assertEqual(ports.merge_config("# CONFIG_A is not set\nCONFIG_B=y\n", ["CONFIG_A=y", "CONFIG_C=4"]),
                         "CONFIG_A=y\nCONFIG_B=y\nCONFIG_C=4\n")
        self.assertEqual(ports.disable_unrequested("CONFIG_A=y\nCONFIG_B=y\nCONFIG_N=3\n", ["CONFIG_A=y"]),
                         "CONFIG_A=y\n# CONFIG_B is not set\nCONFIG_N=3\n")

    def test_applet_names(self):
        self.assertEqual(ports.applet_names("/bin/sh\n/usr/bin/[\n/usr/bin/[[\n/sbin/x\n"), ["[", "[[", "sh", "x"])
        for bad in ("/bin/sh\n/bin/sh\n", "bin/sh\n", "/etc/sh\n", "/bin/busybox\n", "/bin/a b\n", ""):
            with self.assertRaises(ValueError, msg=bad):
                ports.applet_names(bad)

    def test_archive_admission(self):
        with tempfile.TemporaryDirectory() as scratch:
            directory = Path(scratch)
            good = archive(directory, {"demo-1": None, "demo-1/Makefile": b"all:\n"})
            port = {"name": "demo", "version": "1", "sha256": hashlib.sha256(good.read_bytes()).hexdigest()}
            self.assertEqual(ports.admit_archive(good, port), "demo-1")
            ports.extract(good, directory / "out")
            self.assertEqual((directory / "out/demo-1/Makefile").read_bytes(), b"all:\n")
            with self.assertRaises(ValueError):
                ports.admit_archive(good, dict(port, sha256="0" * 64))
            for members in ({"demo-1/../x": b""}, {"other/x": b""}, {"demo-1/link": "/etc/passwd"},
                            {"/demo-1/x": b""}):
                bad = archive(Path(tempfile.mkdtemp(dir=scratch)), members)
                with self.assertRaises(ValueError, msg=str(members)):
                    ports.admit_archive(bad, dict(port, sha256=hashlib.sha256(bad.read_bytes()).hexdigest()))

    def test_build_refusals(self):
        def args(**values):
            defaults = {"name": "busybox", "arch": "x86_64", "mode": "debug", "archive": Path("/nonexistent"),
                        "toolchain": Path("/nonexistent"), "out": Path("/nonexistent/out"), "musl_build": None,
                        "ppc_clang": None, "softfp_build": None, "softfp_manifest_sha256": None, "jobs": 4}
            defaults.update(values)
            return type("Args", (), defaults)
        with self.assertRaisesRegex(ValueError, "unknown port"):
            ports.build_port(args(name="toybox"))
        with self.assertRaisesRegex(ValueError, "jobs"):
            ports.build_port(args(jobs=0))
        with self.assertRaisesRegex(ValueError, "--musl-build"):
            ports.build_port(args())

    def test_admission_requires_exact_manifest(self):
        with tempfile.TemporaryDirectory() as scratch:
            build = Path(scratch)
            (build / "manifest.json").write_text(json.dumps({"schema_version": 1, "status": "build-failed"}))
            sha = hashlib.sha256((build / "manifest.json").read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "hash"):
                ports.admit(build, "0" * 64, "x86_64")
            with self.assertRaisesRegex(ValueError, "finished build"):
                ports.admit(build, sha, "x86_64")


if __name__ == "__main__":
    unittest.main()

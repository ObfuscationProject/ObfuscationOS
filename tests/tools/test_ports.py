import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import ports  # noqa: E402


class PortsFrameworkTests(unittest.TestCase):
    def test_repository_descriptors_validate(self):
        loaded = ports.load()
        self.assertIn("musl", loaded)
        self.assertEqual(ports.validate(loaded), [])
        self.assertEqual(ports.order(loaded, ["toybox"]), ["musl", "toybox"])

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
        with self.assertRaises(SystemExit):
            ports.order({"a": dict(base, name="a", depends=["b"]), "b": dict(base, name="b", depends=["a"])}, ["a"])


if __name__ == "__main__":
    unittest.main()

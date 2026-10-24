"""The documented aggregate command must discover tests after tool imports."""
from pathlib import Path
import subprocess
import sys
import unittest


class ToolDiscoveryTests(unittest.TestCase):
    def test_aggregate_discovery_has_no_import_collisions(self):
        root = Path(__file__).resolve().parents[2]
        script = """
import pathlib, sys, unittest
loader = unittest.TestLoader()
suite = loader.discover('tests/tools', pattern='test_*.py')
assert not loader.errors, loader.errors
assert suite.countTestCases() > 0
for name in ('test_native_user_registry', 'test_native_child_events', 'test_users_store'):
    assert pathlib.Path(sys.modules[name].__file__).resolve().parent == pathlib.Path('tests/tools').resolve(), name
"""
        result = subprocess.run([sys.executable, '-B', '-c', script], cwd=root,
                                text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

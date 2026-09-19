"""Failed image generation must not destroy an existing persistent disk."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

source = Path(__file__).resolve().parents[2] / 'tools/mkext4.py'
spec = importlib.util.spec_from_file_location('mkext4', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Ext4PackagingTests(unittest.TestCase):
    def test_failed_generation_preserves_existing_image(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'old.img'
            output.write_bytes(b'precious image')
            args = ['mkext4', '--root', str(root), '--out', str(output)]
            with patch('sys.argv', args), patch.object(module, 'require', side_effect=lambda name: name), \
                 patch.object(module.subprocess, 'check_call', side_effect=RuntimeError('mkfs failed')):
                with self.assertRaises(RuntimeError):
                    module.main()
            self.assertEqual(output.read_bytes(), b'precious image')

    def test_missing_root_is_rejected_before_touching_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'old.img'
            output.write_bytes(b'precious image')
            with patch('sys.argv', ['mkext4', '--root', str(root / 'missing'), '--out', str(output)]):
                with self.assertRaises(SystemExit):
                    module.main()
            self.assertEqual(output.read_bytes(), b'precious image')

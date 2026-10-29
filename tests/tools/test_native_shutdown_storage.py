"""Actual OS storage callbacks with exported SDK types and hosted owner seams."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NativeShutdownStorageTests(unittest.TestCase):
    def test_actual_storage_action_ownership_and_consumption_policy(self):
        self.assertIn('OK_TEST_KERNEL_SDK', os.environ,
                      'Set OK_TEST_KERNEL_SDK to an explicit exported SDK')
        sdk = Path(os.environ['OK_TEST_KERNEL_SDK']).resolve()
        for header in ('ok/core/shutdown_storage.hpp',):
            self.assertTrue((sdk / 'include' / header).is_file())
        with tempfile.TemporaryDirectory(prefix='native-storage-policy-') as directory:
            temporary = Path(directory)
            # Substitute only service boundaries. Status, power/ticket/barrier,
            # and architecture declarations come from the SDK.
            include = temporary / 'include/ok/fs'
            include.mkdir(parents=True)
            seam = ROOT / 'tests/hosted/native_shutdown_storage_seams.hpp'
            for header in ('ext4/layout.hpp', 'ext4_mounted_common_profile.hpp', 'fat_fs.hpp', 'devfs.hpp'):
                (include / header).parent.mkdir(parents=True, exist_ok=True)
                (include / header).write_text(f'#include "{seam}"\n')
            driver = temporary / 'include/ok/driver'
            driver.mkdir()
            (driver / 'driver.hpp').write_text(f'#include "{seam}"\n')
            binary = temporary / 'storage-policy'
            subprocess.run(['c++', '-std=c++23', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=undefined', '-fno-sanitize-recover=all',
                            '-I', str(temporary / 'include'), '-I', str(sdk / 'include'),
                            str(ROOT / 'tests/native_shutdown_storage_tests.cpp'), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, timeout=8, check=True)
            self.assertIn(b'ordering and sticky failure controls passed', result.stdout)


if __name__ == '__main__':
    unittest.main()

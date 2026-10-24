"""Distribution metadata is explicit under host umask and SGID ancestry."""
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from mkarchive import pack

spec = importlib.util.spec_from_file_location("stage_rootfs_modes", ROOT / "tools/stage_rootfs.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class StageRootfsModeTests(unittest.TestCase):
    def test_resolver_daemon_and_client_are_ordinary_apps_with_selected_root_notify_service(self):
        targets = (ROOT / 'xmake/targets.lua').read_text()
        for name in ('resolved', 'resolvectl'):
            self.assertEqual(stage.APPS.count(name), 1)
            self.assertIn('"' + name + '"', targets.splitlines()[0])
        configuration = (ROOT / 'config/services-login.conf').read_bytes()
        self.assertEqual(configuration.count(b'service resolved notify /bin/resolved - 0 0\n'), 1)
        self.assertNotIn(b'resolvectl', configuration)
        self.assertNotIn(b'resolved', (ROOT / 'config/services.conf').read_bytes())
        self.assertEqual(len(stage.ELF_PROFILES), 10)

    def test_native_mountctl_is_an_ordinary_app_without_a_service_entry(self):
        self.assertEqual(stage.APPS.count('mountctl'), 1)
        targets = (ROOT / 'xmake/targets.lua').read_text()
        self.assertIn('"mountctl"', targets.splitlines()[0])
        for name in ('services.conf', 'services-login.conf'):
            self.assertNotIn(b'mountctl', (ROOT / 'config' / name).read_bytes())

    def test_exact_guest_modes_ignore_host_umask_sgid_and_source_special_bits(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            project = work / "project"
            (project / "config").mkdir(parents=True)
            (project / "config/services.conf").write_bytes(
                b"OK_SERVICE_MANIFEST 1\nservice console simple /bin/oksh -\n")
            (project / "config/services.conf").chmod(0o644)
            (project / "config/hosts").write_bytes(b'127.0.0.1 localhost\n')
            (project / "config/hosts").chmod(0o644)
            module = project / "modules/system-gui/system-gui.okmod"
            module.parent.mkdir(parents=True); module.write_bytes(b"module fixture"); module.chmod(0o7777)
            apps = work / "apps"; apps.mkdir()
            for app in stage.APPS:
                source = apps / (app + ".elf")
                source.write_bytes(b"ELF fixture: " + app.encode()); source.chmod(0o6755)
            parent = work / "sgid-parent"; parent.mkdir(); parent.chmod(0o2770)
            archives = []
            for mask in (0o077, 0o002):
                out = parent / ("root-" + oct(mask))
                args = ["stage_rootfs", "--apps-dir", str(apps), "--out", str(out)]
                old_mask = os.umask(mask)
                try:
                    with patch.object(stage, "__file__", str(project / "tools/stage_rootfs.py")), \
                            patch.object(sys, "argv", args):
                        self.assertEqual(stage.main(), 0)
                finally:
                    os.umask(old_mask)
                with self.subTest(mask=oct(mask)):
                    directories = ("", "bin", "etc", "boot", "boot/modules", "home", "root", "run", "dev", "tmp")
                    for relative in directories:
                        mode = stat.S_IMODE((out / relative).lstat().st_mode)
                        self.assertEqual(mode, 0o1777 if relative == "tmp" else 0o700 if relative == "root" else 0o755, relative)
                    for app in stage.APPS:
                        name = "init" if app == "init" else "bin/" + app
                        self.assertEqual(stat.S_IMODE((out / name).lstat().st_mode), 0o755, name)
                        self.assertEqual((out / name).read_bytes(), (apps / (app + ".elf")).read_bytes())
                    for name in ("etc/os-release", "etc/services.conf", "etc/hosts", "boot/modules/system-gui.okmod"):
                        self.assertEqual(stat.S_IMODE((out / name).lstat().st_mode), 0o644, name)
                    self.assertEqual(stat.S_IMODE((out / "etc/accounts.db").lstat().st_mode), 0o600)
                    self.assertEqual((out / "etc/accounts.db").read_bytes(), b"OKACCOUNTS 1\nstate unconfigured\n")
                    self.assertEqual((out / "etc/hosts").read_bytes(), b'127.0.0.1 localhost\n')
                    self.assertEqual((out / "boot/modules/system-gui.okmod").read_bytes(), b"module fixture")
                    self.assertEqual(stat.S_IMODE(parent.lstat().st_mode), 0o2770)
                    self.assertEqual(stat.S_IMODE(module.lstat().st_mode), 0o7777)
                    for app in stage.APPS:
                        self.assertEqual(stat.S_IMODE((apps / (app + ".elf")).lstat().st_mode), 0o6755)
                    archives.append(pack(out))
            self.assertEqual(archives[0], archives[1])


if __name__ == "__main__":
    unittest.main()

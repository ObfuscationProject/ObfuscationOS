"""Synthetic marker/command controls; this suite never starts a FAT guest."""
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import json

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.append(str(SCRIPTS))
spec = importlib.util.spec_from_file_location('fat_media_runner', SCRIPTS / 'test_fat_media.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class FatMediaRunnerTests(unittest.TestCase):
    def test_mount_requires_exact_filesystem_and_mountpoint(self):
        for filesystem in ('fat32', 'exfat'):
            mount = f'OK_STORAGE scope=hardware source=virtio filesystem={filesystem} mode=rw mount=/media\n'.encode()
            good = mount + b'OK_SYSTEM_GUI boot=complete\noksh> '
            runner.validate_boot(good, filesystem)
            for bad in (good.replace(b'/media', b'/'), good.replace(b'mode=rw', b'mode=ro'),
                        good.replace(b'source=virtio', b'source=archive'), good + mount,
                        good.replace(mount, b''), good.replace(b'OK_SYSTEM_GUI boot=complete\n', b'')):
                with self.subTest(filesystem=filesystem, bad=bad), self.assertRaises(ValueError):
                    runner.validate_boot(bad, filesystem)

    def test_each_phase_requires_one_complete_result_and_prompt(self):
        for phase, marker in runner.MARKERS.items():
            runner.validate_phase(marker + b'\noksh> ', phase)
            runner.validate_phase(marker + b'\r\noksh> ', phase)
            for bad in (marker, marker + b'\n', marker + b'\noksh>', marker + b'\n' + marker + b'\noksh> ',
                        b'echo ' + marker + b'\noksh> ', b'oksh> '):
                with self.subTest(phase=phase, bad=bad), self.assertRaises(ValueError):
                    runner.validate_phase(bad, phase)
            wrong = runner.MARKERS['read' if phase != 'read' else 'write']
            with self.assertRaises(ValueError):
                runner.validate_phase(wrong + b'\noksh> ', phase)

    def test_assertion_overrides_success_including_unterminated_failure(self):
        for marker in runner.FAILURES:
            with self.subTest(marker=marker), self.assertRaises(ValueError):
                runner.validate_phase(runner.MARKERS['write'] + b'\n' + marker + b'\noksh> ', 'write')
            with self.assertRaises(ValueError):
                runner.check_failures(runner.MARKERS['write'] + b'\noksh> ' + marker)

    def test_format_and_checker_use_explicit_image_and_readonly_check(self):
        image = Path('/scratch/new-media.img')
        self.assertEqual(runner.format_command('/bin/mkfs.fat', 'fat32', image),
                         ['/bin/mkfs.fat', '-F', '32', '-n', 'OBOSFAT', str(image)])
        self.assertEqual(runner.format_command('/bin/mkfs.exfat', 'exfat', image),
                         ['/bin/mkfs.exfat', '-L', 'OBOSFAT', str(image)])
        self.assertEqual(runner.fsck_command('/bin/fsck.fat', image), ['/bin/fsck.fat', '-n', str(image)])
        with self.assertRaises(ValueError):
            runner.format_command('/bin/mkfs', 'ext4', image)

    def test_synthetic_guest_records_full_phase_and_private_command(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            script = output / 'fake_guest.py'
            script.write_text(
                'import sys\n'
                'print("OK_STORAGE scope=hardware source=virtio filesystem=fat32 mode=rw mount=/media")\n'
                'print("OK_SYSTEM_GUI boot=complete")\n'
                'print("oksh> ", end="", flush=True)\n'
                'assert sys.stdin.readline() == "posix-check --fat-write\\n"\n'
                f'print({runner.MARKERS["write"].decode()!r})\n'
                'print("oksh> ", end="", flush=True)\n'
                'assert sys.stdin.readline() == "sync /media\\n"\n'
                'print("Filesystem synchronized")\n'
                'print("oksh> ", end="", flush=True)\n'
                'sys.stdin.read()\n')
            args = SimpleNamespace(qemu=Path('/unused/qemu'), arch='x86_64', filesystem='fat32', timeout=5)
            command = [sys.executable, '-B', str(script)]
            with patch.object(runner, 'command_for', return_value=command) as factory:
                row = runner.guest(args, output / 'kernel.bin', output / 'media.img', 'write', output)
            factory.assert_called_once_with(args.qemu, args.arch, output / 'kernel.bin', output / 'media.img', 'none', native_profile=True)
            self.assertEqual(row['status'], 'passed')
            self.assertEqual(row, json.loads((output / 'write-result.json').read_text()))
            self.assertEqual(row['serial_sha256'], runner.sha(output / 'write-serial.log'))
            self.assertEqual(json.loads((output / 'write-command.json').read_text()), command)

    def test_synthetic_late_guest_failure_is_retained_and_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            script = output / 'fake_guest.py'
            script.write_text(
                'import signal, sys\n'
                'def stop(signum, frame):\n'
                '    print("FAT_CHECK failed: late synthetic assertion", flush=True)\n'
                '    raise SystemExit(0)\n'
                'signal.signal(signal.SIGTERM, stop)\n'
                'print("OK_STORAGE scope=hardware source=virtio filesystem=exfat mode=rw mount=/media")\n'
                'print("OK_SYSTEM_GUI boot=complete")\n'
                'print("oksh> ", end="", flush=True)\n'
                'sys.stdin.readline()\n'
                f'print({runner.MARKERS["read"].decode()!r})\n'
                'print("oksh> ", end="", flush=True)\n'
                'assert sys.stdin.readline() == "sync /media\\n"\n'
                'print("Filesystem synchronized")\n'
                'print("oksh> ", end="", flush=True)\n'
                'signal.pause()\n')
            args = SimpleNamespace(qemu=Path('/unused/qemu'), arch='x86_64', filesystem='exfat', timeout=5)
            with patch.object(runner, 'command_for', return_value=[sys.executable, '-B', str(script)]):
                with self.assertRaisesRegex(ValueError, 'native FAT guest reported'):
                    runner.guest(args, output / 'kernel.bin', output / 'media.img', 'read', output)
            row = json.loads((output / 'read-result.json').read_text())
            self.assertEqual(row['status'], 'failed')
            self.assertIn(b'FAT_CHECK failed: late synthetic assertion', (output / 'read-serial.log').read_bytes())

    def test_synthetic_abnormal_exit_after_success_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            script = output / 'fake_guest.py'
            script.write_text(
                'import signal, sys\n'
                'signal.signal(signal.SIGTERM, lambda *unused: sys.exit(7))\n'
                'print("OK_STORAGE scope=hardware source=virtio filesystem=fat32 mode=rw mount=/media")\n'
                'print("OK_SYSTEM_GUI boot=complete")\n'
                'print("oksh> ", end="", flush=True)\n'
                'assert sys.stdin.readline() == "posix-check --fat-write\\n"\n'
                f'print({runner.MARKERS["write"].decode()!r})\n'
                'print("oksh> ", end="", flush=True)\n'
                'assert sys.stdin.readline() == "sync /media\\n"\n'
                'print("Filesystem synchronized")\n'
                'print("oksh> ", end="", flush=True)\n'
                'signal.pause()\n')
            args = SimpleNamespace(qemu=Path('/unused/qemu'), arch='x86_64', filesystem='fat32', timeout=5)
            with patch.object(runner, 'command_for', return_value=[sys.executable, '-B', str(script)]):
                with self.assertRaisesRegex(ValueError, 'unexpected QEMU exit status: 7'):
                    runner.guest(args, output / 'kernel.bin', output / 'media.img', 'write', output)
            row = json.loads((output / 'write-result.json').read_text())
            self.assertEqual(row['status'], 'failed')
            self.assertEqual(row['qemu_returncode'], 7)

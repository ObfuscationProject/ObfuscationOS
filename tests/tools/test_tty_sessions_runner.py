"""Synthetic configuration and serial checks for scripts/test_tty_sessions.py; no guest starts."""
import importlib.util
import os
from pathlib import Path
import sys
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / 'scripts'
sys.path.append(str(SCRIPTS))
spec = importlib.util.spec_from_file_location('tty_sessions_runner', SCRIPTS / 'test_tty_sessions.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

# Shape of a saved .xmake/<plat>/<arch>/xmake.conf.
CONFIG = '''{
    arch = "x86_64",
    kernel_sdk = "/sdk/x86_64/debug",
    mode = "debug",
    native_console_login = false,
    native_init_acceptance = %s,
    native_init_control = true,
    native_udp_probe = false,
    native_vm_acceptance = false,
    userland_build = false
}'''


class FakeGuest:
    """A QEMU stand-in whose serial output is a pipe the test writes."""

    def __init__(self, output: bytes):
        read, write = os.pipe()
        os.write(write, output)
        os.close(write)
        self.stdout = os.fdopen(read, 'rb', buffering=0)


class TtySessionsRunnerTests(unittest.TestCase):
    def test_saved_options_are_read(self):
        self.assertEqual(runner.enabled_options(CONFIG % 'false') & {'native_init_acceptance', 'native_console_login'},
                         set())
        enabled = runner.enabled_options(CONFIG % 'true')
        self.assertIn('native_init_acceptance', enabled)
        self.assertIn('native_init_control', enabled)
        self.assertNotIn('native_vm_acceptance', enabled)

    def test_startup_acceptance_is_refused(self):
        runner.refuse_configuration(runner.enabled_options(CONFIG % 'false'))
        for name in runner.ACCEPTANCE_OPTIONS:
            with self.assertRaisesRegex(ValueError, name):
                runner.refuse_configuration({name})

    def test_acceptance_before_the_shell_fails_at_once(self):
        # A failed acceptance boot never reaches the prompt; it must not wait out the timeout.
        guest = FakeGuest(b'POSIX_CHECK failed: child_status(child) == 0 errno=16\r\n'
                          b'OK_USERLAND scope=hardware acceptance=FAIL\r\n')
        self.addCleanup(guest.stdout.close)
        serial = bytearray()
        with self.assertRaisesRegex(RuntimeError, 'startup acceptance'):
            runner.receive(guest, serial, lambda: runner.PROMPT in serial, time.monotonic() + 2)


if __name__ == '__main__':
    unittest.main()

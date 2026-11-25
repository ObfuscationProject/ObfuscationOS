"""Hosted login input boundaries over a modelled pts; this is not a terminal or guest login test."""
from pathlib import Path
import ctypes
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

BACKEND = r'''
#include <errno.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <sys/types.h>
#include <termios.h>

static const unsigned char *input;
static size_t input_size, consumed, output_size, event_size;
static unsigned char output[1024];
static char events[20000];
static int flushes, mode, read_interrupted, write_interrupted, sets, echoed_reads;
static tcflag_t lflag;
static const tcflag_t initial_lflag = ECHO | ECHOE | ECHOK | ICANON | ISIG | IEXTEN;

void login_test_begin(const unsigned char *data, size_t size, int options)
{
    input = data; input_size = size; mode = options;
    consumed = output_size = event_size = 0;
    flushes = read_interrupted = write_interrupted = sets = echoed_reads = 0;
    lflag = initial_lflag;
    memset(output, 0, sizeof(output));
    memset(events, 0, sizeof(events));
}
int login_test_flush(int descriptor, int queue)
{
    events[event_size++] = 'F';
    ++flushes;
    if ((mode & 1) || descriptor != 0 || queue != TCIFLUSH) { errno = EIO; return -1; }
    return 0;
}
int login_test_getattr(int descriptor, struct termios *attributes)
{
    events[event_size++] = 'A';
    if ((mode & 64) || descriptor != 0) { errno = EIO; return -1; }
    memset(attributes, 0, sizeof(*attributes));
    attributes->c_iflag = ICRNL;
    attributes->c_lflag = lflag;
    return 0;
}
int login_test_setattr(int descriptor, int action, const struct termios *attributes)
{
    events[event_size++] = 'S';
    ++sets;
    if (descriptor != 0 || action != TCSANOW || attributes->c_iflag != ICRNL) { errno = EINVAL; return -1; }
    if (((mode & 128) && sets == 1) || ((mode & 256) && sets == 2)) { errno = EIO; return -1; }
    lflag = attributes->c_lflag;
    return 0;
}
ssize_t login_test_read(int descriptor, void *buffer, size_t size)
{
    events[event_size++] = 'R';
    if (lflag & (ECHO | ECHONL)) ++echoed_reads;
    if ((mode & 2) && !read_interrupted++) { errno = EINTR; return -1; }
    if (descriptor != 0 || size != 1 || (mode & 8)) { errno = EIO; return -1; }
    if (consumed == input_size) return 0;
    *(unsigned char *)buffer = input[consumed++];
    return 1;
}
ssize_t login_test_write(int descriptor, const void *data, size_t size)
{
    events[event_size++] = 'W';
    if ((mode & 4) && !write_interrupted++) { errno = EINTR; return -1; }
    if (mode & 16) return 0;
    if (descriptor != 1 || output_size + size >= sizeof(output)) { errno = EIO; return -1; }
    if ((mode & 32) && size > 1) size = 1;
    memcpy(output + output_size, data, size);
    output_size += size;
    return (ssize_t)size;
}
size_t login_test_consumed(void) { return consumed; }
int login_test_flushes(void) { return flushes; }
int login_test_echoed_reads(void) { return echoed_reads; }
int login_test_restored(void) { return lflag == initial_lflag; }
const char *login_test_output(void) { return (const char *)output; }
const char *login_test_events(void) { return events; }
'''


class NativeLoginInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='native-login-input-host-')
        temporary = Path(cls.directory.name)
        (temporary / 'backend.c').write_text(BACKEND)
        output = temporary / 'login-input.so'
        subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0',
                        '-fPIC', '-shared', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        '-Dread=login_test_read', '-Dwrite=login_test_write',
                        '-Dtcflush=login_test_flush', '-Dtcgetattr=login_test_getattr',
                        '-Dtcsetattr=login_test_setattr', '-I', str(temporary),
                        str(ROOT / 'apps/login/input.c'), str(ROOT / 'apps/login/password.c'),
                        str(temporary / 'backend.c'), '-o', str(output)], check=True)
        cls.lib = ctypes.CDLL(str(output), use_errno=True)
        cls.lib.login_test_begin.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
        for name in ('ok_login_read_line', 'ok_login_read_secret'):
            getattr(cls.lib, name).argtypes = [ctypes.c_uint32, ctypes.c_char_p,
                ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
        cls.lib.ok_login_epoch.argtypes = [ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_uint32)]
        cls.lib.login_test_output.restype = ctypes.c_char_p
        cls.lib.login_test_events.restype = ctypes.c_char_p
        cls.lib.login_test_consumed.restype = ctypes.c_size_t

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def line(self, data, capacity=129, mode=0, secret=True):
        self.lib.login_test_begin(data, len(data), mode)
        output = ctypes.create_string_buffer(b'X' * capacity, capacity)
        length = ctypes.c_size_t(999)
        if secret:
            result = self.lib.ok_login_read_secret(17, b'Password: ', output, capacity, ctypes.byref(length))
            self.assertEqual(self.lib.login_test_echoed_reads(), 0)
            self.assertTrue(self.lib.login_test_restored(), self.lib.login_test_events())
        else:
            result = self.lib.ok_login_read_line(17, b'Login: ', output, capacity, ctypes.byref(length))
        return result, output.raw, length.value

    def epoch(self, entries):
        environment = (ctypes.c_char_p * (len(entries) + 1))(*entries, None)
        output = ctypes.c_uint32(0xa5a5a5a5)
        result = self.lib.ok_login_epoch(environment, ctypes.byref(output))
        return result, output.value

    def test_epoch_requires_unique_canonical_explicit_bounded_value(self):
        for value, number in [(b'1', 1), (b'17', 17), (b'1073741823', 0x3fffffff)]:
            self.assertEqual(self.epoch([b'PATH=/bin', b'OK_CONSOLE_EPOCH=' + value]), (0, number))
        invalid = [[], [b'OK_CONSOLE_EPOCH'], [b'NOT_OK_CONSOLE_EPOCH=17'],
                   [b'OK_CONSOLE_EPOCH=17', b'OK_CONSOLE_EPOCH=17']]
        invalid.extend([[b'OK_CONSOLE_EPOCH=' + value] for value in
                        (b'', b'0', b'00', b'01', b'+1', b'-1', b' 1', b'1 ',
                         b'1\n', b'1073741824', b'4294967297', b'9' * 240)])
        invalid.extend([[b'X=' + b'a' * 254, b'OK_CONSOLE_EPOCH=17'],
                        [b'X=1'] * 16 + [b'OK_CONSOLE_EPOCH=17']])
        for entries in invalid:
            with self.subTest(entries=entries):
                self.assertEqual(self.epoch(entries), (-1, 0xa5a5a5a5))

    def test_secret_clears_echo_then_flushes_before_prompt_and_restores(self):
        secret = '密 码 !'.encode()
        result, output, length = self.line(secret + b'\n')
        self.assertEqual((result, output[:length], length), (0, secret, len(secret)))
        self.assertEqual(self.lib.login_test_output(), b'Password: \n')
        events = self.lib.login_test_events()
        self.assertTrue(events.startswith(b'ASFWR'), events)
        self.assertTrue(events.endswith(b'RWS'), events)
        self.assertEqual(self.lib.login_test_flushes(), 1)

    def test_echoed_name_uses_the_line_discipline_echo_without_an_extra_newline(self):
        result, output, length = self.line(b'chosen_admin\n', secret=False)
        self.assertEqual((result, output[:length], length), (0, b'chosen_admin', 12))
        self.assertEqual(self.lib.login_test_output(), b'Login: ')
        self.assertEqual(self.lib.login_test_events(), b'FW' + b'R' * 13)
        self.assertEqual(self.lib.login_test_echoed_reads(), 13)
        self.assertTrue(self.lib.login_test_restored())

    def test_secret_restores_echo_on_every_failure_path(self):
        cases = [(b'secret', 0), (b'secret\n', 1), (b'secret\n', 8), (b'secret\n', 16),
                 (b'a' * 200 + b'\n', 0), (b'a' * 10000, 0), (b'abc\0d\n', 0)]
        for data, mode in cases:
            with self.subTest(mode=mode, size=len(data)):
                result, output, length = self.line(data, mode=mode)
                self.assertIn(result, (-1, 1))
                self.assertEqual((output, length), (bytes(129), 0))
                self.assertEqual(self.lib.login_test_events()[-1:], b'S')

    def test_terminal_attribute_failures_never_read_and_restore_failure_drops_the_line(self):
        for mode, events in ((64, b'A'), (128, b'ASS')):
            with self.subTest(mode=mode):
                result, output, length = self.line(b'secret\n', mode=mode)
                self.assertEqual((result, output, length), (-1, bytes(129), 0))
                self.assertEqual(self.lib.login_test_events(), events)
                self.assertEqual(self.lib.login_test_output(), b'')
                self.assertEqual(self.lib.login_test_consumed(), 0)
        self.lib.login_test_begin(b'secret\n', 7, 256)
        output = ctypes.create_string_buffer(b'X' * 129, 129)
        length = ctypes.c_size_t(999)
        self.assertEqual(self.lib.ok_login_read_secret(17, b'Password: ', output, 129, ctypes.byref(length)), -1)
        self.assertEqual((output.raw, length.value), (bytes(129), 0))
        self.assertEqual(self.lib.login_test_consumed(), 7)

    def test_exact_password_limit_and_empty_line(self):
        for data in (b'', b'a' * 128):
            result, output, length = self.line(data + b'\n')
            self.assertEqual((result, output[:length], length), (0, data, len(data)))
            self.assertEqual(output[length], 0)

    def test_overflow_and_nul_reject_whole_line_without_prefix(self):
        for data in (b'a' * 129 + b'\nNEXT', b'abc\x00def\nNEXT', b'abcd\nNEXT'):
            capacity = 4 if data.startswith(b'abcd') else 129
            result, output, length = self.line(data, capacity)
            self.assertEqual((result, output, length), (1, bytes(capacity), 0))
            self.assertEqual(self.lib.login_test_consumed(), data.index(b'\n') + 1)
            self.assertEqual(self.lib.login_test_output(), b'Password: \n')

    def test_drain_has_finite_budget_and_flushes_remainder(self):
        result, output, length = self.line(b'a' * 10000)
        self.assertEqual((result, output, length), (1, bytes(129), 0))
        self.assertEqual(self.lib.login_test_consumed(), 128 + 4096)
        self.assertEqual(self.lib.login_test_flushes(), 2)

    def test_eintr_and_short_writes_do_not_lose_bytes(self):
        result, output, length = self.line(b'abc\n', mode=2 | 4 | 32)
        self.assertEqual((result, output[:length], length), (0, b'abc', 3))
        self.assertEqual(self.lib.login_test_output(), b'Password: \n')

    def test_eof_flush_authority_and_io_errors_erase_partial_secrets(self):
        for data, mode in [(b'secret', 0), (b'secret\n', 1), (b'secret\n', 8),
                           (b'secret\n', 16), (b'', 0)]:
            with self.subTest(mode=mode, data=data):
                self.assertEqual(self.line(data, mode=mode), (-1, bytes(129), 0))
        self.line(b'secret\n', mode=1)
        self.assertEqual(self.lib.login_test_events(), b'ASFS')
        self.assertEqual(self.lib.login_test_output(), b'')
        self.line(b'name\n', mode=1, secret=False)
        self.assertEqual(self.lib.login_test_events(), b'F')

    def test_cr_is_a_line_boundary_and_never_part_of_password(self):
        result, output, length = self.line(b'abc\r\nNEXT')
        self.assertEqual((result, output[:length], length), (0, b'abc', 3))
        self.assertEqual(self.lib.login_test_consumed(), 4)

    def test_invalid_arguments_fail_before_console_use_and_clear_output(self):
        for name in ('ok_login_read_line', 'ok_login_read_secret'):
            for epoch, prompt in [(0, b'Password: '), (0x40000000, b'Password: '), (17, None)]:
                self.lib.login_test_begin(b'secret\n', 7, 0)
                output = ctypes.create_string_buffer(b'X' * 129, 129)
                length = ctypes.c_size_t(999)
                self.assertEqual(getattr(self.lib, name)(epoch, prompt, output, 129,
                                                         ctypes.byref(length)), -1)
                self.assertEqual((output.raw, length.value), (bytes(129), 0))
                self.assertEqual(self.lib.login_test_events(), b'')


if __name__ == '__main__':
    unittest.main()

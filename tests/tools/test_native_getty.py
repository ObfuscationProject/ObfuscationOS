"""Hosted getty session logic over a scripted console, ptmx master and child.

apps/getty/main.c is compiled with host headers and every system call
replaced by a deterministic model. The model is not a terminal or a kernel:
these tests do not establish guest execution, line discipline behaviour or
hangup delivery (scripts/test_getty_login.py drives the guest).
"""
from pathlib import Path
import ctypes
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]

BACKEND = r'''
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <setjmp.h>
#include <signal.h>
#include <stdarg.h>
#include <stdint.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <termios.h>
#include <time.h>

enum {
 OPEN_ERROR = 1, CLOEXEC_ERROR = 2, GRANT_ERROR = 4, UNLOCK_ERROR = 8, WINDOW_ERROR = 16,
 FORK_ERROR = 32, CHILD = 64, SETSID_ERROR = 128, SLAVE_OPEN_ERROR = 256, NO_CTTY = 512,
 EXEC_ERROR = 1024, IGNORE_HANGUP = 2048, HUP_AS_IN = 4096, MASTER_EAGAIN = 8192,
 MASTER_FULL = 16384, NONBLOCK_ERROR = 32768
};
enum { OUTPUT = 1, INPUT = 2, EXIT = 3, SLAVE_CLOSE = 4, REVOKE = 5 };
enum { MASTER = 5, SLAVE = 6, CHILD_PID = 77 };

static unsigned options;
static size_t console_limit, master_limit, master_full_until;
static struct { int tick, kind, value; const unsigned char *data; size_t size; int done; } script[32];
static size_t script_count;
static unsigned char master_out[8192], console_in[4096], console_out[16384], master_in[8192];
static unsigned char write_starts[16385];
static size_t out_head, out_tail, in_head, in_tail, console_used, master_used;
static char events[4096], polls[1024], signals[64], child_env[256], child_argv[64];
static size_t event_count, poll_count;
static int tick, master_open, master_cloexec, master_flags, slave_open, child_alive, child_reaped;
static int child_status, revoked, backend_bad, writes_to_master, window_rows, window_cols;
static int slave_open_flags, dups;
static jmp_buf jump;

int getty_application_main(int, char **, char **);
static void event(char c) { if (event_count + 1 < sizeof(events)) events[event_count++] = c; else backend_bad = 1; }
static void check(int condition) { if (!condition) backend_bad = 1; }
static void child_exits(int status) { if (child_alive) { child_alive = 0; child_status = status; slave_open = 0; } }

void getty_begin(unsigned flags, size_t console_bytes, size_t master_bytes, size_t full_until)
{
 options = flags; console_limit = console_bytes; master_limit = master_bytes; master_full_until = full_until;
 memset(script, 0, sizeof(script)); script_count = 0;
 out_head = out_tail = in_head = in_tail = console_used = master_used = 0;
 memset(console_out, 0, sizeof(console_out)); memset(master_in, 0, sizeof(master_in));
 memset(write_starts, 0, sizeof(write_starts));
 memset(events, 0, sizeof(events)); memset(polls, 0, sizeof(polls)); memset(signals, 0, sizeof(signals));
 memset(child_env, 0, sizeof(child_env)); memset(child_argv, 0, sizeof(child_argv));
 event_count = poll_count = 0;
 tick = master_open = master_cloexec = master_flags = revoked = backend_bad = writes_to_master = 0;
 window_rows = window_cols = dups = slave_open_flags = 0;
 slave_open = child_alive = 1; child_reaped = 0; child_status = -12345;
}
void getty_script(int at, int kind, const unsigned char *data, size_t size, int value)
{
 if (script_count == 32) { backend_bad = 1; return; }
 script[script_count].tick = at; script[script_count].kind = kind; script[script_count].data = data;
 script[script_count].size = size; script[script_count++].value = value;
}
static void advance(void)
{
 /* A getty that never ends its session is a failure, not a hung test. */
 if (++tick > 10000) { backend_bad = 1; revoked = 1; child_exits(SIGKILL); }
 for (size_t i = 0; i < script_count; ++i) {
  if (script[i].done || script[i].tick > tick) continue;
  script[i].done = 1;
  if (script[i].kind == OUTPUT && slave_open) {
   check(out_tail + script[i].size <= sizeof(master_out));
   memcpy(master_out + out_tail, script[i].data, script[i].size); out_tail += script[i].size;
  } else if (script[i].kind == INPUT) {
   check(in_tail + script[i].size <= sizeof(console_in));
   memcpy(console_in + in_tail, script[i].data, script[i].size); in_tail += script[i].size;
  } else if (script[i].kind == EXIT) child_exits(script[i].value);
  else if (script[i].kind == SLAVE_CLOSE) slave_open = 0;
  else if (script[i].kind == REVOKE) revoked = 1;
 }
}
int getty_run(char **environment, int argc)
{
 char *arguments[] = {"/bin/getty", "extra", 0};
 int code = setjmp(jump);
 if (code) return code;
 return getty_application_main(argc, arguments, environment);
}
const char *getty_events(void) { return events; }
const char *getty_polls(void) { return polls; }
const char *getty_signals(void) { return signals; }
const char *getty_child_env(void) { return child_env; }
const char *getty_child_argv(void) { return child_argv; }
const unsigned char *getty_console(size_t *size) { *size = console_used; return console_out; }
const unsigned char *getty_master_input(size_t *size) { *size = master_used; return master_in; }
int getty_bad(void) { return backend_bad; }
int getty_master_open(void) { return master_open; }
int getty_master_flags(void) { return master_flags; }
int getty_cloexec(void) { return master_cloexec; }
int getty_window(void) { return window_rows * 1000 + window_cols; }
int getty_slave_flags(void) { return slave_open_flags; }
int getty_ticks(void) { return tick; }
int getty_write_start(size_t offset) { return offset < sizeof(write_starts) && write_starts[offset]; }

int test_posix_openpt(int flags)
{
 event('P'); check(flags == (O_RDWR | O_NOCTTY));
 if (options & OPEN_ERROR) { errno = EAGAIN; return -1; }
 master_open = 1; master_flags = O_RDWR; return MASTER;
}
int test_fcntl(int fd, int command, ...)
{
 va_list arguments; va_start(arguments, command);
 int value = command == F_GETFL ? 0 : va_arg(arguments, int);
 va_end(arguments);
 check(fd == MASTER && master_open);
 if (command == F_SETFD) {
  event('D'); if (options & CLOEXEC_ERROR) { errno = EBADF; return -1; }
  master_cloexec = value == FD_CLOEXEC; return 0;
 }
 if (command == F_GETFL) { event('g'); return master_flags; }
 check(command == F_SETFL); event('L');
 if (options & NONBLOCK_ERROR) { errno = EINVAL; return -1; }
 master_flags = value; return 0;
}
int test_grantpt(int fd) { event('G'); check(fd == MASTER); if (options & GRANT_ERROR) { errno = EINVAL; return -1; } return 0; }
int test_unlockpt(int fd) { event('U'); check(fd == MASTER); if (options & UNLOCK_ERROR) { errno = EINVAL; return -1; } return 0; }
int test_ptsname_r(int fd, char *buffer, size_t size)
{
 event('N'); check(fd == MASTER && size >= sizeof("/dev/pts/3"));
 strcpy(buffer, "/dev/pts/3"); return 0;
}
int test_ioctl(int fd, unsigned long request, ...)
{
 va_list arguments; va_start(arguments, request);
 struct winsize *window = va_arg(arguments, struct winsize *);
 va_end(arguments);
 event('Z'); check(fd == MASTER && request == TIOCSWINSZ);
 if (options & WINDOW_ERROR) { errno = EIO; return -1; }
 window_rows = window->ws_row; window_cols = window->ws_col;
 check(!window->ws_xpixel && !window->ws_ypixel); return 0;
}
pid_t test_fork(void)
{
 event('F'); check(master_open && master_cloexec && (master_flags & O_NONBLOCK) && window_rows);
 if (options & FORK_ERROR) { errno = EAGAIN; return -1; }
 return options & CHILD ? 0 : CHILD_PID;
}
pid_t test_getpid(void) { return CHILD_PID; }

/* The child side. */
void (*test_signal(int number, void (*handler)(int)))(int)
{
 event('S'); check(handler == SIG_DFL && (options & CHILD));
 size_t used = strlen(signals);
 if (used + 4 < sizeof(signals)) { signals[used] = (char)('A' + number); }
 return SIG_IGN;
}
pid_t test_setsid(void)
{
 event('n'); check(options & CHILD);
 if (options & SETSID_ERROR) { errno = EPERM; return -1; }
 return CHILD_PID;
}
int test_open(const char *path, int flags, ...)
{
 event('o'); check((options & CHILD) && !strcmp(path, "/dev/pts/3")); slave_open_flags = flags;
 if (options & SLAVE_OPEN_ERROR) { errno = EIO; return -1; }
 return SLAVE;
}
pid_t test_tcgetsid(int fd)
{
 event('t'); check(fd == SLAVE);
 return options & NO_CTTY ? 1 : CHILD_PID;
}
int test_dup2(int from, int to)
{
 event('d'); check(from == SLAVE && to == dups++); return to;
}
int test_execve(const char *path, char *const argv[], char *const envp[])
{
 event('X'); check(!strcmp(path, "/bin/login") && dups == 3);
 for (size_t i = 0; argv[i]; ++i) {
  check(strlen(child_argv) + strlen(argv[i]) + 2 < sizeof(child_argv));
  strcat(child_argv, argv[i]); strcat(child_argv, "\n");
 }
 for (size_t i = 0; envp[i]; ++i) {
  check(strlen(child_env) + strlen(envp[i]) + 2 < sizeof(child_env));
  strcat(child_env, envp[i]); strcat(child_env, "\n");
 }
 if (options & EXEC_ERROR) { errno = ENOENT; return -1; }
 longjmp(jump, 1000);
}
_Noreturn void test_exit(int status) { event('E'); longjmp(jump, 2000 + status); }

/* The parent side. */
int test_poll(struct pollfd *fds, nfds_t count, int timeout)
{
 event('p'); check(count == 2 && timeout > 0 && timeout <= 1000 && master_open);
 check(fds[0].fd == 0 && fds[1].fd == MASTER);
 if (poll_count + 3 < sizeof(polls)) {
  polls[poll_count++] = fds[0].events & POLLIN ? 'c' : '-';
  polls[poll_count++] = fds[1].events & POLLOUT ? 'o' : '-';
  polls[poll_count++] = ' ';
 }
 check(fds[1].events & POLLIN);
 advance();
 int ready = 0;
 fds[0].revents = fds[1].revents = 0;
 if (revoked) fds[0].revents = POLLERR | POLLHUP;
 else if ((fds[0].events & POLLIN) && in_head < in_tail) fds[0].revents = POLLIN;
 if (out_head < out_tail) fds[1].revents |= POLLIN;
 else if (!slave_open) fds[1].revents |= options & HUP_AS_IN ? POLLIN : POLLHUP;
 if ((fds[1].events & POLLOUT) && (size_t)tick >= master_full_until) fds[1].revents |= POLLOUT;
 ready = !!fds[0].revents + !!fds[1].revents;
 return ready;
}
ssize_t test_read(int fd, void *buffer, size_t size)
{
 if (fd == 0) {
  event('r'); check(!(options & CHILD));
  if (revoked) { errno = EACCES; return -1; }
  check(in_head < in_tail);
  size_t count = in_tail - in_head < size ? in_tail - in_head : size;
  memcpy(buffer, console_in + in_head, count); in_head += count; return (ssize_t)count;
 }
 event('R'); check(fd == MASTER && master_open);
 if (out_head < out_tail) {
  size_t count = out_tail - out_head < size ? out_tail - out_head : size;
  memcpy(buffer, master_out + out_head, count); out_head += count; return (ssize_t)count;
 }
 if (!slave_open) { errno = EIO; return -1; }
 check(master_flags & O_NONBLOCK);
 errno = EAGAIN; return -1;
}
ssize_t test_write(int fd, const void *data, size_t size)
{
 if (fd == 1) {
  event('w'); check(size > 0);
  size_t count = size < console_limit ? size : console_limit;
  check(console_used + count <= sizeof(console_out));
  write_starts[console_used] = 1;
  memcpy(console_out + console_used, data, count); console_used += count;
  write_starts[console_used] = 1; return (ssize_t)count;
 }
 event('W'); check(fd == MASTER && master_open && (master_flags & O_NONBLOCK) && size > 0);
 ++writes_to_master;
 if ((size_t)tick < master_full_until || ((options & MASTER_EAGAIN) && writes_to_master % 2)) {
  errno = EAGAIN; return -1;
 }
 size_t count = size < master_limit ? size : master_limit;
 check(master_used + count <= sizeof(master_in));
 memcpy(master_in + master_used, data, count); master_used += count; return (ssize_t)count;
}
int test_close(int fd)
{
 if (options & CHILD) { event(fd == MASTER ? 'm' : 'x'); check(fd == MASTER || fd == SLAVE); return 0; }
 event('c'); check(fd == MASTER && master_open); master_open = 0;
 /* The last master close hangs up the session leader. */
 if (!(options & IGNORE_HANGUP)) child_exits(SIGHUP);
 slave_open = 0;
 return 0;
}
pid_t test_waitpid(pid_t pid, int *status, int flags)
{
 check(pid == CHILD_PID && !child_reaped && (flags == WNOHANG || flags == 0));
 event(flags ? 'h' : 'H');
 if (!child_alive) { child_reaped = 1; *status = child_status; return pid; }
 if (flags) return 0;
 backend_bad = 1; errno = ECHILD; return -1;
}
int test_kill(pid_t pid, int number)
{
 event('k'); check(pid == CHILD_PID && number == SIGKILL && !master_open);
 child_exits(SIGKILL); return 0;
}
int test_nanosleep(const struct timespec *request, struct timespec *remaining)
{
 event('s'); check(!remaining && !request->tv_sec && request->tv_nsec > 0 && request->tv_nsec <= 1000000000L);
 advance(); return 0;
}
'''

OUTPUT, INPUT, EXIT, SLAVE_CLOSE, REVOKE = 1, 2, 3, 4, 5
SIGHUP, SIGKILL = 1, 9


class NativeGettyTests(unittest.TestCase):
    OPEN_ERROR = 1
    CLOEXEC_ERROR = 2
    GRANT_ERROR = 4
    UNLOCK_ERROR = 8
    WINDOW_ERROR = 16
    FORK_ERROR = 32
    CHILD = 64
    SETSID_ERROR = 128
    SLAVE_OPEN_ERROR = 256
    NO_CTTY = 512
    EXEC_ERROR = 1024
    IGNORE_HANGUP = 2048
    HUP_AS_IN = 4096
    MASTER_EAGAIN = 8192
    NONBLOCK_ERROR = 32768

    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='native-getty-host-')
        temporary = Path(cls.directory.name)
        (temporary / 'backend.c').write_text(BACKEND)
        common = ['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror', '-fPIC',
                  '-U_FORTIFY_SOURCE', '-D_FORTIFY_SOURCE=0', '-D_GNU_SOURCE',
                  '-fsanitize=undefined', '-fno-sanitize-recover=all']
        names = ('posix_openpt', 'fcntl', 'grantpt', 'unlockpt', 'ptsname_r', 'ioctl', 'fork',
                 'getpid', 'signal', 'setsid', 'open', 'tcgetsid', 'dup2', 'execve', 'poll',
                 'read', 'write', 'close', 'waitpid', 'kill', 'nanosleep')
        substitutions = [f'-D{name}=test_{name}' for name in names]
        substitutions += ['-Dmain=getty_application_main', '-D_Exit=test_exit']
        application = temporary / 'getty.o'
        subprocess.run(common + substitutions + ['-c', str(ROOT / 'apps/getty/main.c'), '-o', str(application)],
                       check=True)
        output = temporary / 'getty.so'
        subprocess.run(common + ['-shared', str(application), str(temporary / 'backend.c'), '-o', str(output)],
                       check=True)
        cls.lib = ctypes.CDLL(str(output), use_errno=True)
        cls.lib.getty_begin.argtypes = [ctypes.c_uint, ctypes.c_size_t, ctypes.c_size_t, ctypes.c_size_t]
        cls.lib.getty_script.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
        cls.lib.getty_run.argtypes = [ctypes.POINTER(ctypes.c_char_p), ctypes.c_int]
        for name in ('events', 'polls', 'signals', 'child_env', 'child_argv'):
            getattr(cls.lib, 'getty_' + name).restype = ctypes.c_char_p
        for name in ('console', 'master_input'):
            getattr(cls.lib, 'getty_' + name).restype = ctypes.c_void_p
            getattr(cls.lib, 'getty_' + name).argtypes = [ctypes.POINTER(ctypes.c_size_t)]

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def run_getty(self, script=(), flags=0, console_limit=4096, master_limit=4096, full_until=0,
                  environment=None, argc=1):
        self.lib.getty_begin(flags, console_limit, master_limit, full_until)
        self.held = []
        for at, kind, *rest in script:
            data = rest[0] if rest and isinstance(rest[0], bytes) else b''
            value = rest[0] if rest and isinstance(rest[0], int) else 0
            self.held.append(ctypes.create_string_buffer(data, max(len(data), 1)))
            self.lib.getty_script(at, kind, self.held[-1], len(data), value)
        if environment is None:
            environment = [b'PATH=/bin', b'HOME=/', b'TERM=vt100', b'OK_SERVICE_GENERATION=1',
                           b'OK_SERVICE_NAME=console', b'OK_SERVICE_ATTEMPT=1',
                           b'OK_SERVICE_READY_FD=-1', b'OK_CONSOLE_EPOCH=5']
        env = (ctypes.c_char_p * (len(environment) + 1))(*environment, None)
        result = self.lib.getty_run(env, argc)
        self.assertEqual(self.lib.getty_bad(), 0, self.lib.getty_events())
        return result, self.lib.getty_events()

    def console(self):
        size = ctypes.c_size_t()
        address = self.lib.getty_console(ctypes.byref(size))
        return ctypes.string_at(address, size.value)

    def master_input(self):
        size = ctypes.c_size_t()
        address = self.lib.getty_master_input(ctypes.byref(size))
        return ctypes.string_at(address, size.value)

    def session(self):
        return [(1, OUTPUT, b'ObfuscationOS\r\nLogin: '), (2, INPUT, b'root\n'),
                (3, OUTPUT, b'root\r\nPassword: '), (4, INPUT, b'secret\n'),
                (5, OUTPUT, b'\r\noksh> '), (6, INPUT, b'exit\n'),
                (7, OUTPUT, b'exit\r\n'), (7, EXIT, 0)]

    def test_master_is_cloexec_nonblocking_unlocked_and_sized_before_the_fork(self):
        result, events = self.run_getty(self.session())
        self.assertEqual(result, 0)
        self.assertTrue(events.startswith(b'PDgLGUNZF'), events)
        self.assertTrue(self.lib.getty_cloexec())
        self.assertEqual(self.lib.getty_master_flags() & 3, 2)
        self.assertEqual(self.lib.getty_window(), 24080)

    def test_session_relays_both_directions_and_reports_open_and_close(self):
        result, events = self.run_getty(self.session())
        self.assertEqual(result, 0)
        self.assertEqual(self.console(),
                         b'GETTY event=open pts=3 pid=77\nObfuscationOS\r\nLogin: root\r\nPassword: '
                         b'\r\noksh> exit\r\nGETTY event=close pts=3 pid=77 status=0 reason=exit\n')
        self.assertEqual(self.master_input(), b'root\nsecret\nexit\n')
        self.assertFalse(self.lib.getty_master_open())
        # Each event line is one console write that other writers cannot split.
        console = self.console()
        for start in (0, console.index(b'GETTY event=close')):
            end = console.index(b'\n', start) + 1
            self.assertTrue(self.lib.getty_write_start(start) and self.lib.getty_write_start(end))
            self.assertFalse(any(self.lib.getty_write_start(i) for i in range(start + 1, end)))
        self.assertLess(events.rindex(b'h'), events.index(b'c'))

    def test_output_left_on_the_master_at_exit_is_drained_before_close(self):
        tail = bytes(range(32, 127)) * 7
        result, events = self.run_getty([(1, OUTPUT, b'oksh> '), (2, OUTPUT, tail), (2, EXIT, 3 << 8)])
        self.assertEqual(result, 0)
        self.assertEqual(self.console(), b'GETTY event=open pts=3 pid=77\noksh> ' + tail +
                         b'\nGETTY event=close pts=3 pid=77 status=768 reason=exit\n')
        self.assertLess(events.rindex(b'R'), events.index(b'c'))

    def test_partial_console_and_master_writes_keep_every_byte_in_order(self):
        script = [item for item in self.session() if item[1] != EXIT] + [(40, EXIT, 0)]
        result, events = self.run_getty(script, flags=self.MASTER_EAGAIN, console_limit=3, master_limit=2)
        self.assertEqual(result, 0)
        self.assertEqual(self.master_input(), b'root\nsecret\nexit\n')
        self.assertIn(b'Login: root\r\nPassword: \r\noksh> exit\r\n', self.console())
        self.assertRegex(self.console(), rb'\nGETTY event=close pts=3 pid=77 status=0 reason=(exit|hangup)\n$')

    def test_console_input_waits_while_the_master_is_full(self):
        result, events = self.run_getty([(1, INPUT, b'typed ahead\n'), (2, INPUT, b'more\n'), (9, EXIT, 0)],
                                        full_until=5)
        self.assertEqual(result, 0)
        self.assertEqual(self.master_input(), b'typed ahead\nmore\n')
        polls = self.lib.getty_polls().split()
        # First poll reads the console; then only POLLOUT on the master is
        # requested until it has room, and console reads resume after that.
        self.assertEqual(polls[0], b'c-')
        self.assertEqual(polls[1:4], [b'-o', b'-o', b'-o'])
        self.assertIn(b'c-', polls[5:])
        self.assertEqual(events.count(b'r'), 2)

    def test_slave_hangup_closes_master_then_reaps_the_hung_up_leader(self):
        for flags in (0, self.HUP_AS_IN):
            with self.subTest(flags=flags):
                result, events = self.run_getty([(1, OUTPUT, b'oksh> '), (2, SLAVE_CLOSE)], flags=flags)
                self.assertEqual(result, 0)
                self.assertTrue(self.console().endswith(
                    b'oksh> \nGETTY event=close pts=3 pid=77 status=1 reason=hangup\n'), self.console())
                self.assertLess(events.index(b'c'), events.index(b'h', events.index(b'c')))

    def test_a_session_that_survives_the_hangup_is_killed_after_a_bounded_grace(self):
        result, events = self.run_getty([(1, SLAVE_CLOSE)], flags=self.IGNORE_HANGUP)
        self.assertEqual(result, 0)
        after = events[events.index(b'c'):].rstrip(b'w')
        self.assertEqual(after.count(b's'), 30)
        self.assertEqual(after.count(b'k'), 1)
        self.assertTrue(after.endswith(b'kH'), after)
        self.assertTrue(self.console().endswith(b'status=9 reason=hangup\n'))

    def test_revoked_lease_hangs_the_session_up_without_further_console_reads(self):
        result, events = self.run_getty([(1, OUTPUT, b'oksh> '), (2, INPUT, b'ls\n'), (3, REVOKE),
                                          (3, OUTPUT, b'late output')])
        self.assertEqual(result, 0)
        self.assertEqual(events.count(b'r'), 1)
        self.assertNotIn(b'R', events[events.index(b'c'):])
        self.assertNotIn(b'late output', self.console())
        self.assertTrue(self.console().endswith(
            b'oksh> \nGETTY event=close pts=3 pid=77 status=1 reason=revoked\n'), self.console())

    def test_child_resets_signals_takes_the_slave_as_ctty_and_execs_login(self):
        result, events = self.run_getty(flags=self.CHILD)
        self.assertEqual(result, 1000)
        self.assertTrue(events.startswith(b'PDgLGUNZF' + b'S' * 10 + b'mnotdddxX'), events)
        self.assertEqual(self.lib.getty_slave_flags(), 2)
        self.assertEqual(self.lib.getty_child_argv(), b'/bin/login\n')
        self.assertEqual(self.lib.getty_child_env(), b'TERM=vt100\nOK_CONSOLE_EPOCH=5\n')
        signals = self.lib.getty_signals()
        for number in (1, 2, 3, 15, 17, 18, 20, 21, 22, 28):
            self.assertIn(bytes([65 + number]), signals)
        self.assertEqual(self.console(), b'')

    def test_child_setup_failures_never_exec_login(self):
        for flags, stage, absent in ((self.SETSID_ERROR, b'setsid', b'o'), (self.SLAVE_OPEN_ERROR, b'open', b'd'),
                                     (self.NO_CTTY, b'ctty', b'd'), (self.EXEC_ERROR, b'exec', b'')):
            with self.subTest(stage=stage):
                result, events = self.run_getty(flags=self.CHILD | flags)
                self.assertEqual(result, 2127)
                self.assertIn(b'GETTY event=error stage=' + stage + b' errno=', self.console())
                if absent:
                    self.assertNotIn(absent, events[events.index(b'F'):])
                    self.assertNotIn(b'X', events)

    def test_setup_failures_report_close_the_master_and_never_fork(self):
        for flags, closes in ((self.OPEN_ERROR, 0), (self.CLOEXEC_ERROR, 1), (self.NONBLOCK_ERROR, 1),
                              (self.GRANT_ERROR, 1), (self.UNLOCK_ERROR, 1), (self.WINDOW_ERROR, 1)):
            with self.subTest(flags=flags):
                result, events = self.run_getty(flags=flags)
                self.assertEqual(result, 1)
                self.assertNotIn(b'F', events)
                self.assertEqual(events.count(b'c'), closes)
                self.assertTrue(self.console().startswith(b'GETTY event=error stage=open errno='))
        result, events = self.run_getty(flags=self.FORK_ERROR)
        self.assertEqual(result, 1)
        self.assertTrue(events.rstrip(b'w').endswith(b'Fc'))
        self.assertTrue(self.console().startswith(b'GETTY event=error stage=fork errno='))
        result, events = self.run_getty(argc=2)
        self.assertEqual((result, events.strip(b'w')), (1, b''))
        self.assertTrue(self.console().startswith(b'GETTY event=error stage=arguments errno='))


if __name__ == '__main__':
    unittest.main()

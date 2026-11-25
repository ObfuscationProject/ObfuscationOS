/* Guest TTY, session and job-control probe (docs/qualification/GETTY_LOGIN.md).
 *
 * Self-contained: each case opens its own /dev/ptmx pair and forks a session
 * leader that runs the checks, so it needs nothing from the console but a
 * place to print. Native processes have only SIG_DFL and SIG_IGN and receive
 * no SIGCHLD, so every signal outcome is observed through waitpid status
 * words (WUNTRACED, WCONTINUED, WTERMSIG). Every wait and read is bounded, so
 * a broken kernel fails a case instead of hanging the shell.
 *
 * Output: one `TTY_SESSIONS_CASE n=<n> name=<name> result=pass` line per case
 * and a final `TTY_SESSIONS_PROBE stage=PASS cases=<n> arch=<arch>`, or
 * `TTY_SESSIONS_PROBE stage=FAIL case=<n> name=<name> line=<source line>
 * value=<v> errno=<e> arch=<arch>` at the first failure. `line` is the line
 * of the failed check in this file; line 0 means the leader's own status was
 * wrong (value is its wait status) and -1 a lost case process. An optional
 * argument runs a single case by number.
 */
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/wait.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#if defined(OK_USER_ARCH_I386)
#define ARCH "i386"
#elif defined(OK_USER_ARCH_X86_64)
#define ARCH "x86_64"
#elif defined(OK_USER_ARCH_AARCH64)
#define ARCH "aarch64"
#elif defined(OK_USER_ARCH_ARM32)
#define ARCH "arm32"
#elif defined(OK_USER_ARCH_RV64)
#define ARCH "rv64"
#elif defined(OK_USER_ARCH_RV32)
#define ARCH "rv32"
#elif defined(OK_USER_ARCH_LOONGARCH64)
#define ARCH "loongarch64"
#elif defined(OK_USER_ARCH_MIPS64)
#define ARCH "mips64"
#elif defined(OK_USER_ARCH_MIPS)
#define ARCH "mips"
#elif defined(OK_USER_ARCH_PPC)
#define ARCH "ppc"
#else
#error "unknown native profile"
#endif

/* Emulated profiles are slow; a working kernel answers within milliseconds. */
#define WAIT_MS 15000
#define CASE_MS 60000

struct record {
    int32_t line;
    int32_t error;
    int64_t value;
};

/* Set in each case's processes. */
static int report_fd = -1;
static int ready_fd = -1;
static int master = -1;
static int tty = -1;
static char slave_path[32];

static void fail_at(int line, long value)
{
    struct record record = {line, errno, value};
    if (report_fd >= 0)
        write(report_fd, &record, sizeof record);
    _Exit(1);
}

#define CHECK(condition, value)                                                                                      \
    do {                                                                                                             \
        if (!(condition))                                                                                            \
            fail_at(__LINE__, (long)(value));                                                                        \
    } while (0)

/* A witness that outlives the leader reports success with line 0. */
static void witness_pass(void)
{
    struct record record = {0, 0, 0};
    write(report_fd, &record, sizeof record);
}

static int64_t now_ms(void)
{
    struct timespec now = {0, 0};
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static void nap(long ms)
{
    struct timespec delay = {0, ms * 1000000L};
    nanosleep(&delay, 0);
}

static void reset_signals(void)
{
    static const int numbers[] = {SIGHUP, SIGINT, SIGQUIT, SIGTSTP, SIGTTIN, SIGTTOU, SIGCONT, SIGWINCH, SIGTERM};
    for (unsigned i = 0; i < sizeof numbers / sizeof numbers[0]; ++i)
        signal(numbers[i], SIG_DFL);
}

/* Blocks until a signal ends the process. */
static void park(void)
{
    int never[2];
    char byte;
    if (pipe(never) < 0)
        fail_at(__LINE__, 0);
    long got = read(never[0], &byte, 1);
    fail_at(__LINE__, got);
}

static int wait_status(pid_t pid, int options, int line)
{
    const int64_t end = now_ms() + WAIT_MS;
    for (;;) {
        int status = 0;
        const pid_t got = waitpid(pid, &status, options | WNOHANG);
        if (got == pid)
            return status;
        if (got != 0)
            fail_at(line, got);
        if (now_ms() > end) {
            errno = 0;
            fail_at(line, -2);
        }
        nap(2);
    }
}

static void expect_exit0(pid_t pid, int line)
{
    const int status = wait_status(pid, 0, line);
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0)
        fail_at(line, status);
}

static void expect_signal(pid_t pid, int number, int line)
{
    int status;
    do
        status = wait_status(pid, WCONTINUED, line);
    while (WIFCONTINUED(status));
    if (!WIFSIGNALED(status) || WTERMSIG(status) != number)
        fail_at(line, status);
}

static void expect_stop(pid_t pid, int number, int line)
{
    const int status = wait_status(pid, WUNTRACED, line);
    if (!WIFSTOPPED(status) || WSTOPSIG(status) != number)
        fail_at(line, status);
}

static void expect_continued(pid_t pid, int line)
{
    const int status = wait_status(pid, WCONTINUED, line);
    if (!WIFCONTINUED(status))
        fail_at(line, status);
}

static void kill_child(pid_t pid, int line)
{
    if (kill(pid, SIGKILL) < 0)
        fail_at(line, pid);
    expect_signal(pid, SIGKILL, line);
}

/* Reads exactly `count` bytes, waiting at most WAIT_MS for them. */
static void read_exact(int fd, char *buffer, size_t count, int line)
{
    const int64_t end = now_ms() + WAIT_MS;
    size_t have = 0;
    while (have < count) {
        struct pollfd ready = {fd, POLLIN, 0};
        const int64_t left = end - now_ms();
        if (left <= 0) {
            errno = 0;
            fail_at(line, (long)have);
        }
        const int polled = poll(&ready, 1, (int)(left > 200 ? 200 : left));
        if (polled < 0)
            fail_at(line, polled);
        if (polled == 0)
            continue;
        const long got = read(fd, buffer + have, count - have);
        if (got <= 0)
            fail_at(line, got);
        have += (size_t)got;
    }
}

static void expect_bytes(int fd, const char *text, int line)
{
    char buffer[64];
    const size_t count = strlen(text);
    read_exact(fd, buffer, count, line);
    for (size_t i = 0; i < count; ++i)
        if (buffer[i] != text[i]) {
            errno = 0;
            fail_at(line, (long)(i << 8 | (unsigned char)buffer[i]));
        }
}

static void send_text(int fd, const char *text, int line)
{
    const long count = (long)strlen(text);
    const long wrote = write(fd, text, (size_t)count);
    if (wrote != count)
        fail_at(line, wrote);
}

/* One canonical read on the slave must return exactly `text`. */
static void expect_line(int fd, const char *text, int line)
{
    char buffer[64];
    struct pollfd ready = {fd, POLLIN, 0};
    const int polled = poll(&ready, 1, WAIT_MS);
    if (polled != 1)
        fail_at(line, polled);
    const long got = read(fd, buffer, sizeof buffer);
    if (got != (long)strlen(text) || memcmp(buffer, text, (size_t)got) != 0)
        fail_at(line, got);
}

static void wait_byte(int fd, int line)
{
    char byte;
    read_exact(fd, &byte, 1, line);
}

enum { SAME_GROUP, NEW_GROUP, NEW_SESSION, JOIN_GROUP };
static pid_t join_group;

/* Forks a child that runs `body` and exits 0. The child first enters its
 * group or session, resets the job-control signals and reports that it has,
 * so the caller can name its group at once. */
static pid_t spawn(int placement, void (*body)(void), int line)
{
    int sync[2];
    if (pipe(sync) < 0)
        fail_at(line, 0);
    const pid_t pid = fork();
    if (pid < 0)
        fail_at(line, pid);
    if (pid == 0) {
        close(sync[0]);
        reset_signals();
        if (placement == NEW_GROUP && setpgid(0, 0) < 0)
            fail_at(line, 0);
        if (placement == NEW_SESSION && setsid() != getpid())
            fail_at(line, 0);
        if (placement == JOIN_GROUP && setpgid(0, join_group) < 0)
            fail_at(line, join_group);
        if (write(sync[1], "s", 1) != 1)
            fail_at(line, 0);
        close(sync[1]);
        body();
        _Exit(0);
    }
    close(sync[1]);
    wait_byte(sync[0], line);
    close(sync[0]);
    return pid;
}

/* A second member of `group` that never touches the terminal: only a signal
 * sent to the whole group reaches it, not one sent to the caller or the
 * group's leader alone. */
static pid_t companion(pid_t group, int line)
{
    join_group = group;
    return spawn(JOIN_GROUP, park, line);
}

/* Holds a background reader or writer until its companion has joined. */
static int gate[2] = {-1, -1};

static void open_gate(int line)
{
    if (pipe(gate) < 0)
        fail_at(line, 0);
}

static void pass_gate(void)
{
    wait_byte(gate[0], __LINE__);
}

static void release_gate(int line)
{
    if (write(gate[1], "g", 1) != 1)
        fail_at(line, 0);
    close(gate[0]);
    close(gate[1]);
}

static void acquire(void)
{
    tty = open(slave_path, O_RDWR);
    CHECK(tty >= 0, tty);
    CHECK(tcgetsid(tty) == getpid(), tcgetsid(tty));
}

/* A leader that hands the foreground away reclaims it from the background,
 * which raises SIGTTOU unless the signal is ignored (as a shell does). */
static void reclaim(int line)
{
    if (tcsetpgrp(tty, getpgrp()) != 0)
        fail_at(line, 0);
    if (tcgetpgrp(tty) != getpgrp())
        fail_at(line, tcgetpgrp(tty));
}

static int open_pair(char *path, size_t size)
{
    const int fd = posix_openpt(O_RDWR | O_NOCTTY);
    if (fd < 0 || grantpt(fd) < 0 || unlockpt(fd) < 0 || ptsname_r(fd, path, size) != 0)
        return -1;
    return fd;
}

/* 1: open without O_NOCTTY acquires; /dev/tty is the ctty; the master reports
 * the slave's session and group. */
static void case_acquire(void)
{
    const pid_t self = getpid();
    pid_t value = 0;
    acquire();
    CHECK(tcgetpgrp(tty) == self, tcgetpgrp(tty));
    CHECK(getsid(0) == self, getsid(0));
    CHECK(isatty(tty) == 1, 0);
    CHECK(ioctl(master, TIOCGSID, &value) == 0 && value == self, value);
    CHECK(ioctl(master, TIOCGPGRP, &value) == 0 && value == self, value);
    const int alias = open("/dev/tty", O_RDWR);
    CHECK(alias >= 0, alias);
    CHECK(tcgetsid(alias) == self, tcgetsid(alias));
    send_text(alias, "via-tty\n", __LINE__);
    expect_bytes(master, "via-tty\r\n", __LINE__);
    close(alias);
}

/* 2: O_NOCTTY does not acquire, /dev/tty is ENXIO without a ctty, and
 * TIOCSCTTY(0) then acquires. */
static void case_noctty(void)
{
    tty = open(slave_path, O_RDWR | O_NOCTTY);
    CHECK(tty >= 0, tty);
    CHECK(tcgetsid(tty) < 0 && errno == ENOTTY, 0);
    CHECK(tcgetpgrp(tty) < 0 && errno == ENOTTY, 0);
    CHECK(open("/dev/tty", O_RDWR) < 0 && errno == ENXIO, 0);
    CHECK(ioctl(tty, TIOCSCTTY, 0) == 0, 0);
    CHECK(tcgetsid(tty) == getpid(), tcgetsid(tty));
    CHECK(tcgetpgrp(tty) == getpid(), tcgetpgrp(tty));
    const int alias = open("/dev/tty", O_RDWR);
    CHECK(alias >= 0, alias);
    close(alias);
}

static int other_tty = -1;
static char other_path[32];

static void sctty_member(void)
{
    /* Member with a ctty, then a member without one: never a leader. */
    CHECK(ioctl(other_tty, TIOCSCTTY, 0) < 0 && errno == EPERM, 0);
    CHECK(ioctl(tty, TIOCNOTTY) == 0, 0);
    CHECK(ioctl(other_tty, TIOCSCTTY, 1) < 0 && errno == EPERM, 0);
}

static void sctty_foreign(void)
{
    /* A new leader without a ctty: the first terminal belongs to the probe
     * leader's session, so neither an open nor TIOCSCTTY(1) takes it. */
    const int fd = open(slave_path, O_RDWR);
    CHECK(fd >= 0, fd);
    CHECK(tcgetsid(fd) < 0 && errno == ENOTTY, 0);
    CHECK(ioctl(fd, TIOCSCTTY, 1) < 0 && errno == EPERM, 0);
    CHECK(ioctl(fd, TIOCSCTTY, 0) < 0 && errno == EPERM, 0);
    const int write_only = open(other_path, O_WRONLY | O_NOCTTY);
    CHECK(write_only >= 0, write_only);
    CHECK(ioctl(write_only, TIOCSCTTY, 0) < 0 && errno == EPERM, 0);
    const int readable = open(other_path, O_RDWR | O_NOCTTY);
    CHECK(readable >= 0, readable);
    CHECK(ioctl(readable, TIOCSCTTY, 0) == 0, 0);
    CHECK(tcgetsid(readable) == getpid(), tcgetsid(readable));
}

/* 3: TIOCSCTTY refusals (kernel tty.md section 4). */
static void case_sctty(void)
{
    acquire();
    CHECK(ioctl(tty, TIOCSCTTY, 0) == 0, 0);
    CHECK(ioctl(tty, TIOCSCTTY, 1) == 0, 0);
    CHECK(ioctl(master, TIOCSCTTY, 0) < 0 && errno == ENOTTY, 0);
    const int other_master = open_pair(other_path, sizeof other_path);
    CHECK(other_master >= 0, other_master);
    other_tty = open(other_path, O_RDWR | O_NOCTTY);
    CHECK(other_tty >= 0, other_tty);
    CHECK(ioctl(other_tty, TIOCSCTTY, 0) < 0 && errno == EPERM, 0);
    CHECK(ioctl(other_tty, TIOCSCTTY, 1) < 0 && errno == EPERM, 0);
    expect_exit0(spawn(SAME_GROUP, sctty_member, __LINE__), __LINE__);
    expect_exit0(spawn(NEW_SESSION, sctty_foreign, __LINE__), __LINE__);
    CHECK(tcgetsid(tty) == getpid(), tcgetsid(tty));
    close(other_tty);
    close(other_master);
}

static void notty_member(void)
{
    CHECK(tcgetsid(tty) == getsid(0), tcgetsid(tty));
    CHECK(ioctl(master, TIOCNOTTY) < 0 && errno == ENOTTY, 0);
    CHECK(ioctl(tty, TIOCNOTTY) == 0, 0);
    CHECK(tcgetsid(tty) < 0 && errno == ENOTTY, 0);
    CHECK(open("/dev/tty", O_RDWR) < 0 && errno == ENXIO, 0);
    CHECK(ioctl(tty, TIOCNOTTY) < 0 && errno == ENOTTY, 0);
}

/* 4: TIOCNOTTY by a foreground member detaches only that member. */
static void case_notty_member(void)
{
    acquire();
    expect_exit0(spawn(SAME_GROUP, notty_member, __LINE__), __LINE__);
    CHECK(tcgetsid(tty) == getpid(), tcgetsid(tty));
    CHECK(tcgetpgrp(tty) == getpid(), tcgetpgrp(tty));
    const int alias = open("/dev/tty", O_RDWR);
    CHECK(alias >= 0, alias);
    close(alias);
}

/* 5: TIOCNOTTY by the leader hangs up the whole foreground group and clears
 * the association; the leader may acquire again. */
static void case_notty_leader(void)
{
    acquire();
    const pid_t member = spawn(NEW_GROUP, park, __LINE__);
    const pid_t other = companion(member, __LINE__);
    CHECK(tcsetpgrp(tty, member) == 0, member);
    CHECK(ioctl(tty, TIOCNOTTY) == 0, 0);
    expect_signal(member, SIGHUP, __LINE__);
    expect_signal(other, SIGHUP, __LINE__);
    CHECK(tcgetsid(tty) < 0 && errno == ENOTTY, 0);
    CHECK(open("/dev/tty", O_RDWR) < 0 && errno == ENXIO, 0);
    CHECK(ioctl(tty, TIOCSCTTY, 0) == 0, 0);
    CHECK(tcgetsid(tty) == getpid(), tcgetsid(tty));
    CHECK(tcgetpgrp(tty) == getpid(), tcgetpgrp(tty));
}

/* 6: tcgetsid/tcgetpgrp/tcsetpgrp and their refusals. */
static void case_pgrp(void)
{
    pid_t value = 0;
    acquire();
    CHECK(tcgetpgrp(tty) == getpid(), tcgetpgrp(tty));
    CHECK(tcsetpgrp(tty, -1) < 0 && errno == EINVAL, 0);
    CHECK(tcsetpgrp(tty, 0x7fffffff) < 0 && errno == ESRCH, 0);
    const pid_t foreign = getpgid(getppid());
    CHECK(foreign > 0, foreign);
    CHECK(tcsetpgrp(tty, foreign) < 0 && errno == EPERM, foreign);
    CHECK(tcsetpgrp(master, getpgrp()) == 0, 0);
    const pid_t member = spawn(NEW_GROUP, park, __LINE__);
    CHECK(tcsetpgrp(tty, member) == 0, member);
    CHECK(tcgetpgrp(tty) == member, tcgetpgrp(tty));
    CHECK(ioctl(master, TIOCGPGRP, &value) == 0 && value == member, value);
    CHECK(tcgetsid(tty) == getpid(), tcgetsid(tty));
    signal(SIGTTOU, SIG_IGN);
    reclaim(__LINE__);
    kill_child(member, __LINE__);
}

static void read_ttin(void)
{
    char buffer[16];
    pass_gate();
    const long got = read(tty, buffer, sizeof buffer);
    CHECK(got == 5 && memcmp(buffer, "ttin\n", 5) == 0, got);
}

/* 7: a background read stops the whole group with SIGTTIN; once continued
 * in the foreground the same read completes. */
static void case_ttin_stop(void)
{
    acquire();
    signal(SIGTTOU, SIG_IGN);
    open_gate(__LINE__);
    const pid_t reader = spawn(NEW_GROUP, read_ttin, __LINE__);
    const pid_t other = companion(reader, __LINE__);
    release_gate(__LINE__);
    expect_stop(reader, SIGTTIN, __LINE__);
    expect_stop(other, SIGTTIN, __LINE__);
    CHECK(tcsetpgrp(tty, reader) == 0, reader);
    CHECK(kill(-reader, SIGCONT) == 0, reader);
    expect_continued(reader, __LINE__);
    expect_continued(other, __LINE__);
    send_text(master, "ttin\n", __LINE__);
    expect_exit0(reader, __LINE__);
    expect_bytes(master, "ttin\r\n", __LINE__);
    reclaim(__LINE__);
    kill_child(other, __LINE__);
}

static void read_ignored(void)
{
    char byte;
    signal(SIGTTIN, SIG_IGN);
    struct pollfd ready = {tty, POLLIN, 0};
    CHECK(poll(&ready, 1, 0) == 0 && ready.revents == 0, ready.revents);
    CHECK(read(tty, &byte, 1) < 0 && errno == EIO, 0);
}

/* 8: with SIGTTIN ignored a background read is EIO; poll reports no error. */
static void case_ttin_eio(void)
{
    acquire();
    expect_exit0(spawn(NEW_GROUP, read_ignored, __LINE__), __LINE__);
    CHECK(tcgetpgrp(tty) == getpid(), tcgetpgrp(tty));
}

static void set_attributes(void)
{
    struct termios attributes;
    CHECK(tcgetattr(tty, &attributes) == 0, 0);
    tcsetattr(tty, TCSANOW, &attributes);
    fail_at(__LINE__, 0);
}

static void set_group(void)
{
    tcsetpgrp(tty, getpgrp());
    fail_at(__LINE__, 0);
}

static void ttou_ignored(void)
{
    struct termios attributes;
    signal(SIGTTOU, SIG_IGN);
    CHECK(tcgetattr(tty, &attributes) == 0, 0);
    CHECK(tcsetattr(tty, TCSANOW, &attributes) == 0, 0);
    CHECK(tcflush(tty, TCIFLUSH) == 0, 0);
    CHECK(tcsetpgrp(tty, getpgrp()) == 0, 0);
    CHECK(tcgetpgrp(tty) == getpgrp(), tcgetpgrp(tty));
}

/* 9: background tcsetattr and TIOCSPGRP stop with SIGTTOU, and go through
 * with SIGTTOU ignored. */
static void case_ttou_stop(void)
{
    acquire();
    signal(SIGTTOU, SIG_IGN);
    const pid_t setter = spawn(NEW_GROUP, set_attributes, __LINE__);
    expect_stop(setter, SIGTTOU, __LINE__);
    kill_child(setter, __LINE__);
    const pid_t grabber = spawn(NEW_GROUP, set_group, __LINE__);
    expect_stop(grabber, SIGTTOU, __LINE__);
    kill_child(grabber, __LINE__);
    CHECK(tcgetpgrp(tty) == getpid(), tcgetpgrp(tty));
    expect_exit0(spawn(NEW_GROUP, ttou_ignored, __LINE__), __LINE__);
    reclaim(__LINE__);
}

static void write_stopped(void)
{
    pass_gate();
    write(tty, "t", 1);
    fail_at(__LINE__, 0);
}

static void write_ignored(void)
{
    signal(SIGTTOU, SIG_IGN);
    CHECK(write(tty, "ign", 3) == 3, 0);
}

static void write_plain(void)
{
    CHECK(write(tty, "plain", 5) == 5, 0);
}

static void set_tostop(int on)
{
    struct termios attributes;
    CHECK(tcgetattr(tty, &attributes) == 0, 0);
    if (on)
        attributes.c_lflag |= TOSTOP;
    else
        attributes.c_lflag &= ~(tcflag_t)TOSTOP;
    CHECK(tcsetattr(tty, TCSANOW, &attributes) == 0, 0);
}

/* 10: TOSTOP stops a background writer's group with SIGTTOU (nothing reaches
 * the master); ignored SIGTTOU or a clear TOSTOP lets the write through. */
static void case_tostop(void)
{
    acquire();
    set_tostop(1);
    open_gate(__LINE__);
    const pid_t writer = spawn(NEW_GROUP, write_stopped, __LINE__);
    const pid_t other = companion(writer, __LINE__);
    release_gate(__LINE__);
    expect_stop(writer, SIGTTOU, __LINE__);
    expect_stop(other, SIGTTOU, __LINE__);
    kill_child(writer, __LINE__);
    kill_child(other, __LINE__);
    expect_exit0(spawn(NEW_GROUP, write_ignored, __LINE__), __LINE__);
    expect_bytes(master, "ign", __LINE__);
    set_tostop(0);
    expect_exit0(spawn(NEW_GROUP, write_plain, __LINE__), __LINE__);
    expect_bytes(master, "plain", __LINE__);
}

/* A reader that the leader moves to the foreground must not read before
 * that, or SIGTTIN stops it first. */
static void await_foreground(void)
{
    const int64_t end = now_ms() + WAIT_MS;
    while (tcgetpgrp(tty) != getpgrp()) {
        CHECK(now_ms() < end, tcgetpgrp(tty));
        nap(2);
    }
}

static void read_forever(void)
{
    char byte;
    await_foreground();
    const long got = read(tty, &byte, 1);
    fail_at(__LINE__, got);
}

/* 11: VINTR written to the master kills the whole foreground group with
 * SIGINT. */
static void case_isig_int(void)
{
    acquire();
    signal(SIGTTOU, SIG_IGN);
    const pid_t reader = spawn(NEW_GROUP, read_forever, __LINE__);
    const pid_t other = companion(reader, __LINE__);
    CHECK(tcsetpgrp(tty, reader) == 0, reader);
    send_text(master, "\x03", __LINE__);
    expect_signal(reader, SIGINT, __LINE__);
    expect_signal(other, SIGINT, __LINE__);
    expect_bytes(master, "^C", __LINE__);
    reclaim(__LINE__);
}

static void read_go(void)
{
    char buffer[16];
    await_foreground();
    const long got = read(tty, buffer, sizeof buffer);
    CHECK(got == 3 && memcmp(buffer, "go\n", 3) == 0, got);
}

/* 12: VSUSP stops the whole foreground group with SIGTSTP; kill(-pgid,
 * SIGCONT) continues it and the reader's read then completes. */
static void case_isig_tstp(void)
{
    acquire();
    signal(SIGTTOU, SIG_IGN);
    const pid_t reader = spawn(NEW_GROUP, read_go, __LINE__);
    const pid_t other = companion(reader, __LINE__);
    CHECK(tcsetpgrp(tty, reader) == 0, reader);
    send_text(master, "\x1a", __LINE__);
    expect_stop(reader, SIGTSTP, __LINE__);
    expect_stop(other, SIGTSTP, __LINE__);
    expect_bytes(master, "^Z", __LINE__);
    CHECK(kill(-reader, SIGCONT) == 0, reader);
    expect_continued(reader, __LINE__);
    expect_continued(other, __LINE__);
    send_text(master, "go\n", __LINE__);
    expect_exit0(reader, __LINE__);
    expect_bytes(master, "go\r\n", __LINE__);
    reclaim(__LINE__);
    kill_child(other, __LINE__);
}

/* 13: pts defaults: canonical lines with erase, ECHO/ECHOE, ICRNL, ONLCR
 * and VEOF, all observed from the master. */
static void case_canonical(void)
{
    struct termios attributes;
    acquire();
    CHECK(tcgetattr(tty, &attributes) == 0, 0);
    CHECK((attributes.c_lflag & (ISIG | ICANON | ECHO | ECHOE)) == (ISIG | ICANON | ECHO | ECHOE),
          attributes.c_lflag);
    CHECK((attributes.c_oflag & (OPOST | ONLCR)) == (OPOST | ONLCR), attributes.c_oflag);
    CHECK((attributes.c_iflag & ICRNL) != 0, attributes.c_iflag);
    CHECK(attributes.c_cc[VINTR] == 3 && attributes.c_cc[VSUSP] == 26 && attributes.c_cc[VEOF] == 4, 0);
    send_text(master, "ab\x7f" "c\n", __LINE__);
    expect_bytes(master, "ab\b \bc\r\n", __LINE__);
    expect_line(tty, "ac\n", __LINE__);
    send_text(master, "pq", __LINE__);
    expect_bytes(master, "pq", __LINE__);
    struct pollfd ready = {tty, POLLIN, 0};
    CHECK(poll(&ready, 1, 100) == 0, ready.revents);
    send_text(master, "\r", __LINE__);
    expect_bytes(master, "\r\n", __LINE__);
    expect_line(tty, "pq\n", __LINE__);
    send_text(tty, "out\n", __LINE__);
    expect_bytes(master, "out\r\n", __LINE__);
    send_text(master, "\x04", __LINE__);
    char byte;
    CHECK(poll(&ready, 1, WAIT_MS) == 1, 0);
    CHECK(read(tty, &byte, 1) == 0, 0);
    send_text(tty, "!", __LINE__);
    expect_bytes(master, "!", __LINE__);
}

/* 14: with ECHO clear input is not echoed; restoring it echoes again. */
static void case_echo_off(void)
{
    struct termios attributes;
    acquire();
    CHECK(tcgetattr(tty, &attributes) == 0, 0);
    attributes.c_lflag &= ~(tcflag_t)ECHO;
    CHECK(tcsetattr(tty, TCSANOW, &attributes) == 0, 0);
    send_text(master, "pw\n", __LINE__);
    expect_line(tty, "pw\n", __LINE__);
    send_text(tty, "!", __LINE__);
    expect_bytes(master, "!", __LINE__);
    attributes.c_lflag |= ECHO;
    CHECK(tcsetattr(tty, TCSAFLUSH, &attributes) == 0, 0);
    send_text(master, "e\n", __LINE__);
    expect_bytes(master, "e\r\n", __LINE__);
    expect_line(tty, "e\n", __LINE__);
}

static void hangup_witness(void)
{
    struct termios attributes;
    char byte;
    signal(SIGHUP, SIG_IGN);
    const int64_t end = now_ms() + WAIT_MS;
    for (;;) {
        struct pollfd ready = {tty, POLLIN, 0};
        CHECK(poll(&ready, 1, 100) >= 0, 0);
        if (ready.revents & POLLHUP)
            break;
        CHECK(now_ms() < end, ready.revents);
    }
    CHECK(read(tty, &byte, 1) == 0, 0);
    CHECK(write(tty, "x", 1) < 0 && errno == EIO, 0);
    CHECK(tcgetattr(tty, &attributes) < 0 && errno == EIO, 0);
    CHECK(open("/dev/tty", O_RDWR) < 0 && errno == ENXIO, 0);
    witness_pass();
}

/* 15: the master's last close sends SIGHUP to the session leader (the probe
 * sees it die); a member that ignores SIGHUP sees the hung-up slave. */
static void case_master_close(void)
{
    acquire();
    close(master);
    master = -1;
    spawn(NEW_GROUP, hangup_witness, __LINE__);
    CHECK(write(ready_fd, "r", 1) == 1, 0);
    park();
}

static pid_t hup_target, hup_other;

static void leader_exit_witness(void)
{
    signal(SIGTTOU, SIG_IGN);
    hup_target = spawn(NEW_GROUP, park, __LINE__);
    hup_other = companion(hup_target, __LINE__);
    CHECK(tcsetpgrp(tty, hup_target) == 0, hup_target);
    CHECK(tcgetpgrp(tty) == hup_target, tcgetpgrp(tty));
    CHECK(write(ready_fd, "r", 1) == 1, 0);
    expect_signal(hup_target, SIGHUP, __LINE__);
    expect_signal(hup_other, SIGHUP, __LINE__);
    CHECK(tcgetsid(tty) < 0 && errno == ENOTTY, 0);
    witness_pass();
}

/* 16: the session leader's exit sends SIGHUP to the whole foreground group. */
static void case_leader_exit(void)
{
    int ready[2];
    acquire();
    CHECK(pipe(ready) == 0, 0);
    ready_fd = ready[1];
    spawn(NEW_GROUP, leader_exit_witness, __LINE__);
    wait_byte(ready[0], __LINE__);
}

static void orphan_witness(void)
{
    signal(SIGHUP, SIG_IGN);
    const pid_t dies = fork();
    CHECK(dies >= 0, dies);
    if (dies == 0) {
        signal(SIGHUP, SIG_DFL);
        park();
    }
    const pid_t survives = fork();
    CHECK(survives >= 0, survives);
    if (survives == 0)
        park();
    CHECK(kill(dies, SIGSTOP) == 0, dies);
    expect_stop(dies, SIGSTOP, __LINE__);
    CHECK(kill(survives, SIGSTOP) == 0, survives);
    expect_stop(survives, SIGSTOP, __LINE__);
    const pid_t leader = getppid();
    CHECK(write(ready_fd, "r", 1) == 1, 0);
    expect_signal(dies, SIGHUP, __LINE__);
    expect_continued(survives, __LINE__);
    CHECK(getppid() != leader, getppid());
    kill_child(survives, __LINE__);
    witness_pass();
}

/* 17: when the leader exits, the witness's group is orphaned with stopped
 * members, which get SIGHUP then SIGCONT. */
static void case_orphan_stop(void)
{
    int ready[2];
    acquire();
    CHECK(pipe(ready) == 0, 0);
    ready_fd = ready[1];
    spawn(NEW_GROUP, orphan_witness, __LINE__);
    wait_byte(ready[0], __LINE__);
}

static pid_t orphan_parent;
static int orphan_done = -1;

static void orphan_reader(void)
{
    char byte;
    const int64_t end = now_ms() + WAIT_MS;
    while (getppid() == orphan_parent) {
        CHECK(now_ms() < end, getppid());
        nap(2);
    }
    CHECK(read(tty, &byte, 1) < 0 && errno == EIO, 0);
    CHECK(tcsetpgrp(tty, getpgrp()) < 0 && errno == ENOTTY, 0);
    struct termios attributes;
    CHECK(tcgetattr(tty, &attributes) == 0, 0);
    CHECK(tcsetattr(tty, TCSANOW, &attributes) < 0 && errno == EIO, 0);
    witness_pass();
    CHECK(write(orphan_done, "d", 1) == 1, 0);
}

static void orphan_middle(void)
{
    orphan_parent = getpid();
    spawn(NEW_GROUP, orphan_reader, __LINE__);
}

/* 18: a background group orphaned by its parent's exit gets EIO for a read
 * and tcsetattr and ENOTTY for TIOCSPGRP instead of a stop. */
static void case_orphan_read(void)
{
    int done[2];
    acquire();
    CHECK(pipe(done) == 0, 0);
    orphan_done = done[1];
    expect_exit0(spawn(SAME_GROUP, orphan_middle, __LINE__), __LINE__);
    wait_byte(done[0], __LINE__);
}

/* 19: TIOCSWINSZ on either end reads back on the other, and a foreground
 * member at the default SIGWINCH disposition is neither stopped nor killed.
 * Whether SIGWINCH was sent is not observable here: native processes have
 * no handlers or masks, and the default action ignores it. */
static void case_winsize(void)
{
    struct winsize size = {0, 0, 0, 0};
    int status = 0;
    acquire();
    signal(SIGTTOU, SIG_IGN);
    CHECK(ioctl(tty, TIOCGWINSZ, &size) == 0 && size.ws_row == 0 && size.ws_col == 0, size.ws_row);
    const pid_t member = spawn(NEW_GROUP, park, __LINE__);
    CHECK(tcsetpgrp(tty, member) == 0, member);
    size.ws_row = 24;
    size.ws_col = 80;
    CHECK(ioctl(tty, TIOCSWINSZ, &size) == 0, 0);
    size.ws_row = size.ws_col = 0;
    CHECK(ioctl(master, TIOCGWINSZ, &size) == 0 && size.ws_row == 24 && size.ws_col == 80, size.ws_row);
    size.ws_row = 30;
    size.ws_col = 100;
    CHECK(ioctl(master, TIOCSWINSZ, &size) == 0, 0);
    size.ws_row = size.ws_col = 0;
    CHECK(ioctl(tty, TIOCGWINSZ, &size) == 0 && size.ws_row == 30 && size.ws_col == 100, size.ws_row);
    nap(50);
    CHECK(waitpid(member, &status, WNOHANG | WUNTRACED) == 0, status);
    reclaim(__LINE__);
    kill_child(member, __LINE__);
}

/* 20, run last: every earlier case released its PTY pairs, so besides this
 * case's own pair exactly OK_PTS_CAPACITY - 1 open before the table is full
 * (posix_openpt gives EAGAIN for the kernel's ENOSPC). The maintenance image
 * holds no other pair. */
static void case_pts_capacity(void)
{
    int masters[OK_PTS_CAPACITY];
    char path[32];
    unsigned count = 0;
    for (;;) {
        const int fd = posix_openpt(O_RDWR | O_NOCTTY);
        if (fd < 0) {
            CHECK(errno == EAGAIN, count);
            break;
        }
        CHECK(count < OK_PTS_CAPACITY - 1, count);
        masters[count++] = fd;
    }
    CHECK(count == OK_PTS_CAPACITY - 1, count);
    for (unsigned i = 0; i < count; ++i)
        close(masters[i]);
    const int again = open_pair(path, sizeof path);
    CHECK(again >= 0, again);
    close(again);
}

struct probe_case {
    const char *name;
    void (*body)(void);
    int witnesses;
    int master_close;
};

static const struct probe_case cases[] = {
    {"acquire", case_acquire, 0, 0},
    {"noctty", case_noctty, 0, 0},
    {"sctty_eperm", case_sctty, 0, 0},
    {"notty_member", case_notty_member, 0, 0},
    {"notty_leader", case_notty_leader, 0, 0},
    {"pgrp", case_pgrp, 0, 0},
    {"ttin_stop", case_ttin_stop, 0, 0},
    {"ttin_eio", case_ttin_eio, 0, 0},
    {"ttou_stop", case_ttou_stop, 0, 0},
    {"tostop", case_tostop, 0, 0},
    {"isig_int", case_isig_int, 0, 0},
    {"isig_tstp", case_isig_tstp, 0, 0},
    {"canonical", case_canonical, 0, 0},
    {"echo_off", case_echo_off, 0, 0},
    {"master_close", case_master_close, 1, 1},
    {"leader_exit", case_leader_exit, 1, 0},
    {"orphan_stop", case_orphan_stop, 1, 0},
    {"orphan_read", case_orphan_read, 1, 0},
    {"winsize", case_winsize, 0, 0},
    {"pts_capacity", case_pts_capacity, 0, 0},
};
#define CASE_COUNT ((int)(sizeof cases / sizeof cases[0]))

/* Output is assembled per line and written once, so lines never interleave. */
struct line {
    char text[192];
    size_t used;
};

static void put(struct line *line, const char *text)
{
    while (*text && line->used + 1 < sizeof line->text)
        line->text[line->used++] = *text++;
}

static void put_number(struct line *line, long value)
{
    char digits[24];
    int count = 0;
    unsigned long magnitude = value < 0 ? 0UL - (unsigned long)value : (unsigned long)value;
    if (value < 0)
        put(line, "-");
    do {
        digits[count++] = (char)('0' + magnitude % 10);
        magnitude /= 10;
    } while (magnitude);
    while (count && line->used + 1 < sizeof line->text)
        line->text[line->used++] = digits[--count];
}

static void emit(struct line *line)
{
    put(line, "\n");
    write(1, line->text, line->used);
}

static int report_failure(int number, const struct record *record)
{
    struct line line = {{0}, 0};
    put(&line, "TTY_SESSIONS_PROBE stage=FAIL case=");
    put_number(&line, number);
    put(&line, " name=");
    put(&line, number >= 1 && number <= CASE_COUNT ? cases[number - 1].name : "setup");
    put(&line, " line=");
    put_number(&line, record->line);
    put(&line, " value=");
    put_number(&line, (long)record->value);
    put(&line, " errno=");
    put_number(&line, record->error);
    put(&line, " arch=" ARCH);
    emit(&line);
    return 1;
}

static int wait_leader(pid_t leader, int *status)
{
    const int64_t end = now_ms() + CASE_MS;
    for (;;) {
        const pid_t got = waitpid(leader, status, WNOHANG);
        if (got == leader)
            return 0;
        if (got != 0 || now_ms() > end)
            return -1;
        nap(5);
    }
}

/* Runs one case: the leader is a new session; every process of the case
 * holds the report pipe, so its end of file means all of them are gone. */
static int run_case(int number)
{
    const struct probe_case *selected = &cases[number - 1];
    struct record failure = {0, 0, 0};
    int report[2], ready[2], status = 0;
    master = open_pair(slave_path, sizeof slave_path);
    if (master < 0) {
        failure.line = __LINE__;
        failure.error = errno;
        return report_failure(number, &failure);
    }
    if (pipe(report) < 0 || pipe(ready) < 0) {
        failure.line = __LINE__;
        failure.error = errno;
        return report_failure(number, &failure);
    }
    const pid_t leader = fork();
    if (leader == 0) {
        close(report[0]);
        close(ready[0]);
        report_fd = report[1];
        ready_fd = ready[1];
        if (setsid() != getpid())
            fail_at(__LINE__, 0);
        selected->body();
        _Exit(0);
    }
    close(report[1]);
    close(ready[1]);
    if (leader < 0) {
        failure.line = __LINE__;
        failure.error = errno;
        return report_failure(number, &failure);
    }
    int expected_ok = 1;
    if (selected->master_close) {
        char byte;
        struct pollfd wait_ready = {ready[0], POLLIN, 0};
        if (poll(&wait_ready, 1, CASE_MS) != 1 || read(ready[0], &byte, 1) != 1)
            expected_ok = 0;
        close(master);
        master = -1;
    }
    const int waited = wait_leader(leader, &status);
    if (waited < 0) {
        kill(-leader, SIGKILL);
        kill(leader, SIGKILL);
        waitpid(leader, &status, 0);
        expected_ok = 0;
        status = -1;
    } else if (selected->master_close) {
        expected_ok = expected_ok && WIFSIGNALED(status) && WTERMSIG(status) == SIGHUP;
    } else {
        expected_ok = WIFEXITED(status) && WEXITSTATUS(status) == 0;
    }
    int passes = 0, closed = 0;
    struct record found = {0, 0, 0};
    const int64_t end = now_ms() + CASE_MS;
    while (now_ms() < end) {
        struct pollfd readable = {report[0], POLLIN, 0};
        if (poll(&readable, 1, 200) <= 0)
            continue;
        struct record record;
        const long got = read(report[0], &record, sizeof record);
        if (got == 0) {
            closed = 1;
            break;
        }
        if (got != (long)sizeof record)
            break;
        if (record.line != 0) {
            found = record;
            break;
        }
        ++passes;
    }
    close(report[0]);
    close(ready[0]);
    if (master >= 0)
        close(master);
    master = -1;
    if (found.line != 0)
        return report_failure(number, &found);
    if (!expected_ok) {
        failure.value = status;
        return report_failure(number, &failure);
    }
    if (!closed || passes != selected->witnesses) {
        failure.line = -1;
        failure.value = passes;
        return report_failure(number, &failure);
    }
    struct line line = {{0}, 0};
    put(&line, "TTY_SESSIONS_CASE n=");
    put_number(&line, number);
    put(&line, " name=");
    put(&line, selected->name);
    put(&line, " result=pass");
    emit(&line);
    return 0;
}

int main(int argc, char **argv)
{
    int first = 1, last = CASE_COUNT;
    reset_signals();
    if (argc > 1) {
        first = last = atoi(argv[1]);
        if (first < 1 || first > CASE_COUNT) {
            struct record usage = {__LINE__, 0, first};
            return report_failure(0, &usage);
        }
    }
    for (int number = first; number <= last; ++number)
        if (run_case(number) != 0)
            return 1;
    struct line line = {{0}, 0};
    put(&line, "TTY_SESSIONS_PROBE stage=PASS cases=");
    put_number(&line, last - first + 1);
    put(&line, " arch=" ARCH);
    emit(&line);
    return 0;
}

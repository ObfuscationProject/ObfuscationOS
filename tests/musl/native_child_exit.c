/* Bounded user-observed child-exit policy; kernel diagnostics are separate. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include "thread_syscall.h"

#if defined(__x86_64__)
#define ARCH "x86_64"
#elif defined(__i386__)
#define ARCH "i386"
#elif defined(__aarch64__)
#define ARCH "aarch64"
#elif defined(__arm__)
#define ARCH "arm32"
#elif defined(__riscv) && __riscv_xlen == 32
#define ARCH "rv32"
#elif defined(__riscv)
#define ARCH "rv64"
#elif defined(__loongarch64)
#define ARCH "loongarch64"
#elif defined(__mips64)
#define ARCH "mips64"
#elif defined(__mips__)
#define ARCH "mips"
#elif defined(__powerpc__)
#define ARCH "ppc"
#if __SIZEOF_POINTER__ != 4 || __BYTE_ORDER__ != __ORDER_BIG_ENDIAN__ || !defined(__NO_FPRS__)
#error "PPC requires big-endian scalar soft-float"
#endif
#else
#error "Unsupported child-exit target"
#endif

_Static_assert(sizeof(siginfo_t) == 128, "target siginfo must occupy 128 bytes");
_Static_assert(offsetof(siginfo_t, si_signo) == 0, "target signo offset");
#if defined(__mips__)
_Static_assert(offsetof(siginfo_t, si_code) == 4 && offsetof(siginfo_t, si_errno) == 8, "MIPS header order");
#else
_Static_assert(offsetof(siginfo_t, si_code) == 8 && offsetof(siginfo_t, si_errno) == 4, "generic header order");
#endif
_Static_assert(offsetof(siginfo_t, si_pid) == (sizeof(void *) == 8 ? 16 : 12), "target child pid offset");
_Static_assert(offsetof(siginfo_t, si_uid) == (sizeof(void *) == 8 ? 20 : 16), "target child uid offset");
_Static_assert(offsetof(siginfo_t, si_status) == (sizeof(void *) == 8 ? 24 : 20), "target child status offset");
static int case_id = -1;
static unsigned sequence;
static const char *image_path;
static volatile sig_atomic_t handled;
static volatile unsigned char handler_bytes[128];
struct subject { pid_t pid; int gate; int status; };
static struct subject subjects[2];

static __attribute__((noreturn)) void fail(unsigned line)
{
    char b[] = "CHILD_EXIT_FAIL line=0000 case=00\n";
    unsigned at = sizeof("CHILD_EXIT_FAIL line=") - 1;
    for (unsigned i = 0; i < 4; ++i) { b[at + 3 - i] = '0' + line % 10; line /= 10; }
    at = sizeof("CHILD_EXIT_FAIL line=0000 case=") - 1;
    b[at] = '0' + (case_id < 0 ? 9 : case_id / 10);
    b[at + 1] = '0' + (case_id < 0 ? 9 : case_id % 10);
    thread_syscall4(SYS_write, 1, (uintptr_t)b, sizeof(b) - 1, 0);
    thread_syscall4(SYS_exit_group, 91, 0, 0, 0);
    for (;;) {}
}
#define CHECK(c) do { if (!(c)) fail(__LINE__); } while (0)

static __attribute__((format(printf, 1, 2))) void marker(const char *format, ...)
{
    char b[768]; va_list ap; va_start(ap, format);
    int length = vsnprintf(b, sizeof(b), format, ap); va_end(ap);
    CHECK(length > 0 && (size_t)length < sizeof(b));
    CHECK(thread_syscall4(SYS_write, 1, (uintptr_t)b, length, 0) == length);
}
static void event(const char *operation, long a, long b, long c)
{
    marker("CHILD_EXIT_EVENT arch=%s case=%d seq=%u op=%s a=%ld b=%ld c=%ld\n",
           ARCH, case_id, sequence++, operation, a, b, c);
}
static int64_t now(void)
{
    struct timespec t; CHECK(clock_gettime(CLOCK_MONOTONIC, &t) == 0);
    return (int64_t)t.tv_sec * 1000000000 + t.tv_nsec;
}
static void deadline(int64_t begin) { CHECK(now() - begin < 5000000000LL); }
static sigset_t child_set(void)
{
    sigset_t set; CHECK(sigemptyset(&set) == 0 && sigaddset(&set, SIGCHLD) == 0); return set;
}
static int blocked(void)
{
    sigset_t set; CHECK(sigprocmask(SIG_SETMASK, 0, &set) == 0);
    return sigismember(&set, SIGCHLD);
}
static int pending(void)
{
    sigset_t set; CHECK(sigpending(&set) == 0); return sigismember(&set, SIGCHLD);
}
static void pending_is(int expected, int await)
{
    int64_t begin = now();
    if (await) while (pending() != expected) deadline(begin);
    CHECK(pending() == expected);
    event("PENDING", expected, blocked(), handled);
}
static void handler(int signal, siginfo_t *info, void *context)
{
    int saved_errno = errno;
    CHECK(signal == SIGCHLD && info && context && handled == 0);
    for (unsigned i = 0; i < 128; ++i) handler_bytes[i] = ((unsigned char *)info)[i];
    handled = 1; errno = saved_errno;
}
static void configure(int kind, int no_wait, int mask)
{
    struct sigaction action = {0};
    action.sa_flags = SA_NOCLDSTOP | (no_wait ? SA_NOCLDWAIT : 0);
    if (kind == 2) { action.sa_flags |= SA_SIGINFO; action.sa_sigaction = handler; }
    else action.sa_handler = kind ? SIG_IGN : SIG_DFL;
    CHECK(sigemptyset(&action.sa_mask) == 0 && sigaction(SIGCHLD, &action, 0) == 0);
    struct sigaction copied; CHECK(sigaction(SIGCHLD, 0, &copied) == 0);
    CHECK((copied.sa_flags & (SA_NOCLDSTOP | SA_NOCLDWAIT | SA_SIGINFO)) == action.sa_flags);
    sigset_t set = child_set();
    CHECK(sigprocmask(mask ? SIG_BLOCK : SIG_UNBLOCK, &set, 0) == 0 && blocked() == mask);
    event("CONFIG", kind, no_wait, mask);
}
/* External musl target layouts: 3-word header, pointer-aligned union, swapped
 * MIPS errno/code. Child clocks and all padding are required to remain zero. */
static void expected_info(unsigned char out[128], int code, pid_t pid, uid_t uid, int status)
{
    memset(out, 0, 128); int32_t number = SIGCHLD, value = code, child_status = status;
    uint32_t sender = (uint32_t)pid, user = (uint32_t)uid;
    memcpy(out, &number, 4);
#if defined(__mips__)
    memcpy(out + 4, &value, 4);
#else
    memcpy(out + 8, &value, 4);
#endif
    unsigned offset = sizeof(void *) == 8 ? 16 : 12;
    memcpy(out + offset, &sender, 4); memcpy(out + offset + 4, &user, 4);
    memcpy(out + offset + 8, &child_status, 4);
}
static void info_record(const char *via, const unsigned char bytes[128], int code, pid_t pid, int status)
{
    unsigned char expected[128]; expected_info(expected, code, pid, getuid(), status);
    CHECK(memcmp(bytes, expected, 128) == 0);
    char hex[257]; const char digits[] = "0123456789abcdef";
    for (unsigned i = 0; i < 128; ++i) { hex[i * 2] = digits[bytes[i] >> 4]; hex[i * 2 + 1] = digits[bytes[i] & 15]; }
    hex[256] = 0;
    marker("CHILD_EXIT_INFO arch=%s case=%d seq=%u via=%s signal=%d code=%d child=%ld uid=%lu status=%d bytes=128 hex=%s\n",
           ARCH, case_id, sequence++, via, SIGCHLD, code, (long)pid, (unsigned long)getuid(), status, hex);
}
static void receive(int code, pid_t pid, int status)
{
    sigset_t set = child_set(); struct timespec timeout = {0};
    struct { unsigned char before[16]; siginfo_t info; unsigned char after[16]; } guarded;
    memset(&guarded, 0xa5, sizeof(guarded)); int64_t begin = now();
    for (;;) {
        errno = 0; int value = sigtimedwait(&set, &guarded.info, &timeout);
        if (value == SIGCHLD) break;
        CHECK(value == -1 && (errno == EAGAIN || errno == EINTR)); deadline(begin);
    }
    for (unsigned i = 0; i < 16; ++i) CHECK(guarded.before[i] == 0xa5 && guarded.after[i] == 0xa5);
    info_record("wait", (const unsigned char *)&guarded.info, code, pid, status);
}
static void receive_handler(pid_t pid, int status)
{
    int64_t begin = now(); while (handled != 1) deadline(begin);
    unsigned char bytes[128]; for (unsigned i = 0; i < 128; ++i) bytes[i] = handler_bytes[i];
    info_record("handler", bytes, CLD_EXITED, pid, status);
}
static void absent(void)
{
    sigset_t set = child_set(); siginfo_t info; struct timespec timeout = {0}; errno = 0;
    CHECK(sigtimedwait(&set, &info, &timeout) == -1 && errno == EAGAIN);
    event("ABSENT", EAGAIN, blocked(), handled);
}
static void nonblock(int fd)
{
    int flags = fcntl(fd, F_GETFL); CHECK(flags >= 0 && fcntl(fd, F_SETFL, flags | O_NONBLOCK) == 0);
}
static void byte_read(int fd, char expected)
{
    int64_t begin = now(); char byte;
    for (;;) { ssize_t n = read(fd, &byte, 1); if (n == 1) break;
        CHECK(n == -1 && (errno == EAGAIN || errno == EINTR)); deadline(begin); }
    CHECK(byte == expected);
}
static void spawn(unsigned slot, int status)
{
    CHECK(slot < 2); int gate[2]; CHECK(pipe(gate) == 0); nonblock(gate[0]);
    pid_t pid = fork(); CHECK(pid >= 0);
    if (!pid) {
        CHECK(close(gate[1]) == 0); byte_read(gate[0], 'R'); CHECK(close(gate[0]) == 0);
        if (status == SIGTERM) { CHECK(kill(getpid(), SIGTERM) == 0); fail(__LINE__); }
        _Exit(status >> 8);
    }
    CHECK(close(gate[0]) == 0); subjects[slot] = (struct subject){pid, gate[1], status};
    event("SPAWN", slot, pid, status);
}
static void release(unsigned slot)
{
    struct subject *s = subjects + slot; event("RELEASE", slot, s->pid, 0);
    CHECK(write(s->gate, "R", 1) == 1 && close(s->gate) == 0); s->gate = -1;
}
/* Musl waitpid deliberately selects waitid(WEXITED) on RV32. */
static int reap_pid(pid_t pid, int expected, int no_child)
{
    int64_t begin = now(); int status = 0x12345678;
    for (;;) {
        errno = 0; pid_t result = waitpid(pid, &status, WNOHANG);
        if (result == pid) { CHECK(!no_child && status == expected); return status; }
        if (result == -1 && errno == ECHILD) { CHECK(no_child); return 0; }
        CHECK(result == 0 || (result == -1 && errno == EINTR)); deadline(begin);
    }
}
static void reap(unsigned slot, int no_child)
{
    struct subject *s = subjects + slot;
    int status = reap_pid(s->pid, s->status, no_child);
    event(no_child ? "ECHILD" : "WAIT", slot, s->pid, status);
}
static void policy(void)
{
    int kind = case_id / 4, mask = (case_id / 2) % 2, no_wait = case_id % 2;
    configure(kind, no_wait, mask); spawn(0, 37 << 8); release(0);
    if (mask && kind != 1) { pending_is(1, 1); receive(CLD_EXITED, subjects[0].pid, 37); pending_is(0, 0); }
    else if (kind == 2) receive_handler(subjects[0].pid, 37);
    reap(0, kind == 1 || no_wait); pending_is(0, 0); absent();
    CHECK(handled == (kind == 2 && !mask));
}
static void killed(void)
{
    configure(2, 0, 1); spawn(0, SIGTERM); release(0); receive(CLD_KILLED, subjects[0].pid, SIGTERM);
    reap(0, 0); pending_is(0, 0); absent();
}
static void coalesced(void)
{
    configure(2, 0, 1); spawn(0, 41 << 8); release(0); reap(0, 0); pending_is(1, 0);
    spawn(1, 42 << 8); release(1); reap(1, 0); pending_is(1, 0);
    receive(CLD_EXITED, subjects[0].pid, 41); pending_is(0, 0); absent();
}
static void user_first(void)
{
    configure(2, 0, 1); CHECK(kill(getpid(), SIGCHLD) == 0); event("SEND_USER", getpid(), SIGCHLD, 0);
    pending_is(1, 0); spawn(0, 43 << 8); release(0); reap(0, 0); pending_is(1, 0);
    receive(SI_USER, getpid(), 0); pending_is(0, 0); absent();
}
static void no_retro(void)
{
    configure(2, 0, 1); spawn(0, 44 << 8); release(0); pending_is(1, 1);
    configure(1, 0, 1); pending_is(0, 0); reap(0, 0); absent();
    configure(2, 0, 1); spawn(1, 45 << 8); release(1); pending_is(1, 1);
    configure(2, 1, 1); pending_is(1, 0); reap(1, 0);
    receive(CLD_EXITED, subjects[1].pid, 45); pending_is(0, 0); absent();
}
static void fork_inheritance(void)
{
    configure(2, 0, 1); spawn(0, 46 << 8); release(0); pending_is(1, 1);
    int report[2]; CHECK(pipe(report) == 0); nonblock(report[0]);
    pid_t pid = fork(); CHECK(pid >= 0);
    if (!pid) {
        CHECK(close(report[0]) == 0); struct sigaction a;
        CHECK(sigaction(SIGCHLD, 0, &a) == 0 && a.sa_sigaction == handler);
        CHECK((a.sa_flags & (SA_SIGINFO | SA_NOCLDWAIT | SA_NOCLDSTOP)) == (SA_SIGINFO | SA_NOCLDSTOP));
        CHECK(blocked() == 1 && pending() == 0 && handled == 0);
        CHECK(write(report[1], "I", 1) == 1 && close(report[1]) == 0); _Exit(0);
    }
    CHECK(close(report[1]) == 0); subjects[1] = (struct subject){pid, -1, 0}; event("SPAWN", 1, pid, 0);
    byte_read(report[0], 'I'); CHECK(close(report[0]) == 0);
    event("INHERIT", pid, 1, 0); event("INHERIT_ACTION", 2, 0, 1);
    reap(1, 0); reap(0, 0); pending_is(1, 0);
    receive(CLD_EXITED, subjects[0].pid, 46); pending_is(0, 0); absent();
}
static void finish(void)
{
    marker("CHILD_EXIT_DONE arch=%s case=%d pid=%ld events=%u handlers=%d\n",
           ARCH, case_id, (long)getpid(), sequence, (int)handled);
}
static __attribute__((noreturn)) void exec_inheritance(void)
{
    configure(2, 0, 1); spawn(0, 47 << 8); release(0); pending_is(1, 1);
    struct sigaction ignored = {0}; ignored.sa_handler = SIG_IGN;
    CHECK(sigemptyset(&ignored.sa_mask) == 0 && sigaction(SIGUSR1, &ignored, 0) == 0);
    char pid[24], child[24], seq[24];
    snprintf(pid, sizeof(pid), "%ld", (long)getpid()); snprintf(child, sizeof(child), "%ld", (long)subjects[0].pid);
    snprintf(seq, sizeof(seq), "%u", sequence + 1);
    char *args[] = {(char *)image_path, "child-exit-replaced", pid, child, seq, 0}; char *env[] = {0};
    errno = 0; CHECK(execve("/bin/no-child-exit-image", args, env) == -1 && errno == ENOENT);
    struct sigaction a; CHECK(sigaction(SIGCHLD, 0, &a) == 0 && a.sa_sigaction == handler);
    CHECK((a.sa_flags & (SA_SIGINFO | SA_NOCLDWAIT | SA_NOCLDSTOP)) == (SA_SIGINFO | SA_NOCLDSTOP));
    CHECK(pending() == 1 && blocked() == 1); event("EXEC_FAILED", ENOENT, 2, 1);
    execve(image_path, args, env); fail(__LINE__);
}
static void replacement(int argc, char **argv)
{
    CHECK(argc == 5); case_id = 17; sequence = (unsigned)strtoul(argv[4], 0, 10);
    CHECK(getpid() == (pid_t)strtol(argv[2], 0, 10) && !handled);
    subjects[0] = (struct subject){(pid_t)strtol(argv[3], 0, 10), -1, 47 << 8};
    struct sigaction a; CHECK(sigaction(SIGCHLD, 0, &a) == 0 && a.sa_handler == SIG_DFL);
    CHECK(!(a.sa_flags & (SA_SIGINFO | SA_NOCLDWAIT | SA_NOCLDSTOP)) && blocked() == 1);
    event("EXEC_CHECK", getpid(), 0, 1);
    CHECK(sigaction(SIGUSR1, 0, &a) == 0 && a.sa_handler == SIG_IGN); event("IGNORE_CHECK", SIGUSR1, 1, 0);
    pending_is(1, 0); receive(CLD_EXITED, subjects[0].pid, 47); reap(0, 0); pending_is(0, 0); absent(); finish();
}
int main(int argc, char **argv)
{
    image_path = argv[0];
    if (argc > 1 && !strcmp(argv[1], "child-exit-replaced")) { replacement(argc, argv); return 0; }
    CHECK(argc == 1); sigset_t empty; CHECK(sigemptyset(&empty) == 0 && sigprocmask(SIG_SETMASK, &empty, 0) == 0);
    struct sigaction action = {0}; action.sa_handler = SIG_DFL;
    CHECK(sigemptyset(&action.sa_mask) == 0 && sigaction(SIGCHLD, &action, 0) == 0);
    for (case_id = 0; case_id < 18; ++case_id) {
        marker("CHILD_EXIT_BEGIN arch=%s case=%d parent=%ld\n", ARCH, case_id, (long)getpid());
        pid_t pid = fork(); CHECK(pid >= 0);
        if (!pid) {
            sequence = 0; handled = 0; memset(subjects, 0, sizeof(subjects));
            CHECK(thread_syscall4(SYS_gettid, 0, 0, 0, 0) == getpid() && pending() == 0);
            marker("CHILD_EXIT_CASE arch=%s case=%d pid=%ld uid=%lu\n", ARCH, case_id, (long)getpid(), (unsigned long)getuid());
            if (case_id < 12) policy();
            else if (case_id == 12) killed(); else if (case_id == 13) coalesced();
            else if (case_id == 14) user_first(); else if (case_id == 15) no_retro();
            else if (case_id == 16) fork_inheritance(); else exec_inheritance();
            finish(); _Exit(0);
        }
        CHECK(reap_pid(pid, 0, 0) == 0);
        marker("CHILD_EXIT_REAP arch=%s case=%d parent=%ld child=%ld status=0\n", ARCH, case_id, (long)getpid(), (long)pid);
    }
    marker("CHILD_EXIT_PASS %s cases=18 policy=12 killed=1 coalesced=1 user_first=1 no_retro=2 fork=1 exec=1 bytes=128\n", ARCH);
    return 0;
}

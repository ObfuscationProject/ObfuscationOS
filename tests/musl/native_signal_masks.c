#define _GNU_SOURCE
#include <errno.h>
#include <sched.h>
#include <signal.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>
#include "../probe_output.h"
#include "thread_syscall.h"

/* Raw clone children use only raw syscalls and never the parent's libc TLS. */
extern int __clone(int (*)(void *), void *, int, void *, int *, void *, int *);
#define CHECK(x) do { if (!(x)) probe_failure("SIGNAL_MASK_FAIL", __LINE__, errno); } while (0)
#if defined(__mips__)
#define MASK_BYTES 16
#else
#define MASK_BYTES 8
#endif
#define WORD_BITS (8 * sizeof(unsigned long))
struct mask { unsigned long words[MASK_BYTES / sizeof(unsigned long)]; };
_Static_assert(sizeof(struct mask) == MASK_BYTES, "Linux native-long signal mask");
struct state { volatile uint32_t tid, idle; volatile long fork_pid; const char *path; };
static const int shared = CLONE_VM | CLONE_FS | CLONE_FILES | CLONE_SIGHAND | CLONE_THREAD | CLONE_SYSVSEM;

static long call(long nr, uintptr_t a, uintptr_t b, uintptr_t c, uintptr_t d)
{
    return thread_syscall4(nr, a, b, c, d);
}
static long change(int how, const struct mask *input, struct mask *output, size_t size)
{
    return call(SYS_rt_sigprocmask, (uintptr_t)how, (uintptr_t)input, (uintptr_t)output, size);
}
static void bit(struct mask *mask, unsigned signal, int set)
{
    const unsigned long flag = 1UL << ((signal - 1) % WORD_BITS);
    if (set) mask->words[(signal - 1) / WORD_BITS] |= flag;
    else mask->words[(signal - 1) / WORD_BITS] &= ~flag;
}
static struct mask pattern(unsigned kind)
{
    struct mask result = {0};
    bit(&result, 10 + kind, 1);
    bit(&result, 31 + kind, 1);
    bit(&result, 64 - kind, 1);
#if MASK_BYTES == 16
    bit(&result, 65 + kind, 1);
    bit(&result, 128 - kind, 1);
#endif
    return result;
}
static int equal(const struct mask *a, const struct mask *b)
{
    for (size_t i = 0; i < MASK_BYTES / sizeof(unsigned long); ++i)
        if (a->words[i] != b->words[i]) return 0;
    return 1;
}
static int current(const struct mask *expected)
{
    struct mask value = {0};
    return change(-1, 0, &value, sizeof(value)) == 0 && equal(&value, expected);
}
static void raw_failure(unsigned line)
{
    char number[16]; size_t count = 0;
    const char prefix[] = "SIGNAL_MASK_FAIL raw_line=";
    (void)call(SYS_write, 1, (uintptr_t)prefix, sizeof(prefix) - 1, 0);
    do { number[count++] = (char)('0' + line % 10); line /= 10; } while (line);
    while (count) (void)call(SYS_write, 1, (uintptr_t)&number[--count], 1, 0);
    const char newline = '\n';
    (void)call(SYS_write, 1, (uintptr_t)&newline, 1, 0);
    (void)call(SYS_exit_group, 91, 0, 0, 0);
    for (;;) {}
}
#define RAW_CHECK(x) do { if (!(x)) raw_failure(__LINE__); } while (0)
static long raw_fork(void)
{
#ifdef SYS_fork
    return call(SYS_fork, 0, 0, 0, 0);
#else
    return call(SYS_clone, SIGCHLD, 0, 0, 0);
#endif
}
static void raw_exit(unsigned code)
{
    (void)call(SYS_exit, code, 0, 0, 0);
    for (;;) {}
}
static int same(const char *a, const char *b)
{
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}

static void raw_boundaries(void)
{
    struct mask a = pattern(0), b = pattern(1), old = {0}, value = {0}, all;
    for (size_t i = 0; i < MASK_BYTES / sizeof(unsigned long); ++i) all.words[i] = ~0UL;
    CHECK(change(SIG_SETMASK, &all, 0, sizeof(all)) == 0);
    bit(&all, SIGKILL, 0); bit(&all, SIGSTOP, 0);
    CHECK(current(&all));
    CHECK(change(SIG_SETMASK, &a, &old, sizeof(a)) == 0 && equal(&old, &all));
    CHECK(change(-1, 0, &value, sizeof(value)) == 0 && equal(&value, &a));
    CHECK(change(-1, 0, 0, sizeof(value)) == 0);
    CHECK(change(SIG_SETMASK, (const struct mask *)(uintptr_t)1, (struct mask *)(uintptr_t)1, sizeof(a) - 1) == -EINVAL);
    old = b;
    CHECK(change(-1, (const struct mask *)(uintptr_t)1, &old, sizeof(a)) == -EFAULT && equal(&old, &b) && current(&a));
    old = b;
    CHECK(change(-1, &b, &old, sizeof(a)) == -EINVAL && equal(&old, &b) && current(&a));
    CHECK(change(-1, &b, (struct mask *)(uintptr_t)1, sizeof(a)) == -EINVAL && current(&a));
    CHECK(change(SIG_SETMASK, &b, (struct mask *)(uintptr_t)1, sizeof(b)) == -EFAULT && current(&b));
    /* Read the input before writing oldset when both pointers alias. */
    old = a;
    CHECK(change(SIG_SETMASK, &old, &old, sizeof(old)) == 0 && equal(&old, &b) && current(&a));
    CHECK(change(SIG_BLOCK, &b, &old, sizeof(b)) == 0 && equal(&old, &a));
    for (size_t i = 0; i < MASK_BYTES / sizeof(unsigned long); ++i) value.words[i] = a.words[i] | b.words[i];
    CHECK(current(&value));
    CHECK(change(SIG_UNBLOCK, &b, &old, sizeof(b)) == 0 && equal(&old, &value) && current(&a));
    CHECK(change(SIG_SETMASK, 0, 0, 0) == -EINVAL && current(&a));
}

static int inheritance_peer(void *opaque)
{
    struct state *state = opaque;
    struct mask a = pattern(0), b = pattern(1);
    RAW_CHECK(current(&a));
    RAW_CHECK(change(SIG_SETMASK, &b, 0, sizeof(b)) == 0 && current(&b));
    long child = raw_fork();
    RAW_CHECK(child >= 0);
    if (!child) {
        RAW_CHECK(current(&b));
        RAW_CHECK(change(SIG_SETMASK, &a, 0, sizeof(a)) == 0 && current(&a));
        raw_exit(0);
    }
    RAW_CHECK(current(&b));
    __atomic_store_n(&state->fork_pid, child, __ATOMIC_RELEASE);
    return 0;
}

static void execute(const char *path, const char *mode, const struct mask *expected)
{
    char *arguments[] = {(char *)path, (char *)mode, 0};
    char *environment[] = {0};
    const char missing[] = "/bin/no-signal-mask-image";
    RAW_CHECK(call(SYS_execve, (uintptr_t)missing, (uintptr_t)arguments, (uintptr_t)environment, 0) == -ENOENT);
    RAW_CHECK(current(expected));
    (void)call(SYS_execve, (uintptr_t)path, (uintptr_t)arguments, (uintptr_t)environment, 0);
    raw_failure(__LINE__);
}
static int exec_peer(void *opaque)
{
    struct state *state = opaque;
    struct mask a = pattern(0), d = pattern(3);
    RAW_CHECK(current(&a));
    RAW_CHECK(change(SIG_SETMASK, &d, 0, sizeof(d)) == 0 && current(&d));
    execute(state->path, "after-peer-exec", &d);
    return 75;
}
static void wait_child(long pid)
{
    int status = -1;
    CHECK(pid > 0 && waitpid((pid_t)pid, &status, 0) == pid && WIFEXITED(status) && WEXITSTATUS(status) == 0);
}
static void exec_process(const char *path, void *stack, int peer)
{
    long child = raw_fork();
    CHECK(child >= 0);
    if (!child) {
        if (!peer) {
            struct mask c = pattern(2);
            RAW_CHECK(change(SIG_SETMASK, &c, 0, sizeof(c)) == 0);
            execute(path, "after-leader-exec", &c);
        }
        struct state state = {.path = path};
        RAW_CHECK(__clone(exec_peer, (char *)stack + 16384, shared, &state, 0, 0, 0) > 0);
        /* The nonleader's exec must retire this distinct-mask leader. */
        for (;;) {
            struct mask a = pattern(0);
            RAW_CHECK(current(&a));
            RAW_CHECK(call(SYS_futex, (uintptr_t)&state.idle, 128, 0, 0) == 0);
        }
    }
    wait_child(child);
    struct mask a = pattern(0);
    CHECK(current(&a));
}

int main(int argc, char **argv)
{
    if (argc == 2 && (same(argv[1], "after-leader-exec") || same(argv[1], "after-peer-exec"))) {
        const int peer = same(argv[1], "after-peer-exec");
        struct mask expected = pattern(peer ? 3 : 2);
        CHECK(current(&expected));
        CHECK(call(SYS_gettid, 0, 0, 0, 0) == call(SYS_getpid, 0, 0, 0, 0));
        probe_text(peer ? "OK_MUSL_SIGNAL_EXEC caller=nonleader mask=pass\n" :
                          "OK_MUSL_SIGNAL_EXEC caller=leader mask=pass\n");
        return 0;
    }
    CHECK(argc == 1);
    struct mask original = {0};
    CHECK(change(-1, 0, &original, sizeof(original)) == 0);
    raw_boundaries();
    void *stack = mmap(0, 16384, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK(stack != MAP_FAILED);
    struct state state = {0};
    int tid = __clone(inheritance_peer, (char *)stack + 16384,
                      shared | CLONE_PARENT_SETTID | CLONE_CHILD_SETTID | CLONE_CHILD_CLEARTID,
                      &state, (int *)&state.tid, 0, (int *)&state.tid);
    CHECK(tid > 0);
    while (__atomic_load_n(&state.tid, __ATOMIC_ACQUIRE)) {
        long result = call(SYS_futex, (uintptr_t)&state.tid, 0, (uint32_t)tid, 0);
        CHECK(result == 0 || result == -EAGAIN);
    }
    struct mask a = pattern(0);
    CHECK(current(&a));
    wait_child(__atomic_load_n(&state.fork_pid, __ATOMIC_ACQUIRE));
    CHECK(current(&a));
    const char *path = argv[0][0] == '/' ? argv[0] : "/bin/native-signal-masks";
    exec_process(path, stack, 0);
    exec_process(path, stack, 1);
    CHECK(munmap(stack, 16384) == 0);
    CHECK(change(SIG_SETMASK, &original, 0, sizeof(original)) == 0);
    probe_text("OK_MUSL_SIGNAL_MASKS raw=pass copies=pass clone=pass fork=pass exec=pass nonleader_exec=pass failed_exec=pass\n");
    return 0;
}

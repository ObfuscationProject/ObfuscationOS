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

/* Raw clone children use only raw syscalls, never the parent's libc TLS. */
extern int __clone(int (*)(void *), void *, int, void *, int *, void *, int *);
#define CHECK(x) do { if (!(x)) probe_failure("ROBUST_LIST_FAIL", __LINE__, errno); } while (0)
#define WAITERS UINT32_C(0x80000000)
#define OWNER_DIED UINT32_C(0x40000000)
#define TID_MASK UINT32_C(0x3fffffff)

struct list { struct list *next; };
struct head { struct list list; long offset; struct list *pending; };
struct node { struct list list; volatile uint32_t word; };
struct state {
    struct head head;
    struct node node;
    volatile uint32_t tid, phase, gate, delay, error;
    int pending_zero;
};
_Static_assert(sizeof(struct head) == 3 * sizeof(long), "Linux robust head word layout");
_Static_assert(offsetof(struct node, word) % 4 == 0, "futex alignment");

static long call(long nr, uintptr_t a, uintptr_t b, uintptr_t c, uintptr_t d)
{
    return thread_syscall4(nr, a, b, c, d);
}
static long set_list(struct head *head, size_t length)
{
    return call(SYS_set_robust_list, (uintptr_t)head, length, 0, 0);
}
static long get_list(long tid, struct head **head, size_t *length)
{
    return call(SYS_get_robust_list, (uintptr_t)tid, (uintptr_t)head, (uintptr_t)length, 0);
}
static long futex(volatile uint32_t *word, unsigned op, uint32_t expected, const void *timeout)
{
    return call(SYS_futex, (uintptr_t)word, op, expected, (uintptr_t)timeout);
}
static int child_failure(struct state *state, unsigned line)
{
    __atomic_store_n(&state->error, line, __ATOMIC_RELEASE);
    __atomic_store_n(&state->phase, 1, __ATOMIC_RELEASE);
    (void)futex(&state->phase, 129, 1, 0);
    return 73;
}
#define CHILD_CHECK(x) do { if (!(x)) return child_failure(state, __LINE__); } while (0)
static int owner(void *opaque)
{
    struct state *state = opaque;
    struct head *registered = (struct head *)(uintptr_t)1;
    size_t length = 0;
    const long tid = call(SYS_gettid, 0, 0, 0, 0);
    CHILD_CHECK(tid > 0 && (uint32_t)tid == state->tid && !((uint32_t)tid & ~TID_MASK));
    CHILD_CHECK(get_list(0, &registered, &length) == 0 && !registered && length == sizeof(struct head));
    state->head.offset = offsetof(struct node, word) - offsetof(struct node, list);
    state->node.list.next = &state->head.list;
    state->head.list.next = state->pending_zero ? &state->head.list : &state->node.list;
    state->head.pending = state->pending_zero ? &state->node.list : 0;
    state->node.word = state->pending_zero ? 0 : WAITERS | (uint32_t)tid;
    CHILD_CHECK(set_list(&state->head, sizeof(struct head)) == 0);
    CHILD_CHECK(get_list(0, &registered, &length) == 0 && registered == &state->head && length == sizeof(struct head));
    __atomic_store_n(&state->phase, 1, __ATOMIC_RELEASE);
    (void)futex(&state->phase, 129, 1, 0);
    while (!__atomic_load_n(&state->gate, __ATOMIC_ACQUIRE)) {
        long result = futex(&state->gate, 128, 0, 0);
        CHILD_CHECK(result == 0 || result == -EAGAIN);
    }
    /* Let the parent block first. It requires a real shared-operation wake:
       early owner death produces EAGAIN and fails, pending-zero would hang. */
    struct { int64_t seconds, nanoseconds; } wide = {0, 20000000};
    struct { long seconds, nanoseconds; } legacy = {0, 20000000};
    const void *timeout = sizeof(long) == 8 ? (const void *)&wide : (const void *)&legacy;
#if defined(SYS_futex_time64) && SYS_futex == SYS_futex_time64
    timeout = &wide;
#endif
    CHILD_CHECK(futex(&state->delay, 128, 0, timeout) == -ETIMEDOUT);
    return 0; /* Musl's clone trampoline issues raw SYS_exit. */
}

static void registrations(struct head *parent)
{
    struct head *value = 0;
    size_t length = 0;
    CHECK(set_list(parent, sizeof(*parent)) == 0);
    CHECK(get_list(0, &value, &length) == 0 && value == parent && length == sizeof(*parent));
    CHECK(get_list(call(SYS_gettid, 0, 0, 0, 0), &value, &length) == 0 && value == parent);
    CHECK(set_list((struct head *)(uintptr_t)1, sizeof(*parent) - 1) == -EINVAL);
    CHECK(get_list(0, &value, &length) == 0 && value == parent);
    CHECK(get_list(-1, &value, &length) == -ESRCH);
    value = (struct head *)(uintptr_t)123;
    CHECK(get_list(0, &value, (size_t *)(uintptr_t)1) == -EFAULT && value == (struct head *)(uintptr_t)123);
    length = 0;
    CHECK(get_list(0, (struct head **)(uintptr_t)1, &length) == -EFAULT && length == sizeof(*parent));
    /* Registration does not dereference a head; exit performs the bounded walk. */
    CHECK(set_list((struct head *)(uintptr_t)1, sizeof(*parent)) == 0);
    CHECK(get_list(0, &value, &length) == 0 && value == (struct head *)(uintptr_t)1);
    CHECK(set_list(0, sizeof(*parent)) == 0);
    CHECK(get_list(0, &value, &length) == 0 && !value && length == sizeof(*parent));
    CHECK(set_list(parent, sizeof(*parent)) == 0);
}

static void fork_reset(struct head *parent)
{
#ifdef SYS_fork
    long child = call(SYS_fork, 0, 0, 0, 0);
#else
    long child = call(SYS_clone, SIGCHLD, 0, 0, 0);
#endif
    CHECK(child >= 0);
    if (!child) {
        struct head *value = (struct head *)(uintptr_t)1;
        size_t length = 0;
        long valid = get_list(0, &value, &length) == 0 && !value && length == sizeof(struct head);
        /* A malformed registered head must not prevent ordinary process exit. */
        valid = valid && set_list((struct head *)(uintptr_t)1, sizeof(struct head)) == 0;
        (void)call(SYS_exit, valid ? 0 : 74, 0, 0, 0);
        for (;;) {}
    }
    int status = -1;
    CHECK(waitpid((pid_t)child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    struct head *value = 0;
    size_t length = 0;
    CHECK(get_list(0, &value, &length) == 0 && value == parent && length == sizeof(*parent));
}

int main(void)
{
    struct head *original = 0;
    size_t original_length = 0;
    CHECK(get_list(0, &original, &original_length) == 0 && original_length == sizeof(struct head));
    struct head parent = {0};
    parent.list.next = &parent.list;
    registrations(&parent);
    void *stack = mmap(0, 16384, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK(stack != MAP_FAILED);
    const int flags = CLONE_VM | CLONE_FS | CLONE_FILES | CLONE_SIGHAND | CLONE_THREAD | CLONE_SYSVSEM |
                      CLONE_PARENT_SETTID | CLONE_CHILD_SETTID | CLONE_CHILD_CLEARTID;
    for (unsigned round = 0; round < 8; ++round) {
        struct state state = {.pending_zero = (int)(round & 1)};
        int tid = __clone(owner, (char *)stack + 16384, flags, &state, (int *)&state.tid, 0, (int *)&state.tid);
        CHECK(tid > 0 && state.tid == (uint32_t)tid);
        while (!__atomic_load_n(&state.phase, __ATOMIC_ACQUIRE)) {
            long result = futex(&state.phase, 128, 0, 0);
            CHECK(result == 0 || result == -EAGAIN);
        }
        CHECK(!__atomic_load_n(&state.error, __ATOMIC_ACQUIRE));
        struct head *value = 0;
        size_t length = 0;
        CHECK(get_list(tid, &value, &length) == 0 && value == &state.head && length == sizeof(struct head));
        __atomic_store_n(&state.gate, 1, __ATOMIC_RELEASE);
        long woken = futex(&state.gate, 129, 1, 0);
        CHECK(woken == 0 || woken == 1);
        CHECK(futex(&state.node.word, 0, state.pending_zero ? 0 : WAITERS | (uint32_t)tid, 0) == 0);
        CHECK(__atomic_load_n(&state.node.word, __ATOMIC_ACQUIRE) == (state.pending_zero ? 0 : WAITERS | OWNER_DIED));
        while (__atomic_load_n(&state.tid, __ATOMIC_ACQUIRE)) {
            long result = futex(&state.tid, 0, (uint32_t)tid, 0);
            CHECK(result == 0 || result == -EAGAIN);
        }
        CHECK(!__atomic_load_n(&state.error, __ATOMIC_ACQUIRE));
        CHECK(get_list(0, &value, &length) == 0 && value == &parent);
    }
    fork_reset(&parent);
    CHECK(munmap(stack, 16384) == 0);
    CHECK(set_list(original, original_length) == 0);
    probe_text("OK_MUSL_ROBUST_LISTS registration=pass clone_reset=pass owner_death=pass pending_zero=pass shared_wake=pass fork_reset=pass malformed=pass unregister=pass rounds=8\n");
    return 0;
}

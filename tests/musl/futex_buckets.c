/* Futex queue behaviour of the kernel's hashed futex buckets (kernel spec 4.5)
 * on every profile, with musl threads. `futex-buckets [rounds]`:
 *
 * - wait_wake: a thread waits on a private word until the main thread changes
 *   it and wakes one waiter, `rounds` times. Every wait returns 0 or EAGAIN.
 * - timeout: a thread whose 30 ms wait expires returns ETIMEDOUT and leaves
 *   no queued wait behind: a later WAKE on the word finds nothing to wake.
 * - timed_out_vs_wake: thread T waits 30 ms, thread U waits without a timeout,
 *   both on one word, T first. The main thread spins (no syscall) until T's
 *   deadline has long passed, then wakes one waiter: the wake must reach U,
 *   since a waiter that timed out no longer takes a wake (Linux
 *   futex_wake_mark). T returns ETIMEDOUT.
 * - requeue: two waiters on word A; CMP_REQUEUE moves them to word B; a wake
 *   on A then finds none and wakes on B release both.
 * - signal_vs_wake: a thread waits without a timeout and a handler without
 *   SA_RESTART; the main thread sends SIGUSR1 and wakes one waiter back to back.
 *   The handler always runs, and the wait returns 0 exactly when the wake
 *   counted it (otherwise EINTR), so no wake is lost to the signal.
 *
 * Prints exactly one line:
 *
 *   FUTEX_BUCKETS_PASS arch=<arch> rounds=R wakes=<n> requeued=<n> eintr=<n> woken=<n> late=<n> spawn_retries=<n>
 *   FUTEX_BUCKETS_FAIL arch=<arch> reason=<token> expected=<n> actual=<n>
 *
 * It does not show that two CPUs ran the racing threads at the same instant.
 * The lines are written without stdio: the ppc libc's printf needs a
 * floating-point runtime the probe link does not have.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#if defined(__i386__)
#define PROBE_ARCH "i386"
#elif defined(__x86_64__)
#define PROBE_ARCH "x86_64"
#elif defined(__arm__)
#define PROBE_ARCH "arm32"
#elif defined(__aarch64__)
#define PROBE_ARCH "aarch64"
#elif defined(__riscv) && __riscv_xlen == 32
#define PROBE_ARCH "rv32"
#elif defined(__riscv) && __riscv_xlen == 64
#define PROBE_ARCH "rv64"
#elif defined(__mips64)
#define PROBE_ARCH "mips64"
#elif defined(__mips__)
#define PROBE_ARCH "mips"
#elif defined(__loongarch64)
#define PROBE_ARCH "loongarch64"
#elif defined(__powerpc__)
#define PROBE_ARCH "ppc"
#else
#error "unknown probe architecture"
#endif

#ifndef SYS_futex
#define SYS_futex SYS_futex_time64
#endif
#define FUTEX_WAIT 0
#define FUTEX_WAKE 1
#define FUTEX_CMP_REQUEUE 4
#define FUTEX_PRIVATE_FLAG 128

/* The relative timeout in the layout SYS_futex takes (as tests/musl/native_threads.c). */
struct wide_timeout { int64_t seconds, nanoseconds; };
struct legacy_timeout { long seconds, nanoseconds; };

static unsigned rounds = 200;
static unsigned long wakes, requeued, eintr, woken, late;

/* One output line, built in `line` and written whole. */
static char line[256];
static size_t used;
static void text(const char *value)
{
    for (size_t size = strlen(value); size && used < sizeof line - 1; --size) line[used++] = *value++;
}
static void field(const char *name, unsigned long value)
{
    char digits[24];
    size_t count = 0;
    do digits[count++] = (char)('0' + value % 10); while ((value /= 10) != 0);
    text(" "); text(name); text("=");
    while (count && used < sizeof line - 1) line[used++] = digits[--count];
}
static void finish_line(void)
{
    line[used++] = '\n';
    for (size_t done = 0; done < used;) {
        const ssize_t written = write(1, line + done, used - done);
        if (written <= 0) _exit(3);
        done += (size_t)written;
    }
    used = 0;
}
static void fail(const char *reason, unsigned long expected, unsigned long actual)
{
    text("FUTEX_BUCKETS_FAIL arch=" PROBE_ARCH " reason="); text(reason);
    field("expected", expected); field("actual", actual); finish_line();
    exit(1);
}
static uint32_t load(uint32_t *word) { return __atomic_load_n(word, __ATOMIC_SEQ_CST); }
static void store(uint32_t *word, uint32_t value) { __atomic_store_n(word, value, __ATOMIC_SEQ_CST); }
static int64_t now(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t)) fail("clock", 0, (unsigned long)errno);
    return (int64_t)t.tv_sec * 1000000000LL + t.tv_nsec;
}
static void pause_ns(long ns)
{
    struct timespec t = {0, ns};
    while (nanosleep(&t, &t) && errno == EINTR) {}
}
/* Every argument as a full register word, as musl's syscall() reads them. */
static long sys_futex(void *word, long operation, long value, const void *timeout, void *second, long third)
{
    return syscall(SYS_futex, word, operation, value, timeout, second, third);
}
/* Returns 0 or the negative errno. */
static long futex_wait(uint32_t *word, uint32_t value, long timeout_ns)
{
    struct wide_timeout wide = {0, timeout_ns};
    struct legacy_timeout legacy = {0, timeout_ns};
    const void *timeout = sizeof(long) == 8 ? (const void *)&wide : (const void *)&legacy;
#if defined(SYS_futex_time64) && SYS_futex == SYS_futex_time64
    timeout = &wide;
#endif
    const long result = sys_futex(word, FUTEX_WAIT | FUTEX_PRIVATE_FLAG, (long)value, timeout_ns ? timeout : 0, 0, 0);
    return result < 0 ? -errno : result;
}
static long futex_wake(uint32_t *word, int count)
{
    const long result = sys_futex(word, FUTEX_WAKE | FUTEX_PRIVATE_FLAG, count, 0, 0, 0);
    if (result < 0) fail("wake-error", 0, (unsigned long)errno);
    return result;
}
/* Waits up to two seconds for `*word` to reach `value`. */
static int await(uint32_t *word, uint32_t value)
{
    const int64_t start = now();
    while (load(word) != value)
        if (now() - start > 2000000000LL) return 0;
        else pause_ns(1000000);
    return 1;
}
/* A joined thread's slot may still be leaving the kernel on another CPU
 * (the clear-TID wake precedes the end of its exit), so a create that finds
 * the process's threads exhausted (EAGAIN) is retried for up to two seconds,
 * and the retries are reported. */
static unsigned long spawn_retries;
static void spawn(pthread_t *thread, void *(*function)(void *))
{
    const int64_t start = now();
    for (;;) {
        const int error = pthread_create(thread, 0, function, 0);
        if (!error) return;
        if (error != EAGAIN || now() - start > 2000000000LL) fail("pthread-create", 0, (unsigned long)error);
        ++spawn_retries;
        pause_ns(1000000);
    }
}
static void join(pthread_t thread)
{
    if (pthread_join(thread, 0)) fail("pthread-join", 0, 0);
}

/* wait_wake */
static uint32_t ww_word, ww_armed, ww_result_bad;
static void *ww_waiter(void *unused)
{
    (void)unused;
    store(&ww_armed, 1);
    while (load(&ww_word) == 0) {
        const long result = futex_wait(&ww_word, 0, 0);
        if (result != 0 && result != -EAGAIN) store(&ww_result_bad, (uint32_t)-result);
    }
    return 0;
}
static void wait_wake(void)
{
    for (unsigned round = 0; round < rounds; ++round) {
        pthread_t thread;
        store(&ww_word, 0);
        store(&ww_armed, 0);
        spawn(&thread, ww_waiter);
        while (!load(&ww_armed)) {}
        if (round % 4 == 0) pause_ns(2000000);
        store(&ww_word, 1);
        wakes += (unsigned long)futex_wake(&ww_word, 1);
        join(thread);
        if (load(&ww_result_bad)) fail("wait-wake-result", 0, load(&ww_result_bad));
    }
}

/* timeout and timed_out_vs_wake */
static uint32_t tw_word, tw_timed_armed, tw_plain_armed, tw_plain_done, tw_release;
static long tw_timed_result, tw_plain_result;
static int64_t tw_timed_start;
static void *tw_timed(void *unused)
{
    (void)unused;
    tw_timed_start = now();
    store(&tw_timed_armed, 1);
    tw_timed_result = futex_wait(&tw_word, 0, 30000000);
    return 0;
}
static void *tw_plain(void *unused)
{
    (void)unused;
    store(&tw_plain_armed, 1);
    tw_plain_result = -EAGAIN;
    while (!load(&tw_release)) tw_plain_result = futex_wait(&tw_word, 0, 0);
    store(&tw_plain_done, 1);
    return 0;
}
static void timeouts(void)
{
    pthread_t timed, plain;
    store(&tw_word, 0);
    store(&tw_timed_armed, 0);
    spawn(&timed, tw_timed);
    join(timed);
    if (tw_timed_result != -ETIMEDOUT) fail("timeout-result", ETIMEDOUT, (unsigned long)-tw_timed_result);
    if (futex_wake(&tw_word, INT_MAX) != 0) fail("timeout-left-queued", 0, 1);

    for (unsigned round = 0; round < 8; ++round) {
        store(&tw_timed_armed, 0);
        store(&tw_plain_armed, 0);
        store(&tw_plain_done, 0);
        store(&tw_release, 0);
        spawn(&timed, tw_timed);
        while (!load(&tw_timed_armed)) {}
        pause_ns(5000000); /* T queues first. */
        spawn(&plain, tw_plain);
        while (!load(&tw_plain_armed)) {}
        pause_ns(5000000);
        /* No syscall from here to the wake: T's deadline passes while this
         * thread runs, and T may not have resumed when the wake comes. */
        while (now() - tw_timed_start < 120000000LL) {}
        store(&tw_release, 1);
        const long count = futex_wake(&tw_word, 1);
        if (!await(&tw_plain_done, 1)) fail("timed-out-waiter-took-the-wake", 1, (unsigned long)count);
        join(plain);
        join(timed);
        if (tw_timed_result != -ETIMEDOUT) fail("timed-out-result", ETIMEDOUT, (unsigned long)-tw_timed_result);
        if (count != 1 && tw_plain_result != -EAGAIN) fail("wake-count", 1, (unsigned long)count);
        wakes += (unsigned long)count;
    }
}

/* requeue */
static uint32_t rq_a, rq_b, rq_armed, rq_done, rq_release, rq_bad;
static void *rq_waiter(void *unused)
{
    (void)unused;
    __atomic_fetch_add(&rq_armed, 1, __ATOMIC_SEQ_CST);
    while (!load(&rq_release)) {
        const long result = futex_wait(&rq_a, 0, 0);
        if (result != 0 && result != -EAGAIN) store(&rq_bad, (uint32_t)-result);
    }
    __atomic_fetch_add(&rq_done, 1, __ATOMIC_SEQ_CST);
    return 0;
}
static void requeue(void)
{
    for (unsigned round = 0; round < 16; ++round) {
        pthread_t first, second;
        store(&rq_a, 0);
        store(&rq_b, 7);
        store(&rq_armed, 0);
        store(&rq_done, 0);
        store(&rq_release, 0);
        spawn(&first, rq_waiter);
        spawn(&second, rq_waiter);
        while (load(&rq_armed) != 2) {}
        /* Move both waiters from A to B, however late they queue on A. */
        unsigned long moved = 0;
        const int64_t start = now();
        while (moved < 2) {
            const long result = sys_futex(&rq_a, FUTEX_CMP_REQUEUE | FUTEX_PRIVATE_FLAG, 0, (const void *)(uintptr_t)INT_MAX, &rq_b, 0);
            if (result < 0) fail("requeue-error", 0, (unsigned long)errno);
            moved += (unsigned long)result;
            if (moved < 2) {
                if (now() - start > 2000000000LL) fail("requeue-missing", 2, moved);
                pause_ns(1000000);
            }
        }
        if (moved != 2) fail("requeue-count", 2, moved);
        /* Mismatched value: nothing moves. */
        if (sys_futex(&rq_a, FUTEX_CMP_REQUEUE | FUTEX_PRIVATE_FLAG, 0, (const void *)(uintptr_t)INT_MAX, &rq_b, 1) != -1 || errno != EAGAIN)
            fail("requeue-compare", EAGAIN, (unsigned long)errno);
        store(&rq_release, 1);
        if (futex_wake(&rq_a, INT_MAX) != 0) fail("requeue-source-wake", 0, 1);
        unsigned long released = 0;
        while (released < 2) {
            released += (unsigned long)futex_wake(&rq_b, INT_MAX);
            if (released < 2) {
                if (now() - start > 4000000000LL) fail("requeue-destination-wake", 2, released);
                pause_ns(1000000);
            }
        }
        if (released != 2) fail("requeue-destination-count", 2, released);
        join(first);
        join(second);
        if (load(&rq_done) != 2 || load(&rq_bad)) fail("requeue-result", 0, load(&rq_bad));
        requeued += moved;
    }
}

/* signal_vs_wake */
static uint32_t sw_word, sw_armed, sw_handled;
static long sw_result;
static void handler(int signal)
{
    (void)signal;
    __atomic_fetch_add(&sw_handled, 1, __ATOMIC_SEQ_CST);
}
static void *sw_waiter(void *unused)
{
    (void)unused;
    store(&sw_armed, 1);
    sw_result = futex_wait(&sw_word, 0, 0);
    return 0;
}
static void signal_vs_wake(void)
{
    struct sigaction action = {0};
    action.sa_handler = handler;
    if (sigemptyset(&action.sa_mask) || sigaction(SIGUSR1, &action, 0)) fail("sigaction", 0, (unsigned long)errno);
    for (unsigned round = 0; round < rounds / 4 + 8; ++round) {
        pthread_t thread;
        store(&sw_word, 0);
        store(&sw_armed, 0);
        store(&sw_handled, 0);
        spawn(&thread, sw_waiter);
        while (!load(&sw_armed)) {}
        pause_ns(3000000);
        if (pthread_kill(thread, SIGUSR1)) fail("pthread-kill", 0, 0);
        if (round % 2) pause_ns(100000);
        long count = futex_wake(&sw_word, 1);
        int64_t start = now();
        while (!load(&sw_handled) && now() - start < 2000000000LL) pause_ns(1000000);
        /* A waiter that queued only after both, with the signal handled
         * before its syscall, needs another wake: not a race outcome. */
        int rescued = 0;
        start = now();
        while (pthread_tryjoin_np(thread, 0) == EBUSY) {
            if (now() - start > 200000000LL && !rescued) { rescued = 1; ++late; futex_wake(&sw_word, 1); }
            if (now() - start > 4000000000LL) fail("signal-wake-lost", 1, (unsigned long)count);
            pause_ns(1000000);
        }
        if (load(&sw_handled) != 1) fail("signal-handler", 1, load(&sw_handled));
        if (!rescued) {
            if (count == 1 && sw_result != 0) fail("woken-not-zero", 0, (unsigned long)-sw_result);
            if (count == 0 && sw_result != -EINTR) fail("unwoken-not-eintr", EINTR, (unsigned long)-sw_result);
        }
        if (sw_result == -EINTR) ++eintr;
        else if (sw_result == 0) ++woken;
        else fail("signal-result", 0, (unsigned long)-sw_result);
    }
}

int main(int argc, char **argv)
{
    if (argc > 1) rounds = (unsigned)strtoul(argv[1], 0, 10);
    if (!rounds || rounds > 100000) fail("rounds", 1, rounds);
    wait_wake();
    timeouts();
    requeue();
    signal_vs_wake();
    text("FUTEX_BUCKETS_PASS arch=" PROBE_ARCH);
    field("rounds", rounds); field("wakes", wakes); field("requeued", requeued);
    field("eintr", eintr); field("woken", woken); field("late", late); field("spawn_retries", spawn_retries);
    finish_line();
    return 0;
}

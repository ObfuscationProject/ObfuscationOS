/* Source-only acceptance fixture for the serialized Linux FUTEX_WAKE_OP path.
 * A readiness store is advisory. Only positive wake counts and successful
 * waitpid results admit real queued waits. Never change a pending wait value.
 */
#define _GNU_SOURCE 1
#include <errno.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define PAGE 4096
#define FUTEX_WAIT 0
#define FUTEX_WAKE 1
#define FUTEX_WAKE_OP 5
#define FUTEX_PRIVATE_FLAG 128
#define RETRIES 2000
#define CHILDREN 3
#define EXPECTED 7U

_Static_assert(sizeof(uint32_t) == 4, "Linux futex word is exactly four bytes");
_Static_assert(__atomic_always_lock_free(4, 0), "Advisory flags need lock-free word accesses");

struct Shared {
    uint32_t word[2];
    uint32_t ready[CHILDREN];
    uint32_t done[CHILDREN];
};
static struct Shared *shared;
static pid_t children[CHILDREN];
static unsigned checks;

static void cleanup_children(void)
{
    for (unsigned i = 0; i < CHILDREN; ++i)
        if (children[i] > 0) (void)kill(children[i], SIGKILL);
    for (unsigned i = 0; i < CHILDREN; ++i) {
        if (children[i] <= 0) continue;
        int status;
        while (waitpid(children[i], &status, 0) < 0 && errno == EINTR) {}
        children[i] = 0;
    }
}

static void fail(const char *reason)
{
    const int error = errno;
    fprintf(stderr, "FUTEX_WAKE_OP_FAIL reason=%s errno=%d checks=%u\n", reason, error, checks);
    cleanup_children();
    _exit(1);
}

static void check(int value, const char *reason)
{
    ++checks;
    if (!value) fail(reason);
}

static void emit(const char *text, size_t size)
{
    check(write(1, text, size) == (ssize_t)size, "marker-write");
}
#define EMIT(text) emit((text), sizeof(text) - 1)

static uint32_t load_word(const uint32_t *word)
{
    return __atomic_load_n(word, __ATOMIC_ACQUIRE);
}
static void store_word(uint32_t *word, uint32_t value)
{
    __atomic_store_n(word, value, __ATOMIC_RELEASE);
}

static uint32_t encoded(unsigned operation, unsigned comparison, int operand, int compare_operand)
{
    return ((uint32_t)operation << 28) | ((uint32_t)comparison << 24) |
        (((uint32_t)operand & 0xfffU) << 12) | ((uint32_t)compare_operand & 0xfffU);
}

static long wake_operation(uint32_t *first, uint32_t *second, uint32_t limit_first,
                           uint32_t limit_second, uint32_t operation, int flags)
{
    /* The fourth argument is a signed wake count, never a timespec pointer.
     * Explicit long-width varargs also preserve O32 stacked fifth/sixth words.
     */
    return syscall(SYS_futex, (long)(uintptr_t)first, (long)(FUTEX_WAKE_OP | flags),
                   (long)(unsigned long)limit_first, (long)(unsigned long)limit_second,
                   (long)(uintptr_t)second, (long)(unsigned long)operation);
}

static long ordinary_wake(uint32_t *word, uint32_t limit)
{
    return syscall(SYS_futex, (long)(uintptr_t)word, (long)FUTEX_WAKE,
                   (long)(unsigned long)limit, 0L, 0L, 0L);
}

static long wait_word(uint32_t *word, int flags, const struct timespec *limit)
{
#ifdef SYS_futex_time64
    const long number = SYS_futex_time64;
#else
    const long number = SYS_futex;
#endif
    return syscall(number, (long)(uintptr_t)word, (long)(FUTEX_WAIT | flags),
                   (long)EXPECTED, (long)(uintptr_t)limit, 0L, 0L);
}

static void yield_once(void)
{
    /* This delay yields the boot CPU. Elapsed time never proves queue admission. */
    struct timespec remaining = {0, 1000000};
    while (nanosleep(&remaining, &remaining) < 0)
        check(errno == EINTR, "retry-yield");
}

static void reset_words(void)
{
    for (unsigned i = 0; i < CHILDREN; ++i) {
        check(children[i] == 0, "previous-children-retired");
        store_word(&shared->ready[i], 0);
        store_word(&shared->done[i], 0);
    }
    store_word(&shared->word[0], EXPECTED);
    store_word(&shared->word[1], EXPECTED);
}

static void start_waiter(unsigned index, unsigned word, int flags, int expect_timeout)
{
    check(index < CHILDREN && word < 2 && children[index] == 0, "waiter-slot");
    const pid_t child = fork();
    check(child >= 0, "waiter-fork");
    if (!child) {
        const struct timespec limit = {expect_timeout ? 1 : 10, 0};
        store_word(&shared->ready[index], 1);
        errno = 0;
        const long result = wait_word(&shared->word[word], flags, &limit);
        const int error = errno;
        const int correct = expect_timeout ? result == -1 && error == ETIMEDOUT : result == 0;
        store_word(&shared->done[index], correct ? 1U : 2U);
        _exit(correct ? 0 : 101);
    }
    children[index] = child;
}

static void join_waiters(unsigned count)
{
    for (unsigned i = 0; i < count; ++i) {
        int status = 0;
        pid_t result;
        do { result = waitpid(children[i], &status, 0); } while (result < 0 && errno == EINTR);
        check(result == children[i] && WIFEXITED(status) && WEXITSTATUS(status) == 0 &&
              load_word(&shared->done[i]) == 1, "waiter-exit-status");
        children[i] = 0;
    }
}

static void scalar_operations(void)
{
    static const struct {
        unsigned operation;
        int operand, compare_operand;
        uint32_t previous, result;
    } cases[] = {
        {0, -2, 7, 7U, 0xfffffffeU},
        {1, 3, 7, 7U, 10U},
        {2, 8, 7, 7U, 15U},
        {3, 3, 7, 7U, 4U},
        {4, 6, 7, 7U, 1U},
        {1, 1, -1, 0xffffffffU, 0U},
        {8, -1, 7, 7U, 0x80000000U}
    };
    reset_words();
    for (unsigned i = 0; i < sizeof cases / sizeof cases[0]; ++i) {
        store_word(&shared->word[1], cases[i].previous);
        check(wake_operation(&shared->word[0], &shared->word[1], 1, 1,
              encoded(cases[i].operation, 0, cases[i].operand, cases[i].compare_operand), 0) == 0 &&
              load_word(&shared->word[1]) == cases[i].result, "scalar-modification");
    }
    store_word(&shared->word[1], EXPECTED);
    errno = 0;
    check(wake_operation(&shared->word[0], &shared->word[1], 1, 1, encoded(5, 0, 9, 7), 0) == -1 &&
          errno == ENOSYS && load_word(&shared->word[1]) == EXPECTED, "undefined-operation-before-store");
    errno = 0;
    check(wake_operation(&shared->word[0], &shared->word[1], 1, 1, encoded(0, 6, 9, 7), 0) == -1 &&
          errno == ENOSYS && load_word(&shared->word[1]) == 9, "undefined-comparison-after-store");
    reset_words();
    EMIT("FUTEX_WAKE_OP_EVENT scalar=pass set=pass add=pass or=pass andn=pass xor=pass signed=pass wrap=pass shift_mask=pass invalid_op=unchanged invalid_cmp=modified wake=0\n");
}

static void two_queues(int legacy_limits, int scope_and_invalid)
{
    reset_words();
    start_waiter(0, 0, 0, 0);
    start_waiter(1, 1, 0, 0);
    const uint32_t first_limit = legacy_limits ? 0U : 1U;
    const uint32_t second_limit = legacy_limits ? 0xffffffffU : 1U;
    unsigned total = 0;
    for (unsigned attempt = 0; attempt < RETRIES && total < 2; ++attempt) {
        if (scope_and_invalid) {
            check(wake_operation(&shared->word[0], &shared->word[1], 1, 1,
                  encoded(0, 0, 7, 7), FUTEX_PRIVATE_FLAG) == 0, "parent-private-cannot-wake-shared-children");
            errno = 0;
            check(wake_operation(&shared->word[0], &shared->word[1], 1, 1, encoded(5, 0, 7, 7), 0) == -1 &&
                  errno == ENOSYS && load_word(&shared->word[1]) == EXPECTED, "invalid-operation-live-children");
            errno = 0;
            check(wake_operation(&shared->word[0], &shared->word[1], 1, 1, encoded(0, 6, 7, 7), 0) == -1 &&
                  errno == ENOSYS && load_word(&shared->word[1]) == EXPECTED, "invalid-comparison-live-children");
        }
        /* Identity SET leaves a late child's expected second word unchanged. */
        const long woke = wake_operation(&shared->word[0], &shared->word[1], first_limit, second_limit,
                                         encoded(0, 0, 7, 7), 0);
        check(woke >= 0 && woke <= 2 && (unsigned long)woke <= 2U - total &&
              load_word(&shared->word[0]) == EXPECTED && load_word(&shared->word[1]) == EXPECTED,
              "two-queue-exact-positive-count");
        total += (unsigned)woke;
        if (total < 2) yield_once();
    }
    check(total == 2, "two-queues-drained-without-eagain");
    join_waiters(2);
    check(ordinary_wake(&shared->word[0], 1) == 0 && ordinary_wake(&shared->word[1], 1) == 0,
          "two-queues-empty-after-reap");
    if (scope_and_invalid)
        EMIT("FUTEX_WAKE_OP_EVENT shared=pass first_queue=1 second_queue=1 positive_wakes=2 private_wakes=0 invalid_queue_effects=none child_exit=0\n");
    else if (legacy_limits)
        EMIT("FUTEX_WAKE_OP_EVENT legacy=pass first_count=0 second_count=-1 first_queue=1 second_queue=1 positive_wakes=2 child_exit=0\n");
    else
        EMIT("FUTEX_WAKE_OP_EVENT shared=pass first_queue=1 second_queue=1 positive_wakes=2 identity_set=pass child_exit=0\n");
}

static void false_comparison(void)
{
    reset_words();
    start_waiter(0, 0, 0, 0);
    start_waiter(1, 1, 0, 0);
    unsigned total = 0;
    for (unsigned attempt = 0; attempt < RETRIES && !total; ++attempt) {
        const long woke = wake_operation(&shared->word[0], &shared->word[1], 1, 1, encoded(0, 0, 7, 99), 0);
        check((woke == 0 || woke == 1) && load_word(&shared->word[1]) == EXPECTED, "false-comparison-first-only");
        total += (unsigned)woke;
        if (!total) yield_once();
    }
    check(total == 1, "false-comparison-first-queued-wake");
    total = 0;
    for (unsigned attempt = 0; attempt < RETRIES && !total; ++attempt) {
        const long woke = ordinary_wake(&shared->word[1], 1);
        check(woke == 0 || woke == 1, "false-comparison-second-drain-count");
        total += (unsigned)woke;
        if (!total) yield_once();
    }
    check(total == 1, "false-comparison-second-still-needs-wake");
    join_waiters(2);
    EMIT("FUTEX_WAKE_OP_EVENT false_comparison=pass first_wake=1 second_operation_wake=0 second_later_wake=1 child_exit=0\n");
}

static void same_key(void)
{
    reset_words();
    for (unsigned i = 0; i < CHILDREN; ++i) start_waiter(i, 0, 0, 0);
    unsigned total = 0;
    for (unsigned attempt = 0; attempt < RETRIES && total < CHILDREN; ++attempt) {
        const long woke = wake_operation(&shared->word[0], &shared->word[0], 1, 1, encoded(0, 0, 7, 7), 0);
        check(woke >= 0 && woke <= 2 && (unsigned long)woke <= CHILDREN - total &&
              load_word(&shared->word[0]) == EXPECTED, "same-key-no-double-count");
        total += (unsigned)woke;
        if (total < CHILDREN) yield_once();
    }
    check(total == CHILDREN, "same-key-three-unique-wakes");
    join_waiters(CHILDREN);
    check(ordinary_wake(&shared->word[0], 1) == 0, "same-key-empty-after-reap");
    EMIT("FUTEX_WAKE_OP_EVENT same_key=pass waiters=3 positive_wakes=3 per_call_max=2 unique_exit_statuses=3 child_exit=0\n");
}

static void child_private_scope(void)
{
    reset_words();
    start_waiter(0, 0, FUTEX_PRIVATE_FLAG, 1);
    unsigned attempt = 0;
    while (!load_word(&shared->ready[0]) && attempt++ < RETRIES) yield_once();
    check(load_word(&shared->ready[0]) == 1, "private-child-started-advisory");
    unsigned observed = 0;
    for (attempt = 0; attempt < RETRIES && !load_word(&shared->done[0]); ++attempt) {
        check(wake_operation(&shared->word[0], &shared->word[1], 1, 1, encoded(0, 0, 7, 7), 0) == 0,
              "shared-operation-cannot-wake-child-private-key");
        ++observed;
        yield_once();
    }
    check(observed > 0 && load_word(&shared->done[0]) == 1, "private-child-timeout-observed");
    join_waiters(1);
    EMIT("FUTEX_WAKE_OP_EVENT private_child=pass shared_wakes=0 wait_result=etimedout child_exit=0\n");
}

int main(void)
{
    shared = mmap(0, PAGE, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    check(shared != MAP_FAILED && sizeof *shared <= PAGE, "shared-anonymous-page");
    scalar_operations();
    two_queues(0, 0);
    false_comparison();
    two_queues(1, 0);
    same_key();
    two_queues(0, 1);
    child_private_scope();
    check(munmap(shared, PAGE) == 0, "shared-page-retired");
    EMIT("OK_MUSL_FUTEX_WAKE_OP version=1 scope=actual-processes anonymous_shared=pass fork=pass modification=pass two_queues=pass false_comparison=pass legacy_signed_counts=pass same_key=pass invalid_encoding=pass private_domain=pass positive_wakes=11 children_reaped=12 physical_machine=0 smp=0\n");
    return 0;
}

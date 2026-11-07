/* SMP atomicity of FUTEX_WAKE_OP user-word updates (kernel futex slice).
 * `futex-smp-atomic [rounds]` races the kernel's update of one word against
 * user atomics on the same word from another thread:
 *
 * - add: one thread issues FUTEX_WAKE_OP(FUTEX_OP_ADD 1) `rounds` times while
 *   the other increments the word with an atomic fetch-add until the first is
 *   done. No update may be lost: word == rounds + user increments.
 * - bits: one thread sets and clears bit 0 with FUTEX_OP_OR / FUTEX_OP_ANDN
 *   `rounds` times while the other flips bit 1 with an atomic xor. Bit 0 must
 *   end clear, bit 1 must match the parity of the flips, no other bit set.
 * - cow: after fork the word's page is copy-on-write shared. FUTEX_WAKE_OP in
 *   the parent must update only the parent's copy; the child checks its own.
 *
 * `interleaved` counts user increments whose old value shows a kernel update
 * since the previous one: the two sides really ran at the same time. Prints
 * exactly one line:
 *
 *   FUTEX_SMP_ATOMIC_PASS arch=<arch> rounds=R user=<n> flips=<n> interleaved=<n>
 *   FUTEX_SMP_ATOMIC_FAIL arch=<arch> reason=<token> expected=<n> actual=<n>
 */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/syscall.h>
#include <sys/wait.h>
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
#define FUTEX_WAKE_OP 5
#define FUTEX_PRIVATE_FLAG 128
#define FUTEX_OP(op, oparg, cmp, cmparg) \
    ((((op) & 15U) << 28) | (((cmp) & 15U) << 24) | (((oparg) & 0xfffU) << 12) | ((cmparg) & 0xfffU))
#define FUTEX_OP_ADD 1
#define FUTEX_OP_OR 2
#define FUTEX_OP_ANDN 3
#define FUTEX_OP_CMP_EQ 0

static uint32_t word __attribute__((aligned(64)));
static uint32_t other __attribute__((aligned(64)));
static unsigned rounds = 20000;
static unsigned ready, done;
static unsigned long user_count, flips, interleaved;
static int kernel_error;

static void fail(const char *reason, unsigned long expected, unsigned long actual)
{
    printf("FUTEX_SMP_ATOMIC_FAIL arch=" PROBE_ARCH " reason=%s expected=%lu actual=%lu\n", reason, expected, actual);
    fflush(stdout);
    exit(1);
}

static long wake_op(uint32_t *target, unsigned operation, int flags)
{
    return syscall(SYS_futex, &other, FUTEX_WAKE_OP | flags, 0, 0, target, operation);
}

static void start(void)
{
    __atomic_fetch_add(&ready, 1, __ATOMIC_SEQ_CST);
    while (__atomic_load_n(&ready, __ATOMIC_SEQ_CST) < 2) {}
}

static void *kernel_add(void *unused)
{
    (void)unused;
    start();
    for (unsigned i = 0; i < rounds; ++i)
        if (wake_op(&word, FUTEX_OP(FUTEX_OP_ADD, 1, FUTEX_OP_CMP_EQ, 0), FUTEX_PRIVATE_FLAG) != 0)
            kernel_error = errno ? errno : -1;
    __atomic_store_n(&done, 1, __ATOMIC_SEQ_CST);
    return 0;
}

static void *kernel_bits(void *unused)
{
    (void)unused;
    start();
    for (unsigned i = 0; i < rounds; ++i)
        if (wake_op(&word, FUTEX_OP(FUTEX_OP_OR, 1, FUTEX_OP_CMP_EQ, 0), FUTEX_PRIVATE_FLAG) != 0 ||
            wake_op(&word, FUTEX_OP(FUTEX_OP_ANDN, 1, FUTEX_OP_CMP_EQ, 0), FUTEX_PRIVATE_FLAG) != 0)
            kernel_error = errno ? errno : -1;
    __atomic_store_n(&done, 1, __ATOMIC_SEQ_CST);
    return 0;
}

static void race(void *(*kernel_side)(void *), int add)
{
    pthread_t thread;
    __atomic_store_n(&ready, 0, __ATOMIC_SEQ_CST);
    __atomic_store_n(&done, 0, __ATOMIC_SEQ_CST);
    if (pthread_create(&thread, 0, kernel_side, 0)) fail("pthread-create", 0, 0);
    start();
    uint32_t last = __atomic_load_n(&word, __ATOMIC_SEQ_CST);
    while (!__atomic_load_n(&done, __ATOMIC_SEQ_CST)) {
        if (add) {
            const uint32_t old = __atomic_fetch_add(&word, 1, __ATOMIC_SEQ_CST);
            interleaved += old != last;
            last = old + 1;
            ++user_count;
        } else {
            __atomic_fetch_xor(&word, 2, __ATOMIC_SEQ_CST);
            ++flips;
        }
    }
    if (pthread_join(thread, 0)) fail("pthread-join", 0, 0);
    if (kernel_error) fail("wake-op-error", 0, (unsigned long)kernel_error);
}

int main(int argc, char **argv)
{
    if (argc > 1) rounds = (unsigned)strtoul(argv[1], 0, 10);
    if (!rounds || rounds > 10000000) fail("rounds", 1, rounds);

    word = 0;
    race(kernel_add, 1);
    /* The word wraps at 32 bits; a UP boot can spin past that. */
    if (word != (uint32_t)(rounds + user_count)) fail("add-lost-update", (uint32_t)(rounds + user_count), word);

    word = 0;
    race(kernel_bits, 0);
    if (word != ((flips & 1) ? 2U : 0U)) fail("bits-lost-update", (flips & 1) ? 2 : 0, word);

    word = 40;
    int pipe_fds[2];
    if (pipe(pipe_fds)) fail("pipe", 0, errno);
    const pid_t child = fork();
    if (child < 0) fail("fork", 0, errno);
    if (child == 0) {
        char go;
        close(pipe_fds[1]);
        if (read(pipe_fds[0], &go, 1) != 1) _exit(2);
        _exit(__atomic_load_n(&word, __ATOMIC_SEQ_CST) == 40 ? 0 : 3);
    }
    close(pipe_fds[0]);
    if (wake_op(&word, FUTEX_OP(FUTEX_OP_ADD, 2, FUTEX_OP_CMP_EQ, 0), FUTEX_PRIVATE_FLAG) != 0)
        fail("cow-wake-op", 0, (unsigned long)errno);
    if (word != 42) fail("cow-parent", 42, word);
    if (write(pipe_fds[1], "g", 1) != 1) fail("cow-signal", 1, 0);
    int status;
    while (waitpid(child, &status, 0) < 0)
        if (errno != EINTR) fail("cow-wait", 0, errno);
    if (!WIFEXITED(status) || WEXITSTATUS(status)) fail("cow-child", 0, (unsigned long)status);

    printf("FUTEX_SMP_ATOMIC_PASS arch=" PROBE_ARCH " rounds=%u user=%lu flips=%lu interleaved=%lu\n", rounds,
           user_count, flips, interleaved);
    return 0;
}

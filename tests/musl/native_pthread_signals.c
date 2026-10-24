#define _GNU_SOURCE
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <errno.h>
#include <time.h>
#include <unistd.h>
#include <sys/syscall.h>

#if defined(__i386__)
#define PROBE_ARCH "i386"
#elif defined(__x86_64__)
#define PROBE_ARCH "x86_64"
#elif defined(__arm__)
#define PROBE_ARCH "arm32"
#elif defined(__aarch64__)
#define PROBE_ARCH "aarch64"
#elif defined(__riscv) && __riscv_xlen == 64
#define PROBE_ARCH "rv64"
#elif defined(__riscv) && __riscv_xlen == 32
#define PROBE_ARCH "rv32"
#elif defined(__mips64)
#define PROBE_ARCH "mips64"
#elif defined(__mips__) && !defined(__mips64)
#define PROBE_ARCH "mips"
#elif defined(__loongarch64)
#define PROBE_ARCH "loongarch64"
#elif defined(__powerpc__) || defined(__PPC__)
#define PROBE_ARCH "ppc"
#if __SIZEOF_POINTER__ != 4 || __BYTE_ORDER__ != __ORDER_BIG_ENDIAN__ || !defined(__SPE__)
#error "This PPC fixture requires the native big-endian PPC32 e500/SPE profile"
#endif
_Static_assert(sizeof(long) == 4 && sizeof(void *) == 4, "PPC32 native words");
#else
#error "This private signal fixture currently supports i386, x86_64, AArch64, ARM32, RV32, RV64, LoongArch64, MIPS o32, MIPS64 n64 and PPC32"
#endif
// The freestanding musl build admits only its pinned headers, so use compiler
// atomic builtins rather than an implicit compiler stdatomic header search.
#if (defined(__powerpc__) || defined(__PPC__)) && defined(__clang__)
// Clang's C11 builtins accept _Atomic objects without GCC's integer-pointer
// extension; keep identical sequential consistency and lock-free checks.
#define atomic_load(p) __c11_atomic_load((p), __ATOMIC_SEQ_CST)
#define atomic_store(p, v) __c11_atomic_store((p), (v), __ATOMIC_SEQ_CST)
#define atomic_fetch_add(p, v) __c11_atomic_fetch_add((p), (v), __ATOMIC_SEQ_CST)
#else
#define atomic_load(p) __atomic_load_n((p), __ATOMIC_SEQ_CST)
#define atomic_store(p, v) __atomic_store_n((p), (v), __ATOMIC_SEQ_CST)
#define atomic_fetch_add(p, v) __atomic_fetch_add((p), (v), __ATOMIC_SEQ_CST)
#endif
#define atomic_is_lock_free(p) __atomic_always_lock_free(sizeof(*(p)), (p))
static _Thread_local int lane;
static _Atomic int received[2], ready, release_peer, bad;
static _Atomic int main_tid, peer_tid;
static pid_t process_id;
static void handle(int sig, siginfo_t *info, void *context)
{
    sigset_t current;
    if (lane < 0 || lane > 1 || syscall(SYS_gettid) !=
        (lane ? atomic_load(&peer_tid) : atomic_load(&main_tid)) ||
        errno != (lane ? 119 : 118)) {
        atomic_store(&bad, 3);
        return;
    }
    if (sig != SIGUSR1 || !context || info->si_signo != SIGUSR1 ||
        info->si_code != SI_TKILL || info->si_pid != process_id ||
        pthread_sigmask(SIG_SETMASK, NULL, &current) || !sigismember(&current, SIGUSR1))
        atomic_store(&bad, 1);
    atomic_fetch_add(&received[lane], 1);
}
static int wait_for(_Atomic int *word)
{
    struct timespec start, now;
    if (clock_gettime(CLOCK_MONOTONIC, &start)) return 0;
    while (!atomic_load(word)) {
        if (clock_gettime(CLOCK_MONOTONIC, &now)) return 0;
        if (now.tv_sec - start.tv_sec >= 10) return 0;
    }
    return 1;
}
static void *peer(void *unused)
{
    (void)unused;
    lane = 1; errno = 119;
    atomic_store(&peer_tid, (int)syscall(SYS_gettid));
    atomic_store(&ready, 1);
    if (!wait_for(&release_peer) || errno != 119 || atomic_load(&received[1]) != 1)
        atomic_store(&bad, 2);
    return (void *)(uintptr_t)0x1357;
}
#define CHECK(x, n) do { if (!(x) || atomic_load(&bad)) { printf("PTHREAD_SIGNALS_FAIL code=%d bad=%d\n", n, atomic_load(&bad)); return 1; } } while (0)
int main(void)
{
    process_id = getpid();
    atomic_store(&main_tid, (int)syscall(SYS_gettid));
    CHECK(atomic_is_lock_free(&received[0]) && atomic_is_lock_free(&bad), 101);
    struct sigaction prior = {0}, action = {0}, old = {0}, readback = {0};
    prior.sa_handler = SIG_IGN;
    CHECK(sigemptyset(&prior.sa_mask) == 0 && sigaddset(&prior.sa_mask, SIGUSR2) == 0 &&
          sigaction(SIGUSR1, &prior, NULL) == 0, 109);
    action.sa_sigaction = handle; action.sa_flags = SA_SIGINFO;
    CHECK(sigemptyset(&action.sa_mask) == 0 && sigaction(SIGUSR1, &action, &old) == 0, 102);
    CHECK(old.sa_handler == SIG_IGN && !(old.sa_flags & SA_SIGINFO) &&
          sigismember(&old.sa_mask, SIGUSR2) == 1 && sigismember(&old.sa_mask, SIGUSR1) == 0, 110);
    CHECK(sigaction(SIGUSR1, NULL, &readback) == 0 && readback.sa_sigaction == handle &&
          (readback.sa_flags & SA_SIGINFO) && sigismember(&readback.sa_mask, SIGUSR2) == 0 &&
          sigismember(&readback.sa_mask, SIGUSR1) == 0, 111);
    errno = 118;
    CHECK(raise(SIGUSR1) == 0 && atomic_load(&received[0]) == 1 && errno == 118, 103);
    pthread_t child;
    CHECK(pthread_create(&child, NULL, peer, NULL) == 0 && wait_for(&ready), 104);
    CHECK(pthread_kill(child, 0) == 0 && pthread_kill(child, SIGUSR1) == 0, 105);
    CHECK(wait_for(&received[1]) && atomic_load(&received[0]) == 1, 106);
    atomic_store(&release_peer, 1);
    void *result = 0;
    CHECK(pthread_join(child, &result) == 0 && result == (void *)(uintptr_t)0x1357, 107);
    CHECK(lane == 0 && errno == 118 && atomic_load(&received[0]) == 1 &&
          atomic_load(&received[1]) == 1 && atomic_load(&main_tid) != atomic_load(&peer_tid), 112);
    CHECK(sigaction(SIGUSR1, &old, NULL) == 0, 108);
    CHECK(sigaction(SIGUSR1, NULL, &readback) == 0 && readback.sa_handler == SIG_IGN &&
          !(readback.sa_flags & SA_SIGINFO) && sigismember(&readback.sa_mask, SIGUSR2) == 1 &&
          sigismember(&readback.sa_mask, SIGUSR1) == 0, 113);
    puts("PTHREAD_SIGNALS_PASS " PROBE_ARCH " raise=1 peer=1 siginfo=1 masks=1 tls=1 join=1");
    return 0;
}

#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <signal.h>
#include <ucontext.h>
#include <sys/syscall.h>
#include <unistd.h>

#if defined(__x86_64__)
#define PROBE_ARCH "x86_64"
#elif defined(__aarch64__)
#define PROBE_ARCH "aarch64"
#else
#error "This RT-frame fixture currently supports x86_64 and AArch64"
#endif
struct action { uintptr_t handler, flags, restorer, mask; };
static volatile int handled, nested, failure, mode;
static long pid, tid;
#if defined(__x86_64__)
static long raw(long n, long a, long b, long c, long d)
{
    register long r10 __asm__("r10") = d;
    long result;
    __asm__ volatile("syscall" : "=a"(result) : "a"(n), "D"(a), "S"(b), "d"(c), "r"(r10) : "rcx", "r11", "memory");
    return result;
}
__attribute__((naked)) static void restore(void)
{
    __asm__ volatile("mov $15,%rax; syscall; ud2");
}
__asm__(".text\n.global signal_fp_probe\n.type signal_fp_probe,@function\nsignal_fp_probe:\n"
        "movabs $0x12345678abcdef01,%rax\nmovq %rax,%xmm0\nmov $10,%edx\nmov $234,%eax\nsyscall\n"
        "movq %xmm0,%rax\nret\n.size signal_fp_probe,.-signal_fp_probe\n");
extern uint64_t signal_fp_probe(long, long);
#else
static long raw(long n, long a, long b, long c, long d)
{
    register long x8 __asm__("x8") = n;
    register long x0 __asm__("x0") = a;
    register long x1 __asm__("x1") = b;
    register long x2 __asm__("x2") = c;
    register long x3 __asm__("x3") = d;
    __asm__ volatile("svc 0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2), "r"(x3) : "memory", "cc");
    return x0;
}
extern void restore(void);
extern uint64_t signal_fp_probe(long, long);
__asm__(".text\n.global restore\n.type restore,%function\nrestore:\nmov x8,139\nsvc 0\nbrk 0\n.size restore,.-restore\n"
        ".global signal_fp_probe\n.type signal_fp_probe,%function\nsignal_fp_probe:\n"
        "movz x9,0xef01\nmovk x9,0xabcd,lsl 16\nmovk x9,0x5678,lsl 32\nmovk x9,0x1234,lsl 48\n"
        "fmov d0,x9\nmov x2,10\nmov x8,131\nsvc 0\nfmov x0,d0\nret\n.size signal_fp_probe,.-signal_fp_probe\n");
#endif
static long mask(int how, uint64_t *set, uint64_t *old)
{
    return raw(SYS_rt_sigprocmask, how, (long)set, (long)old, 8);
}
static long action(int sig, struct action *set, struct action *old)
{
    return raw(SYS_rt_sigaction, sig, (long)set, (long)old, 8);
}
static int check(int condition, int code);
static void handler_fail(int code)
{
    failure = code;
    // Fatal-return children cannot propagate their private failure global.
    // Stop on the assertion before later frame access or deliberate corruption.
    if (mode == 6 || mode == 7) check(0, 136);
}
static void handler(int sig, siginfo_t *info, void *context)
{
    ucontext_t *uc = context;
    uint64_t blocked = 0;
    if (sig != SIGUSR1 && sig != SIGUSR2) handler_fail(1);
    if (info->si_signo != sig || info->si_code != SI_TKILL || info->si_pid != pid) handler_fail(2);
    if (mask(SIG_SETMASK, 0, &blocked)) handler_fail(3);
    if (sig == SIGUSR2) { ++nested; if (!(blocked & (1ul << (SIGUSR2-1)))) handler_fail(4); return; }
    ++handled;
    if (mode != 2 && !(blocked & (1ul << (SIGUSR1-1)))) handler_fail(5);
    if (mode == 2 && (blocked & (1ul << (SIGUSR1-1)))) handler_fail(6);
    if (!(blocked & (1ul << (SIGUSR2-1)))) handler_fail(7);
    if (mode == 3) {
        uint64_t second = 1ul << (SIGUSR2-1);
        if (mask(SIG_UNBLOCK, &second, 0) || raw(SYS_tgkill, pid, tid, SIGUSR2, 0)) handler_fail(8);
    }
    if (mode == 4) {
#if defined(__x86_64__)
        uc->uc_mcontext.gregs[REG_RAX] = 0x1234;
#else
        uc->uc_mcontext.regs[0] = 0x1234;
#endif
    }
    if (mode == 5) {
        struct action old = {0};
        if (action(SIGUSR1, 0, &old) || old.handler != 0) handler_fail(9);
    }
#if defined(__x86_64__)
    if (mode == 6) ((uint32_t *)uc->uc_mcontext.fpregs)[6] = 0xffffffffu;
    if (mode == 7) uc->uc_mcontext.gregs[REG_RIP] = 0xffff800000000000ul;
    __asm__ volatile("pxor %%xmm0,%%xmm0" ::: "xmm0");
#else
    // Malformed FPSIMD size must be rejected; FPCR RES0 bits alone are not an
    // invalid-frame condition on AArch64 hardware.
    if (mode == 6) ((uint32_t *)uc->uc_mcontext.__reserved)[1] = 527;
    if (mode == 7) uc->uc_mcontext.pc = 0xffff800000000000ul;
    __asm__ volatile("movi v0.2d,0" ::: "v0");
#endif
}
static int check(int condition, int code)
{
    if (condition && !failure) return 1;
    char msg[] = "SIGNAL_DELIVERY_FAIL code=000 handler=0\n";
    const size_t code_at = sizeof("SIGNAL_DELIVERY_FAIL code=") - 1;
    const size_t handler_at = sizeof("SIGNAL_DELIVERY_FAIL code=000 handler=") - 1;
    msg[code_at] = '0' + code / 100; msg[code_at+1] = '0' + code / 10 % 10; msg[code_at+2] = '0' + code % 10;
    msg[handler_at] = '0' + failure;
    raw(SYS_write, 1, (long)msg, sizeof(msg)-1, 0);
    raw(SYS_exit_group, 1, 0, 0, 0);
    return 0;
}
int main(void)
{
    pid = raw(SYS_getpid, 0,0,0,0); tid = raw(SYS_gettid, 0,0,0,0);
    struct action a = {(uintptr_t)handler, 0x04000004, (uintptr_t)restore, 1ul << (SIGUSR2-1)};
    struct action second = {(uintptr_t)handler, 0x04000004, (uintptr_t)restore, 0};
    uint64_t one = 1ul << (SIGUSR1-1), empty = 0;
    check(action(SIGUSR1, &a, 0) == 0 && action(SIGUSR2, &second, 0) == 0, 101);
    errno = 117;
    check(raw(SYS_tgkill, pid, tid, SIGUSR1, 0) == 0 && handled == 1 && errno == 117, 102);
    check(mask(SIG_BLOCK, &one, 0) == 0, 103);
    check(raw(SYS_tgkill, pid, tid, SIGUSR1, 0) == 0 && raw(SYS_tgkill, pid, tid, SIGUSR1, 0) == 0 && handled == 1, 104);
    check(mask(SIG_UNBLOCK, &one, 0) == 0 && handled == 2, 105);
    a.flags |= 0x40000000; mode = 2;
    check(action(SIGUSR1, &a, 0) == 0 && raw(SYS_tgkill, pid, tid, SIGUSR1, 0) == 0 && handled == 3, 106);
    a.flags &= ~0x40000000ul; mode = 3;
    check(action(SIGUSR1, &a, 0) == 0 && raw(SYS_tgkill, pid, tid, SIGUSR1, 0) == 0 && handled == 4 && nested == 1, 107);
    mode = 4;
    check(raw(SYS_tgkill, pid, tid, SIGUSR1, 0) == 0x1234 && handled == 5, 108);
    mode = 0;
    check(signal_fp_probe(pid, tid) == 0x12345678abcdef01ul && handled == 6, 109);
    mode = 5; a.flags |= 0x80000000;
    check(action(SIGUSR1, &a, 0) == 0 && raw(SYS_tgkill, pid, tid, SIGUSR1, 0) == 0 && handled == 7, 110);
    a.flags &= ~0x80000000ul;
    check(action(SIGUSR1, &a, 0) == 0, 111);
    for (int bad = 6; bad <= 7; ++bad) {
#ifdef SYS_fork
        long child = raw(SYS_fork, 0,0,0,0);
#else
        long child = raw(SYS_clone, SIGCHLD,0,0,0);
#endif
        check(child >= 0, 112);
        if (!child) {
            pid = raw(SYS_getpid,0,0,0,0); tid = raw(SYS_gettid,0,0,0,0); mode = bad;
            raw(SYS_tgkill,pid,tid,SIGUSR1,0); raw(SYS_exit_group,99,0,0,0);
        }
        int status = 0;
        check(raw(SYS_wait4,child,(long)&status,0,0) == child && (status & 0x7f) == SIGSEGV, 113);
    }
    check(mask(SIG_SETMASK,0,&empty) == 0 && empty == 0, 114);
    static const char success[] = "SIGNAL_DELIVERY_PASS " PROBE_ARCH " handler=7 nested=1 coalesced=1 nodefer=1 reset=1 registers=1 fp=1 corrupt_return=2\n";
    check(raw(SYS_write,1,(long)success,sizeof(success)-1,0) == sizeof(success)-1,115);
    return 0;
}

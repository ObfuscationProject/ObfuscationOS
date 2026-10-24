#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <signal.h>
#include <ucontext.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

#if defined(__riscv) && __riscv_xlen == 32
#define PROBE_ARCH "rv32"
#define STORE "sw"
#define LOAD "lw"
#elif defined(__riscv) && __riscv_xlen == 64
#define PROBE_ARCH "rv64"
#define STORE "sd"
#define LOAD "ld"
#else
#error "This raw signal fixture supports RV32GC and RV64GC"
#endif
#ifdef SA_RESTORER
#error "RISC-V Linux kernel action records have no restorer member"
#endif

struct action { uintptr_t handler, flags; unsigned long mask[8 / sizeof(unsigned long)]; };
_Static_assert(offsetof(struct action, mask) == 2*sizeof(uintptr_t), "Linux action mask offset");
_Static_assert(sizeof(struct action) == 2*sizeof(uintptr_t)+8, "Linux action copy length");
static volatile int handled, nested, failure, mode, restorers;
static volatile uintptr_t desired_tp;
static _Alignas(16) unsigned char tp_storage[64];
static long pid, tid;
static long raw(long n, long a, long b, long c, long d)
{
    register long a7 __asm__("a7") = n;
    register long a0 __asm__("a0") = a;
    register long a1 __asm__("a1") = b;
    register long a2 __asm__("a2") = c;
    register long a3 __asm__("a3") = d;
    __asm__ volatile("ecall" : "+r"(a0) : "r"(a7), "r"(a1), "r"(a2), "r"(a3) : "memory");
    return a0;
}
extern long signal_fp_probe(long, long, uint64_t *, uint32_t *);
extern long signal_tp_probe(long, long, uintptr_t *);
extern long signal_bad_return_probe(long, long);
// Each wrapper keeps all bookkeeping on a valid aligned stack. The TP wrapper
// records the returned TP then reinstalls libc's original TP before entering C.
// The bad-return wrapper immediately loads the restored stack, so SP=0 cannot
// pass by issuing an exit syscall without ever touching the invalid stack.
__asm__(".text\n.balign 4\n.global signal_fp_probe\n.type signal_fp_probe,@function\nsignal_fp_probe:\n"
        "addi sp,sp,-32\n" STORE " ra,24(sp)\n" STORE " a2,16(sp)\n" STORE " a3,8(sp)\n"
        "frcsr t0\nsw t0,0(sp)\nla t0,fp_magic\nfld ft0,0(t0)\nli t0,0x41\nfscsr t0\n"
        "li a2,10\nli a7,131\necall\n" LOAD " t0,16(sp)\nfsd ft0,0(t0)\n"
        LOAD " t0,8(sp)\nfrcsr t1\nsw t1,0(t0)\nlw t0,0(sp)\nfscsr t0\n"
        LOAD " ra,24(sp)\naddi sp,sp,32\nret\n.size signal_fp_probe,.-signal_fp_probe\n"
        ".balign 4\n.global signal_tp_probe\n.type signal_tp_probe,@function\nsignal_tp_probe:\n"
        "addi sp,sp,-32\n" STORE " ra,24(sp)\n" STORE " tp,16(sp)\n" STORE " a2,8(sp)\n"
        "li a2,10\nli a7,131\necall\n" LOAD " t0,8(sp)\n" STORE " tp,0(t0)\n"
        LOAD " tp,16(sp)\n" LOAD " ra,24(sp)\naddi sp,sp,32\nret\n.size signal_tp_probe,.-signal_tp_probe\n"
        ".balign 4\n.global signal_bad_return_probe\n.type signal_bad_return_probe,@function\nsignal_bad_return_probe:\n"
        "addi sp,sp,-16\n" STORE " ra,0(sp)\nli a2,10\nli a7,131\necall\n"
        LOAD " ra,0(sp)\naddi sp,sp,16\nret\n.size signal_bad_return_probe,.-signal_bad_return_probe\n"
        ".section .rodata\n.balign 8\nfp_magic: .quad 0x12345678abcdef01\n.text\n");
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
    const volatile uint32_t *restorer = (const volatile uint32_t *)__builtin_return_address(0);
    if (((uintptr_t)restorer & 3) || restorer[0] != 0x08b00893 || restorer[1] != 0x00000073) handler_fail(10);
    ++restorers;
    if (sig == SIGUSR2) { ++nested; if (!(blocked & (UINT64_C(1) << (SIGUSR2-1)))) handler_fail(4); return; }
    ++handled;
    if (mode != 2 && !(blocked & (UINT64_C(1) << (SIGUSR1-1)))) handler_fail(5);
    if (mode == 2 && (blocked & (UINT64_C(1) << (SIGUSR1-1)))) handler_fail(6);
    if (!(blocked & (UINT64_C(1) << (SIGUSR2-1)))) handler_fail(7);
    if (mode == 3) {
        uint64_t second = UINT64_C(1) << (SIGUSR2-1);
        if (mask(SIG_UNBLOCK, &second, 0) || raw(SYS_tgkill, pid, tid, SIGUSR2, 0)) handler_fail(8);
    }
    if (mode == 4) uc->uc_mcontext.__gregs[REG_A0] = 0x1234;
    if (mode == 5) {
        struct action old = {0};
        if (action(SIGUSR1, 0, &old) || old.handler != 0) handler_fail(9);
    }
    if (mode == 6) uc->uc_mcontext.__gregs[REG_SP] = 0;
    if (mode == 7) uc->uc_mcontext.__gregs[REG_PC] = 0;
    if (mode == 8) uc->uc_mcontext.__gregs[REG_TP] = desired_tp;
    if (mode == 9 && (uc->uc_mcontext.__fpregs.__d.__f[0] != UINT64_C(0x12345678abcdef01) ||
                      uc->uc_mcontext.__fpregs.__d.__fcsr != 0x41)) handler_fail(11);
    __asm__ volatile("fcvt.d.w ft0,zero; fscsr zero" ::: "ft0");
}
static int check(int condition, int code)
{
    if (condition && !failure) return 1;
    char text[] = "SIGNAL_RISCV_FAIL code=000 handler=00\n";
    size_t at = sizeof("SIGNAL_RISCV_FAIL code=") - 1;
    text[at] = '0' + code/100; text[at+1] = '0' + code/10%10; text[at+2] = '0' + code%10;
    at = sizeof("SIGNAL_RISCV_FAIL code=000 handler=") - 1;
    text[at] = '0' + failure/10; text[at+1] = '0' + failure%10;
    raw(SYS_write, 1, (long)text, sizeof(text)-1, 0);
    raw(SYS_exit_group, 1, 0, 0, 0);
    return 0;
}
int main(void)
{
    pid = raw(SYS_getpid,0,0,0,0); tid = raw(SYS_gettid,0,0,0,0);
    struct action a = {(uintptr_t)handler, SA_SIGINFO, {1ul << (SIGUSR2-1)}};
    struct action second = {(uintptr_t)handler, SA_SIGINFO, {0}};
    uint64_t one = UINT64_C(1) << (SIGUSR1-1), empty = 0;
    check(action(SIGUSR1,&a,0)==0 && action(SIGUSR2,&second,0)==0,101);
    errno=117;
    check(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==1 && errno==117,102);
    check(mask(SIG_BLOCK,&one,0)==0,103);
    check(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==1,104);
    check(mask(SIG_UNBLOCK,&one,0)==0 && handled==2,105);
    a.flags|=SA_NODEFER;mode=2;
    check(action(SIGUSR1,&a,0)==0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==3,106);
    a.flags&=~(uintptr_t)SA_NODEFER;mode=3;
    check(action(SIGUSR1,&a,0)==0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==4 && nested==1,107);
    mode=4;
    check(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0x1234 && handled==5,108);
    uint64_t fp_result=0;uint32_t fcsr_result=0;mode=9;
    check(signal_fp_probe(pid,tid,&fp_result,&fcsr_result)==0 && fp_result==UINT64_C(0x12345678abcdef01) &&
          fcsr_result==0x41 && handled==6,109);
    uintptr_t tp_result=0;desired_tp=(uintptr_t)&tp_storage[32];mode=8;
    check(signal_tp_probe(pid,tid,&tp_result)==0 && tp_result==desired_tp && handled==7 && errno==117,110);
    mode=5;a.flags|=SA_RESETHAND;
    check(action(SIGUSR1,&a,0)==0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==8,111);
    a.flags&=~(uintptr_t)SA_RESETHAND;
    check(action(SIGUSR1,&a,0)==0,112);
    for(int bad=6;bad<=7;++bad) {
        long child=raw(SYS_clone,SIGCHLD,0,0,0);
        check(child>=0,113);
        if(!child) {
            pid=raw(SYS_getpid,0,0,0,0);tid=raw(SYS_gettid,0,0,0,0);mode=bad;
            signal_bad_return_probe(pid,tid);raw(SYS_exit_group,99,0,0,0);
        }
        int status=0;
        // RV32's time64 ABI has waitid rather than wait4; pinned musl selects
        // that existing process syscall and converts its siginfo into status.
        check(waitpid((pid_t)child,&status,0)==child && (status&0x7f)==SIGSEGV,114);
    }
    check(mask(SIG_SETMASK,0,&empty)==0 && empty==0 && restorers==9,115);
    static const char success[] = "SIGNAL_RISCV_PASS " PROBE_ARCH " handler=8 nested=1 coalesced=1 nodefer=1 reset=1 registers=1 fp=1 fcsr=1 tp=1 restorer=9 corrupt_return=2\n";
    check(raw(SYS_write,1,(long)success,sizeof(success)-1,0)==sizeof(success)-1,116);
    return 0;
}

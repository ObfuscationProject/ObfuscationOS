#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <signal.h>
#include <ucontext.h>
#include <sys/syscall.h>
#include <unistd.h>

#if !defined(__i386__)
#error "This legacy/RT signal probe requires i386"
#endif
struct action { uint32_t handler, flags, restorer; uint64_t mask; };
_Static_assert(sizeof(struct action) == 20, "Linux i386 kernel sigaction");
struct context32 {
    uint32_t gs, fs, es, ds, edi, esi, ebp, esp, ebx, edx, ecx, eax;
    uint32_t trap, error, eip, cs, eflags, oldesp, ss, fp, oldmask, cr2;
};
_Static_assert(sizeof(struct context32) == 88, "Linux i386 sigcontext");
_Static_assert(offsetof(mcontext_t, fpregs) == offsetof(struct context32, fp), "musl FP offset");
_Static_assert(offsetof(ucontext_t, uc_mcontext) == 20, "musl RT context offset");
static volatile int handled, nested, failure, mode, realtime;
static long pid, tid;
static const uint64_t high_mask = UINT64_C(1) << 39;
uint32_t signal_fp_xmm, signal_fp_mxcsr;
uint64_t signal_fp_x87;

static long raw(long n, long a, long b, long c, long d)
{
    long result;
    __asm__ volatile("int $0x80" : "=a"(result) : "a"(n), "b"(a), "c"(b), "d"(c), "S"(d) : "memory", "cc");
    return result;
}
extern void restore_legacy(void), restore_rt(void), legacy_entry(void), signal_fp_probe(long, long), clobber_fp(void);
void legacy_handle(void *frame);
// The legacy restorer discards the signal argument before syscall 119. RT
// syscall 173 sees the stack immediately after the handler's return address.
__asm__(".text\n.global restore_legacy\n.type restore_legacy,@function\nrestore_legacy:\n"
        "pop %eax\nmov $119,%eax\nint $0x80\nud2\n.size restore_legacy,.-restore_legacy\n"
        ".global restore_rt\n.type restore_rt,@function\nrestore_rt:\n"
        "mov $173,%eax\nint $0x80\nud2\n.size restore_rt,.-restore_rt\n"
        ".global legacy_entry\n.type legacy_entry,@function\nlegacy_entry:\n"
        "mov %esp,%eax\nsub $8,%esp\npush %eax\ncall legacy_handle\nadd $12,%esp\nret\n"
        ".size legacy_entry,.-legacy_entry\n"
        ".global clobber_fp\n.type clobber_fp,@function\nclobber_fp:\n"
        "pxor %xmm0,%xmm0\nfldz\nret\n.size clobber_fp,.-clobber_fp\n"
        ".global signal_fp_probe\n.type signal_fp_probe,@function\nsignal_fp_probe:\n"
        "push %ebx\nmov 8(%esp),%ebx\nmov 12(%esp),%ecx\n"
        "fninit\nfld1\nmov $0x12345678,%eax\nmovd %eax,%xmm0\n"
        "sub $4,%esp\nmovl $0x1f80,(%esp)\nldmxcsr (%esp)\nadd $4,%esp\n"
        "mov $10,%edx\nmov $270,%eax\nint $0x80\n"
        "movd %xmm0,signal_fp_xmm\nfstpl signal_fp_x87\nstmxcsr signal_fp_mxcsr\n"
        "pop %ebx\nret\n.size signal_fp_probe,.-signal_fp_probe\n");

static long mask(int how, const uint64_t *set, uint64_t *old)
{
    return raw(SYS_rt_sigprocmask, how, (long)set, (long)old, 8);
}
static long action(int sig, struct action *set, struct action *old)
{
    return raw(SYS_rt_sigaction, sig, (long)set, (long)old, 8);
}
static void check(int condition, int code);
static void handler_fail(int code)
{
    failure = code;
    // Fatal-return children cannot propagate their private failure global.
    // Stop on the assertion before later frame access or deliberate corruption.
    if (mode == 6 || mode == 7) check(0, 136);
}
static void handle_context(int sig, struct context32 *sc, siginfo_t *info)
{
    uint64_t blocked = 0;
    if (sig != SIGUSR1 && sig != SIGUSR2) handler_fail(1);
    if (realtime && (!info || info->si_signo != sig || info->si_code != SI_TKILL || info->si_pid != pid)) handler_fail(2);
    if (mask(SIG_SETMASK, 0, &blocked) || !(blocked & high_mask)) handler_fail(3);
    if (sig == SIGUSR2) { ++nested; if (!(blocked & (UINT64_C(1) << (SIGUSR2-1)))) handler_fail(4); return; }
    ++handled;
    if (mode != 2 && !(blocked & (UINT64_C(1) << (SIGUSR1-1)))) handler_fail(5);
    if (mode == 2 && (blocked & (UINT64_C(1) << (SIGUSR1-1)))) handler_fail(6);
    if (!(blocked & (UINT64_C(1) << (SIGUSR2-1)))) handler_fail(7);
    if (mode == 3) {
        uint64_t second = UINT64_C(1) << (SIGUSR2-1);
        if (mask(SIG_UNBLOCK, &second, 0) || raw(SYS_tgkill,pid,tid,SIGUSR2,0)) handler_fail(8);
    }
    if (mode == 4) sc->eax = 0x1234;
    if (mode == 5) {
        struct action old = {0xa5a5a5a5, 0xa5a5a5a5, 0xa5a5a5a5, UINT64_C(0xa5a5a5a5a5a5a5a5)};
        if (action(SIGUSR1,0,&old) || old.handler != 0) handler_fail(9);
    }
    if (mode == 6) sc->eip = 0;
    if (mode == 7) sc->ss = 0;
    if (mode == 8) {
        unsigned char *fp = (void *)(uintptr_t)sc->fp;
        if (!fp) handler_fail(10);
        else {
            // Linux's old FSAVE prefix is authoritative for x87. Change ST0
            // from 1 to 2 while leaving the duplicate FXSAVE x87 slot at 1.
            fp[28+8] = 0; fp[28+9] = 0x40;
            *(uint32_t *)(fp + 272) = 0x76543210;
            *(uint32_t *)(fp + 136) = 0x3f80;
        }
    }
    clobber_fp();
}
void legacy_handle(void *frame)
{
    uint32_t *words = frame;
    handle_context((int)words[1], (struct context32 *)(words+2), 0);
}
static void rt_handle(int sig, siginfo_t *info, void *context)
{
    ucontext_t *uc = context;
    handle_context(sig, (struct context32 *)&uc->uc_mcontext, info);
}
static void check(int condition, int code)
{
    if (condition && !failure) return;
    char msg[] = "SIGNAL_I386_FAIL code=000 handler=00 rt=0\n";
    const size_t at = sizeof("SIGNAL_I386_FAIL code=")-1;
    const size_t bad = sizeof("SIGNAL_I386_FAIL code=000 handler=")-1;
    msg[at] = '0'+code/100; msg[at+1] = '0'+code/10%10; msg[at+2] = '0'+code%10;
    msg[bad] = '0'+failure/10; msg[bad+1] = '0'+failure%10;
    msg[sizeof(msg)-3] = '0'+realtime;
    raw(SYS_write,1,(long)msg,sizeof(msg)-1,0);
    raw(SYS_exit_group,1,0,0,0);
}
int main(void)
{
    pid = raw(SYS_getpid,0,0,0,0); tid = raw(SYS_gettid,0,0,0,0);
    for (realtime = 0; realtime < 2; ++realtime) {
        handled = nested = mode = 0;
        struct action a = {realtime ? (uint32_t)rt_handle : (uint32_t)legacy_entry,
            0x04000000u | (realtime ? 4u : 0u),
            (uint32_t)(realtime ? restore_rt : restore_legacy), UINT64_C(1) << (SIGUSR2-1)};
        struct action second = a; second.mask = 0;
        uint64_t one = UINT64_C(1) << (SIGUSR1-1), current = 0;
        check(mask(SIG_SETMASK,&high_mask,0) == 0,100);
        check(action(SIGUSR1,&a,0) == 0 && action(SIGUSR2,&second,0) == 0,101);
        errno = 117;
        check(raw(SYS_tgkill,pid,tid,SIGUSR1,0) == 0 && handled == 1 && errno == 117,102);
        check(mask(SIG_BLOCK,&one,0) == 0,103);
        check(raw(SYS_tgkill,pid,tid,SIGUSR1,0) == 0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0) == 0 && handled == 1,104);
        check(mask(SIG_UNBLOCK,&one,0) == 0 && handled == 2,105);
        mode = 2; a.flags |= 0x40000000u;
        check(action(SIGUSR1,&a,0) == 0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0) == 0 && handled == 3,106);
        mode = 3; a.flags &= ~0x40000000u;
        check(action(SIGUSR1,&a,0) == 0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0) == 0 && handled == 4 && nested == 1,107);
        mode = 4;
        check(raw(SYS_tgkill,pid,tid,SIGUSR1,0) == 0x1234 && handled == 5,108);
        mode = 0; signal_fp_probe(pid,tid);
        check(signal_fp_xmm == 0x12345678 && signal_fp_x87 == UINT64_C(0x3ff0000000000000) && signal_fp_mxcsr == 0x1f80 && handled == 6,109);
        mode = 8; signal_fp_probe(pid,tid);
        check(signal_fp_xmm == 0x76543210 && signal_fp_x87 == UINT64_C(0x4000000000000000) && signal_fp_mxcsr == 0x3f80 && handled == 7,110);
        mode = 5; a.flags |= 0x80000000u;
        check(action(SIGUSR1,&a,0) == 0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0) == 0 && handled == 8,111);
        a.flags &= ~0x80000000u;
        check(action(SIGUSR1,&a,0) == 0,112);
        for (int bad = 6; bad <= 7; ++bad) {
            long child = raw(SYS_fork,0,0,0,0);
            check(child >= 0,113);
            if (!child) {
                pid = raw(SYS_getpid,0,0,0,0); tid = raw(SYS_gettid,0,0,0,0); mode = bad;
                raw(SYS_tgkill,pid,tid,SIGUSR1,0); raw(SYS_exit_group,99,0,0,0);
            }
            int status = 0;
            check(raw(SYS_wait4,child,(long)&status,0,0) == child && (status & 0x7f) == SIGSEGV,114);
        }
        check(mask(SIG_SETMASK,0,&current) == 0 && current == high_mask,115);
    }
    uint64_t empty = 0;
    check(mask(SIG_SETMASK,&empty,0) == 0,116);
    static const char success[] = "SIGNAL_I386_PASS i386 legacy=1 rt=1 handler=16 nested=2 coalesced=2 nodefer=2 reset=2 registers=2 x87=2 xmm=2 mxcsr=2 edited_fp=2 high_mask=2 corrupt_return=4\n";
    check(raw(SYS_write,1,(long)success,sizeof(success)-1,0) == sizeof(success)-1,117);
    return 0;
}

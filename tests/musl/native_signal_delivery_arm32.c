#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <signal.h>
#include <ucontext.h>
#include <sys/syscall.h>
#include <unistd.h>

#if !defined(__arm__) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "This signal probe requires little-endian ARMv7 EABI"
#endif
// Kernel sigset_t has two 32-bit words; uint64_t would introduce ARM padding.
struct action { uint32_t handler, flags, restorer, mask[2]; };
struct vfp_context {
    uint32_t magic, size;
    uint64_t d[32];
    uint32_t fpscr, padding, fpexc, fpinst, fpinst2, tail_padding, end;
};
_Static_assert(sizeof(struct action) == 20, "Linux ARM kernel sigaction");
_Static_assert(offsetof(struct action, mask) == 12, "Kernel signal-mask offset");
_Static_assert(sizeof(ucontext_t) == 744, "Linux ARM ucontext");
_Static_assert(offsetof(ucontext_t, uc_mcontext) == 20, "ARM context offset");
_Static_assert(offsetof(ucontext_t, uc_sigmask) == 104, "ARM mask offset");
_Static_assert(offsetof(ucontext_t, uc_regspace) == 232, "ARM VFP extension");
_Static_assert(offsetof(mcontext_t, arm_r0) == 12, "ARM r0 offset");
_Static_assert(offsetof(mcontext_t, arm_pc) == 72, "ARM PC offset");
_Static_assert(offsetof(struct vfp_context, d) == 8, "VFP registers");
_Static_assert(offsetof(struct vfp_context, fpscr) == 264, "VFP FPSCR");
_Static_assert(offsetof(struct vfp_context, fpexc) == 272, "VFP FPEXC");
_Static_assert(offsetof(struct vfp_context, end) == 288, "VFP terminal magic");
static volatile int handled, nested, failure, mode, realtime, handler_thumb, restorer_thumb;
static volatile int interrupted_thumb = -1;
static long pid, tid;
static uint32_t expected_restorer, expected_flags;
static const uint64_t high_mask = UINT64_C(1) << 39;
uint32_t signal_entry_lr, signal_entry_kind, signal_restored[4], signal_fp_fpscr, signal_fp_r0;
_Alignas(8) uint64_t signal_fp_observed[4];
const _Alignas(8) uint64_t signal_fp_initial[4] = {
    UINT64_C(0x1122334455667788), UINT64_C(0x2233445566778899),
    UINT64_C(0x33445566778899aa), UINT64_C(0x445566778899aabb)
};
static const uint64_t edited[4] = {
    UINT64_C(0x8877665544332211), UINT64_C(0x9988776655443322),
    UINT64_C(0xaa99887766554433), UINT64_C(0xbbaa998877665544)
};
extern void entry_arm(void), entry_thumb(void);
extern void legacy_arm(void), legacy_thumb(void), rt_arm(void), rt_thumb(void);
extern long registers_arm(long, long), registers_thumb(long, long);
extern void fp_arm(long, long), fp_thumb(long, long), bad_return_arm(long, long);
static void check(int condition, int code);
static void handler_fail(int code)
{
    failure = code;
    // Fatal-return children cannot propagate their private failure global.
    // Stop on the assertion before later frame access or deliberate corruption.
    if (mode == 6 || mode == 7) check(0, 136);
}
void entry_common(int, siginfo_t *, void *, void *);

// Each actual ARM/Thumb entry forwards SP before any prologue. Saving LR across
// the C callback retains the independently selected interworking restorer.
#define HANDLER_BODY(kind) \
    "mov r3,sp\npush {r4,lr}\nldr r4,=signal_entry_lr\nstr lr,[r4]\n" \
    "ldr r4,=signal_entry_kind\nmov r12,#" #kind "\nstr r12,[r4]\n" \
    "bl entry_common\n" \
    "vmov.i32 d0,#0\nvmov.i32 d15,#0\nvmov.i32 d16,#0\nvmov.i32 d31,#0\n" \
    "mov r4,#0\nvmsr fpscr,r4\npop {r4,lr}\nbx lr\n"
#define RESTORER_BODY(number, offset) \
    "ldr r3,=signal_restored\nldr r2,[r3,#" #offset "]\nadd r2,r2,#1\n" \
    "str r2,[r3,#" #offset "]\nmov r7,#" #number "\nsvc #0\nudf #0\n"
#define REGISTERS_BODY \
    "push {r7,lr}\nmov r2,#10\nmovw r7,#268\nsvc #0\npop {r7,pc}\n"
// AAPCS D15 and the caller's FPSCR are saved around the ordinary C-call probe.
// Hardware observations occur before either is restored; r0 is recorded before
// any following instruction can replace the sigreturn-restored syscall result.
#define FP_BODY \
    "push {r4-r8,lr}\nvpush {d15}\nvmrs r8,fpscr\n" \
    "ldr r4,=signal_fp_initial\nvldr d0,[r4,#0]\nvldr d15,[r4,#8]\n" \
    "vldr d16,[r4,#16]\nvldr d31,[r4,#24]\nmov r4,#0x400000\nvmsr fpscr,r4\n" \
    "mov r2,#10\nmovw r7,#268\nsvc #0\n" \
    "ldr r4,=signal_fp_r0\nstr r0,[r4]\nldr r4,=signal_fp_observed\n" \
    "vstr d0,[r4,#0]\nvstr d15,[r4,#8]\nvstr d16,[r4,#16]\nvstr d31,[r4,#24]\n" \
    "vmrs r5,fpscr\nldr r4,=signal_fp_fpscr\nstr r5,[r4]\n" \
    "vmsr fpscr,r8\nvpop {d15}\npop {r4-r8,pc}\n"
__asm__(".syntax unified\n.fpu neon\n.text\n.arm\n.align 2\n"
        ".global entry_arm\n.type entry_arm,%function\nentry_arm:\n" HANDLER_BODY(0)
        ".size entry_arm,.-entry_arm\n"
        ".global legacy_arm\n.type legacy_arm,%function\nlegacy_arm:\n" RESTORER_BODY(119,0)
        ".size legacy_arm,.-legacy_arm\n"
        ".global rt_arm\n.type rt_arm,%function\nrt_arm:\n" RESTORER_BODY(173,8)
        ".size rt_arm,.-rt_arm\n"
        ".global registers_arm\n.type registers_arm,%function\nregisters_arm:\n" REGISTERS_BODY
        ".size registers_arm,.-registers_arm\n"
        ".global fp_arm\n.type fp_arm,%function\nfp_arm:\n" FP_BODY
        ".size fp_arm,.-fp_arm\n"
        // A missing bad-return corruption reaches this normal exit sentinel.
        ".global bad_return_arm\n.type bad_return_arm,%function\nbad_return_arm:\n"
        "mov r2,#10\nmovw r7,#268\nsvc #0\n"
        ".global bad_return_sentinel\nbad_return_sentinel:\n"
        "mov r0,#99\nmov r7,#1\nsvc #0\nudf #0\n"
        ".size bad_return_arm,.-bad_return_arm\n.ltorg\n"
        ".thumb\n.align 2\n"
        ".global entry_thumb\n.type entry_thumb,%function\n.thumb_func\nentry_thumb:\n" HANDLER_BODY(1)
        ".size entry_thumb,.-entry_thumb\n"
        ".global legacy_thumb\n.type legacy_thumb,%function\n.thumb_func\nlegacy_thumb:\n" RESTORER_BODY(119,4)
        ".size legacy_thumb,.-legacy_thumb\n"
        ".global rt_thumb\n.type rt_thumb,%function\n.thumb_func\nrt_thumb:\n" RESTORER_BODY(173,12)
        ".size rt_thumb,.-rt_thumb\n"
        ".global registers_thumb\n.type registers_thumb,%function\n.thumb_func\nregisters_thumb:\n" REGISTERS_BODY
        ".size registers_thumb,.-registers_thumb\n"
        ".global fp_thumb\n.type fp_thumb,%function\n.thumb_func\nfp_thumb:\n" FP_BODY
        ".size fp_thumb,.-fp_thumb\n.ltorg\n.arm\n.align 2\n");

static long raw(long number, long a, long b, long c, long d)
{
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r3 __asm__("r3") = d;
    register long r7 __asm__("r7") = number;
    __asm__ volatile("svc #0" : "+r"(r0) : "r"(r1), "r"(r2), "r"(r3), "r"(r7) : "memory", "cc");
    return r0;
}
static long mask(int how, const uint64_t *set, uint64_t *old)
{
    return raw(SYS_rt_sigprocmask, how, (long)set, (long)old, 8);
}
static long action(int sig, struct action *set, struct action *old)
{
    return raw(SYS_rt_sigaction, sig, (long)set, (long)old, 8);
}
void entry_common(int sig, siginfo_t *info, void *context, void *frame)
{
    ucontext_t *uc = realtime ? context : frame;
    if (((uintptr_t)frame & 7) || signal_entry_lr != expected_restorer || signal_entry_kind != (uint32_t)handler_thumb) handler_fail(1);
    if (realtime && ((void *)info != frame || (uintptr_t)context != (uintptr_t)frame+128 ||
        info->si_signo != sig || info->si_code != SI_TKILL || info->si_pid != pid)) handler_fail(2);
    if (!realtime && uc->uc_flags != 0x5ac3c35a) handler_fail(3);
    struct vfp_context *fp = (void *)uc->uc_regspace;
    if (fp->magic != 0x56465001 || fp->size != 288 || fp->fpexc != 0x40000000 || fp->end) handler_fail(4);
    if ((uc->uc_mcontext.arm_pc & 1) ||
        (interrupted_thumb >= 0 && !!(uc->uc_mcontext.arm_cpsr & 0x20) != interrupted_thumb)) handler_fail(5);
    if (errno != 117) handler_fail(6);
    uint64_t blocked = 0;
    if (mask(SIG_SETMASK,0,&blocked) || !(blocked & high_mask)) handler_fail(7);
    if (sig == SIGUSR2) {
        ++nested;
        if (!(blocked & (UINT64_C(1) << (SIGUSR2-1)))) handler_fail(8);
        return;
    }
    if (sig != SIGUSR1) handler_fail(9);
    ++handled;
    if (!!(blocked & (UINT64_C(1) << (SIGUSR1-1))) != (mode != 2)) handler_fail(10);
    if (!(blocked & (UINT64_C(1) << (SIGUSR2-1)))) handler_fail(11);
    if (mode == 3) {
        uint64_t second = UINT64_C(1) << (SIGUSR2-1);
        if (mask(SIG_UNBLOCK,&second,0) || raw(SYS_tgkill,pid,tid,SIGUSR2,0)) handler_fail(12);
    }
    if (mode == 4) uc->uc_mcontext.arm_r0 = 0x1234;
    if (mode == 5) {
        struct action old = {0xa5a5a5a5,0xa5a5a5a5,0xa5a5a5a5,{0xa5a5a5a5,0xa5a5a5a5}};
        if (action(SIGUSR1,0,&old) || old.handler || old.flags != expected_flags || old.restorer != expected_restorer ||
            old.mask[0] != (1u << (SIGUSR2-1)) || old.mask[1]) handler_fail(13);
    }
    if (mode == 6) uc->uc_mcontext.arm_pc = 0;
    if (mode == 7) fp->magic = 0;
    if (mode == 8 || mode == 9) {
        if (fp->d[0] != signal_fp_initial[0] || fp->d[15] != signal_fp_initial[1] ||
            fp->d[16] != signal_fp_initial[2] || fp->d[31] != signal_fp_initial[3] || fp->fpscr != 0x400000) handler_fail(14);
        if (mode == 9) {
            fp->d[0] = edited[0]; fp->d[15] = edited[1]; fp->d[16] = edited[2]; fp->d[31] = edited[3];
            fp->fpscr = 0x800000;
            uc->uc_mcontext.arm_r0 = 0x5678;
        }
    }
}
static void check(int condition, int code)
{
    if (condition && !failure) return;
    char msg[] = "SIGNAL_ARM32_FAIL code=000 handler=00 rt=0 h=0 r=0\n";
    const size_t at = sizeof("SIGNAL_ARM32_FAIL code=")-1;
    const size_t bad = sizeof("SIGNAL_ARM32_FAIL code=000 handler=")-1;
    msg[at] = '0'+code/100; msg[at+1] = '0'+code/10%10; msg[at+2] = '0'+code%10;
    msg[bad] = '0'+failure/10; msg[bad+1] = '0'+failure%10;
    msg[sizeof(msg)-11] = '0'+realtime; msg[sizeof(msg)-7] = '0'+handler_thumb; msg[sizeof(msg)-3] = '0'+restorer_thumb;
    raw(SYS_write,1,(long)msg,sizeof(msg)-1,0);
    raw(SYS_exit_group,1,0,0,0);
}
int main(void)
{
    pid = raw(SYS_getpid,0,0,0,0); tid = raw(SYS_gettid,0,0,0,0);
    for (realtime=0;realtime!=2;++realtime) for (handler_thumb=0;handler_thumb!=2;++handler_thumb) for (restorer_thumb=0;restorer_thumb!=2;++restorer_thumb) {
        handled = nested = mode = 0; interrupted_thumb = -1;
        expected_restorer = (uintptr_t)(realtime ? (restorer_thumb ? rt_thumb : rt_arm) : (restorer_thumb ? legacy_thumb : legacy_arm));
        expected_flags = SA_RESTORER | (realtime ? SA_SIGINFO : 0);
        struct action a = {(uintptr_t)(handler_thumb ? entry_thumb : entry_arm),expected_flags,expected_restorer,{1u << (SIGUSR2-1),0}};
        struct action second = a; second.mask[0] = 0;
        uint64_t one = UINT64_C(1) << (SIGUSR1-1), current = 0;
        const unsigned restorer_index = realtime*2+restorer_thumb;
        signal_restored[restorer_index] = 0;
        check((a.handler & 1) == (unsigned)handler_thumb && (a.restorer & 1) == (unsigned)restorer_thumb,100);
        check(mask(SIG_SETMASK,&high_mask,0) == 0,101);
        check(action(SIGUSR1,&a,0) == 0 && action(SIGUSR2,&second,0) == 0,102);
        errno = 117;
        check(raw(SYS_tgkill,pid,tid,SIGUSR1,0) == 0 && handled == 1 && errno == 117,103);
        check(mask(SIG_BLOCK,&one,0) == 0,104);
        check(raw(SYS_tgkill,pid,tid,SIGUSR1,0) == 0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0) == 0 && handled == 1,105);
        check(mask(SIG_UNBLOCK,&one,0) == 0 && handled == 2,106);
        mode = 2; a.flags |= SA_NODEFER;
        check(action(SIGUSR1,&a,0) == 0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0) == 0 && handled == 3,107);
        mode = 3; a.flags &= ~SA_NODEFER;
        check(action(SIGUSR1,&a,0) == 0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0) == 0 && handled == 4 && nested == 1,108);
        mode = 4; interrupted_thumb = 0;
        check(registers_arm(pid,tid) == 0x1234 && handled == 5,109);
        interrupted_thumb = 1;
        check(registers_thumb(pid,tid) == 0x1234 && handled == 6,110);
        for (mode=8;mode!=10;++mode) for (interrupted_thumb=0;interrupted_thumb!=2;++interrupted_thumb) {
            if (interrupted_thumb) fp_thumb(pid,tid); else fp_arm(pid,tid);
            const uint64_t *expected = mode == 9 ? edited : signal_fp_initial;
            check(signal_fp_observed[0] == expected[0] && signal_fp_observed[1] == expected[1] &&
                  signal_fp_observed[2] == expected[2] && signal_fp_observed[3] == expected[3] &&
                  signal_fp_fpscr == (mode == 9 ? 0x800000u : 0x400000u) && signal_fp_r0 == (mode == 9 ? 0x5678u : 0),111);
        }
        check(handled == 10,112);
        interrupted_thumb = -1; mode = 5; a.flags |= SA_RESETHAND; expected_flags = a.flags;
        check(action(SIGUSR1,&a,0) == 0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0) == 0 && handled == 11,113);
        check(signal_restored[restorer_index] == 12,114);
        a.flags &= ~SA_RESETHAND;
        check(action(SIGUSR1,&a,0) == 0,115);
        if (!handler_thumb && !restorer_thumb) for (int bad=6;bad!=8;++bad) {
            long child = raw(SYS_fork,0,0,0,0);
            check(child >= 0,116);
            if (!child) {
                pid = raw(SYS_getpid,0,0,0,0); tid = raw(SYS_gettid,0,0,0,0); mode = bad;
                bad_return_arm(pid,tid); raw(SYS_exit_group,98,0,0,0);
            }
            int status = 0;
            check(raw(SYS_wait4,child,(long)&status,0,0) == child && (status & 0x7f) == SIGSEGV,117);
        }
        check(mask(SIG_SETMASK,0,&current) == 0 && current == high_mask,118);
    }
    uint64_t empty = 0;
    check(mask(SIG_SETMASK,&empty,0) == 0,119);
    static const char success[] = "SIGNAL_ARM32_PASS arm32 legacy=4 rt=4 combinations=8 handlers=88 nested=8 coalesced=8 nodefer=8 reset=8 registers=16 fp=16 edited_fp=16 d32=1 fpscr=1 arm_thumb=1 restorers=96 high_mask=8 corrupt_return=4\n";
    check(raw(SYS_write,1,(long)success,sizeof(success)-1,0) == sizeof(success)-1,120);
    return 0;
}

#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <signal.h>
#include <ucontext.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

#if !defined(__loongarch64) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error "This scalar-FPU signal probe requires little-endian LoongArch64 LP64D"
#endif
#ifdef SA_RESTORER
#error "LoongArch Linux kernel actions do not contain a restorer member"
#endif
#define PROBE_ARCH "loongarch64"
struct action { uintptr_t handler, flags; uint64_t mask; };
struct fp_context {
    uint32_t magic, size; uint64_t header_padding;
    uint64_t f[32]; uint8_t fcc[8]; uint32_t fcsr, padding;
    uint32_t end_magic, end_size; uint64_t end_padding;
};
_Static_assert(sizeof(struct action) == 24, "Linux kernel sigaction copy length");
_Static_assert(offsetof(struct action, mask) == 16, "Linux action mask offset");
_Static_assert(offsetof(ucontext_t, uc_sigmask) == 40, "Linux signal mask offset");
_Static_assert(offsetof(ucontext_t, uc_mcontext) == 176, "Linux machine context offset");
_Static_assert(offsetof(mcontext_t, __gregs) == 8, "Linux general registers");
_Static_assert(offsetof(mcontext_t, __extcontext) == 272, "Linux extension offset");
_Static_assert(offsetof(struct fp_context, f) == 16, "FPU extension header");
_Static_assert(offsetof(struct fp_context, fcc) == 272, "FCC byte lanes");
_Static_assert(offsetof(struct fp_context, fcsr) == 280, "FCSR offset");
_Static_assert(offsetof(struct fp_context, end_magic) == 288, "Terminal extension");
_Static_assert(SYS_tgkill == 131 && SYS_rt_sigreturn == 139, "Assembly syscall numbers");

enum { ORDINARY=0, NODEFER=2, NESTED=3, REGISTERS=4, RESET=5,
       TP_EDIT=8, FP_KEEP=9, FP_EDIT=10, FCSR_PENDING=20, FCSR_COALESCED=21,
       FCSR_BLOCKED=22, FCSR_IGNORED=23, BAD_SP=30, BAD_PC=31,
       BAD_MAGIC=32, BAD_SIZE=33 };
static volatile int handled, nested, failure, mode, restorers, fpe_count;
static long pid, tid, uid;
static uintptr_t expected_flags, first_restorer;
static const uint64_t high_mask = UINT64_C(1) << 39;
static _Alignas(16) unsigned char tp_storage[64], fpe_stack[32768];
static volatile uintptr_t desired_tp, original_frame;
static volatile uint32_t *original_fcsr;
volatile uint32_t pending_phase;
volatile uint64_t observed_r4;
volatile uint32_t observed_fcsr;
volatile uint8_t observed_fcc[8];
_Alignas(16) volatile uint64_t observed_fp[32];
// Distinct finite bit patterns keep FP operations out of the observation path.
const _Alignas(16) uint64_t initial_fp[32] = {
    0x3f00112233445500ULL,0x3f00112233445501ULL,0x3f00112233445502ULL,0x3f00112233445503ULL,
    0x3f00112233445504ULL,0x3f00112233445505ULL,0x3f00112233445506ULL,0x3f00112233445507ULL,
    0x3f00112233445508ULL,0x3f00112233445509ULL,0x3f0011223344550aULL,0x3f0011223344550bULL,
    0x3f0011223344550cULL,0x3f0011223344550dULL,0x3f0011223344550eULL,0x3f0011223344550fULL,
    0x3f00112233445510ULL,0x3f00112233445511ULL,0x3f00112233445512ULL,0x3f00112233445513ULL,
    0x3f00112233445514ULL,0x3f00112233445515ULL,0x3f00112233445516ULL,0x3f00112233445517ULL,
    0x3f00112233445518ULL,0x3f00112233445519ULL,0x3f0011223344551aULL,0x3f0011223344551bULL,
    0x3f0011223344551cULL,0x3f0011223344551dULL,0x3f0011223344551eULL,0x3f0011223344551fULL
};
const uint8_t initial_fcc[8] = {1,0,1,0,0,1,0,1};
// Every low bit changes: no FCC lane can pass by staying at the clobbered zero.
static const uint8_t edited_fcc[8] = {0xfe,0xff,0xa0,0xa1,0x83,0x82,0x05,0x04};
static const uint32_t pending_value = 0x03050201, cleared_value = 0x02050201;
extern void signal_entry(void), signal_fp_probe(long, long), signal_pending_probe(long, long);
extern long signal_tp_probe(long, long, uintptr_t *);
extern void signal_bad_return_probe(long, long), pending_resume(void);
extern const uint32_t reference_trampoline[4];
void entry_common(int, siginfo_t *, void *, void *, uintptr_t);

#define FP32(OP) \
    OP(0,0) OP(1,8) OP(2,16) OP(3,24) OP(4,32) OP(5,40) OP(6,48) OP(7,56) \
    OP(8,64) OP(9,72) OP(10,80) OP(11,88) OP(12,96) OP(13,104) OP(14,112) OP(15,120) \
    OP(16,128) OP(17,136) OP(18,144) OP(19,152) OP(20,160) OP(21,168) OP(22,176) OP(23,184) \
    OP(24,192) OP(25,200) OP(26,208) OP(27,216) OP(28,224) OP(29,232) OP(30,240) OP(31,248)
#define FP_LOAD(N,O) "fld.d $f" #N ",$t0," #O "\n"
#define FP_STORE(N,O) "fst.d $f" #N ",$t0," #O "\n"
#define FP_ZERO(N,O) "movgr2fr.d $f" #N ",$zero\n"
#define FCC8(OP) OP(0) OP(1) OP(2) OP(3) OP(4) OP(5) OP(6) OP(7)
#define FCC_LOAD(N) "ld.bu $t1,$t0," #N "\nmovgr2cf $fcc" #N ",$t1\n"
#define FCC_STORE(N) "movcf2gr $t1,$fcc" #N "\nst.b $t1,$t0," #N "\n"
#define FCC_ZERO(N) "movgr2cf $fcc" #N ",$zero\n"
// These leaf wrappers retain the ABI's callee-saved f24-f31 and the caller's
// control state. Actual return observations precede restoration to the C caller.
#define SAVE_CALLER \
    "addi.d $sp,$sp,-96\nst.d $ra,$sp,80\n" \
    "fst.d $f24,$sp,0\nfst.d $f25,$sp,8\nfst.d $f26,$sp,16\nfst.d $f27,$sp,24\n" \
    "fst.d $f28,$sp,32\nfst.d $f29,$sp,40\nfst.d $f30,$sp,48\nfst.d $f31,$sp,56\n" \
    "movfcsr2gr $t1,$fcsr0\nst.w $t1,$sp,64\naddi.d $t0,$sp,72\n" FCC8(FCC_STORE)
#define RESTORE_CALLER \
    "ld.w $t1,$sp,64\nmovgr2fcsr $fcsr0,$t1\naddi.d $t0,$sp,72\n" FCC8(FCC_LOAD) \
    "fld.d $f24,$sp,0\nfld.d $f25,$sp,8\nfld.d $f26,$sp,16\nfld.d $f27,$sp,24\n" \
    "fld.d $f28,$sp,32\nfld.d $f29,$sp,40\nfld.d $f30,$sp,48\nfld.d $f31,$sp,56\n" \
    "ld.d $ra,$sp,80\naddi.d $sp,$sp,96\njr $ra\n"
#define OBSERVE_CONTROL \
    "la.local $t0,observed_r4\nst.d $a0,$t0,0\n" \
    "movfcsr2gr $t1,$fcsr0\nla.local $t0,observed_fcsr\nst.w $t1,$t0,0\n"
__asm__(".text\n.balign 4\n.global signal_entry\n.type signal_entry,@function\nsignal_entry:\n"
        "move $a3,$sp\nmove $a4,$ra\naddi.d $sp,$sp,-16\nst.d $ra,$sp,0\nbl entry_common\n"
        // Clobber after C returns: all hardware FP state must come from sigreturn.
        FP32(FP_ZERO) FCC8(FCC_ZERO) "movgr2fcsr $fcsr0,$zero\n"
        "ld.d $ra,$sp,0\naddi.d $sp,$sp,16\njr $ra\n.size signal_entry,.-signal_entry\n"
        ".balign 4\n.global signal_fp_probe\n.type signal_fp_probe,@function\nsignal_fp_probe:\n"
        SAVE_CALLER "la.local $t0,initial_fp\n" FP32(FP_LOAD)
        "la.local $t0,initial_fcc\n" FCC8(FCC_LOAD)
        "li.w $t1,0x10200\nmovgr2fcsr $fcsr0,$t1\nli.w $a2,10\nli.w $a7,131\nsyscall 0\n"
        OBSERVE_CONTROL "la.local $t0,observed_fp\n" FP32(FP_STORE)
        "la.local $t0,observed_fcc\n" FCC8(FCC_STORE) RESTORE_CALLER
        ".size signal_fp_probe,.-signal_fp_probe\n"
        ".balign 4\n.global signal_tp_probe\n.type signal_tp_probe,@function\nsignal_tp_probe:\n"
        "addi.d $sp,$sp,-32\nst.d $ra,$sp,0\nst.d $tp,$sp,8\nst.d $a2,$sp,16\n"
        "li.w $a2,10\nli.w $a7,131\nsyscall 0\nld.d $t0,$sp,16\nst.d $tp,$t0,0\n"
        // Never execute C, TLS access, or errno with the deliberately fake TP.
        "ld.d $tp,$sp,8\nld.d $ra,$sp,0\naddi.d $sp,$sp,32\njr $ra\n"
        ".size signal_tp_probe,.-signal_tp_probe\n"
        ".balign 4\n.global signal_pending_probe\n.type signal_pending_probe,@function\nsignal_pending_probe:\n"
        SAVE_CALLER "li.w $a2,10\nli.w $a7,131\nsyscall 0\n"
        ".global pending_resume\npending_resume:\n"
        "la.local $t0,pending_phase\nli.w $t1,1\nst.w $t1,$t0,0\n"
        OBSERVE_CONTROL RESTORE_CALLER ".size signal_pending_probe,.-signal_pending_probe\n"
        ".balign 4\n.global signal_bad_return_probe\n.type signal_bad_return_probe,@function\nsignal_bad_return_probe:\n"
        "addi.d $sp,$sp,-16\nst.d $ra,$sp,0\nli.w $a2,10\nli.w $a7,131\nsyscall 0\n"
        // Touch restored SP before the sentinel: SP=0 cannot pass on an exit alone.
        "ld.d $ra,$sp,0\nli.w $a0,99\nli.w $a7,94\nsyscall 0\nbreak 0\n"
        ".size signal_bad_return_probe,.-signal_bad_return_probe\n"
        // Both ORI/li.w and ADDI.W load the same positive syscall139. These
        // assembler-derived byte oracles are never installed as restorers.
        ".section .rodata\n.balign 4\n.global reference_trampoline\nreference_trampoline:\n"
        "li.w $a7,139\nsyscall 0\naddi.w $a7,$zero,139\nsyscall 0\n.text\n");

static long raw(long number, long a, long b, long c, long d)
{
    register long a7 __asm__("$a7") = number;
    register long a0 __asm__("$a0") = a;
    register long a1 __asm__("$a1") = b;
    register long a2 __asm__("$a2") = c;
    register long a3 __asm__("$a3") = d;
    __asm__ volatile("syscall 0" : "+r"(a0) : "r"(a7), "r"(a1), "r"(a2), "r"(a3)
                     : "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7", "$t8", "memory");
    return a0;
}
static long mask(int how, const uint64_t *set, uint64_t *old)
{
    return raw(SYS_rt_sigprocmask,how,(long)set,(long)old,8);
}
static long action(int sig, const struct action *set, struct action *old)
{
    return raw(SYS_rt_sigaction,sig,(long)set,(long)old,8);
}
static uint64_t edited_fp(unsigned i) { return initial_fp[i] ^ UINT64_C(0x0077665544332200); }
static void check(int condition, int code);
static void fail(int code)
{
    if (!failure) failure = code;
    // A child-local assertion must not disappear behind an expected fatal
    // signal. The existing diagnostic uses raw write/exit_group, without TLS.
    if ((mode >= BAD_SP && mode <= BAD_SIZE) || mode == FCSR_BLOCKED || mode == FCSR_IGNORED)
        check(0, 136);
}
void entry_common(int sig, siginfo_t *info, void *context, void *frame, uintptr_t ra)
{
    ucontext_t *uc = context;
    struct fp_context *fp = (void *)uc->uc_mcontext.__extcontext;
    uint64_t blocked = 0;
    if (((uintptr_t)frame & 15) || (void *)info != frame || (uintptr_t)context != (uintptr_t)frame+128) fail(1);
    const volatile uint32_t *trampoline = (const volatile uint32_t *)ra;
    if (!ra || (ra & 3) || ra == (uintptr_t)reference_trampoline || ra == (uintptr_t)(reference_trampoline+2) ||
        (trampoline[0] != reference_trampoline[0] && trampoline[0] != reference_trampoline[2]) ||
        trampoline[1] != reference_trampoline[1]) fail(2);
    if (!first_restorer) first_restorer = ra;
    else if (ra != first_restorer) fail(3);
    ++restorers;
    if (info->si_signo != sig || info->si_errno ||
        (sig != SIGFPE && (info->si_code != SI_TKILL || info->si_pid != pid || info->si_uid != uid))) fail(4);
    if ((uc->uc_mcontext.__pc & 3) || uc->uc_mcontext.__gregs[0] ||
        !(uc->uc_mcontext.__flags & 1)) fail(5);
    if (fp->magic != 0x46505501 || fp->size != 288 || fp->end_magic || fp->end_size) fail(6);
    if (errno != 117) fail(7);
    if (mask(SIG_SETMASK,0,&blocked) || !(blocked & high_mask)) fail(8);
    if (sig == SIGFPE) {
        ++fpe_count;
        if (mode == FCSR_BLOCKED || mode == FCSR_IGNORED) raw(SYS_exit_group,97,0,0,0);
        if (mode != FCSR_PENDING && mode != FCSR_COALESCED) fail(20);
        if (pending_phase || uc->uc_mcontext.__pc != (uintptr_t)pending_resume) fail(21);
        if ((uintptr_t)frame < (uintptr_t)fpe_stack ||
            (uintptr_t)frame+880 > (uintptr_t)fpe_stack+sizeof(fpe_stack) ||
            ((uintptr_t)frame < original_frame+880 && original_frame < (uintptr_t)frame+880)) fail(22);
        // This original normal-stack frame cannot be overwritten by SIGFPE's
        // alternate-stack frame. Clearing must be a real user-frame writeback.
        if (!original_fcsr || *original_fcsr != cleared_value || fp->fcsr != cleared_value) fail(23);
        if (!(blocked & (UINT64_C(1) << (SIGFPE-1)))) fail(24);
        if (mode == FCSR_PENDING) {
            if (info->si_code != 128) fail(25);
            const unsigned char *bytes = (const unsigned char *)info;
            for (unsigned i=12;i<128;++i) if (bytes[i]) fail(26);
        } else if (info->si_code != SI_TKILL || info->si_pid != pid || info->si_uid != uid) fail(27);
        fp->fcsr = 0;
        uc->uc_mcontext.__gregs[4] = 0x9abc;
        return;
    }
    if (sig == SIGUSR2) {
        ++nested;
        if (!(blocked & (UINT64_C(1) << (SIGUSR1-1))) || !(blocked & (UINT64_C(1) << (SIGUSR2-1)))) fail(9);
        return;
    }
    if (sig != SIGUSR1) fail(10);
    ++handled;
    if (!!(blocked & (UINT64_C(1) << (SIGUSR1-1))) != (mode != NODEFER)) fail(11);
    if (!(blocked & (UINT64_C(1) << (SIGUSR2-1)))) fail(12);
    if (mode == NESTED) {
        uint64_t second = UINT64_C(1) << (SIGUSR2-1);
        if (mask(SIG_UNBLOCK,&second,0) || raw(SYS_tgkill,pid,tid,SIGUSR2,0)) fail(13);
    }
    if (mode == REGISTERS) uc->uc_mcontext.__gregs[4] = 0x1234;
    if (mode == TP_EDIT) uc->uc_mcontext.__gregs[2] = desired_tp;
    if (mode == RESET) {
        struct action old = {UINT64_C(0xa5a5a5a5a5a5a5a5),UINT64_C(0xa5a5a5a5a5a5a5a5),UINT64_C(0xa5a5a5a5a5a5a5a5)};
        if (action(SIGUSR1,0,&old) || old.handler || old.flags != expected_flags ||
            old.mask != (UINT64_C(1) << (SIGUSR2-1))) fail(14);
    }
    if (mode == FP_KEEP || mode == FP_EDIT) {
        for (unsigned i=0;i<32;++i) if (fp->f[i] != initial_fp[i]) fail(15);
        for (unsigned i=0;i<8;++i) if (fp->fcc[i] != initial_fcc[i]) fail(16);
        if (fp->fcsr != 0x10200) fail(17);
        if (mode == FP_EDIT) {
            for (unsigned i=0;i<32;++i) fp->f[i] = edited_fp(i);
            for (unsigned i=0;i<8;++i) fp->fcc[i] = edited_fcc[i];
            fp->fcsr = 0xa0100;
            uc->uc_mcontext.__gregs[4] = 0x5678;
        }
    }
    if (mode >= FCSR_PENDING && mode <= FCSR_IGNORED) {
        original_frame = (uintptr_t)frame;
        original_fcsr = &fp->fcsr;
        if (mode == FCSR_COALESCED && raw(SYS_tgkill,pid,tid,SIGFPE,0)) fail(28);
        fp->fcsr = pending_value;
    }
    if (mode == BAD_SP) uc->uc_mcontext.__gregs[3] = 0;
    if (mode == BAD_PC) uc->uc_mcontext.__pc = 0;
    if (mode == BAD_MAGIC) fp->magic = 0xdeadbeef;
    if (mode == BAD_SIZE) fp->size = 16;
}
static void check(int condition, int code)
{
    if (condition && !failure) return;
    char msg[] = "SIGNAL_LOONGARCH64_FAIL code=000 handler=00 mode=00\n";
    const size_t at=sizeof("SIGNAL_LOONGARCH64_FAIL code=")-1;
    const size_t h=sizeof("SIGNAL_LOONGARCH64_FAIL code=000 handler=")-1;
    const size_t m=sizeof("SIGNAL_LOONGARCH64_FAIL code=000 handler=00 mode=")-1;
    msg[at]='0'+code/100;msg[at+1]='0'+code/10%10;msg[at+2]='0'+code%10;
    msg[h]='0'+failure/10;msg[h+1]='0'+failure%10;
    msg[m]='0'+mode/10;msg[m+1]='0'+mode%10;
    raw(SYS_write,1,(long)msg,sizeof(msg)-1,0);
    raw(SYS_exit_group,1,0,0,0);
}
static void check_fp(int edited, int code)
{
    check(observed_r4 == (edited ? 0x5678 : 0) && observed_fcsr == (edited ? 0xa0100 : 0x10200),code);
    for (unsigned i=0;i<32;++i) check(observed_fp[i] == (edited ? edited_fp(i) : initial_fp[i]),code+1);
    for (unsigned i=0;i<8;++i) check(observed_fcc[i] == (edited ? (edited_fcc[i]&1) : initial_fcc[i]),code+2);
}
int main(void)
{
    pid=raw(SYS_getpid,0,0,0,0);tid=raw(SYS_gettid,0,0,0,0);uid=raw(SYS_getuid,0,0,0,0);
    errno=117;
    struct action a={(uintptr_t)signal_entry,SA_SIGINFO,UINT64_C(1)<<(SIGUSR2-1)};
    struct action second={(uintptr_t)signal_entry,SA_SIGINFO,0};
    uint64_t one=UINT64_C(1)<<(SIGUSR1-1),current=0,empty=0;
    check(mask(SIG_SETMASK,&high_mask,0)==0 && action(SIGUSR2,&second,0)==0,101);
    // Linux always supplies the frame/info/context arguments, even without SA_SIGINFO.
    for (unsigned siginfo=0;siginfo<2;++siginfo) {
        a.flags=siginfo ? SA_SIGINFO : 0;mode=ORDINARY;
        int base=handled,base_nested=nested;
        check(action(SIGUSR1,&a,0)==0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==base+1 && errno==117,102);
        check(mask(SIG_BLOCK,&one,0)==0,103);
        check(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==base+1,104);
        check(mask(SIG_UNBLOCK,&one,0)==0 && handled==base+2,105);
        a.flags|=SA_NODEFER;mode=NODEFER;
        check(action(SIGUSR1,&a,0)==0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==base+3,106);
        a.flags&=~(uintptr_t)SA_NODEFER;mode=NESTED;
        check(action(SIGUSR1,&a,0)==0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==base+4 && nested==base_nested+1,107);
        mode=REGISTERS;
        check(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0x1234 && handled==base+5,108);
        mode=FP_KEEP;signal_fp_probe(pid,tid);check_fp(0,109);
        mode=FP_EDIT;signal_fp_probe(pid,tid);check_fp(1,112);
        uintptr_t actual_tp=0;desired_tp=(uintptr_t)&tp_storage[32];mode=TP_EDIT;
        check(signal_tp_probe(pid,tid,&actual_tp)==0 && actual_tp==desired_tp && handled==base+8 && errno==117,115);
        a.flags|=SA_RESETHAND;expected_flags=a.flags;mode=RESET;
        check(action(SIGUSR1,&a,0)==0 && raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==base+9,116);
        check(mask(SIG_SETMASK,0,&current)==0 && current==high_mask,117);
    }
    a.flags=SA_SIGINFO;
    check(action(SIGUSR1,&a,0)==0,118);
    for (int bad=BAD_SP;bad<=BAD_SIZE;++bad) {
        long child=raw(SYS_clone,SIGCHLD,0,0,0);
        check(child>=0,119);
        if (!child) {
            pid=raw(SYS_getpid,0,0,0,0);tid=raw(SYS_gettid,0,0,0,0);mode=bad;
            signal_bad_return_probe(pid,tid);raw(SYS_exit_group,98,0,0,0);
        }
        int status=0;
        check(waitpid((pid_t)child,&status,0)==child && WIFSIGNALED(status) && WTERMSIG(status)==SIGSEGV,120);
    }
    stack_t stack={.ss_sp=fpe_stack,.ss_flags=0,.ss_size=sizeof(fpe_stack)};
    struct action fpe={(uintptr_t)signal_entry,SA_SIGINFO|SA_ONSTACK,0};
    a.mask|=UINT64_C(1)<<(SIGFPE-1);
    check(raw(SYS_sigaltstack,(long)&stack,0,0,0)==0 && action(SIGUSR1,&a,0)==0 && action(SIGFPE,&fpe,0)==0,121);
    for (int pending=FCSR_PENDING;pending<=FCSR_COALESCED;++pending) {
        mode=pending;pending_phase=0;int before=fpe_count;
        signal_pending_probe(pid,tid);
        check(pending_phase==1 && fpe_count==before+1 && observed_r4==0x9abc && observed_fcsr==0,122);
        check(mask(SIG_SETMASK,0,&current)==0 && current==high_mask,123);
    }
    for (int forced=FCSR_BLOCKED;forced<=FCSR_IGNORED;++forced) {
        long child=raw(SYS_clone,SIGCHLD,0,0,0);
        check(child>=0,124);
        if (!child) {
            pid=raw(SYS_getpid,0,0,0,0);tid=raw(SYS_gettid,0,0,0,0);mode=forced;pending_phase=0;
            if (mode==FCSR_BLOCKED) {
                uint64_t bit=UINT64_C(1)<<(SIGFPE-1);check(mask(SIG_BLOCK,&bit,0)==0,125);
            } else {
                fpe.handler=(uintptr_t)SIG_IGN;check(action(SIGFPE,&fpe,0)==0,126);
            }
            signal_pending_probe(pid,tid);raw(SYS_exit_group,99,0,0,0);
        }
        int status=0;
        check(waitpid((pid_t)child,&status,0)==child && WIFSIGNALED(status) && WTERMSIG(status)==SIGFPE,127);
    }
    check(handled==20 && nested==2 && fpe_count==2 && restorers==24,128);
    check(mask(SIG_SETMASK,&empty,0)==0 && errno==117,129);
    static const char success[]="SIGNAL_LOONGARCH64_PASS " PROBE_ARCH " handlers=20 nested=2 coalesced=2 nodefer=2 reset=2 registers=4 fp=4 edited_fp=2 f32=1 fcc8=1 fcsr=1 tp=2 restorers=24 high_mask=2 corrupt_return=4 pending_fcsr=2 fcsr_writeback=2 sigfpe_before_resume=2 si_kernel=1 forced_default=2 preserved_payload=1\n";
    check(raw(SYS_write,1,(long)success,sizeof(success)-1,0)==sizeof(success)-1,130);
    return 0;
}

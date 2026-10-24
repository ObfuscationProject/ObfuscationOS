#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <signal.h>
#include <ucontext.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

#if !defined(__mips64) || !defined(_ABI64) || _MIPS_SIM != _ABI64 || !defined(__MIPSEB__) || __mips_fpr != 64 || __mips_isa_rev != 2
#error "This probe requires native big-endian MIPS64r2 n64 FR1 with legacy NaNs"
#endif
#ifdef SA_RESTORER
#error "Native MIPS Linux actions have no restorer field"
#endif
struct mask128 { uint64_t word[2]; };
struct action { uint32_t flags; uintptr_t handler; struct mask128 mask; };
_Static_assert(sizeof(struct action)==32 && offsetof(struct action,handler)==8 && offsetof(struct action,mask)==16,"n64 action wire");
_Static_assert(sizeof(struct mask128)==16 && sizeof(uintptr_t)==8,"n64 mask and pointer");
_Static_assert(sizeof(mcontext_t)==600 && offsetof(mcontext_t,gregs)==0,"n64 scalar context");
_Static_assert(offsetof(mcontext_t,fpregs)==256 && offsetof(mcontext_t,fpc_csr)==584,"n64 FR1 context");
_Static_assert(offsetof(mcontext_t,used_math)==588 && offsetof(mcontext_t,mdhi)==512 && offsetof(mcontext_t,mdlo)==544,"n64 mode and HI/LO");
_Static_assert(offsetof(mcontext_t,pc)==576 && offsetof(mcontext_t,dsp)==592 && offsetof(mcontext_t,reserved)==596,"n64 tail");
_Static_assert(offsetof(ucontext_t,uc_mcontext)==40 && offsetof(ucontext_t,uc_sigmask)==640,"n64 ucontext");
_Static_assert(sizeof(stack_t)==24 && offsetof(stack_t,ss_size)==8 && offsetof(stack_t,ss_flags)==16,"n64 altstack");
_Static_assert(offsetof(siginfo_t,si_code)==4 && offsetof(siginfo_t,si_errno)==8 && offsetof(siginfo_t,si_pid)==16,"n64 siginfo order");
_Static_assert(SYS_rt_sigreturn==5211 && SYS_tgkill==5225 && SYS_set_thread_area==5242,"assembly syscall constants");
_Static_assert(SA_SIGINFO==8 && SIGUSR1==16 && SIGUSR2==17 && SIGFPE==8,"MIPS signal constants");

enum { ORDINARY=0, NODEFER=1, NESTED=2, RESET=3, STATE_KEEP=4, STATE_EDIT=5,
       BAD_SP=10, BAD_PC=11, BAD_MODE=12, HIGH_FATAL=13, BAD_DSP=14, BAD_HI1=15, BAD_FCSR=16,
       BAD_HIGH_SP=17, BAD_HIGH_PC=18, FCSR_PENDING=20, FCSR_COALESCED=21,
       FCSR_BLOCKED=22, FCSR_IGNORED=23 };
static volatile int mode, failure, handled, nested, fpe_count, restorers[2], active_depth, nodefer_nested;
static int realtime;
static long pid, tid, uid;
static uintptr_t first_restorer[2];
static stack_t expected_stack={.ss_sp=0,.ss_size=0,.ss_flags=SS_DISABLE};
static uint32_t expected_flags;
static const struct mask128 high_mask={{0x8000010000000000ULL,0x4000000000000001ULL}};
static _Alignas(16) unsigned char fpe_stack[32768], edited_stack[1024];
volatile uintptr_t state_sp;
volatile uint32_t seeded_fcsr;
_Alignas(8) volatile uint64_t seeded_fp[32];
volatile uint64_t observed_gpr[32], observed_hi, observed_lo, observed_tls, initial_tls, observed_cookie, observed_cookie2, tls_install_result, tls_restore_result;
volatile uint32_t observed_fcsr, observed_path, pending_phase;
_Alignas(8) volatile uint64_t observed_fp[32];
const _Alignas(8) uint64_t initial_fp[32]={
    0x3f00112233445000ULL,0x3f00112233445001ULL,0x3f00112233445002ULL,0x3f00112233445003ULL,
    0x3f00112233445004ULL,0x3f00112233445005ULL,0x3f00112233445006ULL,0x3f00112233445007ULL,
    0x3f00112233445008ULL,0x3f00112233445009ULL,0x3f0011223344500aULL,0x3f0011223344500bULL,
    0x3f0011223344500cULL,0x3f0011223344500dULL,0x3f0011223344500eULL,0x3f0011223344500fULL,
    0x3f00112233445010ULL,0x3f00112233445011ULL,0x3f00112233445012ULL,0x3f00112233445013ULL,
    0x3f00112233445014ULL,0x3f00112233445015ULL,0x3f00112233445016ULL,0x3f00112233445017ULL,
    0x3f00112233445018ULL,0x3f00112233445019ULL,0x3f0011223344501aULL,0x3f0011223344501bULL,
    0x3f0011223344501cULL,0x3f0011223344501dULL,0x3f0011223344501eULL,0x3f0011223344501fULL};
static volatile uintptr_t original_frame;
static volatile uint32_t *original_fcsr;
static unsigned char original_neighbors[8];
static const uint32_t pending_value=0x00823085u, cleared_value=0x00802085u;
static const uint64_t tls_cookie=0x1234567887654321ULL;
extern void signal_entry(void), state_probe(long,long), state_resume(void), state_resume_edited(void);
extern const uint32_t reference_trampoline[4];
void entry_common(int,void *,void *,void *,uintptr_t,uintptr_t,uint64_t);

#define FPRS(OP) OP(0,0) OP(1,8) OP(2,16) OP(3,24) OP(4,32) OP(5,40) OP(6,48) OP(7,56) OP(8,64) OP(9,72) OP(10,80) OP(11,88) OP(12,96) OP(13,104) OP(14,112) OP(15,120) OP(16,128) OP(17,136) OP(18,144) OP(19,152) OP(20,160) OP(21,168) OP(22,176) OP(23,184) OP(24,192) OP(25,200) OP(26,208) OP(27,216) OP(28,224) OP(29,232) OP(30,240) OP(31,248)
#define FP_LOAD(N,O) "ldc1 $f" #N "," #O "($8)\n"
#define FP_STORE(N,O) "sdc1 $f" #N "," #O "($8)\n"
#define FP_ZERO(N,O) "dmtc1 $0,$f" #N "\n"
#define GPRS(OP) OP(0,0) OP(1,8) OP(2,16) OP(3,24) OP(4,32) OP(5,40) OP(6,48) OP(7,56) OP(8,64) OP(9,72) OP(10,80) OP(11,88) OP(12,96) OP(13,104) OP(14,112) OP(15,120) OP(16,128) OP(17,136) OP(18,144) OP(19,152) OP(20,160) OP(21,168) OP(22,176) OP(23,184) OP(24,192) OP(25,200) OP(28,224) OP(29,232) OP(30,240) OP(31,248)
#define GPR_STORE(N,O) "sd $" #N "," #O "($sp)\n"
#define GPR_COPY(N,O) "ld $9," #O "($sp)\nsd $9," #O "($8)\n"
#define GPR_POISON(N,O) "dli $" #N ",0x5a5a6b6b7c7c8d8d\n"
#define POISONABLE(OP) OP(1,0) OP(2,0) OP(3,0) OP(4,0) OP(5,0) OP(6,0) OP(7,0) OP(8,0) OP(9,0) OP(10,0) OP(11,0) OP(12,0) OP(13,0) OP(14,0) OP(15,0) OP(16,0) OP(17,0) OP(18,0) OP(19,0) OP(20,0) OP(21,0) OP(22,0) OP(23,0) OP(24,0) OP(25,0) OP(28,0) OP(30,0)
#define ADDRESS(S) "lui $8,%highest(" #S ")\ndaddiu $8,$8,%higher(" #S ")\ndsll $8,$8,16\ndaddiu $8,$8,%hi(" #S ")\ndsll $8,$8,16\ndaddiu $8,$8,%lo(" #S ")\n"
// k0/k1 are reserved across syscall and TLB refill; no user scratch uses them.
// Snapshot first, then use the already-saved a4/a5. Never reconstruct returned
// SP from a global until after both actual-SP cookies and all state are observed.
#define OBSERVE \
    "daddiu $sp,$sp,-256\n" GPRS(GPR_STORE) \
    "daddiu $9,$sp,256\nsd $9,232($sp)\n" \
    ADDRESS(observed_gpr) GPRS(GPR_COPY) \
    "ld $9,256($sp)\n" ADDRESS(observed_cookie) "sd $9,0($8)\n" \
    "ld $9,264($sp)\n" ADDRESS(observed_cookie2) "sd $9,0($8)\n" \
    ADDRESS(observed_fp) FPRS(FP_STORE) \
    "mfhi $9\n" ADDRESS(observed_hi) "sd $9,0($8)\nmflo $9\n" ADDRESS(observed_lo) "sd $9,0($8)\n" \
    "cfc1 $9,$31\n" ADDRESS(observed_fcsr) "sw $9,0($8)\nrdhwr $9,$29\n" ADDRESS(observed_tls) "sd $9,0($8)\n"
__asm__(".text\n.balign 4\n.set push\n.set noreorder\n.set noat\n.set nomips16\n"
        ".global signal_entry\n.type signal_entry,@function\nsignal_entry:\nmove $7,$sp\nmove $8,$31\nmove $9,$25\nrdhwr $10,$29\ndaddiu $sp,$sp,-32\nsd $31,0($sp)\nsd $28,8($sp)\n"
        "lui $25,%highest(entry_common)\ndaddiu $25,$25,%higher(entry_common)\ndsll $25,$25,16\ndaddiu $25,$25,%hi(entry_common)\ndsll $25,$25,16\ndaddiu $25,$25,%lo(entry_common)\njalr $25\nnop\n"
        FPRS(FP_ZERO)
        "ctc1 $0,$31\nmthi $0\nmtlo $0\n"
        POISONABLE(GPR_POISON)
        "ld $31,0($sp)\ndaddiu $sp,$sp,32\njr $31\nnop\n.size signal_entry,.-signal_entry\n"
        ".global state_probe\n.type state_probe,@function\nstate_probe:\ndaddiu $sp,$sp,-416\nsd $16,16($sp)\nsd $17,24($sp)\nsd $18,32($sp)\nsd $19,40($sp)\nsd $20,48($sp)\nsd $21,56($sp)\nsd $22,64($sp)\nsd $23,72($sp)\nsd $28,80($sp)\nsd $30,88($sp)\nsd $31,96($sp)\ncfc1 $9,$31\nsw $9,104($sp)\nmfhi $9\nsd $9,112($sp)\nmflo $9\nsd $9,120($sp)\nsdc1 $f0,128($sp)\nsdc1 $f1,136($sp)\nsdc1 $f2,144($sp)\nsdc1 $f3,152($sp)\nsdc1 $f4,160($sp)\nsdc1 $f5,168($sp)\nsdc1 $f6,176($sp)\nsdc1 $f7,184($sp)\nsdc1 $f8,192($sp)\nsdc1 $f9,200($sp)\nsdc1 $f10,208($sp)\nsdc1 $f11,216($sp)\nsdc1 $f12,224($sp)\nsdc1 $f13,232($sp)\nsdc1 $f14,240($sp)\nsdc1 $f15,248($sp)\nsdc1 $f16,256($sp)\nsdc1 $f17,264($sp)\nsdc1 $f18,272($sp)\nsdc1 $f19,280($sp)\nsdc1 $f20,288($sp)\nsdc1 $f21,296($sp)\nsdc1 $f22,304($sp)\nsdc1 $f23,312($sp)\nsdc1 $f24,320($sp)\nsdc1 $f25,328($sp)\nsdc1 $f26,336($sp)\nsdc1 $f27,344($sp)\nsdc1 $f28,352($sp)\nsdc1 $f29,360($sp)\nsdc1 $f30,368($sp)\nsdc1 $f31,376($sp)\nsd $4,384($sp)\nsd $5,392($sp)\nrdhwr $9,$29\n"
        ADDRESS(initial_tls) "sd $9,0($8)\n"
        ADDRESS(state_sp) "sd $sp,0($8)\ndli $9,0x6c7d8e9fab12cd34\nsd $9,0($sp)\ndli $9,0x98a7b6c5d4e3f201\nsd $9,8($sp)\n"
        "dli $4,0x1234567887654321\nli $2,5242\nsyscall\n"
        ADDRESS(tls_install_result) "sd $2,0($8)\n"
        ADDRESS(initial_fp) FPRS(FP_LOAD) ADDRESS(seeded_fp) FPRS(FP_STORE)
        "li $9,0x00800005\nctc1 $9,$31\ndli $9,0x12563478a1b2c3d4\nmthi $9\ndli $9,0x87654321fedcba98\nmtlo $9\ncfc1 $9,$31\n"
        ADDRESS(seeded_fcsr) "sw $9,0($8)\n"
        "dli $1,0x1020304010000101\ndli $3,0x1020304010000303\ndli $7,0x1020304010000707\ndli $8,0x1020304010000808\ndli $9,0x1020304010000909\ndli $10,0x1020304010000a0a\ndli $11,0x1020304010000b0b\ndli $12,0x1020304010000c0c\ndli $13,0x1020304010000d0d\ndli $14,0x1020304010000e0e\ndli $15,0x1020304010000f0f\ndli $16,0x1020304010001010\ndli $17,0x1020304010001111\ndli $18,0x1020304010001212\ndli $19,0x1020304010001313\ndli $20,0x1020304010001414\ndli $21,0x1020304010001515\ndli $22,0x1020304010001616\ndli $23,0x1020304010001717\ndli $24,0x1020304010001818\ndli $25,0x1020304010001919\ndli $28,0x1020304010001c1c\ndli $30,0x1020304010001e1e\ndli $31,0x1020304010001f1f\nld $4,384($sp)\nld $5,392($sp)\nli $6,16\nli $2,5225\nsyscall\n.global state_resume\nstate_resume:\n"
        OBSERVE
        "li $9,1\n"
        ADDRESS(observed_path) "sw $9,0($8)\nb state_restore\nnop\n"
        ".global state_resume_edited\nstate_resume_edited:\n"
        OBSERVE
        "li $9,2\n"
        ADDRESS(observed_path) "sw $9,0($8)\n"
        "state_restore:\nli $9,1\n"
        ADDRESS(pending_phase) "sw $9,0($8)\n"
        ADDRESS(state_sp) "ld $sp,0($8)\n"
        ADDRESS(initial_tls) "ld $4,0($8)\nli $2,5242\nsyscall\n"
        ADDRESS(tls_restore_result) "sd $2,0($8)\n"
        "lw $9,104($sp)\nctc1 $9,$31\nld $9,112($sp)\nmthi $9\nld $9,120($sp)\nmtlo $9\nldc1 $f0,128($sp)\nldc1 $f1,136($sp)\nldc1 $f2,144($sp)\nldc1 $f3,152($sp)\nldc1 $f4,160($sp)\nldc1 $f5,168($sp)\nldc1 $f6,176($sp)\nldc1 $f7,184($sp)\nldc1 $f8,192($sp)\nldc1 $f9,200($sp)\nldc1 $f10,208($sp)\nldc1 $f11,216($sp)\nldc1 $f12,224($sp)\nldc1 $f13,232($sp)\nldc1 $f14,240($sp)\nldc1 $f15,248($sp)\nldc1 $f16,256($sp)\nldc1 $f17,264($sp)\nldc1 $f18,272($sp)\nldc1 $f19,280($sp)\nldc1 $f20,288($sp)\nldc1 $f21,296($sp)\nldc1 $f22,304($sp)\nldc1 $f23,312($sp)\nldc1 $f24,320($sp)\nldc1 $f25,328($sp)\nldc1 $f26,336($sp)\nldc1 $f27,344($sp)\nldc1 $f28,352($sp)\nldc1 $f29,360($sp)\nldc1 $f30,368($sp)\nldc1 $f31,376($sp)\nld $16,16($sp)\nld $17,24($sp)\nld $18,32($sp)\nld $19,40($sp)\nld $20,48($sp)\nld $21,56($sp)\nld $22,64($sp)\nld $23,72($sp)\nld $28,80($sp)\nld $30,88($sp)\nld $31,96($sp)\ndaddiu $sp,$sp,416\njr $31\nnop\n.size state_probe,.-state_probe\n"
        ".section .rodata\n.balign 16\n.global reference_trampoline\nreference_trampoline:\nli $2,5211\nsyscall\nnop\nnop\n.text\n.set pop\n"
);

static long raw(long n,long a,long b,long c,long d)
{
    register long r4 __asm__("$4")=a, r5 __asm__("$5")=b, r6 __asm__("$6")=c, r7 __asm__("$7")=d;
    register long r2 __asm__("$2");
    __asm__ volatile("daddu $2,$0,%2 ; syscall" : "=&r"(r2), "+r"(r7)
        : "ir"(n), "0"(r2), "r"(r4), "r"(r5), "r"(r6)
        : "$1","$3","$10","$11","$12","$13","$14","$15","$24","$25","hi","lo","memory");
    return r7 && r2>0 ? -r2 : r2;
}
static long mask(int how,const struct mask128 *set,struct mask128 *old) { return raw(SYS_rt_sigprocmask,how,(long)set,(long)old,16); }
static long action(int sig,const struct action *set,struct action *old) { return raw(SYS_rt_sigaction,sig,(long)set,(long)old,16); }
static struct mask128 bit(int sig) { struct mask128 m={{0}};m.word[(sig-1)/64]=1ULL<<((sig-1)%64);return m; }
static int has(const struct mask128 *m,int sig) { return !!(m->word[(sig-1)/64]&(1ULL<<((sig-1)%64))); }
static int same(const struct mask128 *a,const struct mask128 *b) { for(unsigned i=0;i<2;++i) if(a->word[i]!=b->word[i])return 0;return 1; }
static void check(int condition,int code);
static void fail(int code)
{
    if(!failure)failure=code;
    // Fatal-return tests run in fork children. A child-local failure flag must
    // not disappear behind the expected SIGSEGV/SIGFPE wait status. check uses
    // raw write/exit_group only; the temporary full-width TLS cookie is active.
    if((mode>=BAD_SP && mode<=BAD_HIGH_PC) || mode==FCSR_BLOCKED || mode==FCSR_IGNORED)
        check(0,136);
}
static uint64_t edited_fp(unsigned i) { return initial_fp[i]^0x0011223344556600ULL; }
static uint64_t initial_gpr(unsigned i)
{
    if(i==0 || i==2 || i==7)return 0;
    if(i==4)return pid;
    if(i==5)return tid;
    if(i==6)return SIGUSR1;
    if(i==29)return state_sp;
    return 0x1020304010000000ULL+i*0x101u;
}
static uint64_t edited_gpr(unsigned i) { return i==0?0:i==29?(uintptr_t)(edited_stack+768):0xa1b2c3d420000000ULL+i*0x101u; }
static uint64_t fp_get(mcontext_t *sc,unsigned i) { const unsigned char *p=(const void *)&sc->fpregs; uint64_t v=0;for(unsigned j=0;j<8;++j)v=(v<<8)|p[8*i+j];return v; }
static void fp_set(mcontext_t *sc,unsigned slot,uint64_t v) { unsigned char *p=(void *)&sc->fpregs;p+=8*slot;for(unsigned j=0;j<8;++j)p[j]=(unsigned char)(v>>(56-8*j)); }

void entry_common(int sig,void *second,void *context,void *frame,uintptr_t ra,uintptr_t entry_t9,uint64_t entry_tls)
{
    const int rt=1; // Native n64 always uses the RT frame, even without SA_SIGINFO.
    const uintptr_t base=(uintptr_t)frame;
    mcontext_t *sc=&((ucontext_t *)context)->uc_mcontext;
    struct mask128 *saved=(void *)(base+792), blocked={{0}};
    siginfo_t *info=second;
    if((base&15) || (uintptr_t)context!=base+152 || (uintptr_t)second!=base+24)fail(1);
    if(entry_t9!=(uintptr_t)signal_entry)fail(2);
    const stack_t *saved_stack=&((ucontext_t *)context)->uc_stack;
    if((uintptr_t)saved_stack!=base+168 || saved_stack->ss_sp!=expected_stack.ss_sp || saved_stack->ss_size!=expected_stack.ss_size || saved_stack->ss_flags!=expected_stack.ss_flags)fail(38);
    if(sc->hi1 || sc->hi2 || sc->hi3 || sc->lo1 || sc->lo2 || sc->lo3 || sc->dsp)fail(39);
    const volatile uint32_t *tramp=(const void *)ra;
    if(!ra || (ra&3) || (ra>=base && ra<base+808) || ra==(uintptr_t)reference_trampoline ||
       tramp[0]!=reference_trampoline[0] || tramp[1]!=reference_trampoline[1])fail(3);
    if(first_restorer[realtime] && first_restorer[realtime]!=ra)fail(4);
    first_restorer[realtime]=ra;++restorers[realtime];
    if(rt && (info->si_signo!=sig || info->si_errno || (sig!=SIGFPE && (info->si_code!=SI_TKILL || info->si_pid!=pid || info->si_uid!=uid))))fail(5);
    if(sc->gregs[0] || (sc->pc&3) || sc->used_math!=3)fail(6);
    if(mode!=STATE_KEEP && mode!=STATE_EDIT && mode<FCSR_PENDING && mode<BAD_SP && errno!=117)fail(7);
    if((mode==STATE_KEEP || mode==STATE_EDIT || mode>=FCSR_PENDING || (mode>=BAD_SP && mode<=BAD_HIGH_PC)) && (entry_tls!=tls_cookie || tls_install_result))fail(37);
    if(mask(SIG_SETMASK,0,&blocked) || (blocked.word[0]&high_mask.word[0])!=high_mask.word[0] || (blocked.word[1]&high_mask.word[1])!=high_mask.word[1])fail(8);
    if(sig==SIGFPE) {
        ++fpe_count;
        if(mode==FCSR_BLOCKED || mode==FCSR_IGNORED)raw(SYS_exit_group,97,0,0,0);
        if(mode!=FCSR_PENDING && mode!=FCSR_COALESCED)fail(20);
        if(pending_phase || sc->pc!=(uintptr_t)state_resume)fail(21);
        const uintptr_t limit=(uintptr_t)fpe_stack+sizeof(fpe_stack);
        if(base<(uintptr_t)fpe_stack || base+808>limit || (base<original_frame+808 && original_frame<base+808))fail(22);
        // Observe the exact original user bytes, on a different stack from
        // this forced frame. Merely normalizing this new frame cannot pass.
        const volatile unsigned char *patch=(const void *)original_fcsr;
        if(!patch || *original_fcsr!=cleared_value || sc->fpc_csr!=cleared_value)fail(23);
        if(patch)for(unsigned j=0;j<4;++j) {
            if(patch[j]!=(unsigned char)(cleared_value>>(24-8*j)))fail(24);
            if(patch[(int)j-4]!=original_neighbors[j] || patch[4+j]!=original_neighbors[4+j])fail(25);
        }
        if(!has(&blocked,SIGFPE))fail(26);
        if(mode==FCSR_PENDING) {
            if(info->si_code!=128)fail(27);
            const unsigned char *bytes=(const void *)info;
            for(unsigned j=12;j<128;++j)if(bytes[j])fail(28);
        } else if(info->si_code!=SI_TKILL || info->si_pid!=pid || info->si_uid!=uid)fail(29);
        sc->fpc_csr=0;sc->gregs[2]=0x13579bdf12344567ULL;sc->gregs[7]=0x2468ace0567889abULL;
        return;
    }
    if(sig==SIGUSR2) { ++nested;if(!has(&blocked,SIGUSR1) || !has(&blocked,SIGUSR2))fail(9);return; }
    if(sig!=SIGUSR1)fail(10);
    ++handled;++active_depth;
    if(has(&blocked,SIGUSR1)!=(mode!=NODEFER) || !has(&blocked,SIGUSR2))fail(11);
    if(mode==NODEFER) {
        if(active_depth==1) { if(raw(SYS_tgkill,pid,tid,SIGUSR1,0))fail(12); }
        else if(active_depth==2)++nodefer_nested;
        else fail(13);
    }
    if(mode==NESTED) { struct mask128 m=bit(SIGUSR2);if(mask(SIG_UNBLOCK,&m,0) || raw(SYS_tgkill,pid,tid,SIGUSR2,0))fail(14); }
    if(mode==RESET) {
        struct action old={0x5a5a5a5a,0x5a5a5a5a5a5a5a5aULL,{{0x5a5a5a5a5a5a5a5aULL,0x5a5a5a5a5a5a5a5aULL}}};
        struct mask128 wanted=bit(SIGUSR2);
        if(action(SIGUSR1,0,&old) || old.handler || old.flags!=expected_flags || !same(&old.mask,&wanted))fail(15);
    }
    if(mode==STATE_KEEP || mode==STATE_EDIT) {
        if(seeded_fcsr!=0x00800005u)fail(35);
        for(unsigned i=0;i<32;++i)if(seeded_fp[i]!=initial_fp[i])fail(36);
        for(unsigned i=0;i<32;++i)if(i!=26 && i!=27 && sc->gregs[i]!=initial_gpr(i))fail(30);
        if(sc->pc!=(uintptr_t)state_resume || sc->mdhi!=0x12563478a1b2c3d4ULL || sc->mdlo!=0x87654321fedcba98ULL || sc->fpc_csr!=0x00800005u)fail(31);
        for(unsigned i=0;i<32;++i)if(fp_get(sc,i)!=initial_fp[i])fail(32);
        if(!same(saved,&high_mask))fail(33);
        if(mode==STATE_EDIT) {
            for(unsigned i=0;i<32;++i)if(i!=26 && i!=27)sc->gregs[i]=edited_gpr(i);
            sc->pc=(uintptr_t)state_resume_edited;sc->mdhi=0x89abcdefaabbccddULL;sc->mdlo=0x76543210eeff0011ULL;
            for(unsigned i=0;i<32;++i)fp_set(sc,i,edited_fp(i));
            sc->fpc_csr=0x02800012u;
            // These ignored native n64 fields cannot change privileged mode or TLS.
            sc->reserved=0xffffffffu;((ucontext_t *)context)->uc_flags=~0UL;((ucontext_t *)context)->uc_link=(void *)~0UL;
        }
    }
    if(mode>=FCSR_PENDING && mode<=FCSR_IGNORED) {
        // Preserve the PC tail and used_math adjacent to the four-byte FCSR patch.
        sc->reserved=0x6b7c8d9eu;
        original_frame=base;original_fcsr=&sc->fpc_csr;
        const unsigned char *p=(const void *)original_fcsr;
        for(unsigned j=0;j<4;++j) { original_neighbors[j]=p[(int)j-4];original_neighbors[4+j]=p[4+j]; }
        if(mode==FCSR_COALESCED && raw(SYS_tgkill,pid,tid,SIGFPE,0))fail(34);
        sc->fpc_csr=pending_value;
    }
    if(mode==BAD_SP)sc->gregs[29]=0;
    if(mode==BAD_PC)sc->pc=0;
    // This admitted n64 backend requires FR1 and rejects unretained extension state.
    if(mode==BAD_MODE)sc->used_math=1;
    if(mode==BAD_DSP)sc->dsp=1;
    if(mode==BAD_HI1)sc->hi1=0x1234567800000000ULL;
    if(mode==BAD_FCSR)sc->fpc_csr=0x00040000u;
    if(mode==BAD_HIGH_SP)sc->gregs[29]|=0x100000000ULL;
    if(mode==BAD_HIGH_PC)sc->pc|=0x100000000ULL;
    --active_depth;
}
static void check(int condition,int code)
{
    if(condition && !failure)return;
    char msg[]="SIGNAL_MIPS64_FAIL code=000 handler=00 mode=00 rt=0\n";
    size_t c=sizeof("SIGNAL_MIPS64_FAIL code=")-1,h=sizeof("SIGNAL_MIPS64_FAIL code=000 handler=")-1,m=sizeof("SIGNAL_MIPS64_FAIL code=000 handler=00 mode=")-1,r=sizeof("SIGNAL_MIPS64_FAIL code=000 handler=00 mode=00 rt=")-1;
    msg[c]='0'+code/100%10;msg[c+1]='0'+code/10%10;msg[c+2]='0'+code%10;msg[h]='0'+failure/10;msg[h+1]='0'+failure%10;msg[m]='0'+mode/10;msg[m+1]='0'+mode%10;msg[r]='0'+realtime;
    raw(SYS_write,1,(long)msg,sizeof(msg)-1,0);raw(SYS_exit_group,1,0,0,0);for(;;){}
}
static void install(uint32_t flags,int pending)
{
    realtime=!!(flags&SA_SIGINFO);
    struct action a={flags,(uintptr_t)signal_entry,{{0}}}, second={flags&SA_SIGINFO,(uintptr_t)signal_entry,{{0}}};
    a.mask=bit(SIGUSR2);if(pending)a.mask.word[0]|=1ULL<<(SIGFPE-1);
    check(action(SIGUSR1,&a,0)==0 && action(SIGUSR2,&second,0)==0,101);
}
static void core(int rt)
{
    int base=handled,old_nested=nested,old_nodefer=nodefer_nested;uint32_t flags=rt?SA_SIGINFO:0;
    struct mask128 one=bit(SIGUSR1),current={{0}};
    mode=ORDINARY;install(flags,0);
    check(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==base+1,102);
    check(mask(SIG_BLOCK,&one,0)==0,103);
    for(unsigned i=0;i<3;++i)check(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==base+1,104);
    check(mask(SIG_UNBLOCK,&one,0)==0 && handled==base+2,105);
    mode=NODEFER;install(flags|SA_NODEFER,0);
    check(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==base+4 && nodefer_nested==old_nodefer+1,106);
    mode=NESTED;install(flags,0);
    check(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==base+5 && nested==old_nested+1,107);
    mode=RESET;expected_flags=flags|SA_RESETHAND;install(expected_flags,0);
    check(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==base+6,108);
    check(mask(SIG_SETMASK,0,&current)==0 && same(&current,&high_mask) && errno==117,109);
}
static void states(int rt)
{
    install(rt?SA_SIGINFO:0,0);
    *(uint64_t *)(edited_stack+768)=0x6c7d8e9fab12cd34ULL;
    *(uint64_t *)(edited_stack+776)=0x98a7b6c5d4e3f201ULL;
    for(int edited=0;edited<2;++edited) {
        mode=edited?STATE_EDIT:STATE_KEEP;state_probe(pid,tid);
        check(observed_path==(unsigned)(edited?2:1) && observed_cookie==0x6c7d8e9fab12cd34ULL && observed_cookie2==0x98a7b6c5d4e3f201ULL && observed_tls==tls_cookie && !tls_install_result && !tls_restore_result && errno==117,110);
        for(unsigned i=0;i<32;++i)if(i!=26 && i!=27)check(observed_gpr[i]==(edited?edited_gpr(i):initial_gpr(i)),111);
        check(observed_hi==(edited?0x89abcdefaabbccddULL:0x12563478a1b2c3d4ULL) && observed_lo==(edited?0x76543210eeff0011ULL:0x87654321fedcba98ULL) && observed_fcsr==(edited?0x02800012u:0x00800005u),112);
        for(unsigned i=0;i<32;++i)check(observed_fp[i]==(edited?edited_fp(i):initial_fp[i]),113);
    }
}
static void corrupt(int rt,int bad)
{
    mode=bad;install(rt?SA_SIGINFO:0,0);
    long child=raw(SYS_fork,0,0,0,0);check(child>=0,114);
    if(!child) { pid=raw(SYS_getpid,0,0,0,0);tid=raw(SYS_gettid,0,0,0,0);state_probe(pid,tid);raw(SYS_exit_group,99,0,0,0); }
    int status=0;check(waitpid((pid_t)child,&status,0)==child && WIFSIGNALED(status) && WTERMSIG(status)==SIGSEGV,115);
}
static void highest_fatal(void)
{
    mode=HIGH_FATAL;
    struct action dfl={0,(uintptr_t)SIG_DFL,{{0}}};
    struct mask128 highest=bit(128);
    check(action(128,&dfl,0)==0 && mask(SIG_UNBLOCK,&highest,0)==0,133);
    long child=raw(SYS_fork,0,0,0,0);check(child>=0,134);
    if(!child) {
        pid=raw(SYS_getpid,0,0,0,0);tid=raw(SYS_gettid,0,0,0,0);
        raw(SYS_tgkill,pid,tid,128,0);raw(SYS_exit_group,99,0,0,0);
    }
    // Native MIPS signal128 is valid, but traditional wait macros mask the
    // signal to seven bits: 128 collides with the core bit. Inspect the raw
    // status, not WIFSIGNALED/WTERMSIG; exit99 must remain distinguishable.
    int status=-1;check(waitpid((pid_t)child,&status,0)==child && status==128,135);
}
static void pending(int rt,int selected)
{
    mode=selected;install(rt?SA_SIGINFO:0,1);
    stack_t stack={.ss_sp=fpe_stack,.ss_size=sizeof(fpe_stack),.ss_flags=0};
    struct action fpe={SA_SIGINFO|SA_ONSTACK,(uintptr_t)signal_entry,{{0}}};
    check(raw(SYS_sigaltstack,(long)&stack,0,0,0)==0 && action(SIGFPE,&fpe,0)==0,116);
    expected_stack=stack;
    pending_phase=0;
    if(selected==FCSR_PENDING || selected==FCSR_COALESCED) {
        int before=fpe_count;state_probe(pid,tid);
        check(pending_phase==1 && observed_path==1 && fpe_count==before+1 && observed_gpr[2]==0x13579bdf12344567ULL && observed_gpr[7]==0x2468ace0567889abULL && observed_tls==tls_cookie && !tls_install_result && !tls_restore_result && observed_fcsr==0,117);
        struct mask128 current={{0}};check(mask(SIG_SETMASK,0,&current)==0 && same(&current,&high_mask),118);
    } else {
        long child=raw(SYS_fork,0,0,0,0);check(child>=0,119);
        if(!child) {
            pid=raw(SYS_getpid,0,0,0,0);tid=raw(SYS_gettid,0,0,0,0);
            if(selected==FCSR_BLOCKED) { struct mask128 m=bit(SIGFPE);check(mask(SIG_BLOCK,&m,0)==0,120); }
            else { fpe.handler=(uintptr_t)SIG_IGN;check(action(SIGFPE,&fpe,0)==0,121); }
            state_probe(pid,tid);raw(SYS_exit_group,99,0,0,0);
        }
        int status=0;check(waitpid((pid_t)child,&status,0)==child && WIFSIGNALED(status) && WTERMSIG(status)==SIGFPE,122);
    }
}
static int equal(const char *a,const char *b) { while(*a && *a==*b){++a;++b;}return *a==*b; }
static void line(const char *s) { size_t n=0;while(s[n])++n;check(raw(SYS_write,1,(long)s,n,0)==(long)n,130); }
int main(int argc,char **argv)
{
    pid=raw(SYS_getpid,0,0,0,0);tid=raw(SYS_gettid,0,0,0,0);uid=raw(SYS_getuid,0,0,0,0);errno=117;
    __asm__ volatile("mtc1 $0,$f0; ctc1 $0,$31" ::: "memory");
    check(mask(SIG_SETMASK,&high_mask,0)==0,100);
    // Case selection executes the exact same strict assertions, independently
    // of earlier cases. Case passes never substitute for the aggregate marker.
    if(argc==2) {
        const char *name=argv[1];int found=0;
        if(equal(name,"highest-fatal")){highest_fatal();found=1;}
        for(int rt=0;rt<2;++rt) {
            if(equal(name,rt?"core-siginfo":"core-plain")){core(rt);found=1;}
            if(equal(name,rt?"state-siginfo":"state-plain")){states(rt);found=1;}
            if(equal(name,rt?"bad-sp-siginfo":"bad-sp-plain")){corrupt(rt,BAD_SP);found=1;}
            if(equal(name,rt?"bad-pc-siginfo":"bad-pc-plain")){corrupt(rt,BAD_PC);found=1;}
            if(equal(name,rt?"bad-mode-siginfo":"bad-mode-plain")){corrupt(rt,BAD_MODE);found=1;}
            if(equal(name,rt?"bad-dsp-siginfo":"bad-dsp-plain")){corrupt(rt,BAD_DSP);found=1;}
            if(equal(name,rt?"bad-hi1-siginfo":"bad-hi1-plain")){corrupt(rt,BAD_HI1);found=1;}
            if(equal(name,rt?"bad-fcsr-siginfo":"bad-fcsr-plain")){corrupt(rt,BAD_FCSR);found=1;}
            if(equal(name,rt?"bad-high-sp-siginfo":"bad-high-sp-plain")){corrupt(rt,BAD_HIGH_SP);found=1;}
            if(equal(name,rt?"bad-high-pc-siginfo":"bad-high-pc-plain")){corrupt(rt,BAD_HIGH_PC);found=1;}

            if(equal(name,rt?"pending-siginfo":"pending-plain")){pending(rt,FCSR_PENDING);found=1;}
            if(equal(name,rt?"coalesced-siginfo":"coalesced-plain")){pending(rt,FCSR_COALESCED);found=1;}
            if(equal(name,rt?"blocked-siginfo":"blocked-plain")){pending(rt,FCSR_BLOCKED);found=1;}
            if(equal(name,rt?"ignored-siginfo":"ignored-plain")){pending(rt,FCSR_IGNORED);found=1;}
        }
        check(found,131);line("SIGNAL_MIPS64_CASE_PASS ");line(name);line("\n");return 0;
    }
    check(argc==1,132);
    for(int rt=0;rt<2;++rt) { core(rt);states(rt);for(int bad=BAD_SP;bad<=BAD_HIGH_PC;++bad)if(bad!=HIGH_FATAL)corrupt(rt,bad);for(int p=FCSR_PENDING;p<=FCSR_IGNORED;++p)pending(rt,p); }
    highest_fatal();
    check(handled==20 && nested==2 && nodefer_nested==2 && fpe_count==4 && restorers[0]+restorers[1]==26 && first_restorer[0]==first_restorer[1],123);
    struct mask128 empty={{0}};check(mask(SIG_SETMASK,&empty,0)==0 && errno==117,124);
    line("SIGNAL_MIPS64_PASS mips64 plain_rt=1 siginfo_rt=1 handlers=20 nested=2 nodefer_nested=2 coalesced=2 reset=2 gpr=4 fpr32=4 edited_fp=2 hilo=4 fcsr=4 tls=4 restorers=26 high_mask=2 corrupt_return=16 pending_fcsr=4 fcsr_writeback=4 sigfpe_before_resume=4 si_kernel=2 forced_default=4 preserved_payload=2 highest_fatal=1\n");
    return 0;
}

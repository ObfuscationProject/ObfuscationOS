#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <signal.h>
#include <ucontext.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

#if !defined(__mips__) || !defined(_ABIO32) || _MIPS_SIM != _ABIO32 || !defined(__MIPSEB__) || __mips_fpr != 32 || __mips_isa_rev != 2
#error "This probe requires native big-endian MIPS32r2 o32 FR0 with legacy NaNs"
#endif
#ifdef SA_RESTORER
#error "Native MIPS Linux actions have no restorer field"
#endif
struct mask128 { uint32_t word[4]; };
struct action { uint32_t flags; uintptr_t handler; struct mask128 mask; };
// Independently compiled archived Linux declarations establish these offsets.
// Musl reserves a larger trailing sigset_t than the actual kernel frame uses.
_Static_assert(sizeof(struct action)==24 && offsetof(struct action,handler)==4 && offsetof(struct action,mask)==8,"o32 action wire");
_Static_assert(sizeof(struct mask128)==16 && sizeof(uintptr_t)==4,"o32 mask and pointer");
_Static_assert(sizeof(mcontext_t)==592 && offsetof(mcontext_t,gregs)==16,"o32 scalar context");
_Static_assert(offsetof(mcontext_t,fpregs)==272 && offsetof(mcontext_t,fpc_csr)==532,"o32 FP context");
_Static_assert(offsetof(mcontext_t,used_math)==540 && offsetof(mcontext_t,mdhi)==552 && offsetof(mcontext_t,mdlo)==560,"o32 mode and HI/LO");
_Static_assert(offsetof(ucontext_t,uc_mcontext)==24 && offsetof(ucontext_t,uc_sigmask)==616,"o32 ucontext");
_Static_assert(offsetof(siginfo_t,si_code)==4 && offsetof(siginfo_t,si_errno)==8 && offsetof(siginfo_t,si_pid)==12,"MIPS siginfo order");
_Static_assert(SYS_sigreturn==4119 && SYS_rt_sigreturn==4193 && SYS_tgkill==4266,"assembly syscall constants");
_Static_assert(SA_SIGINFO==8 && SIGUSR1==16 && SIGUSR2==17 && SIGFPE==8,"MIPS signal constants");

enum { ORDINARY=0, NODEFER=1, NESTED=2, RESET=3, STATE_KEEP=4, STATE_EDIT=5,
       BAD_SP=10, BAD_PC=11, BAD_MODE=12, HIGH_FATAL=13, FCSR_PENDING=20, FCSR_COALESCED=21,
       FCSR_BLOCKED=22, FCSR_IGNORED=23 };
static volatile int mode, failure, handled, nested, fpe_count, restorers[2], active_depth, nodefer_nested;
static int realtime;
static long pid, tid, uid;
static uintptr_t first_restorer[2];
static uint32_t expected_flags;
static const struct mask128 high_mask={{0,0x80000100u,1u,0x40000000u}};
static _Alignas(16) unsigned char fpe_stack[32768], edited_stack[256];
volatile uintptr_t state_sp;
volatile uint32_t seeded_fcsr;
_Alignas(8) volatile uint64_t seeded_fp[16];
volatile uint32_t observed_gpr[32], observed_hi, observed_lo, observed_fcsr, observed_tls, initial_tls, observed_cookie, observed_path, pending_phase;
_Alignas(8) volatile uint64_t observed_fp[16];
const _Alignas(8) uint64_t initial_fp[16]={
    0x3f00112233445000ULL,0x3f00112233445001ULL,0x3f00112233445002ULL,0x3f00112233445003ULL,
    0x3f00112233445004ULL,0x3f00112233445005ULL,0x3f00112233445006ULL,0x3f00112233445007ULL,
    0x3f00112233445008ULL,0x3f00112233445009ULL,0x3f0011223344500aULL,0x3f0011223344500bULL,
    0x3f0011223344500cULL,0x3f0011223344500dULL,0x3f0011223344500eULL,0x3f0011223344500fULL};
static volatile uintptr_t original_frame;
static volatile uint32_t *original_fcsr;
static unsigned char original_neighbors[8];
static const uint32_t pending_value=0x00823085u, cleared_value=0x00802085u;
extern void signal_entry(void), state_probe(long,long), state_resume(void), state_resume_edited(void);
extern const uint32_t reference_trampolines[4];
void entry_common(int,void *,void *,void *,uintptr_t,uintptr_t);

#define PAIRS(OP) OP(0,0) OP(2,8) OP(4,16) OP(6,24) OP(8,32) OP(10,40) OP(12,48) OP(14,56) OP(16,64) OP(18,72) OP(20,80) OP(22,88) OP(24,96) OP(26,104) OP(28,112) OP(30,120)
#define FP_LOAD(N,O) "ldc1 $f" #N "," #O "($8)\n"
#define FP_STORE(N,O) "sdc1 $f" #N "," #O "($8)\n"
#define FP_ZERO(N,O) "mtc1 $0,$f" #N "\n"
#define GPRS(OP) OP(0,0) OP(1,4) OP(2,8) OP(3,12) OP(4,16) OP(5,20) OP(6,24) OP(7,28) OP(8,32) OP(9,36) OP(10,40) OP(11,44) OP(12,48) OP(13,52) OP(14,56) OP(15,60) OP(16,64) OP(17,68) OP(18,72) OP(19,76) OP(20,80) OP(21,84) OP(22,88) OP(23,92) OP(24,96) OP(25,100) OP(28,112) OP(29,116) OP(30,120) OP(31,124)
#define GPR_STORE(N,O) "sw $" #N "," #O "($sp)\n"
#define GPR_COPY(N,O) "lw $9," #O "($sp)\nsw $9," #O "($8)\n"
#define GPR_POISON(N,O) "li $" #N ",0x5a5a\n"
#define POISONABLE(OP) OP(1,0) OP(2,0) OP(3,0) OP(4,0) OP(5,0) OP(6,0) OP(7,0) OP(8,0) OP(9,0) OP(10,0) OP(11,0) OP(12,0) OP(13,0) OP(14,0) OP(15,0) OP(16,0) OP(17,0) OP(18,0) OP(19,0) OP(20,0) OP(21,0) OP(22,0) OP(23,0) OP(24,0) OP(25,0) OP(28,0) OP(30,0)
#define ADDRESS(S) "lui $8,%hi(" #S ")\naddiu $8,$8,%lo(" #S ")\n"
// k0/k1 may be clobbered by a TLB refill and are never used as user scratch.
// First save all meaningful GPRs directly through the returned valid SP. Only
// then may the already-saved t0/t1 carry addresses or values across user faults.
// The 128-byte snapshot fits below both the original SP and edited_stack+192.
#define OBSERVE \
    "addiu $sp,$sp,-128\n" GPRS(GPR_STORE) \
    "addiu $9,$sp,128\nsw $9,116($sp)\n" \
    ADDRESS(observed_gpr) GPRS(GPR_COPY) \
    "lw $9,128($sp)\n" ADDRESS(observed_cookie) "sw $9,0($8)\n" \
    ADDRESS(observed_fp) PAIRS(FP_STORE) \
    "mfhi $9\n" ADDRESS(observed_hi) "sw $9,0($8)\nmflo $9\n" ADDRESS(observed_lo) "sw $9,0($8)\n" \
    "cfc1 $9,$31\n" ADDRESS(observed_fcsr) "sw $9,0($8)\nrdhwr $9,$29\n" ADDRESS(observed_tls) "sw $9,0($8)\n"
__asm__(".text\n.balign 4\n.set push\n.set noreorder\n.set noat\n.set nomips16\n"
        ".global signal_entry\n.type signal_entry,@function\nsignal_entry:\n"
        "move $7,$sp\naddiu $sp,$sp,-40\nsw $31,24($sp)\nsw $31,16($sp)\nsw $25,20($sp)\n"
        "lui $25,%hi(entry_common)\naddiu $25,$25,%lo(entry_common)\njalr $25\nnop\n"
        // No C epilogue can hide the poison: this occurs after entry_common.
        PAIRS(FP_ZERO)
        "mtc1 $0,$f1\nmtc1 $0,$f3\nmtc1 $0,$f5\nmtc1 $0,$f7\nmtc1 $0,$f9\nmtc1 $0,$f11\nmtc1 $0,$f13\nmtc1 $0,$f15\n"
        "mtc1 $0,$f17\nmtc1 $0,$f19\nmtc1 $0,$f21\nmtc1 $0,$f23\nmtc1 $0,$f25\nmtc1 $0,$f27\nmtc1 $0,$f29\nmtc1 $0,$f31\n"
        "ctc1 $0,$31\nmthi $0\nmtlo $0\n" POISONABLE(GPR_POISON)
        "lw $31,24($sp)\naddiu $sp,$sp,40\njr $31\nnop\n.size signal_entry,.-signal_entry\n"
        ".global state_probe\n.type state_probe,@function\nstate_probe:\n"
        "addiu $sp,$sp,-160\nsw $16,16($sp)\nsw $17,20($sp)\nsw $18,24($sp)\nsw $19,28($sp)\n"
        "sw $20,32($sp)\nsw $21,36($sp)\nsw $22,40($sp)\nsw $23,44($sp)\nsw $28,48($sp)\nsw $30,52($sp)\nsw $31,56($sp)\n"
        "sdc1 $f20,64($sp)\nsdc1 $f22,72($sp)\nsdc1 $f24,80($sp)\nsdc1 $f26,88($sp)\nsdc1 $f28,96($sp)\nsdc1 $f30,104($sp)\n"
        "cfc1 $9,$31\nsw $9,112($sp)\nmfhi $9\nsw $9,116($sp)\nmflo $9\nsw $9,120($sp)\n"
        "sw $4,128($sp)\nsw $5,132($sp)\nrdhwr $9,$29\n" ADDRESS(initial_tls) "sw $9,0($8)\n"
        ADDRESS(state_sp) "sw $sp,0($8)\nli $9,0x6c7d8e9f\nsw $9,0($sp)\n"
        ADDRESS(initial_fp) PAIRS(FP_LOAD) ADDRESS(seeded_fp) PAIRS(FP_STORE)
        "li $9,0x00800005\nctc1 $9,$31\nli $9,0x12563478\nmthi $9\nli $9,0x87654321\nmtlo $9\n"
        "cfc1 $9,$31\n" ADDRESS(seeded_fcsr) "sw $9,0($8)\n"
        "li $1,0x10000101\nli $3,0x10000303\nli $6,16\nli $7,0x10000707\n"
        "li $8,0x10000808\nli $9,0x10000909\nli $10,0x10000a0a\nli $11,0x10000b0b\nli $12,0x10000c0c\nli $13,0x10000d0d\nli $14,0x10000e0e\nli $15,0x10000f0f\n"
        "li $16,0x10001010\nli $17,0x10001111\nli $18,0x10001212\nli $19,0x10001313\nli $20,0x10001414\nli $21,0x10001515\nli $22,0x10001616\nli $23,0x10001717\n"
        "li $24,0x10001818\nli $25,0x10001919\nli $28,0x10001c1c\nli $30,0x10001e1e\nli $31,0x10001f1f\n"
        "lw $4,128($sp)\nlw $5,132($sp)\nli $2,4266\nsyscall\n"
        ".global state_resume\nstate_resume:\n" OBSERVE
        "li $9,1\n" ADDRESS(observed_path) "sw $9,0($8)\nb state_restore\nnop\n"
        ".global state_resume_edited\nstate_resume_edited:\n" OBSERVE
        "li $9,2\n" ADDRESS(observed_path) "sw $9,0($8)\n"
        "state_restore:\nli $9,1\n" ADDRESS(pending_phase) "sw $9,0($8)\n"
        // Only after observing every register and loading the actual returned
        // SP cookie may this leaf wrapper recover its original ABI frame.
        ADDRESS(state_sp) "lw $sp,0($8)\nlw $9,112($sp)\nctc1 $9,$31\n"
        "lw $9,116($sp)\nmthi $9\nlw $9,120($sp)\nmtlo $9\n"
        "ldc1 $f20,64($sp)\nldc1 $f22,72($sp)\nldc1 $f24,80($sp)\nldc1 $f26,88($sp)\nldc1 $f28,96($sp)\nldc1 $f30,104($sp)\n"
        "lw $16,16($sp)\nlw $17,20($sp)\nlw $18,24($sp)\nlw $19,28($sp)\nlw $20,32($sp)\nlw $21,36($sp)\nlw $22,40($sp)\nlw $23,44($sp)\n"
        "lw $28,48($sp)\nlw $30,52($sp)\nlw $31,56($sp)\naddiu $sp,$sp,160\njr $31\nnop\n.size state_probe,.-state_probe\n"
        // Assembled byte oracles; never passed to sigaction or installed.
        ".section .rodata\n.balign 4\n.global reference_trampolines\nreference_trampolines:\n"
        "li $2,4119\nsyscall\nli $2,4193\nsyscall\n.text\n.set pop\n");

static long raw(long n,long a,long b,long c,long d)
{
    register long r4 __asm__("$4")=a, r5 __asm__("$5")=b, r6 __asm__("$6")=c, r7 __asm__("$7")=d;
    register long r2 __asm__("$2");
    __asm__ volatile("addu $2,$0,%2 ; syscall" : "=&r"(r2), "+r"(r7)
        : "ir"(n), "0"(r2), "r"(r4), "r"(r5), "r"(r6)
        : "$1","$3","$8","$9","$10","$11","$12","$13","$14","$15","$24","$25","hi","lo","memory");
    return r7 && r2>0 ? -r2 : r2;
}
static long mask(int how,const struct mask128 *set,struct mask128 *old) { return raw(SYS_rt_sigprocmask,how,(long)set,(long)old,16); }
static long action(int sig,const struct action *set,struct action *old) { return raw(SYS_rt_sigaction,sig,(long)set,(long)old,16); }
static struct mask128 bit(int sig) { struct mask128 m={{0}};m.word[(sig-1)/32]=1u<<((sig-1)%32);return m; }
static int has(const struct mask128 *m,int sig) { return !!(m->word[(sig-1)/32]&(1u<<((sig-1)%32))); }
static int same(const struct mask128 *a,const struct mask128 *b) { for(unsigned i=0;i<4;++i) if(a->word[i]!=b->word[i])return 0;return 1; }
static void check(int condition, int code);
static void fail(int code)
{
    if (!failure) failure = code;
    // A child-local assertion must not disappear behind an expected fatal
    // signal. The existing diagnostic uses raw write/exit_group, without TLS.
    if ((mode >= BAD_SP && mode <= BAD_MODE) || mode == FCSR_BLOCKED || mode == FCSR_IGNORED)
        check(0, 136);
}
static uint64_t edited_fp(unsigned i) { return initial_fp[i]^0x0011223344556600ULL; }
static uint32_t initial_gpr(unsigned i)
{
    if(i==0 || i==2 || i==7)return 0;
    if(i==4)return pid;
    if(i==5)return tid;
    if(i==6)return SIGUSR1;
    if(i==29)return state_sp;
    return 0x10000000u+i*0x101u;
}
static uint32_t edited_gpr(unsigned i) { return i==0?0:i==29?(uintptr_t)(edited_stack+192):0x20000000u+i*0x101u; }
static uint64_t high_wire(uint32_t value) { return 0xa1b2c3d400000000ULL|value; }
static uint64_t fp_get(mcontext_t *sc,unsigned i) { const unsigned char *p=(const void *)&sc->fpregs; uint64_t v=0;for(unsigned j=0;j<8;++j)v=(v<<8)|p[16*i+j];return v; }
static void fp_set(mcontext_t *sc,unsigned slot,uint64_t v) { unsigned char *p=(void *)&sc->fpregs;p+=8*slot;for(unsigned j=0;j<8;++j)p[j]=(unsigned char)(v>>(56-8*j)); }

void entry_common(int sig,void *second,void *context,void *frame,uintptr_t ra,uintptr_t entry_t9)
{
    const int rt=sig==SIGFPE?1:realtime;
    const uintptr_t base=(uintptr_t)frame;
    mcontext_t *sc=rt?&((ucontext_t *)context)->uc_mcontext:context;
    struct mask128 *saved=(void *)(base+(rt?768:616)), blocked={{0}};
    siginfo_t *info=second;
    if((base&7) || (uintptr_t)context!=base+(rt?152:24) || (uintptr_t)second!=(rt?base+24:0))fail(1);
    if(entry_t9!=(uintptr_t)signal_entry)fail(2);
    const volatile uint32_t *tramp=(const void *)ra;
    if(!ra || (ra&3) || (ra>=base && ra<base+(rt?784:632)) || ra==(uintptr_t)reference_trampolines || ra==(uintptr_t)(reference_trampolines+2) ||
       tramp[0]!=reference_trampolines[rt*2] || tramp[1]!=reference_trampolines[rt*2+1])fail(3);
    if(first_restorer[rt] && first_restorer[rt]!=ra)fail(4);
    first_restorer[rt]=ra;++restorers[rt];
    if(rt && (info->si_signo!=sig || info->si_errno || (sig!=SIGFPE && (info->si_code!=SI_TKILL || info->si_pid!=pid || info->si_uid!=uid))))fail(5);
    if(sc->gregs[0] || (sc->pc&3) || sc->used_math!=1)fail(6);
    if(errno!=117)fail(7);
    if(mask(SIG_SETMASK,0,&blocked) || (blocked.word[1]&high_mask.word[1])!=high_mask.word[1] || (blocked.word[2]&high_mask.word[2])!=high_mask.word[2] || (blocked.word[3]&high_mask.word[3])!=high_mask.word[3])fail(8);
    if(sig==SIGFPE) {
        ++fpe_count;
        if(mode==FCSR_BLOCKED || mode==FCSR_IGNORED)raw(SYS_exit_group,97,0,0,0);
        if(mode!=FCSR_PENDING && mode!=FCSR_COALESCED)fail(20);
        if(pending_phase || (uint32_t)sc->pc!=(uintptr_t)state_resume)fail(21);
        const uintptr_t limit=(uintptr_t)fpe_stack+sizeof(fpe_stack);
        if(base<(uintptr_t)fpe_stack || base+784>limit || (base<original_frame+(realtime?784:632) && original_frame<base+784))fail(22);
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
        sc->fpc_csr=0;sc->gregs[2]=high_wire(0x4567);sc->gregs[7]=high_wire(0x89ab);
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
        struct action old={0x5a5a5a5a,0x5a5a5a5a,{{0x5a5a5a5a,0x5a5a5a5a,0x5a5a5a5a,0x5a5a5a5a}}};
        struct mask128 wanted=bit(SIGUSR2);
        if(action(SIGUSR1,0,&old) || old.handler || old.flags!=expected_flags || !same(&old.mask,&wanted))fail(15);
    }
    if(mode==STATE_KEEP || mode==STATE_EDIT) {
        if(seeded_fcsr!=0x00800005u)fail(35);
        for(unsigned i=0;i<16;++i)if(seeded_fp[i]!=initial_fp[i])fail(36);
        for(unsigned i=0;i<32;++i)if(i!=26 && i!=27 && sc->gregs[i]!=initial_gpr(i))fail(30);
        if(sc->pc!=(uintptr_t)state_resume || sc->mdhi!=0x12563478u || sc->mdlo!=0x87654321u || sc->fpc_csr!=0x00800005u)fail(31);
        for(unsigned i=0;i<16;++i)if(fp_get(sc,i)!=initial_fp[i])fail(32);
        if(!same(saved,&high_mask))fail(33);
        if(mode==STATE_EDIT) {
            for(unsigned i=0;i<32;++i)if(i!=26 && i!=27)sc->gregs[i]=high_wire(edited_gpr(i));
            sc->pc=high_wire((uintptr_t)state_resume_edited);sc->mdhi=high_wire(0x89abcdef);sc->mdlo=high_wire(0x76543210);
            for(unsigned i=0;i<16;++i) { fp_set(sc,2*i,edited_fp(i));fp_set(sc,2*i+1,0xfedcba9876543210ULL+i); }
            sc->fpc_csr=0x02800012u;
            // These wire fields are unused, never authority to change CP0/TLS.
            sc->regmask=0xffffffffu;sc->status=0xffffffffu;sc->fpc_eir=0xffffffffu;
        }
    }
    if(mode>=FCSR_PENDING && mode<=FCSR_IGNORED) {
        // A nonzero ignored neighbor makes an over-wide patch observable.
        sc->fpc_eir=0x6b7c8d9eu;
        original_frame=base;original_fcsr=&sc->fpc_csr;
        const unsigned char *p=(const void *)original_fcsr;
        for(unsigned j=0;j<4;++j) { original_neighbors[j]=p[(int)j-4];original_neighbors[4+j]=p[4+j]; }
        if(mode==FCSR_COALESCED && raw(SYS_tgkill,pid,tid,SIGFPE,0))fail(34);
        sc->fpc_csr=pending_value;
    }
    if(mode==BAD_SP)sc->gregs[29]=0;
    if(mode==BAD_PC)sc->pc=0;
    // The admitted scalar backend cannot restore FR1. A permissive Linux/QEMU
    // implementation may ignore this bit; that remains a strict profile failure.
    if(mode==BAD_MODE)sc->used_math=3;
    --active_depth;
}
static void check(int condition,int code)
{
    if(condition && !failure)return;
    char msg[]="SIGNAL_MIPS_FAIL code=000 handler=00 mode=00 rt=0\n";
    size_t c=sizeof("SIGNAL_MIPS_FAIL code=")-1,h=sizeof("SIGNAL_MIPS_FAIL code=000 handler=")-1,m=sizeof("SIGNAL_MIPS_FAIL code=000 handler=00 mode=")-1,r=sizeof("SIGNAL_MIPS_FAIL code=000 handler=00 mode=00 rt=")-1;
    msg[c]='0'+code/100%10;msg[c+1]='0'+code/10%10;msg[c+2]='0'+code%10;msg[h]='0'+failure/10;msg[h+1]='0'+failure%10;msg[m]='0'+mode/10;msg[m+1]='0'+mode%10;msg[r]='0'+realtime;
    raw(SYS_write,1,(long)msg,sizeof(msg)-1,0);raw(SYS_exit_group,1,0,0,0);for(;;){}
}
static void install(uint32_t flags,int pending)
{
    realtime=!!(flags&SA_SIGINFO);
    struct action a={flags,(uintptr_t)signal_entry,{{0}}}, second={flags&SA_SIGINFO,(uintptr_t)signal_entry,{{0}}};
    a.mask=bit(SIGUSR2);if(pending)a.mask.word[0]|=1u<<(SIGFPE-1);
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
    *(uint32_t *)(edited_stack+192)=0x6c7d8e9f;
    for(int edited=0;edited<2;++edited) {
        mode=edited?STATE_EDIT:STATE_KEEP;state_probe(pid,tid);
        check(observed_path==(unsigned)(edited?2:1) && observed_cookie==0x6c7d8e9f && observed_tls==initial_tls && errno==117,110);
        for(unsigned i=0;i<32;++i)if(i!=26 && i!=27)check(observed_gpr[i]==(edited?edited_gpr(i):initial_gpr(i)),111);
        check(observed_hi==(edited?0x89abcdefu:0x12563478u) && observed_lo==(edited?0x76543210u:0x87654321u) && observed_fcsr==(edited?0x02800012u:0x00800005u),112);
        for(unsigned i=0;i<16;++i)check(observed_fp[i]==(edited?edited_fp(i):initial_fp[i]),113);
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
    pending_phase=0;
    if(selected==FCSR_PENDING || selected==FCSR_COALESCED) {
        int before=fpe_count;state_probe(pid,tid);
        check(pending_phase==1 && observed_path==1 && fpe_count==before+1 && observed_gpr[2]==0x4567 && observed_gpr[7]==0x89ab && observed_fcsr==0,117);
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
            if(equal(name,rt?"core-rt":"core-legacy")){core(rt);found=1;}
            if(equal(name,rt?"state-rt":"state-legacy")){states(rt);found=1;}
            if(equal(name,rt?"bad-sp-rt":"bad-sp-legacy")){corrupt(rt,BAD_SP);found=1;}
            if(equal(name,rt?"bad-pc-rt":"bad-pc-legacy")){corrupt(rt,BAD_PC);found=1;}
            if(equal(name,rt?"bad-mode-rt":"bad-mode-legacy")){corrupt(rt,BAD_MODE);found=1;}
            if(equal(name,rt?"pending-rt":"pending-legacy")){pending(rt,FCSR_PENDING);found=1;}
            if(equal(name,rt?"coalesced-rt":"coalesced-legacy")){pending(rt,FCSR_COALESCED);found=1;}
            if(equal(name,rt?"blocked-rt":"blocked-legacy")){pending(rt,FCSR_BLOCKED);found=1;}
            if(equal(name,rt?"ignored-rt":"ignored-legacy")){pending(rt,FCSR_IGNORED);found=1;}
        }
        check(found,131);line("SIGNAL_MIPS_CASE_PASS ");line(name);line("\n");return 0;
    }
    check(argc==1,132);
    for(int rt=0;rt<2;++rt) { core(rt);states(rt);for(int bad=BAD_SP;bad<=BAD_MODE;++bad)corrupt(rt,bad);for(int p=FCSR_PENDING;p<=FCSR_IGNORED;++p)pending(rt,p); }
    highest_fatal();
    check(handled==20 && nested==2 && nodefer_nested==2 && fpe_count==4 && restorers[0]+restorers[1]==26 && first_restorer[0]!=first_restorer[1],123);
    struct mask128 empty={{0}};check(mask(SIG_SETMASK,&empty,0)==0 && errno==117,124);
    line("SIGNAL_MIPS_PASS mips legacy=1 rt=1 handlers=20 nested=2 nodefer_nested=2 coalesced=2 reset=2 gpr=4 fpr16=4 edited_fp=2 hilo=4 fcsr=4 tls=4 restorers=26 high_mask=2 corrupt_return=6 pending_fcsr=4 fcsr_writeback=4 sigfpe_before_resume=4 si_kernel=2 forced_default=4 preserved_payload=2 highest_fatal=1\n");
    return 0;
}

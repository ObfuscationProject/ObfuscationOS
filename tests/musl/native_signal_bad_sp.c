#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <signal.h>
#include <ucontext.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

// Assembly publishes this address before installing the deliberately invalid
// SP. No wrapper restores SP itself: post-sigreturn cookie loads must use
// the actual restored SP and fault if the handler failed to repair it.
volatile uintptr_t signal_good_sp;
extern long send_bad_sp(long, long, long, uintptr_t);
#if defined(__i386__)
#define ARCH "i386"
static long raw(long n, long a, long b, long c, long d)
{
    long result;
    __asm__ volatile("int $0x80" : "=a"(result) : "a"(n), "b"(a), "c"(b), "d"(c), "S"(d) : "memory", "cc");
    return result;
}
extern void restore(void);
__asm__(".text\n.global restore\n.type restore,@function\nrestore:\nmov $173,%eax\nint $0x80\nud2\n.size restore,.-restore\n");
// The first two instructions after int80 load cookies through returned ESP.
// No saved register/global repairs the stack before those actual loads.
__asm__(".text\n.global send_bad_sp\n.type send_bad_sp,@function\nsend_bad_sp:\n"
        "push %ebx\npush %esi\nsub $20,%esp\n"
        "movl $0x13572468,(%esp)\nmovl $0x23456789,4(%esp)\nmov %esp,signal_good_sp\n"
        "mov 32(%esp),%ebx\nmov 36(%esp),%ecx\nmov 40(%esp),%edx\nmov 44(%esp),%esi\n"
        "mov %esi,%esp\nmov $270,%eax\nint $0x80\n"
        "mov (%esp),%ecx\nmov 4(%esp),%edx\ntest %eax,%eax\njne 1f\n"
        "cmp $0x13572468,%ecx\njne 1f\ncmp $0x23456789,%edx\njne 1f\n"
        "xor %eax,%eax\njmp 2f\n1: mov $1,%eax\n"
        "2: add $20,%esp\npop %esi\npop %ebx\nret\n.size send_bad_sp,.-send_bad_sp\n");
static uintptr_t saved_sp(ucontext_t *uc) { return uc->uc_mcontext.gregs[REG_ESP]; }
static void repair_sp(ucontext_t *uc, uintptr_t good) { uc->uc_mcontext.gregs[REG_ESP] = good; }
#elif defined(__arm__)
#define ARCH "arm32"
static long raw(long n, long a, long b, long c, long d)
{
    register long r7 __asm__("r7") = n;
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r3 __asm__("r3") = d;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r7), "r"(r1), "r"(r2), "r"(r3) : "memory", "cc");
    return r0;
}
extern void restore(void);
__asm__(".syntax unified\n.text\n.arm\n.align 2\n.global restore\n.type restore,%function\nrestore:\nmov r7,#173\nsvc 0\nudf 0\n.size restore,.-restore\n");
// The first two post-svc instructions use only the returned SP. No saved
// register or global repairs it before either actual cookie load.
__asm__(".text\n.arm\n.align 2\n.global send_bad_sp\n.type send_bad_sp,%function\nsend_bad_sp:\n"
        "push {r4,r5,r7,lr}\nsub sp,sp,#8\n"
        "movw r4,#0x2468\nmovt r4,#0x1357\nmovw r5,#0x6789\nmovt r5,#0x2345\n"
        "str r4,[sp]\nstr r5,[sp,#4]\nldr r12,=signal_good_sp\nstr sp,[r12]\n"
        "mov sp,r3\nmovw r7,#268\nsvc 0\n"
        "ldr r1,[sp]\nldr r2,[sp,#4]\ncmp r0,#0\nbne 1f\n"
        "cmp r1,r4\nbne 1f\ncmp r2,r5\nbne 1f\nmov r0,#0\nb 2f\n"
        "1: mov r0,#1\n2: add sp,sp,#8\npop {r4,r5,r7,pc}\n"
        ".size send_bad_sp,.-send_bad_sp\n.ltorg\n");
static uintptr_t saved_sp(ucontext_t *uc) { return uc->uc_mcontext.arm_sp; }
static void repair_sp(ucontext_t *uc, uintptr_t good) { uc->uc_mcontext.arm_sp = good; }
#elif defined(__x86_64__)
#define ARCH "x86_64"
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
__asm__(".text\n.global send_bad_sp\n.type send_bad_sp,@function\nsend_bad_sp:\n"
        "push %r12\npush %r13\nsub $16,%rsp\n"
        "movabs $0x13572468abcdef01,%r12\nmov %r12,(%rsp)\n"
        "movabs $0x23456789fedcba10,%r13\nmov %r13,8(%rsp)\n"
        "mov %rsp,signal_good_sp(%rip)\nmov %rcx,%rsp\nmov $234,%eax\nsyscall\n"
        "test %rax,%rax\njne 1f\ncmp %r12,(%rsp)\njne 1f\ncmp %r13,8(%rsp)\njne 1f\n"
        "xor %eax,%eax\njmp 2f\n1: mov $1,%eax\n"
        "2: add $16,%rsp\npop %r13\npop %r12\nret\n.size send_bad_sp,.-send_bad_sp\n");
static uintptr_t saved_sp(ucontext_t *uc) { return uc->uc_mcontext.gregs[REG_RSP]; }
static void repair_sp(ucontext_t *uc, uintptr_t good) { uc->uc_mcontext.gregs[REG_RSP] = good; }
#elif defined(__aarch64__)
#define ARCH "aarch64"
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
__asm__(".text\n.global restore\n.type restore,%function\nrestore:\nmov x8,139\nsvc 0\nbrk 0\n.size restore,.-restore\n"
        ".global send_bad_sp\n.type send_bad_sp,%function\nsend_bad_sp:\n"
        "stp x19,x20,[sp,#-48]!\nstp x29,x30,[sp,#16]\nmov x19,sp\n"
        "adrp x9,signal_good_sp\nadd x9,x9,:lo12:signal_good_sp\nstr x19,[x9]\n"
        "mov x20,#0x1357\nstr x20,[sp,#32]\nmov sp,x3\nmov x8,131\nsvc 0\n"
        "cmp x0,#0\nb.ne 1f\nldr x9,[sp,#32]\ncmp x9,x20\ncset x0,ne\nb 2f\n"
        "1: mov x0,#1\n2: ldp x29,x30,[sp,#16]\nldp x19,x20,[sp],#48\nret\n"
        ".size send_bad_sp,.-send_bad_sp\n");
static uintptr_t saved_sp(ucontext_t *uc) { return uc->uc_mcontext.sp; }
static void repair_sp(ucontext_t *uc, uintptr_t good) { uc->uc_mcontext.sp = good; }
#elif defined(__powerpc__) || defined(__PPC__)
#define ARCH "ppc"
#if __SIZEOF_POINTER__ != 4 || __BYTE_ORDER__ != __ORDER_BIG_ENDIAN__ || !defined(__SPE__)
#error "This PPC fixture requires the native big-endian PPC32 e500/SPE profile"
#endif
_Static_assert(sizeof(long) == 4 && sizeof(void *) == 4, "PPC32 native words");
static long raw(long n, long a, long b, long c, long d)
{
    register long r0 __asm__("r0") = n;
    register long r3 __asm__("r3") = a;
    register long r4 __asm__("r4") = b;
    register long r5 __asm__("r5") = c;
    register long r6 __asm__("r6") = d;
    // Linux PPC reports positive errno in r3 only when CR0.SO is set.
    __asm__ volatile("sc ; bns+ 1f ; neg %1, %1 ; 1:"
                     : "+r"(r0), "+r"(r3), "+r"(r4), "+r"(r5), "+r"(r6)
                     : : "memory", "cr0", "r7", "r8", "r9", "r10", "r11", "r12");
    return r3;
}
extern void restore(void);
__asm__(".text\n.balign 4\n.global restore\n.type restore,@function\nrestore:\nli 0,172\nsc\ntrap\n.size restore,.-restore\n");
// Align our frame to 16 bytes even when the EABI libc caller uses eight.
// Preserve the original caller SP in the ABI backchain. The first two post-sc
// instructions read cookies through actual returned r1 before any repair.
__asm__(".text\n.balign 4\n.global send_bad_sp\n.type send_bad_sp,@function\nsend_bad_sp:\n"
        "mr 7,1\nclrrwi 1,1,4\nstwu 1,-32(1)\nstw 7,0(1)\nlis 7,0x1357\nori 7,7,0x2468\nlis 8,0x2345\nori 8,8,0x6789\n"
        "stw 7,8(1)\nstw 8,12(1)\nstw 2,16(1)\nstw 13,20(1)\nmflr 7\nstw 7,24(1)\n"
        "lis 7,signal_good_sp@ha\nstw 1,signal_good_sp@l(7)\nmr 1,6\nli 0,250\nsc\n"
        "lwz 7,8(1)\nlwz 8,12(1)\nbso 1f\ncmpwi 3,0\nbne 1f\n"
        "lis 9,0x1357\nori 9,9,0x2468\ncmpw 7,9\nbne 1f\n"
        "lis 9,0x2345\nori 9,9,0x6789\ncmpw 8,9\nbne 1f\n"
        "lwz 9,16(1)\ncmpw 2,9\nbne 1f\nlwz 9,20(1)\ncmpw 13,9\nbne 1f\n"
        "mflr 9\nlwz 10,24(1)\ncmpw 9,10\nbne 1f\nli 3,0\nb 2f\n"
        "1: li 3,1\n2: lwz 1,0(1)\nblr\n.size send_bad_sp,.-send_bad_sp\n");
static uintptr_t saved_sp(ucontext_t *uc) { return uc->uc_regs->gregs[1]; }
static void repair_sp(ucontext_t *uc, uintptr_t good) { uc->uc_regs->gregs[1] = good; }
#elif defined(__mips__) && defined(_ABI64) && _MIPS_SIM == _ABI64
#define ARCH "mips64"
#if !defined(__MIPSEB__) || __mips_fpr != 64 || __mips_isa_rev != 2
#error "This MIPS64 fixture requires the native big-endian MIPS64r2 n64 FR1 profile"
#endif
#ifdef SA_RESTORER
#error "MIPS64 Linux kernel action records have no restorer member"
#endif
_Static_assert(sizeof(long) == 8 && sizeof(void *) == 8, "native n64 words");
static long raw(long n, long a, long b, long c, long d)
{
	register long r4 __asm__("$4") = a;
	register long r5 __asm__("$5") = b;
	register long r6 __asm__("$6") = c;
	register long r7 __asm__("$7") = d;
	register long r2 __asm__("$2");

	__asm__ __volatile__ (
		"daddu $2,$0,%2 ; syscall"
		: "=&r"(r2), "+r"(r7)
		: "ir"(n), "0"(r2), "r"(r4), "r"(r5), "r"(r6)
		: "$1", "$3", "$10", "$11", "$12", "$13", "$14", "$15", "$24", "$25", "hi", "lo", "memory");
	return r7 && r2>0 ? -r2 : r2;
}
// Preserve a 16-aligned n64 frame. The first two post-syscall instructions
// load full-width cookies through the actual returned SP; no saved SP repairs it.
__asm__(".text\n.balign 4\n.set push\n.set noreorder\n.set nomips16\n"
        ".global send_bad_sp\n.type send_bad_sp,@function\nsend_bad_sp:\n"
        "daddiu $sp,$sp,-48\nsd $31,40($sp)\nsd $16,32($sp)\nsd $17,24($sp)\nsd $28,16($sp)\n"
        "dli $16,0x13572468abcdef01\ndli $17,0x23456789fedcba10\n"
        "sd $16,0($sp)\nsd $17,8($sp)\ndla $8,signal_good_sp\nsd $sp,0($8)\n"
        "move $sp,$7\nli $2,5225\nsyscall\n"
        "ld $8,0($sp)\nld $9,8($sp)\nbnez $7,1f\nnop\nbnez $2,1f\nnop\n"
        "bne $8,$16,1f\nnop\nbne $9,$17,1f\nnop\nld $10,16($sp)\nbne $28,$10,1f\nnop\n"
        "move $2,$0\nb 2f\nnop\n1: li $2,1\n"
        "2: ld $31,40($sp)\nld $16,32($sp)\nld $17,24($sp)\ndaddiu $sp,$sp,48\njr $31\nnop\n"
        ".size send_bad_sp,.-send_bad_sp\n.set pop\n");
static uintptr_t saved_sp(ucontext_t *uc) { return (uintptr_t)uc->uc_mcontext.gregs[29]; }
static void repair_sp(ucontext_t *uc, uintptr_t good) { uc->uc_mcontext.gregs[29] = good; }
#elif defined(__mips__) && defined(_ABIO32) && _MIPS_SIM == _ABIO32
#define ARCH "mips"
#if !defined(__MIPSEB__) || __mips_fpr != 32 || __mips_isa_rev != 2
#error "This MIPS fixture requires the native big-endian MIPS32r2 o32 FR0 profile"
#endif
#ifdef SA_RESTORER
#error "MIPS Linux kernel action records have no restorer member"
#endif
static long raw(long n, long a, long b, long c, long d)
{
    register long r4 __asm__("$4") = a;
    register long r5 __asm__("$5") = b;
    register long r6 __asm__("$6") = c;
    register long r7 __asm__("$7") = d;
    register long r2 __asm__("$2");
    // a3 is both the fourth argument and the Linux syscall error flag.
    __asm__ volatile("addu $2,$0,%2 ; syscall"
                     : "=&r"(r2), "+r"(r7)
                     : "ir"(n), "0"(r2), "r"(r4), "r"(r5), "r"(r6)
                     : "$1", "$3", "$8", "$9", "$10", "$11", "$12", "$13",
                       "$14", "$15", "$24", "$25", "hi", "lo", "memory");
    return r7 && r2 > 0 ? -r2 : r2;
}
// Keep the native o32 eight-byte stack alignment. The first two instructions
// after syscall load distinct cookies through the returned SP before any
// check or restore. S0, S1 and GP are observed; no register/global repairs SP.
__asm__(".text\n.balign 4\n.set push\n.set noreorder\n.set nomips16\n"
        ".global send_bad_sp\n.type send_bad_sp,@function\nsend_bad_sp:\n"
        "addiu $sp,$sp,-32\nsw $31,24($sp)\nsw $16,16($sp)\nsw $17,20($sp)\nsw $28,8($sp)\n"
        "lui $16,0x1357\nori $16,$16,0x2468\nlui $17,0x2345\nori $17,$17,0x6789\n"
        "sw $16,0($sp)\nsw $17,4($sp)\nlui $8,%hi(signal_good_sp)\nsw $sp,%lo(signal_good_sp)($8)\n"
        "move $sp,$7\nli $2,4266\nsyscall\n"
        "lw $8,0($sp)\nlw $9,4($sp)\nbnez $7,1f\nnop\nbnez $2,1f\nnop\n"
        "bne $8,$16,1f\nnop\nbne $9,$17,1f\nnop\nlw $10,8($sp)\nbne $28,$10,1f\nnop\n"
        "move $2,$0\nb 2f\nnop\n1: li $2,1\n"
        "2: lw $31,24($sp)\nlw $16,16($sp)\nlw $17,20($sp)\naddiu $sp,$sp,32\njr $31\nnop\n"
        ".size send_bad_sp,.-send_bad_sp\n.set pop\n");
static uintptr_t saved_sp(ucontext_t *uc) { return (uintptr_t)uc->uc_mcontext.gregs[29]; }
static void repair_sp(ucontext_t *uc, uintptr_t good) { uc->uc_mcontext.gregs[29] = good; }
#elif defined(__loongarch64)
#define ARCH "loongarch64"
#ifdef SA_RESTORER
#error "LoongArch64 Linux kernel action records have no restorer member"
#endif
static long raw(long n, long a, long b, long c, long d)
{
    register long a7 __asm__("$a7") = n;
    register long a0 __asm__("$a0") = a;
    register long a1 __asm__("$a1") = b;
    register long a2 __asm__("$a2") = c;
    register long a3 __asm__("$a3") = d;
    __asm__ volatile("syscall 0" : "+r"(a0) : "r"(a7), "r"(a1), "r"(a2), "r"(a3)
                     : "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7", "$t8", "memory");
    return a0;
}
// Keep a 16-byte-aligned frame and preserve RA, S0 and S1. The first
// two post-syscall instructions load cookies through the returned SP before
// any check or register restore. TP is observed unchanged, never repaired.
__asm__(".text\n.balign 4\n.global send_bad_sp\n.type send_bad_sp,@function\nsend_bad_sp:\n"
        "addi.d $sp,$sp,-48\nst.d $ra,$sp,40\nst.d $s0,$sp,32\nst.d $s1,$sp,24\n"
        "li.d $s0,0x13572468abcdef01\nli.d $s1,0x23456789fedcba10\n"
        "st.d $s0,$sp,0\nst.d $s1,$sp,8\nst.d $tp,$sp,16\n"
        "la.local $t0,signal_good_sp\nst.d $sp,$t0,0\nmove $sp,$a3\nli.w $a7,131\nsyscall 0\n"
        "ld.d $t0,$sp,0\nld.d $t1,$sp,8\nbnez $a0,1f\nbne $t0,$s0,1f\nbne $t1,$s1,1f\n"
        "ld.d $t2,$sp,16\nbne $tp,$t2,1f\nmove $a0,$zero\nb 2f\n1: li.w $a0,1\n"
        "2: ld.d $ra,$sp,40\nld.d $s0,$sp,32\nld.d $s1,$sp,24\naddi.d $sp,$sp,48\njr $ra\n"
        ".size send_bad_sp,.-send_bad_sp\n");
static uintptr_t saved_sp(ucontext_t *uc) { return uc->uc_mcontext.__gregs[LARCH_REG_SP]; }
static void repair_sp(ucontext_t *uc, uintptr_t good) { uc->uc_mcontext.__gregs[LARCH_REG_SP] = good; }
#elif defined(__riscv) && (__riscv_xlen == 32 || __riscv_xlen == 64)
#if __riscv_xlen == 32
#define ARCH "rv32"
#define STORE "sw"
#define LOAD "lw"
#else
#define ARCH "rv64"
#define STORE "sd"
#define LOAD "ld"
#endif
#ifdef SA_RESTORER
#error "RISC-V Linux kernel action records have no restorer member"
#endif
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
// The 48-byte frame stays aligned on both ABIs. The first two loads after
// ecall read cookies through the SP supplied by rt_sigreturn, before restoring
// any register. No saved register or global is allowed to repair SP here.
__asm__(".text\n.balign 4\n.global send_bad_sp\n.type send_bad_sp,@function\nsend_bad_sp:\n"
        "addi sp,sp,-48\n" STORE " ra,40(sp)\n" STORE " s0,32(sp)\n" STORE " s1,24(sp)\n"
        "li s0,0x13572468\nli s1,0x23456789\n" STORE " s0,0(sp)\n" STORE " s1,8(sp)\n"
        "la t0,signal_good_sp\n" STORE " sp,0(t0)\nmv sp,a3\nli a7,131\necall\n"
        LOAD " t0,0(sp)\n" LOAD " t1,8(sp)\nbnez a0,1f\nbne t0,s0,1f\nbne t1,s1,1f\n"
        "li a0,0\nj 2f\n1: li a0,1\n2: " LOAD " ra,40(sp)\n" LOAD " s0,32(sp)\n" LOAD " s1,24(sp)\n"
        "addi sp,sp,48\nret\n.size send_bad_sp,.-send_bad_sp\n");
static uintptr_t saved_sp(ucontext_t *uc) { return uc->uc_mcontext.__gregs[REG_SP]; }
static void repair_sp(ucontext_t *uc, uintptr_t good) { uc->uc_mcontext.__gregs[REG_SP] = good; }
#else
#error "Bad-SP recovery fixture supports i386, x86_64, AArch64, ARM32, RV32, RV64, LoongArch64, MIPS o32, MIPS64 n64 and PPC32"
#endif

#if defined(__mips__)
#define SIGNAL_MASK_BYTES 16
#else
#define SIGNAL_MASK_BYTES 8
#endif
#if defined(__mips__) && defined(_ABI64) && _MIPS_SIM == _ABI64
struct action { unsigned flags; uintptr_t handler; unsigned long mask[2]; };
_Static_assert(offsetof(struct action, flags) == 0, "n64 action flags offset");
_Static_assert(offsetof(struct action, handler) == 8, "n64 action handler offset");
_Static_assert(offsetof(struct action, mask) == 16, "n64 action mask offset");
_Static_assert(sizeof(struct action) == 32, "n64 action copy length");
_Static_assert(sizeof(stack_t) == 24 && offsetof(stack_t, ss_size) == 8 && offsetof(stack_t, ss_flags) == 16, "n64 stack record");
_Static_assert(offsetof(ucontext_t, uc_mcontext) == 40 && offsetof(ucontext_t, uc_mcontext.gregs[29]) == 272, "n64 saved SP");
_Static_assert(SYS_tgkill == 5225 && SYS_rt_sigreturn == 5211, "n64 signal syscall numbers");
#elif defined(__mips__) && defined(_ABIO32) && _MIPS_SIM == _ABIO32
struct action { unsigned flags; uintptr_t handler; unsigned long mask[4]; };
_Static_assert(offsetof(struct action, flags) == 0, "MIPS action flags offset");
_Static_assert(offsetof(struct action, handler) == 4, "MIPS action handler offset");
_Static_assert(offsetof(struct action, mask) == 8, "MIPS action mask offset");
_Static_assert(sizeof(struct action) == 24, "MIPS action copy length");
#elif defined(__riscv) || defined(__loongarch64)
struct action { uintptr_t handler, flags; unsigned long mask[8 / sizeof(unsigned long)]; };
_Static_assert(offsetof(struct action, mask) == 2*sizeof(uintptr_t), "Linux action mask offset");
_Static_assert(sizeof(struct action) == 2*sizeof(uintptr_t)+8, "Linux action copy length");
#else
// ARM and PPC align uint64_t to eight bytes; Linux kernel sigaction places the
// eight-byte mask at offset 12. The wire record needs four-byte alignment.
#if defined(__arm__) || defined(__powerpc__) || defined(__PPC__)
struct __attribute__((packed, aligned(4))) action { uintptr_t handler, flags, restorer; uint64_t mask; };
#else
struct action { uintptr_t handler, flags, restorer; uint64_t mask; };
#endif
_Static_assert(offsetof(struct action, mask) == 3*sizeof(uintptr_t), "Linux action mask offset");
_Static_assert(sizeof(struct action) == 3*sizeof(uintptr_t)+8, "Linux action copy length");
#endif
#if defined(__powerpc__) || defined(__PPC__)
_Static_assert(sizeof(stack_t) == 12 && offsetof(stack_t, ss_flags) == 4 && offsetof(stack_t, ss_size) == 8, "PPC32 stack record");
_Static_assert(offsetof(ucontext_t, uc_regs) == 48 && offsetof(ucontext_t, uc_sigmask) == 52 && offsetof(ucontext_t, uc_mcontext) == 192, "PPC32 ucontext layout");
_Static_assert(offsetof(mcontext_t, gregs[1]) == 4, "PPC32 saved r1");
_Static_assert(SYS_tgkill == 250 && SYS_rt_sigreturn == 172 && SYS_rt_sigaction == 173 && SYS_sigaltstack == 185, "PPC32 signal syscall numbers");
#endif
static _Alignas(16) unsigned char alternate[32768];
static volatile uintptr_t requested, observed;
static volatile int failure, handled, repaired, leave_unrepaired;
static int checks;
static long process_id, thread_id;
static stack_t registered;

static void child_exit(int code)
{
    raw(SYS_exit_group, code, 0, 0, 0);
    for (;;) {}
}
static void fail(int code)
{
    char text[] = "SIGNAL_BAD_SP_FAIL code=000 handler=000\n";
    size_t at = sizeof("SIGNAL_BAD_SP_FAIL code=") - 1;
    text[at] = '0' + code/100%10; text[at+1] = '0' + code/10%10; text[at+2] = '0' + code%10;
    at = sizeof("SIGNAL_BAD_SP_FAIL code=000 handler=") - 1;
    text[at] = '0' + failure/100%10; text[at+1] = '0' + failure/10%10; text[at+2] = '0' + failure%10;
    raw(SYS_write, 1, (long)text, sizeof(text)-1, 0);
    child_exit(1);
}
#define CHECK(condition, code) do { ++checks; if (!(condition) || failure) fail(code); } while (0)
// The unrepaired fork child cannot report its private failure flag after the
// expected SIGSEGV. Exit through raw diagnostics before any failed assertion
// can proceed to a faulting dereference or the intentionally invalid return.
#define HCHECK(condition, code) do { if (!(condition)) { \
    if (!failure) failure = code; if (leave_unrepaired) fail(code); } } while (0)
static int in_alternate(uintptr_t at)
{
    return at >= (uintptr_t)alternate && at - (uintptr_t)alternate < sizeof(alternate);
}
static void handler(int sig, siginfo_t *info, void *context)
{
    volatile unsigned char local = 0x5a;
    ucontext_t *uc = context;
    HCHECK(sig == SIGUSR1 && info && info->si_signo == sig &&
           info->si_code == SI_TKILL && info->si_pid == process_id && uc, 201);
    HCHECK(in_alternate((uintptr_t)&local), 202);
#if defined(__powerpc__) || defined(__PPC__)
    HCHECK(uc && uc->uc_regs == &uc->uc_mcontext, 208);
    if (!uc || uc->uc_regs != &uc->uc_mcontext) return;
    HCHECK((signal_good_sp & 15) == 0, 209);
#endif
    observed = saved_sp(uc);
    HCHECK(observed == requested, 203);
    HCHECK(signal_good_sp && signal_good_sp != requested &&
           !in_alternate(signal_good_sp) && (signal_good_sp & 7) == 0, 204);
    stack_t current = {0};
    HCHECK(raw(SYS_sigaltstack, 0, (long)&current, 0, 0) == 0 &&
           current.ss_sp == registered.ss_sp && current.ss_size == registered.ss_size &&
           current.ss_flags == SS_ONSTACK, 205);
    HCHECK(uc->uc_stack.ss_sp == registered.ss_sp && uc->uc_stack.ss_size == registered.ss_size &&
           uc->uc_stack.ss_flags == 0, 206);
    ++handled;
    if (!leave_unrepaired) { repair_sp(uc, signal_good_sp); ++repaired; }
    HCHECK(local == 0x5a, 207);
}
static long fork_child(void)
{
#ifdef SYS_fork
    return raw(SYS_fork, 0, 0, 0, 0);
#else
    return raw(SYS_clone, SIGCHLD, 0, 0, 0);
#endif
}
int main(void)
{
    volatile uint64_t caller_cookie[2] = {0x1234567890abcdeful, 0xfedcba0987654321ul};
    process_id = raw(SYS_getpid, 0, 0, 0, 0);
    thread_id = raw(SYS_gettid, 0, 0, 0, 0);
    registered = (stack_t){ .ss_sp = alternate, .ss_size = sizeof(alternate), .ss_flags = 0 };
    CHECK(raw(SYS_sigaltstack, (long)&registered, 0, 0, 0) == 0, 101);
#if defined(__mips__)
    struct action a = {SA_SIGINFO | SA_ONSTACK, (uintptr_t)handler, {0}};
#elif defined(__riscv) || defined(__loongarch64)
    struct action a = {(uintptr_t)handler, SA_SIGINFO | SA_ONSTACK, {0}};
#else
    struct action a = {(uintptr_t)handler, 0x04000000ul | SA_SIGINFO | SA_ONSTACK, (uintptr_t)restore, 0};
#endif
    CHECK(raw(SYS_rt_sigaction, SIGUSR1, (long)&a, 0, SIGNAL_MASK_BYTES) == 0, 102);
    const uintptr_t values[] = {0, 64, UINTPTR_MAX-15};
    for (unsigned i = 0; i != 3; ++i) {
        requested = values[i];
        CHECK(send_bad_sp(process_id, thread_id, SIGUSR1, requested) == 0, 103);
        CHECK(handled == (int)i+1 && repaired == (int)i+1 && observed == values[i], 104);
        CHECK(caller_cookie[0] == 0x1234567890abcdeful && caller_cookie[1] == 0xfedcba0987654321ul, 105);
    }
    for (int disabled = 0; disabled != 2; ++disabled) {
        long child = fork_child();
        CHECK(child >= 0, 106);
        if (!child) {
            process_id = raw(SYS_getpid, 0, 0, 0, 0);
            thread_id = raw(SYS_gettid, 0, 0, 0, 0);
            requested = 0;
            leave_unrepaired = !disabled;
            if (disabled) {
                stack_t off = {.ss_flags = SS_DISABLE};
                if (raw(SYS_sigaltstack, (long)&off, 0, 0, 0)) child_exit(95);
            }
            send_bad_sp(process_id, thread_id, SIGUSR1, requested);
            child_exit(94);
        }
        int status = -1;
        CHECK(waitpid((pid_t)child, &status, 0) == child && (status & 0x7f) == SIGSEGV, 107);
    }
    stack_t current = {0};
    CHECK(raw(SYS_sigaltstack, 0, (long)&current, 0, 0) == 0 && current.ss_sp == registered.ss_sp &&
          current.ss_size == registered.ss_size && current.ss_flags == 0, 108);
    CHECK(handled == 3 && repaired == 3 && caller_cookie[0] == 0x1234567890abcdeful &&
          caller_cookie[1] == 0xfedcba0987654321ul, 109);
    const char success[] = "SIGNAL_BAD_SP_PASS " ARCH " repaired=3 saved_sp=3 alt_local=3 stack_cookies=3 fault_children=2\n";
    CHECK(raw(SYS_write, 1, (long)success, sizeof(success)-1, 0) == sizeof(success)-1, 110);
    char count[] = "SIGNAL_BAD_SP_CHECKS count=00\n";
    size_t at = sizeof("SIGNAL_BAD_SP_CHECKS count=")-1;
    count[at] = '0' + checks/10; count[at+1] = '0' + checks%10;
    raw(SYS_write, 1, (long)count, sizeof(count)-1, 0);
    return 0;
}

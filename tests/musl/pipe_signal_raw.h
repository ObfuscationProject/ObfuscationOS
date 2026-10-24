#ifndef PIPE_SIGNAL_RAW_H
#define PIPE_SIGNAL_RAW_H
#define STRINGIFY_INNER(x) #x
#define STRINGIFY(x) STRINGIFY_INNER(x)
extern long pipe_signal_raw(long, void *, unsigned long, unsigned long);
extern unsigned char pipe_signal_site[], pipe_signal_resume[];
#if defined(__arm__)
extern long pipe_signal_thumb(long, void *, unsigned long, unsigned long);
extern unsigned char pipe_signal_thumb_site[], pipe_signal_thumb_resume[];
#endif
/* A real leaf syscall site with an independently addressable safe continuation.
 * The MIPS syscall is deliberately outside every branch delay slot. */
__asm__(
".text\n.global pipe_signal_raw\n.global pipe_signal_site\n.global pipe_signal_resume\n"
#if defined(__x86_64__)
"pipe_signal_raw:\n mov $" STRINGIFY(SYS_read) ",%eax\n"
"pipe_signal_site:\n syscall\npipe_signal_resume:\n ret\n"
#elif defined(__i386__)
"pipe_signal_raw:\n push %ebx\n push %esi\n mov 12(%esp),%ebx\n mov 16(%esp),%ecx\n mov 20(%esp),%edx\n mov 24(%esp),%esi\n mov $" STRINGIFY(SYS_read) ",%eax\n"
"pipe_signal_site:\n int $0x80\npipe_signal_resume:\n pop %esi\n pop %ebx\n ret\n"
#elif defined(__aarch64__)
".balign 4\npipe_signal_raw:\n mov x8,#" STRINGIFY(SYS_read) "\n"
"pipe_signal_site:\n svc #0\npipe_signal_resume:\n ret\n"
#elif defined(__arm__)
".syntax unified\n.arm\n.balign 4\n.type pipe_signal_raw,%function\n"
"pipe_signal_raw:\n push {r7,lr}\n mov r7,#" STRINGIFY(SYS_read) "\n"
"pipe_signal_site:\n svc #0\npipe_signal_resume:\n pop {r7,pc}\n"
".thumb\n.balign 2\n.global pipe_signal_thumb\n.type pipe_signal_thumb,%function\n.thumb_func\n"
"pipe_signal_thumb:\n push {r7,lr}\n movs r7,#" STRINGIFY(SYS_read) "\n"
".global pipe_signal_thumb_site\npipe_signal_thumb_site:\n svc #0\n"
".global pipe_signal_thumb_resume\npipe_signal_thumb_resume:\n pop {r7,pc}\n.arm\n"
#elif defined(__riscv)
".option push\n.option norelax\n.option norvc\n.balign 4\n"
"pipe_signal_raw:\n li a7," STRINGIFY(SYS_read) "\n"
"pipe_signal_site:\n ecall\npipe_signal_resume:\n ret\n.option pop\n"
#elif defined(__loongarch64)
".balign 4\npipe_signal_raw:\n li.w $a7," STRINGIFY(SYS_read) "\n"
"pipe_signal_site:\n syscall 0\npipe_signal_resume:\n jr $ra\n"
#elif defined(__mips__)
".set push\n.set noreorder\n.balign 4\npipe_signal_raw:\n li $2," STRINGIFY(SYS_read) "\n"
"pipe_signal_site:\n syscall\npipe_signal_resume:\n beqz $7,1f\n nop\n"
#if defined(__mips64)
" dsubu $2,$0,$2\n"
#else
" subu $2,$0,$2\n"
#endif
"1: jr $ra\n nop\n.set pop\n"
#elif defined(__powerpc__)
".balign 4\npipe_signal_raw:\n mfcr 9\n lis 10,0x1000\n andc 9,9,10\n cmpwi 6,0\n beq 1f\n or 9,9,10\n1: mtcrf 128,9\n li 0," STRINGIFY(SYS_read) "\n"
"pipe_signal_site:\n sc\npipe_signal_resume:\n bns 2f\n neg 3,3\n2: blr\n"
#endif
#if defined(__arm__)
".section .note.GNU-stack,\"\",%progbits\n.text\n"
#else
".section .note.GNU-stack,\"\",@progbits\n.text\n"
#endif
);

/* These are Linux ABI context fields, not kernel internal UserFrame indexes. */
#if defined(__x86_64__)
#define CTX_PC(c) ((c)->uc_mcontext.gregs[REG_RIP])
#define CTX_NUMBER(c) ((c)->uc_mcontext.gregs[REG_RAX])
#define CTX_RESULT(c) ((c)->uc_mcontext.gregs[REG_RAX])
#define CTX_FD(c) ((c)->uc_mcontext.gregs[REG_RDI])
#define CTX_BUFFER(c) ((c)->uc_mcontext.gregs[REG_RSI])
#define CTX_COUNT(c) ((c)->uc_mcontext.gregs[REG_RDX])
#elif defined(__i386__)
#define CTX_PC(c) ((c)->uc_mcontext.gregs[REG_EIP])
#define CTX_NUMBER(c) ((c)->uc_mcontext.gregs[REG_EAX])
#define CTX_RESULT(c) ((c)->uc_mcontext.gregs[REG_EAX])
#define CTX_FD(c) ((c)->uc_mcontext.gregs[REG_EBX])
#define CTX_BUFFER(c) ((c)->uc_mcontext.gregs[REG_ECX])
#define CTX_COUNT(c) ((c)->uc_mcontext.gregs[REG_EDX])
#elif defined(__aarch64__)
#define CTX_PC(c) ((c)->uc_mcontext.pc)
#define CTX_NUMBER(c) ((c)->uc_mcontext.regs[8])
#define CTX_RESULT(c) ((c)->uc_mcontext.regs[0])
#define CTX_FD(c) ((c)->uc_mcontext.regs[0])
#define CTX_BUFFER(c) ((c)->uc_mcontext.regs[1])
#define CTX_COUNT(c) ((c)->uc_mcontext.regs[2])
#elif defined(__arm__)
#define CTX_PC(c) ((c)->uc_mcontext.arm_pc)
#define CTX_NUMBER(c) ((c)->uc_mcontext.arm_r7)
#define CTX_RESULT(c) ((c)->uc_mcontext.arm_r0)
#define CTX_FD(c) ((c)->uc_mcontext.arm_r0)
#define CTX_BUFFER(c) ((c)->uc_mcontext.arm_r1)
#define CTX_COUNT(c) ((c)->uc_mcontext.arm_r2)
#elif defined(__riscv)
#define CTX_PC(c) ((c)->uc_mcontext.__gregs[0])
#define CTX_NUMBER(c) ((c)->uc_mcontext.__gregs[17])
#define CTX_RESULT(c) ((c)->uc_mcontext.__gregs[10])
#define CTX_FD(c) ((c)->uc_mcontext.__gregs[10])
#define CTX_BUFFER(c) ((c)->uc_mcontext.__gregs[11])
#define CTX_COUNT(c) ((c)->uc_mcontext.__gregs[12])
#elif defined(__loongarch64)
#define CTX_PC(c) ((c)->uc_mcontext.__pc)
#define CTX_NUMBER(c) ((c)->uc_mcontext.__gregs[11])
#define CTX_RESULT(c) ((c)->uc_mcontext.__gregs[4])
#define CTX_FD(c) ((c)->uc_mcontext.__gregs[4])
#define CTX_BUFFER(c) ((c)->uc_mcontext.__gregs[5])
#define CTX_COUNT(c) ((c)->uc_mcontext.__gregs[6])
#elif defined(__mips__)
#define CTX_PC(c) ((c)->uc_mcontext.pc)
#define CTX_NUMBER(c) ((c)->uc_mcontext.gregs[2])
#define CTX_RESULT(c) ((c)->uc_mcontext.gregs[2])
#define CTX_FD(c) ((c)->uc_mcontext.gregs[4])
#define CTX_BUFFER(c) ((c)->uc_mcontext.gregs[5])
#define CTX_COUNT(c) ((c)->uc_mcontext.gregs[6])
#elif defined(__powerpc__)
#define CTX_PC(c) ((c)->uc_regs->gregs[32])
#define CTX_NUMBER(c) ((c)->uc_regs->gregs[0])
#define CTX_RESULT(c) ((c)->uc_regs->gregs[3])
#define CTX_FD(c) ((c)->uc_regs->gregs[3])
#define CTX_BUFFER(c) ((c)->uc_regs->gregs[4])
#define CTX_COUNT(c) ((c)->uc_regs->gregs[5])
#endif
static long context_result(ucontext_t *c)
{
#if defined(__mips__)
    return c->uc_mcontext.gregs[7]?-(long)CTX_RESULT(c):(long)CTX_RESULT(c);
#elif defined(__powerpc__)
    return c->uc_regs->gregs[38]&0x10000000u?-(long)CTX_RESULT(c):(long)CTX_RESULT(c);
#else
    return (long)CTX_RESULT(c);
#endif
}
static void context_success(ucontext_t *c,long value)
{
    CTX_RESULT(c)=value;
#if defined(__mips__)
    c->uc_mcontext.gregs[7]=0;
#elif defined(__powerpc__)
    c->uc_regs->gregs[38]&=~0x10000000u;
    /* This diagnostic is deliberately contradictory: it must not authorize replay. */
    c->uc_regs->gregs[43]=0x123;
    c->uc_regs->gregs[34]=0x234;
#endif
}
#endif

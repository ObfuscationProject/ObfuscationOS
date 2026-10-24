#ifndef FUTEX_SIGNAL_RAW_H
#define FUTEX_SIGNAL_RAW_H
extern long futex_signal_raw(unsigned long,void *,unsigned long,unsigned long,void *,unsigned long);
extern unsigned char futex_signal_site[],futex_signal_resume[];
#if defined(__arm__)
extern long futex_signal_thumb(unsigned long,void *,unsigned long,unsigned long,void *,unsigned long);
extern unsigned char futex_signal_thumb_site[],futex_signal_thumb_resume[];
#endif
/* Exact instruction labels, not guessed libc PCs. Arguments five/six are zero;
 * no shared-key, bitset, requeue, PI, vector or branch-delay operation is tested. */
__asm__(
".text\n.global futex_signal_raw\n.global futex_signal_site\n.global futex_signal_resume\n"
#if defined(__x86_64__)
"futex_signal_raw:\n mov %rdi,%rax\n mov %rsi,%rdi\n mov %rdx,%rsi\n mov %rcx,%rdx\n mov %r8,%r10\n xor %r8d,%r8d\n xor %r9d,%r9d\n"
"futex_signal_site:\n syscall\nfutex_signal_resume:\n ret\n"
#elif defined(__i386__)
"futex_signal_raw:\n push %ebx\n push %esi\n push %edi\n push %ebp\n mov 20(%esp),%eax\n mov 24(%esp),%ebx\n mov 28(%esp),%ecx\n mov 32(%esp),%edx\n mov 36(%esp),%esi\n xor %edi,%edi\n xor %ebp,%ebp\n"
"futex_signal_site:\n int $0x80\nfutex_signal_resume:\n pop %ebp\n pop %edi\n pop %esi\n pop %ebx\n ret\n"
#elif defined(__aarch64__)
".balign 4\nfutex_signal_raw:\n mov x8,x0\n mov x0,x1\n mov x1,x2\n mov x2,x3\n mov x3,x4\n mov x4,xzr\n mov x5,xzr\n"
"futex_signal_site:\n svc #0\nfutex_signal_resume:\n ret\n"
#elif defined(__arm__)
".syntax unified\n.arm\n.balign 4\n.type futex_signal_raw,%function\n"
"futex_signal_raw:\n push {r4,r5,r7,lr}\n ldr r4,[sp,#16]\n mov r7,r0\n mov r0,r1\n mov r1,r2\n mov r2,r3\n mov r3,r4\n mov r4,#0\n mov r5,#0\n"
"futex_signal_site:\n svc #0\nfutex_signal_resume:\n pop {r4,r5,r7,pc}\n"
".thumb\n.balign 2\n.global futex_signal_thumb\n.type futex_signal_thumb,%function\n.thumb_func\n"
"futex_signal_thumb:\n push {r4,r5,r7,lr}\n ldr r4,[sp,#16]\n mov r7,r0\n mov r0,r1\n mov r1,r2\n mov r2,r3\n mov r3,r4\n movs r4,#0\n movs r5,#0\n"
".global futex_signal_thumb_site\nfutex_signal_thumb_site:\n svc #0\n"
".global futex_signal_thumb_resume\nfutex_signal_thumb_resume:\n pop {r4,r5,r7,pc}\n.arm\n"
#elif defined(__riscv)
".option push\n.option norelax\n.option norvc\n.balign 4\nfutex_signal_raw:\n mv a7,a0\n mv a0,a1\n mv a1,a2\n mv a2,a3\n mv a3,a4\n li a4,0\n li a5,0\n"
"futex_signal_site:\n ecall\nfutex_signal_resume:\n ret\n.option pop\n"
#elif defined(__loongarch64)
".balign 4\nfutex_signal_raw:\n move $a7,$a0\n move $a0,$a1\n move $a1,$a2\n move $a2,$a3\n move $a3,$a4\n move $a4,$zero\n move $a5,$zero\n"
"futex_signal_site:\n syscall 0\nfutex_signal_resume:\n jr $ra\n"
#elif defined(__mips__)
".set push\n.set noreorder\n.balign 4\nfutex_signal_raw:\n move $2,$4\n move $4,$5\n move $5,$6\n move $6,$7\n"
#if defined(__mips64)
" move $7,$8\n move $8,$0\n move $9,$0\n"
#else
" addiu $sp,$sp,-32\n lw $7,48($sp)\n sw $0,16($sp)\n sw $0,20($sp)\n"
#endif
"futex_signal_site:\n syscall\nfutex_signal_resume:\n beqz $7,1f\n nop\n"
#if defined(__mips64)
" dsubu $2,$0,$2\n1: jr $ra\n nop\n"
#else
" subu $2,$0,$2\n1: addiu $sp,$sp,32\n jr $ra\n nop\n"
#endif
".set pop\n"
#elif defined(__powerpc__)
".balign 4\nfutex_signal_raw:\n mfcr 9\n lis 10,0x1000\n andc 9,9,10\n cmpwi 8,0\n beq 1f\n or 9,9,10\n1: mtcrf 128,9\n mr 0,3\n mr 3,4\n mr 4,5\n mr 5,6\n mr 6,7\n li 7,0\n li 8,0\n"
"futex_signal_site:\n sc\nfutex_signal_resume:\n bns 2f\n neg 3,3\n2: blr\n"
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

#define CTX_ADDRESS(c) CTX_FD(c)
#define CTX_OPERATION(c) CTX_BUFFER(c)
#define CTX_VALUE(c) CTX_COUNT(c)
#if defined(__x86_64__)
#define CTX_TIMEOUT(c) ((c)->uc_mcontext.gregs[REG_R10])
#elif defined(__i386__)
#define CTX_TIMEOUT(c) ((c)->uc_mcontext.gregs[REG_ESI])
#elif defined(__aarch64__)
#define CTX_TIMEOUT(c) ((c)->uc_mcontext.regs[3])
#elif defined(__arm__)
#define CTX_TIMEOUT(c) ((c)->uc_mcontext.arm_r3)
#elif defined(__riscv)
#define CTX_TIMEOUT(c) ((c)->uc_mcontext.__gregs[13])
#elif defined(__loongarch64)
#define CTX_TIMEOUT(c) ((c)->uc_mcontext.__gregs[7])
#elif defined(__mips__)
#define CTX_TIMEOUT(c) ((c)->uc_mcontext.gregs[7])
#elif defined(__powerpc__)
#define CTX_TIMEOUT(c) ((c)->uc_regs->gregs[6])
#endif
#endif

#ifndef POLL_SIGNAL_CONTEXT_H
#define POLL_SIGNAL_CONTEXT_H
/* Attributed unchanged Linux context accessors/result normalizer from the sealed futex guest. */

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

#endif

#ifndef OBFUSCATION_THREAD_SYSCALL_H
#define OBFUSCATION_THREAD_SYSCALL_H
#include <stdint.h>
extern long thread_syscall4(uintptr_t, uintptr_t, uintptr_t, uintptr_t, uintptr_t);
__asm__(
".section .text\n"
".global thread_syscall4\n"
#if defined(__x86_64__)
"thread_syscall4:\n"
"    mov %rdi, %rax\n"
"    mov %rsi, %rdi\n"
"    mov %rdx, %rsi\n"
"    mov %rcx, %rdx\n"
"    mov %r8, %r10\n"
"    syscall\n"
"    ret\n"
#elif defined(__i386__)
"thread_syscall4:\n"
"    push %ebx\n"
"    push %esi\n"
"    mov 12(%esp), %eax\n"
"    mov 16(%esp), %ebx\n"
"    mov 20(%esp), %ecx\n"
"    mov 24(%esp), %edx\n"
"    mov 28(%esp), %esi\n"
"    int $0x80\n"
"    pop %esi\n"
"    pop %ebx\n"
"    ret\n"
#elif defined(__aarch64__)
"thread_syscall4:\n"
"    mov x8, x0\n"
"    mov x0, x1\n"
"    mov x1, x2\n"
"    mov x2, x3\n"
"    mov x3, x4\n"
"    svc #0\n"
"    ret\n"
#elif defined(__arm__)
".arm\n"
"thread_syscall4:\n"
"    push {r7, lr}\n"
"    mov r7, r0\n"
"    mov r0, r1\n"
"    mov r1, r2\n"
"    mov r2, r3\n"
"    ldr r3, [sp, #8]\n"
"    svc #0\n"
"    pop {r7, pc}\n"
#elif defined(__riscv)
".option push\n"
".option norelax\n"
"thread_syscall4:\n"
"    mv a7, a0\n"
"    mv a0, a1\n"
"    mv a1, a2\n"
"    mv a2, a3\n"
"    mv a3, a4\n"
"    ecall\n"
"    ret\n"
".option pop\n"
#elif defined(__loongarch64)
"thread_syscall4:\n"
"    move $a7, $a0\n"
"    move $a0, $a1\n"
"    move $a1, $a2\n"
"    move $a2, $a3\n"
"    move $a3, $a4\n"
"    syscall 0\n"
"    jr $ra\n"
#elif defined(__mips__) || defined(__mips64)
".set push\n"
".set noreorder\n"
"thread_syscall4:\n"
"    move $2, $4\n"
"    move $4, $5\n"
"    move $5, $6\n"
"    move $6, $7\n"
#if defined(__mips64)
"    move $7, $8\n"
#else
"    lw $7, 16($sp)\n"
#endif
"    syscall\n"
"    beqz $7, 1f\n"
"    nop\n"
#if defined(__mips64)
"    dsubu $2, $0, $2\n"
#else
"    subu $2, $0, $2\n"
#endif
"1:  jr $ra\n"
"    nop\n"
".set pop\n"
#elif defined(__powerpc__)
"thread_syscall4:\n"
"    mr 0, 3\n"
"    mr 3, 4\n"
"    mr 4, 5\n"
"    mr 5, 6\n"
"    mr 6, 7\n"
"    sc\n"
"    bns 1f\n"
"    neg 3, 3\n"
"1:  blr\n"
#endif
#if defined(__arm__)
".section .note.GNU-stack,\"\",%progbits\n"
#else
".section .note.GNU-stack,\"\",@progbits\n"
#endif
".text\n"
);
#endif

.syntax unified
.arch armv7-a
.arm
.section .text
.macro OK_SYSCALL name argc
.global \name
.type \name,%function
\name:
    push {r4-r7, r12, lr}
    mov r7, r0
    mov r0, r1
    mov r1, r2
    mov r2, r3
.if \argc > 3
    ldr r3, [sp, #24]
.else
    mov r3, #0
.endif
.if \argc > 4
    ldr r4, [sp, #28]
.else
    mov r4, #0
.endif
.if \argc > 5
    ldr r5, [sp, #32]
.else
    mov r5, #0
.endif
    svc #0
    pop {r4-r7, r12, pc}
.size \name, .-\name
.endm
OK_SYSCALL ok_syscall0, 0
OK_SYSCALL ok_syscall1, 1
OK_SYSCALL ok_syscall2, 2
OK_SYSCALL ok_syscall3, 3
OK_SYSCALL ok_syscall4, 4
OK_SYSCALL ok_syscall5, 5
OK_SYSCALL ok_syscall6, 6
.section .note.GNU-stack,"",%progbits

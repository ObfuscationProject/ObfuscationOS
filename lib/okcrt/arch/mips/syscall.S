.set noreorder
.section .text
# Native Obfuscation ABI: v0=number/result, a0..a3/t0/t1=arguments.
# The O32 C ABI passes arguments beyond a3 in the caller's stack home area.
.macro OK_SYSCALL name, count
.global \name
.type \name, @function
\name:
    move $2, $4
.if \count >= 1
    move $4, $5
.endif
.if \count >= 2
    move $5, $6
.endif
.if \count >= 3
    move $6, $7
.endif
.if \count >= 4
    lw $7, 16($sp)
.endif
.if \count >= 5
    lw $8, 20($sp)
.endif
.if \count >= 6
    lw $9, 24($sp)
.endif
    syscall
    jr $ra
    nop
.endm
OK_SYSCALL ok_syscall0, 0
OK_SYSCALL ok_syscall1, 1
OK_SYSCALL ok_syscall2, 2
OK_SYSCALL ok_syscall3, 3
OK_SYSCALL ok_syscall4, 4
OK_SYSCALL ok_syscall5, 5
OK_SYSCALL ok_syscall6, 6
.section .note.GNU-stack,"",@progbits

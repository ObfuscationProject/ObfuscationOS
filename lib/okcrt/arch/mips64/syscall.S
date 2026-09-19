.set noreorder
.section .text
# Native Obfuscation ABI: v0=number/result, a0..a5=arguments.
.macro OK_SYSCALL name
.global \name
.type \name, @function
\name:
    move $2, $4
    move $4, $5
    move $5, $6
    move $6, $7
    move $7, $8
    move $8, $9
    move $9, $10
    syscall
    jr $ra
    nop
.endm
OK_SYSCALL ok_syscall0
OK_SYSCALL ok_syscall1
OK_SYSCALL ok_syscall2
OK_SYSCALL ok_syscall3
OK_SYSCALL ok_syscall4
OK_SYSCALL ok_syscall5
OK_SYSCALL ok_syscall6
.section .note.GNU-stack,"",@progbits

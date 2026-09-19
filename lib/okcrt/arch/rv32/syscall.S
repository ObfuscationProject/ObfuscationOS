.section .text

.macro OK_SYSCALL name
.global \name
.type \name, @function
\name:
    mv a7, a0
    mv a0, a1
    mv a1, a2
    mv a2, a3
    mv a3, a4
    mv a4, a5
    mv a5, a6
    ecall
    ret
.endm

OK_SYSCALL ok_syscall0
OK_SYSCALL ok_syscall1
OK_SYSCALL ok_syscall2
OK_SYSCALL ok_syscall3
OK_SYSCALL ok_syscall4
OK_SYSCALL ok_syscall5
OK_SYSCALL ok_syscall6

.section .note.GNU-stack,"",@progbits

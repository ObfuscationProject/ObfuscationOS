.section .text

.macro OK_SYSCALL name
.global \name
.type \name, @function
\name:
    move $a7, $a0
    move $a0, $a1
    move $a1, $a2
    move $a2, $a3
    move $a3, $a4
    move $a4, $a5
    move $a5, $a6
    syscall 0
    jr $ra
.endm

OK_SYSCALL ok_syscall0
OK_SYSCALL ok_syscall1
OK_SYSCALL ok_syscall2
OK_SYSCALL ok_syscall3
OK_SYSCALL ok_syscall4
OK_SYSCALL ok_syscall5
OK_SYSCALL ok_syscall6

.section .note.GNU-stack,"",@progbits

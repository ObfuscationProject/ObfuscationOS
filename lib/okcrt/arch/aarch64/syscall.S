.section .text

.macro OK_SYSCALL name argc
.global \name
.type \name, %function
\name:
    mov x8, x0
    mov x0, x1
    mov x1, x2
    mov x2, x3
    mov x3, x4
    mov x4, x5
    mov x5, x6
    svc #0
    ret
.endm

OK_SYSCALL ok_syscall0, 0
OK_SYSCALL ok_syscall1, 1
OK_SYSCALL ok_syscall2, 2
OK_SYSCALL ok_syscall3, 3
OK_SYSCALL ok_syscall4, 4
OK_SYSCALL ok_syscall5, 5
OK_SYSCALL ok_syscall6, 6

.section .note.GNU-stack,"",%progbits

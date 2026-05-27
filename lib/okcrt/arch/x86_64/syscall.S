.section .text

.global ok_syscall0
.type ok_syscall0, @function
ok_syscall0:
    mov %rdi, %rax
    syscall
    ret

.global ok_syscall1
.type ok_syscall1, @function
ok_syscall1:
    mov %rdi, %rax
    mov %rsi, %rdi
    syscall
    ret

.global ok_syscall2
.type ok_syscall2, @function
ok_syscall2:
    mov %rdi, %rax
    mov %rsi, %rdi
    mov %rdx, %rsi
    syscall
    ret

.global ok_syscall3
.type ok_syscall3, @function
ok_syscall3:
    mov %rdi, %rax
    mov %rsi, %rdi
    mov %rdx, %rsi
    mov %rcx, %rdx
    syscall
    ret

.global ok_syscall4
.type ok_syscall4, @function
ok_syscall4:
    mov %rdi, %rax
    mov %rsi, %rdi
    mov %rdx, %rsi
    mov %rcx, %rdx
    mov %r8, %r10
    syscall
    ret

.global ok_syscall5
.type ok_syscall5, @function
ok_syscall5:
    mov %rdi, %rax
    mov %rsi, %rdi
    mov %rdx, %rsi
    mov %rcx, %rdx
    mov %r8, %r10
    mov %r9, %r8
    syscall
    ret

.global ok_syscall6
.type ok_syscall6, @function
ok_syscall6:
    mov %rdi, %rax
    mov %rsi, %rdi
    mov %rdx, %rsi
    mov %rcx, %rdx
    mov %r8, %r10
    mov %r9, %r8
    mov 8(%rsp), %r9
    syscall
    ret

.section .note.GNU-stack,"",@progbits

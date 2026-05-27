.section .text
.global _start
.type _start, @function
_start:
    xor %rbp, %rbp
    mov (%rsp), %rdi
    lea 8(%rsp), %rsi
    lea 16(%rsp,%rdi,8), %rdx
    and $-16, %rsp
    call main
    mov %eax, %edi
    call exit
1:
    hlt
    jmp 1b

.section .note.GNU-stack,"",@progbits

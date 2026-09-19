.section .text
.code32
.global _start
.type _start, @function
_start:
    xor %ebp, %ebp
    mov (%esp), %eax
    lea 4(%esp), %ecx
    lea 8(%esp,%eax,4), %edx
    and $-16, %esp
    sub $4, %esp
    push %edx
    push %ecx
    push %eax
    call main
    add $16, %esp
    sub $12, %esp
    push %eax
    call exit
1:
    ud2
    jmp 1b
.size _start, . - _start
.section .note.GNU-stack,"",@progbits

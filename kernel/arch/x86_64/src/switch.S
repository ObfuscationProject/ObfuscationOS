.intel_syntax noprefix
.section .text, "ax"
.global context_switch
.type context_switch, @function

/* void context_switch(Context* old, Context* new) */
context_switch:
    /* save callee-saved + rsp + resume rip */
    mov [rdi + 0x00], rbx
    mov [rdi + 0x08], rbp
    mov [rdi + 0x10], r12
    mov [rdi + 0x18], r13
    mov [rdi + 0x20], r14
    mov [rdi + 0x28], r15
    mov [rdi + 0x30], rsp
    lea rax, [rip + .resume]
    mov [rdi + 0x38], rax

    /* restore */
    mov rbx, [rsi + 0x00]
    mov rbp, [rsi + 0x08]
    mov r12, [rsi + 0x10]
    mov r13, [rsi + 0x18]
    mov r14, [rsi + 0x20]
    mov r15, [rsi + 0x28]
    mov rsp, [rsi + 0x30]
    jmp qword ptr [rsi + 0x38]

.resume:
    sti
    ret

.section .note.GNU-stack,"",@progbits

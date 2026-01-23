.intel_syntax noprefix
.section .text, "ax"

.extern isr_dispatch

.macro ISR_STUB name, vec
.global \name
.type \name, @function
\name:
    push 0                 /* error code */
    push \vec              /* vector */

    push rax
    push rcx
    push rdx
    push rbx
    push rbp
    push rsi
    push rdi
    push r8
    push r9
    push r10
    push r11
    push r12
    push r13
    push r14
    push r15

    mov rdi, rsp
    call isr_dispatch

    pop r15
    pop r14
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    pop rdi
    pop rsi
    pop rbp
    pop rbx
    pop rdx
    pop rcx
    pop rax

    add rsp, 16            /* vector + error */
    iretq
.endm

ISR_STUB isr_timer_stub, 32
ISR_STUB isr_spurious_stub, 255

.global irq_return_trampoline
.type irq_return_trampoline, @function
irq_return_trampoline:
    pop r15
    pop r14
    pop r13
    pop r12
    pop r11
    pop r10
    pop r9
    pop r8
    pop rdi
    pop rsi
    pop rbp
    pop rbx
    pop rdx
    pop rcx
    pop rax

    add rsp, 16            /* vector + error */
    iretq

.section .note.GNU-stack,"",@progbits

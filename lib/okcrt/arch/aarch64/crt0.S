.section .text
.global _start
.type _start, %function
_start:
    mov x29, xzr
    mov x30, xzr
    ldr x0, [sp]
    add x1, sp, #8
    add x2, x1, x0, lsl #3
    add x2, x2, #8
    bl main
    bl exit
1:
    wfe
    b 1b

.section .note.GNU-stack,"",%progbits

.syntax unified
.arch armv7-a
.arm
.section .text
.global _start
.type _start,%function
_start:
    mov r11, #0
    mov lr, #0
    ldr r0, [sp]
    add r1, sp, #4
    add r2, r1, r0, lsl #2
    add r2, r2, #4
    bic sp, sp, #7
    bl main
    bl exit
1:  b 1b
.section .note.GNU-stack,"",%progbits

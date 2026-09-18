.section .text
.global _start
.type _start, @function
_start:
    li fp, 0
    li ra, 0
    ld a0, 0(sp)
    addi a1, sp, 8
    slli t0, a0, 3
    add a2, a1, t0
    addi a2, a2, 8
    call main
    call exit
1:
    wfi
    j 1b

.section .note.GNU-stack,"",@progbits

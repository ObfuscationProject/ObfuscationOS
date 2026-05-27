.section .text
.global _start
.type _start, @function
_start:
    li fp, 0
    li ra, 0
    call main
    call exit
1:
    wfi
    j 1b

.section .note.GNU-stack,"",@progbits

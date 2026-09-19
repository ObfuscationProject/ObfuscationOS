.set noreorder
.section .text
.global _start
.type _start, @function
_start:
    move $fp, $0
    move $ra, $0
    ld $4, 0($sp)
    daddiu $5, $sp, 8
    dsll $8, $4, 3
    daddu $6, $5, $8
    daddiu $6, $6, 8
    jal main
    nop
    move $4, $2
    jal exit
    nop
1:  b 1b
    nop
.section .note.GNU-stack,"",@progbits

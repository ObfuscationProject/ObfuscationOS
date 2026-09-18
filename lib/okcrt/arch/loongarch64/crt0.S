.section .text
.global _start
.type _start, @function
_start:
    move $fp, $zero
    move $ra, $zero
    ld.d $a0, $sp, 0
    addi.d $a1, $sp, 8
    slli.d $t0, $a0, 3
    add.d $a2, $a1, $t0
    addi.d $a2, $a2, 8
    bl main
    bl exit
1:
    idle 0
    b 1b

.section .note.GNU-stack,"",@progbits

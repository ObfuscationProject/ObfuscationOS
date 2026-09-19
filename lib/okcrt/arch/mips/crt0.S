.set noreorder
.section .text
.global _start
.type _start, @function
_start:
    move $fp, $0
    move $ra, $0
    lw $a0, 0($sp)
    addiu $a1, $sp, 4
    sll $t0, $a0, 2
    addu $a2, $a1, $t0
    addiu $a2, $a2, 4
    # O32 requires four argument home slots below the initial argument vector.
    addiu $sp, $sp, -16
    jal main
    nop
    move $a0, $v0
    jal exit
    nop
1:  b 1b
    nop
.section .note.GNU-stack,"",@progbits

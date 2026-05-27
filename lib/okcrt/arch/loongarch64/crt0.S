.section .text
.global _start
.type _start, @function
_start:
    move $fp, $zero
    move $ra, $zero
    bl main
    bl exit
1:
    idle 0
    b 1b

.section .note.GNU-stack,"",@progbits

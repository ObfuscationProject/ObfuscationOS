.section .text
.global _start
.type _start,@function
_start:
    // The native initial stack contains 32-bit argc/argv/envp words.
    lwz 3,0(1)
    addi 4,1,4
    slwi 5,3,2
    add 5,5,4
    addi 5,5,4
    clrrwi 1,1,4
    li 0,0
    stwu 0,-16(1)
    bl main
    bl exit
1:  trap
    b 1b
.size _start,.-_start
// GCC emits this call in main even for freestanding C. The static ELF loader
// initializes data/BSS; -msdata=none disables SDA relocation and base setup.
.global __eabi
.type __eabi,@function
__eabi:
    blr
.size __eabi,.-__eabi
.section .note.GNU-stack,"",@progbits

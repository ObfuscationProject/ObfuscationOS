/*
 * Multiboot2 + 32-bit protected mode bootstrap (i386)
 * - GRUB enters us in 32-bit protected mode.
 * - We set up a flat GDT and jump into C++ kernel_main.
 */

.intel_syntax noprefix

.section .multiboot, "a"
.align 8

/* Multiboot2 header (must appear early in the image) */
.set MB2_MAGIC,        0xE85250D6
.set MB2_ARCH,         0          /* i386 */
.set MB2_HDR_LEN,      (mb2_end - mb2_start)
.set MB2_CHECKSUM,     -(MB2_MAGIC + MB2_ARCH + MB2_HDR_LEN)

mb2_start:
    .long MB2_MAGIC
    .long MB2_ARCH
    .long MB2_HDR_LEN
    .long MB2_CHECKSUM

    /* End tag: type=0, flags=0, size=8 */
    .word 0
    .word 0
    .long 8
mb2_end:

.section .text, "ax"
.code32
.global _start
.extern kernel_main

_start:
    cli

    /* Set up a temporary 32-bit stack */
    mov esp, offset stack_top

    /* Save Multiboot2 registers for later use:
     * EAX = magic, EBX = multiboot info pointer (physical)
     */
    mov dword ptr [mb2_magic], eax
    mov dword ptr [mb2_info],  ebx

    /* Load flat GDT and refresh segments */
    lgdt [gdt_ptr]
    ljmp 0x08, .flush

.flush:
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov fs, ax
    mov gs, ax

    /* Call kernel_main(uint32_t magic, uintptr_t info) */
    push dword ptr [mb2_info]
    push dword ptr [mb2_magic]
    call kernel_main

.hang:
    hlt
    jmp .hang

/* -------------------- GDT -------------------- */
.align 16
gdt:
    .quad 0x0000000000000000
    /* 0x08: 32-bit code segment */
    .quad 0x00CF9A000000FFFF
    /* 0x10: data segment */
    .quad 0x00CF92000000FFFF
gdt_end:

gdt_ptr:
    .word (gdt_end - gdt - 1)
    .long gdt

/* -------------------- BSS -------------------- */
.section .bss
.align 16
mb2_magic:
    .skip 4
mb2_info:
    .skip 4

.align 16
stack_bottom:
    .skip 16384
stack_top:

.section .note.GNU-stack,"",@progbits

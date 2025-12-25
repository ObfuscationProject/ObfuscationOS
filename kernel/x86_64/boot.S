/*
 * Multiboot2 + long mode bootstrap (x86_64)
 * - GRUB enters us in 32-bit protected mode.
 * - We set up minimal paging (identity map first 1GiB using 2MiB pages),
 *   enable long mode, then jump to 64-bit C++ kernel_main.
 *
 * All comments are in English as requested.
 */

.intel_syntax noprefix

.section .multiboot, "a"
.align 8

/* Multiboot2 header (must appear early in the image) */
.set MB2_MAGIC,        0xE85250D6
.set MB2_ARCH,         0          /* 0 = i386 (used also for x86_64 kernels in practice) */
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
    mov esp, offset stack32_top

    /* (Optional) Save Multiboot2 registers for later use:
     * EAX = magic, EBX = multiboot info pointer (physical)
     */
    mov dword ptr [mb2_magic], eax
    mov dword ptr [mb2_info],  ebx

    call setup_page_tables
    call enable_long_mode

    /* Load GDT suitable for long mode and do a far jump to 64-bit code segment */
    lgdt [gdt64_ptr]
    ljmp 0x08, long_mode_start

/* -------------------- 32-bit helpers -------------------- */

setup_page_tables:
    /* pml4[0] = pdpt | present|write */
    mov eax, offset pdpt
    or eax, 0x3
    mov dword ptr [pml4 + 0], eax
    mov dword ptr [pml4 + 4], 0

    /* pdpt[0] = pd | present|write */
    mov eax, offset pd
    or eax, 0x3
    mov dword ptr [pdpt + 0], eax
    mov dword ptr [pdpt + 4], 0

    /* Fill pd with 512 entries, each mapping 2MiB (identity map 1GiB) */
    xor ecx, ecx
.fill_pd:
    mov eax, ecx
    shl eax, 21                /* eax = ecx * 2MiB */
    or eax, 0x83               /* present|write|huge(2MiB) */
    mov dword ptr [pd + ecx*8 + 0], eax
    mov dword ptr [pd + ecx*8 + 4], 0
    inc ecx
    cmp ecx, 512
    jne .fill_pd
    ret

enable_long_mode:
    /* Load CR3 with PML4 base */
    mov eax, offset pml4
    mov cr3, eax

    /* Enable PAE (CR4.PAE = bit 5) + enable SSE OS support bits (OSFXSR, OSXMMEXCPT) */
    mov eax, cr4
    or eax, (1 << 5)           /* PAE */
    or eax, (1 << 9)           /* OSFXSR */
    or eax, (1 << 10)          /* OSXMMEXCPT */
    mov cr4, eax

    /* Enable long mode (EFER.LME = bit 8) */
    mov ecx, 0xC0000080        /* IA32_EFER */
    rdmsr
    or eax, (1 << 8)
    wrmsr

    /* Enable paging (CR0.PG = bit 31), and make sure EM is cleared for SSE */
    mov eax, cr0
    and eax, ~(1 << 2)         /* CR0.EM = 0 */
    or  eax, (1 << 1)          /* CR0.MP = 1 */
    or  eax, (1 << 31)         /* CR0.PG = 1 */
    mov cr0, eax

    ret

/* -------------------- 64-bit entry -------------------- */

.code64
long_mode_start:
    /* Reload segment selectors (data = 0x10) */
    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov fs, ax
    mov gs, ax

    /* Switch to 64-bit stack, keep 16-byte alignment before call */
    mov rsp, offset stack64_top
    and rsp, -16

    call kernel_main

.hang:
    hlt
    jmp .hang

/* -------------------- GDT -------------------- */
.align 16
gdt64:
    .quad 0x0000000000000000
    /* 0x08: 64-bit code segment */
    .quad 0x00AF9A000000FFFF
    /* 0x10: data segment */
    .quad 0x00AF92000000FFFF
gdt64_end:

gdt64_ptr:
    .word (gdt64_end - gdt64 - 1)
    .long gdt64

/* -------------------- BSS -------------------- */
.section .bss
.align 4096
pml4:
    .skip 4096
pdpt:
    .skip 4096
pd:
    .skip 4096

.align 16
mb2_magic:
    .skip 4
mb2_info:
    .skip 4

/* Separate 32-bit and 64-bit stacks (simple, safe for now) */
.align 16
stack32_bottom:
    .skip 16384
stack32_top:

.align 16
stack64_bottom:
    .skip 16384
stack64_top:

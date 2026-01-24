.intel_syntax noprefix

.section .ap_trampoline, "ax"
.global ap_trampoline_begin
.global ap_trampoline_end
.set AP_PARAMS_PHYS, 0x8000
.set TRAMP_PHYS, 0x7000

ap_trampoline_begin:

.code16
ap_start16:
    mov al, 'A'
    out 0xE9, al

    /* Enable A20 (Fast A20 Gate, port 0x92) */
    in  al, 0x92
    or  al, 0x02        /* set A20 enable bit */
    and al, 0xFE        /* keep reset bit cleared */
    out 0x92, al
    
    cli
    mov ax, cs
    mov ds, ax
    mov es, ax
    mov ss, ax
    mov sp, 0x9000

    /* Get current IP into BX (position-independent base) */
    call 1f
1:  pop bx

    /* Build gdt32_desc.base = (CS<<4) + (gdt32 - ap_trampoline_begin) */
    mov ax, cs
    movzx eax, ax
    shl eax, 4
    add eax, (gdt32 - ap_trampoline_begin)

    mov di, bx
    add di, (gdt32_desc - 1b)
    /* limit already encoded, just patch base */
    mov dword ptr [di + 2], eax

    lgdt [di]

    mov eax, cr0
    or eax, 1
    mov cr0, eax
    ljmp 0x08, (TRAMP_PHYS + (ap_pm32 - ap_trampoline_begin))

/* ---------------- 32-bit protected mode ---------------- */
.code32
ap_pm32:
    mov al, 'B'
    out 0xE9, al

    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax

    /* Build gdt64_desc.base = tramp_base + (gdt64 - ap_trampoline_begin) */
    call 2f
2:  pop ebx
    mov eax, ebx
    sub eax, (2b - ap_trampoline_begin)   /* eax = trampoline_base (linear) */
    add eax, (gdt64 - ap_trampoline_begin)

    lea edi, [ebx + (gdt64_desc - 2b)]
    mov dword ptr [edi + 2], eax
    lgdt [edi]

    /* Load CR3 from AP_PARAMS_PHYS + 0 (pml4_phys low32) */
    mov eax, dword ptr [AP_PARAMS_PHYS + 0]
    mov cr3, eax

    mov al, '1'
    out 0xE9, al

    mov eax, cr4
    or eax, (1 << 5)
    mov cr4, eax

    mov al, '2'
    out 0xE9, al

    mov ecx, 0xC0000080
    rdmsr
    or eax, (1 << 8)
    wrmsr

    mov al, '3'
    out 0xE9, al

    mov eax, cr0
    or eax, (1 << 31)
    mov cr0, eax

    mov al, '4'
    out 0xE9, al

    ljmp 0x08, (TRAMP_PHYS + (ap_lm64 - ap_trampoline_begin))

/* ---------------- 64-bit long mode ---------------- */
.code64
ap_lm64:
    mov al, 'C'
    out 0xE9, al

    mov ax, 0x10
    mov ds, ax
    mov es, ax
    mov ss, ax

    mov rsp, qword ptr [AP_PARAMS_PHYS + 16]
    and rsp, -16

    mov edi, dword ptr [AP_PARAMS_PHYS + 24]
    mov rax, qword ptr [AP_PARAMS_PHYS + 8]
    call rax

.hang:
    hlt
    jmp .hang

/* ---------------- GDT data (PIC) ---------------- */
.align 8
gdt32:
    .quad 0
    .quad 0x00CF9A000000FFFF
    .quad 0x00CF92000000FFFF
gdt32_end:

gdt32_desc:
    .word (gdt32_end - gdt32 - 1)
    .long 0x00000000   /* base patched at runtime */

.align 8
gdt64:
    .quad 0
    .quad 0x00AF9A000000FFFF
    .quad 0x00AF92000000FFFF
gdt64_end:

gdt64_desc:
    .word (gdt64_end - gdt64 - 1)
    .long 0x00000000   /* base patched at runtime */

ap_trampoline_end:

.section .note.GNU-stack,"",@progbits

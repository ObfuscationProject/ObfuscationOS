.intel_syntax noprefix
.section .text, "ax"
.code32
.global context_switch
.type context_switch, @function

/* void context_switch(Context* old, Context* new) */
context_switch:
    mov eax, [esp + 4]
    mov edx, [esp + 8]

    /* save callee-saved + esp + resume eip */
    mov [eax + 0x00], ebx
    mov [eax + 0x04], ebp
    mov [eax + 0x08], esi
    mov [eax + 0x0C], edi
    mov [eax + 0x10], esp
    mov ecx, offset .resume
    mov [eax + 0x14], ecx

    /* restore */
    mov ebx, [edx + 0x00]
    mov ebp, [edx + 0x04]
    mov esi, [edx + 0x08]
    mov edi, [edx + 0x0C]
    mov esp, [edx + 0x10]
    jmp dword ptr [edx + 0x14]

.resume:
    sti
    ret

.section .note.GNU-stack,"",@progbits

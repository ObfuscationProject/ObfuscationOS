.section .text
.code32
// cdecl arguments remain on the caller's stack. Preserve every callee-saved
// register even when it carries one of the six native syscall arguments.
.macro SYSCALL_WRAPPER count
.global ok_syscall\count
.type ok_syscall\count, @function
ok_syscall\count:
    push %ebp
    push %edi
    push %esi
    push %ebx
    mov 20(%esp), %eax
.if \count > 0
    mov 24(%esp), %ebx
.endif
.if \count > 1
    mov 28(%esp), %ecx
.endif
.if \count > 2
    mov 32(%esp), %edx
.endif
.if \count > 3
    mov 36(%esp), %esi
.endif
.if \count > 4
    mov 40(%esp), %edi
.endif
.if \count > 5
    mov 44(%esp), %ebp
.endif
    int $0x80
    pop %ebx
    pop %esi
    pop %edi
    pop %ebp
    ret
.size ok_syscall\count, . - ok_syscall\count
.endm
.irp count,0,1,2,3,4,5,6
    SYSCALL_WRAPPER \count
.endr
.section .note.GNU-stack,"",@progbits

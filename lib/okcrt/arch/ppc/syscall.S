.section .text
// The native ABI returns a signed result in r3; it does not use the Linux
// PowerPC CR0.SO errno convention. These leaf wrappers preserve the SysV ABI.
.macro SYSCALL_WRAPPER count
.global ok_syscall\count
.type ok_syscall\count,@function
ok_syscall\count:
    mr 0,3
.if \count > 0
    mr 3,4
.endif
.if \count > 1
    mr 4,5
.endif
.if \count > 2
    mr 5,6
.endif
.if \count > 3
    mr 6,7
.endif
.if \count > 4
    mr 7,8
.endif
.if \count > 5
    mr 8,9
.endif
    sc
    blr
.size ok_syscall\count,.-ok_syscall\count
.endm
.irp count,0,1,2,3,4,5,6
    SYSCALL_WRAPPER \count
.endr
.section .note.GNU-stack,"",@progbits

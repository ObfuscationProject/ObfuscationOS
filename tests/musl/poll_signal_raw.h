#ifndef POLL_SIGNAL_RAW_H
#define POLL_SIGNAL_RAW_H
/* Six explicit Linux arguments. o32 arguments five/six occupy the user stack;
 * pselect's sixth argument is null, so no temporary signal mask is requested. */
extern long poll_signal_raw(unsigned long,const unsigned long *,unsigned long);
extern unsigned char poll_signal_site[],poll_signal_resume[];
#if defined(__arm__)
extern long poll_signal_thumb(unsigned long,const unsigned long *,unsigned long);
extern unsigned char poll_signal_thumb_site[],poll_signal_thumb_resume[];
#endif
__asm__(
".text\n.global poll_signal_raw\n.global poll_signal_site\n.global poll_signal_resume\n"
#if defined(__x86_64__)
"poll_signal_raw:\n mov %rdi,%rax\n mov %rsi,%r11\n mov 0(%r11),%rdi\n mov 8(%r11),%rsi\n mov 16(%r11),%rdx\n mov 24(%r11),%r10\n mov 32(%r11),%r8\n mov 40(%r11),%r9\n"
"poll_signal_site:\n syscall\npoll_signal_resume:\n ret\n"
#elif defined(__i386__)
"poll_signal_raw:\n push %ebx\n push %esi\n push %edi\n push %ebp\n mov 20(%esp),%eax\n mov 24(%esp),%ebp\n mov 0(%ebp),%ebx\n mov 4(%ebp),%ecx\n mov 8(%ebp),%edx\n mov 12(%ebp),%esi\n mov 16(%ebp),%edi\n mov 20(%ebp),%ebp\n"
"poll_signal_site:\n int $0x80\npoll_signal_resume:\n pop %ebp\n pop %edi\n pop %esi\n pop %ebx\n ret\n"
#elif defined(__aarch64__)
".balign 4\npoll_signal_raw:\n mov x8,x0\n mov x9,x1\n ldp x0,x1,[x9]\n ldp x2,x3,[x9,#16]\n ldp x4,x5,[x9,#32]\n"
"poll_signal_site:\n svc #0\npoll_signal_resume:\n ret\n"
#elif defined(__arm__)
".syntax unified\n.arm\n.balign 4\n.type poll_signal_raw,%function\npoll_signal_raw:\n push {r4,r5,r6,r7,r8,lr}\n mov r7,r0\n mov r6,r1\n ldmia r6,{r0,r1,r2,r3,r4,r5}\n"
"poll_signal_site:\n svc #0\npoll_signal_resume:\n pop {r4,r5,r6,r7,r8,pc}\n"
".thumb\n.balign 2\n.global poll_signal_thumb\n.type poll_signal_thumb,%function\n.thumb_func\npoll_signal_thumb:\n push {r4,r5,r6,r7,r8,lr}\n mov r7,r0\n mov r6,r1\n ldmia r6,{r0,r1,r2,r3,r4,r5}\n"
".global poll_signal_thumb_site\npoll_signal_thumb_site:\n svc #0\n.global poll_signal_thumb_resume\npoll_signal_thumb_resume:\n pop {r4,r5,r6,r7,r8,pc}\n.arm\n"
#elif defined(__riscv)
".option push\n.option norelax\n.option norvc\n.balign 4\npoll_signal_raw:\n mv a7,a0\n mv t0,a1\n"
#if __riscv_xlen == 64
" ld a0,0(t0)\n ld a1,8(t0)\n ld a2,16(t0)\n ld a3,24(t0)\n ld a4,32(t0)\n ld a5,40(t0)\n"
#else
" lw a0,0(t0)\n lw a1,4(t0)\n lw a2,8(t0)\n lw a3,12(t0)\n lw a4,16(t0)\n lw a5,20(t0)\n"
#endif
"poll_signal_site:\n ecall\npoll_signal_resume:\n ret\n.option pop\n"
#elif defined(__loongarch64)
".balign 4\npoll_signal_raw:\n move $a7,$a0\n move $t0,$a1\n ld.d $a0,$t0,0\n ld.d $a1,$t0,8\n ld.d $a2,$t0,16\n ld.d $a3,$t0,24\n ld.d $a4,$t0,32\n ld.d $a5,$t0,40\n"
"poll_signal_site:\n syscall 0\npoll_signal_resume:\n jr $ra\n"
#elif defined(__mips__)
".set push\n.set noreorder\n.balign 4\npoll_signal_raw:\n move $2,$4\n move $10,$5\n"
#if defined(__mips64)
" ld $4,0($10)\n ld $5,8($10)\n ld $6,16($10)\n ld $7,24($10)\n ld $8,32($10)\n ld $9,40($10)\n"
#else
" addiu $sp,$sp,-32\n lw $4,0($10)\n lw $5,4($10)\n lw $6,8($10)\n lw $7,12($10)\n lw $8,16($10)\n lw $9,20($10)\n sw $8,16($sp)\n sw $9,20($sp)\n"
#endif
"poll_signal_site:\n syscall\npoll_signal_resume:\n beqz $7,1f\n nop\n"
#if defined(__mips64)
" dsubu $2,$0,$2\n1: jr $ra\n nop\n"
#else
" subu $2,$0,$2\n1: addiu $sp,$sp,32\n jr $ra\n nop\n"
#endif
".set pop\n"
#elif defined(__powerpc__)
".balign 4\npoll_signal_raw:\n mr 0,3\n mr 11,4\n mfcr 9\n lis 10,0x1000\n andc 9,9,10\n cmpwi 5,0\n beq 1f\n or 9,9,10\n1: mtcrf 128,9\n lwz 3,0(11)\n lwz 4,4(11)\n lwz 5,8(11)\n lwz 6,12(11)\n lwz 7,16(11)\n lwz 8,20(11)\n"
"poll_signal_site:\n sc\npoll_signal_resume:\n bns 2f\n neg 3,3\n2: blr\n"
#endif
#if defined(__arm__)
".section .note.GNU-stack,\"\",%progbits\n.text\n"
#else
".section .note.GNU-stack,\"\",@progbits\n.text\n"
#endif
);
#endif

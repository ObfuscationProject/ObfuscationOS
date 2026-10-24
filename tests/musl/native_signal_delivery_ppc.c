#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <signal.h>
#include <ucontext.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

#if !defined(__powerpc__) || __SIZEOF_POINTER__ != 4 || __BYTE_ORDER__ != __ORDER_BIG_ENDIAN__ || !defined(__NO_FPRS__)
#error "Native PPC32 big-endian scalar soft-float e500v2 guest required"
#endif
struct mask64 { uint32_t word[2]; };
struct action { uint32_t handler, flags, restorer; struct mask64 mask; };
struct context { uint32_t gpr[48]; unsigned char fp[264]; uint32_t pad[2]; uint32_t upper[32], acc[2], spefscr; unsigned char tail[388]; } __attribute__((aligned(16)));
struct legacy { uint32_t unused[4], signal, handler, low_mask, regs; };
_Static_assert(sizeof(struct context)==992 && offsetof(struct context,upper)==464 && offsetof(struct context,spefscr)==600,"PPC SPE context layout");
_Static_assert(sizeof(mcontext_t)==992 && offsetof(mcontext_t,gregs)==0 && offsetof(mcontext_t,fpregs)==192 && offsetof(mcontext_t,vrregs)==464,"musl mcontext");
_Static_assert(sizeof(ucontext_t)==1184 && offsetof(ucontext_t,uc_regs)==48 && offsetof(ucontext_t,uc_sigmask)==52 && offsetof(ucontext_t,uc_mcontext)==192,"native ucontext");
_Static_assert(sizeof(struct sigcontext)==32 && offsetof(struct sigcontext,regs)==28 && offsetof(struct sigcontext,oldmask)==24,"native legacy prefix");
_Static_assert(sizeof(struct action)==20 && offsetof(struct action,mask)==12 && sizeof(stack_t)==12,"native action and stack");
_Static_assert(offsetof(siginfo_t,si_code)==8 && offsetof(siginfo_t,si_pid)==12 && offsetof(siginfo_t,si_uid)==16,"native siginfo");
_Static_assert(SYS_sigreturn==119 && SYS_rt_sigreturn==172 && SYS_tgkill==250 && SYS_exit_group==234,"PPC assembly syscall constants");
enum { ORDINARY, NODEFER, NESTED, RESET, STATE_KEEP, STATE_EDIT, STATE_RELOC, STATE_NOSPE, STATE_PRIVILEGE,
       BAD_SP=10, BAD_PC, BAD_CONTEXT, BAD_ALIGNMENT, BAD_MSR, BAD_SPEFSCR, BAD_FP, BAD_TAIL, BAD_GREG, BAD_UCLINK, BAD_PC_ALIGNMENT, BAD_RETURN };
static volatile int mode, realtime, handled, nested, nested_nodefer, active_depth, failure;
static long pid, tid, uid;
static uintptr_t restorers[2];
static const struct mask64 high_mask={{0x80000000u,0x80000100u}};
static _Alignas(16) unsigned char edited_stack[2048];
static _Alignas(16) struct context relocated;
volatile uintptr_t state_sp;
_Alignas(8) uint32_t initial_spe[32][2];
const _Alignas(8) uint32_t initial_acc[2]={0x12345678,0x9abcdef0};
_Alignas(8) volatile uint32_t observed_spe[32][2], observed_acc[2];
volatile uint32_t observed_control[5], observed_cookies[2], observed_path;
extern void signal_entry(void), action_restorer(void), state_probe(void), state_resume(void), state_resume_edited(void), invalid_return(long);
void entry_common(int,void *,void *,void *,uintptr_t,uintptr_t,uint32_t,uint32_t);
__asm__(
    ".text\n"
    ".machine e500\n"
    ".balign 16\n"
    ".global signal_entry\n"
    ".type signal_entry,@function\n"
    "signal_entry:\n"
    "mr 7,1\n"
    "mflr 8\n"
    "mr 9,2\n"
    "mr 10,13\n"
    "stwu 1,-32(1)\n"
    "stw 8,20(1)\n"
    "bl entry_common\n"
    "lis 0,0xdead\n"
    "ori 0,0,0xbeef\n"
    "evmergelo 0,0,0\n"
    "evmergelo 1,0,1\n"
    "evmergelo 2,0,2\n"
    "evmergelo 3,0,3\n"
    "evmergelo 4,0,4\n"
    "evmergelo 5,0,5\n"
    "evmergelo 6,0,6\n"
    "evmergelo 7,0,7\n"
    "evmergelo 8,0,8\n"
    "evmergelo 9,0,9\n"
    "evmergelo 10,0,10\n"
    "evmergelo 11,0,11\n"
    "evmergelo 12,0,12\n"
    "evmergelo 13,0,13\n"
    "evmergelo 14,0,14\n"
    "evmergelo 15,0,15\n"
    "evmergelo 16,0,16\n"
    "evmergelo 17,0,17\n"
    "evmergelo 18,0,18\n"
    "evmergelo 19,0,19\n"
    "evmergelo 20,0,20\n"
    "evmergelo 21,0,21\n"
    "evmergelo 22,0,22\n"
    "evmergelo 23,0,23\n"
    "evmergelo 24,0,24\n"
    "evmergelo 25,0,25\n"
    "evmergelo 26,0,26\n"
    "evmergelo 27,0,27\n"
    "evmergelo 28,0,28\n"
    "evmergelo 29,0,29\n"
    "evmergelo 30,0,30\n"
    "evmergelo 31,0,31\n"
    "evmra 0,0\n"
    "li 0,0\n"
    "mtspr 512,0\n"
    "mtctr 0\n"
    "mtxer 0\n"
    "mtcr 0\n"
    "lwz 0,20(1)\n"
    "mtlr 0\n"
    "addi 1,1,32\n"
    "blr\n"
    ".size signal_entry,.-signal_entry\n"
    ".global invalid_return\n"
    ".type invalid_return,@function\n"
    "invalid_return:\n"
    "mr 0,3\n"
    "li 1,0\n"
    "sc\n"
    "trap\n"
    ".size invalid_return,.-invalid_return\n"
    ".global action_restorer\n"
    ".type action_restorer,@function\n"
    "action_restorer:\n"
    "li 3,90\n"
    "li 0,234\n"
    "sc\n"
    "trap\n"
    ".size action_restorer,.-action_restorer\n"
    ".global state_probe\n"
    ".type state_probe,@function\n"
    "state_probe:\n"
    "mr 7,1\n"
    "clrrwi 1,1,4\n"
    "stwu 1,-384(1)\n"
    "evstdd 0,0(1)\n"
    "evstdd 1,8(1)\n"
    "evstdd 2,16(1)\n"
    "evstdd 3,24(1)\n"
    "evstdd 4,32(1)\n"
    "evstdd 5,40(1)\n"
    "evstdd 6,48(1)\n"
    "evstdd 7,56(1)\n"
    "evstdd 8,64(1)\n"
    "evstdd 9,72(1)\n"
    "evstdd 10,80(1)\n"
    "evstdd 11,88(1)\n"
    "evstdd 12,96(1)\n"
    "evstdd 13,104(1)\n"
    "evstdd 14,112(1)\n"
    "evstdd 15,120(1)\n"
    "evstdd 16,128(1)\n"
    "evstdd 17,136(1)\n"
    "evstdd 18,144(1)\n"
    "evstdd 19,152(1)\n"
    "evstdd 20,160(1)\n"
    "evstdd 21,168(1)\n"
    "evstdd 22,176(1)\n"
    "evstdd 23,184(1)\n"
    "evstdd 24,192(1)\n"
    "evstdd 25,200(1)\n"
    "evstdd 26,208(1)\n"
    "evstdd 27,216(1)\n"
    "evstdd 28,224(1)\n"
    "evstdd 29,232(1)\n"
    "evstdd 30,240(1)\n"
    "evstdd 31,248(1)\n"
    "stw 7,296(1)\n"
    "mflr 0\n"
    "stw 0,272(1)\n"
    "mfctr 0\n"
    "stw 0,276(1)\n"
    "mfcr 0\n"
    "stw 0,280(1)\n"
    "mfxer 0\n"
    "stw 0,284(1)\n"
    "mfspr 0,512\n"
    "stw 0,288(1)\n"
    "evxor 0,0,0\n"
    "evmwumiaa 0,0,0\n"
    "addi 12,1,256\n"
    "evstdd 0,0(12)\n"
    "lis 11,state_sp@ha\n"
    "addi 11,11,state_sp@l\n"
    "stw 1,0(11)\n"
    "lis 12,initial_spe@ha\n"
    "addi 12,12,initial_spe@l\n"
    "stw 1,12(12)\n"
    "lis 0,0x6b7c\n"
    "ori 0,0,0x8d9e\n"
    "stw 0,-4(1)\n"
    "stw 0,-8(1)\n"
    "stw 0,-12(1)\n"
    "stw 0,-16(1)\n"
    "stw 0,-20(1)\n"
    "stw 0,-24(1)\n"
    "stw 0,-28(1)\n"
    "stw 0,-32(1)\n"
    "stw 0,-36(1)\n"
    "stw 0,-40(1)\n"
    "stw 0,-44(1)\n"
    "stw 0,-48(1)\n"
    "stw 0,-52(1)\n"
    "stw 0,-56(1)\n"
    "stw 0,-60(1)\n"
    "stw 0,-64(1)\n"
    "stw 0,-68(1)\n"
    "stw 0,-72(1)\n"
    "stw 0,-76(1)\n"
    "stw 0,-80(1)\n"
    "stw 0,-84(1)\n"
    "stw 0,-88(1)\n"
    "stw 0,-92(1)\n"
    "stw 0,-96(1)\n"
    "stw 0,-100(1)\n"
    "stw 0,-104(1)\n"
    "stw 0,-108(1)\n"
    "stw 0,-112(1)\n"
    "stw 0,-116(1)\n"
    "stw 0,-120(1)\n"
    "stw 0,-124(1)\n"
    "stw 0,-128(1)\n"
    "stw 0,-132(1)\n"
    "stw 0,-136(1)\n"
    "stw 0,-140(1)\n"
    "stw 0,-144(1)\n"
    "stw 0,-148(1)\n"
    "stw 0,-152(1)\n"
    "stw 0,-156(1)\n"
    "stw 0,-160(1)\n"
    "stw 0,-164(1)\n"
    "stw 0,-168(1)\n"
    "stw 0,-172(1)\n"
    "stw 0,-176(1)\n"
    "stw 0,-180(1)\n"
    "stw 0,-184(1)\n"
    "stw 0,-188(1)\n"
    "stw 0,-192(1)\n"
    "stw 0,-196(1)\n"
    "stw 0,-200(1)\n"
    "stw 0,-204(1)\n"
    "stw 0,-208(1)\n"
    "stw 0,-212(1)\n"
    "stw 0,-216(1)\n"
    "stw 0,-220(1)\n"
    "stw 0,-224(1)\n"
    "lis 0,0x1357\n"
    "ori 0,0,0x2468\n"
    "stw 0,304(1)\n"
    "lis 0,0x2468\n"
    "ori 0,0,0x1357\n"
    "stw 0,308(1)\n"
    "lis 11,initial_acc@ha\n"
    "addi 11,11,initial_acc@l\n"
    "evldd 0,0(11)\n"
    "evmra 0,0\n"
    "lis 0,0x8000\n"
    "ori 0,0,0x0001\n"
    "mtspr 512,0\n"
    "lis 0,0xa000\n"
    "ori 0,0,0x007f\n"
    "mtxer 0\n"
    "lis 0,0x5566\n"
    "ori 0,0,0x7788\n"
    "mtctr 0\n"
    "lis 0,0xabcd\n"
    "ori 0,0,0xef00\n"
    "mtlr 0\n"
    "lis 0,0x5a6b\n"
    "ori 0,0,0x7c8d\n"
    "mtcr 0\n"
    "evldd 0,0(12)\n"
    "evldd 1,8(12)\n"
    "evldd 2,16(12)\n"
    "evldd 3,24(12)\n"
    "evldd 4,32(12)\n"
    "evldd 5,40(12)\n"
    "evldd 6,48(12)\n"
    "evldd 7,56(12)\n"
    "evldd 8,64(12)\n"
    "evldd 9,72(12)\n"
    "evldd 10,80(12)\n"
    "evldd 11,88(12)\n"
    "evldd 13,104(12)\n"
    "evldd 14,112(12)\n"
    "evldd 15,120(12)\n"
    "evldd 16,128(12)\n"
    "evldd 17,136(12)\n"
    "evldd 18,144(12)\n"
    "evldd 19,152(12)\n"
    "evldd 20,160(12)\n"
    "evldd 21,168(12)\n"
    "evldd 22,176(12)\n"
    "evldd 23,184(12)\n"
    "evldd 24,192(12)\n"
    "evldd 25,200(12)\n"
    "evldd 26,208(12)\n"
    "evldd 27,216(12)\n"
    "evldd 28,224(12)\n"
    "evldd 29,232(12)\n"
    "evldd 30,240(12)\n"
    "evldd 31,248(12)\n"
    "evldd 12,96(12)\n"
    "sc\n"
    ".global state_resume\n"
    "state_resume:\n"
    "b observe_keep\n"
    ".global state_resume_edited\n"
    "state_resume_edited:\n"
    "b observe_edit\n"
    "observe_keep:\n"
    "stwu 1,-384(1)\n"
    "evstdd 0,0(1)\n"
    "evstdd 1,8(1)\n"
    "evstdd 2,16(1)\n"
    "evstdd 3,24(1)\n"
    "evstdd 4,32(1)\n"
    "evstdd 5,40(1)\n"
    "evstdd 6,48(1)\n"
    "evstdd 7,56(1)\n"
    "evstdd 8,64(1)\n"
    "evstdd 9,72(1)\n"
    "evstdd 10,80(1)\n"
    "evstdd 11,88(1)\n"
    "evstdd 12,96(1)\n"
    "evstdd 13,104(1)\n"
    "evstdd 14,112(1)\n"
    "evstdd 15,120(1)\n"
    "evstdd 16,128(1)\n"
    "evstdd 17,136(1)\n"
    "evstdd 18,144(1)\n"
    "evstdd 19,152(1)\n"
    "evstdd 20,160(1)\n"
    "evstdd 21,168(1)\n"
    "evstdd 22,176(1)\n"
    "evstdd 23,184(1)\n"
    "evstdd 24,192(1)\n"
    "evstdd 25,200(1)\n"
    "evstdd 26,208(1)\n"
    "evstdd 27,216(1)\n"
    "evstdd 28,224(1)\n"
    "evstdd 29,232(1)\n"
    "evstdd 30,240(1)\n"
    "evstdd 31,248(1)\n"
    "addi 10,1,384\n"
    "stw 10,12(1)\n"
    "lis 11,observed_spe@ha\n"
    "addi 11,11,observed_spe@l\n"
    "lwz 10,0(1)\n"
    "stw 10,0(11)\n"
    "lwz 10,4(1)\n"
    "stw 10,4(11)\n"
    "lwz 10,8(1)\n"
    "stw 10,8(11)\n"
    "lwz 10,12(1)\n"
    "stw 10,12(11)\n"
    "lwz 10,16(1)\n"
    "stw 10,16(11)\n"
    "lwz 10,20(1)\n"
    "stw 10,20(11)\n"
    "lwz 10,24(1)\n"
    "stw 10,24(11)\n"
    "lwz 10,28(1)\n"
    "stw 10,28(11)\n"
    "lwz 10,32(1)\n"
    "stw 10,32(11)\n"
    "lwz 10,36(1)\n"
    "stw 10,36(11)\n"
    "lwz 10,40(1)\n"
    "stw 10,40(11)\n"
    "lwz 10,44(1)\n"
    "stw 10,44(11)\n"
    "lwz 10,48(1)\n"
    "stw 10,48(11)\n"
    "lwz 10,52(1)\n"
    "stw 10,52(11)\n"
    "lwz 10,56(1)\n"
    "stw 10,56(11)\n"
    "lwz 10,60(1)\n"
    "stw 10,60(11)\n"
    "lwz 10,64(1)\n"
    "stw 10,64(11)\n"
    "lwz 10,68(1)\n"
    "stw 10,68(11)\n"
    "lwz 10,72(1)\n"
    "stw 10,72(11)\n"
    "lwz 10,76(1)\n"
    "stw 10,76(11)\n"
    "lwz 10,80(1)\n"
    "stw 10,80(11)\n"
    "lwz 10,84(1)\n"
    "stw 10,84(11)\n"
    "lwz 10,88(1)\n"
    "stw 10,88(11)\n"
    "lwz 10,92(1)\n"
    "stw 10,92(11)\n"
    "lwz 10,96(1)\n"
    "stw 10,96(11)\n"
    "lwz 10,100(1)\n"
    "stw 10,100(11)\n"
    "lwz 10,104(1)\n"
    "stw 10,104(11)\n"
    "lwz 10,108(1)\n"
    "stw 10,108(11)\n"
    "lwz 10,112(1)\n"
    "stw 10,112(11)\n"
    "lwz 10,116(1)\n"
    "stw 10,116(11)\n"
    "lwz 10,120(1)\n"
    "stw 10,120(11)\n"
    "lwz 10,124(1)\n"
    "stw 10,124(11)\n"
    "lwz 10,128(1)\n"
    "stw 10,128(11)\n"
    "lwz 10,132(1)\n"
    "stw 10,132(11)\n"
    "lwz 10,136(1)\n"
    "stw 10,136(11)\n"
    "lwz 10,140(1)\n"
    "stw 10,140(11)\n"
    "lwz 10,144(1)\n"
    "stw 10,144(11)\n"
    "lwz 10,148(1)\n"
    "stw 10,148(11)\n"
    "lwz 10,152(1)\n"
    "stw 10,152(11)\n"
    "lwz 10,156(1)\n"
    "stw 10,156(11)\n"
    "lwz 10,160(1)\n"
    "stw 10,160(11)\n"
    "lwz 10,164(1)\n"
    "stw 10,164(11)\n"
    "lwz 10,168(1)\n"
    "stw 10,168(11)\n"
    "lwz 10,172(1)\n"
    "stw 10,172(11)\n"
    "lwz 10,176(1)\n"
    "stw 10,176(11)\n"
    "lwz 10,180(1)\n"
    "stw 10,180(11)\n"
    "lwz 10,184(1)\n"
    "stw 10,184(11)\n"
    "lwz 10,188(1)\n"
    "stw 10,188(11)\n"
    "lwz 10,192(1)\n"
    "stw 10,192(11)\n"
    "lwz 10,196(1)\n"
    "stw 10,196(11)\n"
    "lwz 10,200(1)\n"
    "stw 10,200(11)\n"
    "lwz 10,204(1)\n"
    "stw 10,204(11)\n"
    "lwz 10,208(1)\n"
    "stw 10,208(11)\n"
    "lwz 10,212(1)\n"
    "stw 10,212(11)\n"
    "lwz 10,216(1)\n"
    "stw 10,216(11)\n"
    "lwz 10,220(1)\n"
    "stw 10,220(11)\n"
    "lwz 10,224(1)\n"
    "stw 10,224(11)\n"
    "lwz 10,228(1)\n"
    "stw 10,228(11)\n"
    "lwz 10,232(1)\n"
    "stw 10,232(11)\n"
    "lwz 10,236(1)\n"
    "stw 10,236(11)\n"
    "lwz 10,240(1)\n"
    "stw 10,240(11)\n"
    "lwz 10,244(1)\n"
    "stw 10,244(11)\n"
    "lwz 10,248(1)\n"
    "stw 10,248(11)\n"
    "lwz 10,252(1)\n"
    "stw 10,252(11)\n"
    "lis 11,observed_control@ha\n"
    "addi 11,11,observed_control@l\n"
    "mflr 10\n"
    "stw 10,0(11)\n"
    "mfctr 10\n"
    "stw 10,4(11)\n"
    "mfcr 10\n"
    "stw 10,8(11)\n"
    "mfxer 10\n"
    "stw 10,12(11)\n"
    "mfspr 10,512\n"
    "stw 10,16(11)\n"
    "lis 11,observed_cookies@ha\n"
    "addi 11,11,observed_cookies@l\n"
    "lwz 10,688(1)\n"
    "stw 10,0(11)\n"
    "lwz 10,692(1)\n"
    "stw 10,4(11)\n"
    "evxor 0,0,0\n"
    "evmwumiaa 0,0,0\n"
    "lis 11,observed_acc@ha\n"
    "addi 11,11,observed_acc@l\n"
    "evstdd 0,0(11)\n"
    "lis 11,observed_path@ha\n"
    "addi 11,11,observed_path@l\n"
    "li 10,1\n"
    "stw 10,0(11)\n"
    "b restore_caller\n"
    "observe_edit:\n"
    "stwu 1,-384(1)\n"
    "evstdd 0,0(1)\n"
    "evstdd 1,8(1)\n"
    "evstdd 2,16(1)\n"
    "evstdd 3,24(1)\n"
    "evstdd 4,32(1)\n"
    "evstdd 5,40(1)\n"
    "evstdd 6,48(1)\n"
    "evstdd 7,56(1)\n"
    "evstdd 8,64(1)\n"
    "evstdd 9,72(1)\n"
    "evstdd 10,80(1)\n"
    "evstdd 11,88(1)\n"
    "evstdd 12,96(1)\n"
    "evstdd 13,104(1)\n"
    "evstdd 14,112(1)\n"
    "evstdd 15,120(1)\n"
    "evstdd 16,128(1)\n"
    "evstdd 17,136(1)\n"
    "evstdd 18,144(1)\n"
    "evstdd 19,152(1)\n"
    "evstdd 20,160(1)\n"
    "evstdd 21,168(1)\n"
    "evstdd 22,176(1)\n"
    "evstdd 23,184(1)\n"
    "evstdd 24,192(1)\n"
    "evstdd 25,200(1)\n"
    "evstdd 26,208(1)\n"
    "evstdd 27,216(1)\n"
    "evstdd 28,224(1)\n"
    "evstdd 29,232(1)\n"
    "evstdd 30,240(1)\n"
    "evstdd 31,248(1)\n"
    "addi 10,1,384\n"
    "stw 10,12(1)\n"
    "lis 11,observed_spe@ha\n"
    "addi 11,11,observed_spe@l\n"
    "lwz 10,0(1)\n"
    "stw 10,0(11)\n"
    "lwz 10,4(1)\n"
    "stw 10,4(11)\n"
    "lwz 10,8(1)\n"
    "stw 10,8(11)\n"
    "lwz 10,12(1)\n"
    "stw 10,12(11)\n"
    "lwz 10,16(1)\n"
    "stw 10,16(11)\n"
    "lwz 10,20(1)\n"
    "stw 10,20(11)\n"
    "lwz 10,24(1)\n"
    "stw 10,24(11)\n"
    "lwz 10,28(1)\n"
    "stw 10,28(11)\n"
    "lwz 10,32(1)\n"
    "stw 10,32(11)\n"
    "lwz 10,36(1)\n"
    "stw 10,36(11)\n"
    "lwz 10,40(1)\n"
    "stw 10,40(11)\n"
    "lwz 10,44(1)\n"
    "stw 10,44(11)\n"
    "lwz 10,48(1)\n"
    "stw 10,48(11)\n"
    "lwz 10,52(1)\n"
    "stw 10,52(11)\n"
    "lwz 10,56(1)\n"
    "stw 10,56(11)\n"
    "lwz 10,60(1)\n"
    "stw 10,60(11)\n"
    "lwz 10,64(1)\n"
    "stw 10,64(11)\n"
    "lwz 10,68(1)\n"
    "stw 10,68(11)\n"
    "lwz 10,72(1)\n"
    "stw 10,72(11)\n"
    "lwz 10,76(1)\n"
    "stw 10,76(11)\n"
    "lwz 10,80(1)\n"
    "stw 10,80(11)\n"
    "lwz 10,84(1)\n"
    "stw 10,84(11)\n"
    "lwz 10,88(1)\n"
    "stw 10,88(11)\n"
    "lwz 10,92(1)\n"
    "stw 10,92(11)\n"
    "lwz 10,96(1)\n"
    "stw 10,96(11)\n"
    "lwz 10,100(1)\n"
    "stw 10,100(11)\n"
    "lwz 10,104(1)\n"
    "stw 10,104(11)\n"
    "lwz 10,108(1)\n"
    "stw 10,108(11)\n"
    "lwz 10,112(1)\n"
    "stw 10,112(11)\n"
    "lwz 10,116(1)\n"
    "stw 10,116(11)\n"
    "lwz 10,120(1)\n"
    "stw 10,120(11)\n"
    "lwz 10,124(1)\n"
    "stw 10,124(11)\n"
    "lwz 10,128(1)\n"
    "stw 10,128(11)\n"
    "lwz 10,132(1)\n"
    "stw 10,132(11)\n"
    "lwz 10,136(1)\n"
    "stw 10,136(11)\n"
    "lwz 10,140(1)\n"
    "stw 10,140(11)\n"
    "lwz 10,144(1)\n"
    "stw 10,144(11)\n"
    "lwz 10,148(1)\n"
    "stw 10,148(11)\n"
    "lwz 10,152(1)\n"
    "stw 10,152(11)\n"
    "lwz 10,156(1)\n"
    "stw 10,156(11)\n"
    "lwz 10,160(1)\n"
    "stw 10,160(11)\n"
    "lwz 10,164(1)\n"
    "stw 10,164(11)\n"
    "lwz 10,168(1)\n"
    "stw 10,168(11)\n"
    "lwz 10,172(1)\n"
    "stw 10,172(11)\n"
    "lwz 10,176(1)\n"
    "stw 10,176(11)\n"
    "lwz 10,180(1)\n"
    "stw 10,180(11)\n"
    "lwz 10,184(1)\n"
    "stw 10,184(11)\n"
    "lwz 10,188(1)\n"
    "stw 10,188(11)\n"
    "lwz 10,192(1)\n"
    "stw 10,192(11)\n"
    "lwz 10,196(1)\n"
    "stw 10,196(11)\n"
    "lwz 10,200(1)\n"
    "stw 10,200(11)\n"
    "lwz 10,204(1)\n"
    "stw 10,204(11)\n"
    "lwz 10,208(1)\n"
    "stw 10,208(11)\n"
    "lwz 10,212(1)\n"
    "stw 10,212(11)\n"
    "lwz 10,216(1)\n"
    "stw 10,216(11)\n"
    "lwz 10,220(1)\n"
    "stw 10,220(11)\n"
    "lwz 10,224(1)\n"
    "stw 10,224(11)\n"
    "lwz 10,228(1)\n"
    "stw 10,228(11)\n"
    "lwz 10,232(1)\n"
    "stw 10,232(11)\n"
    "lwz 10,236(1)\n"
    "stw 10,236(11)\n"
    "lwz 10,240(1)\n"
    "stw 10,240(11)\n"
    "lwz 10,244(1)\n"
    "stw 10,244(11)\n"
    "lwz 10,248(1)\n"
    "stw 10,248(11)\n"
    "lwz 10,252(1)\n"
    "stw 10,252(11)\n"
    "lis 11,observed_control@ha\n"
    "addi 11,11,observed_control@l\n"
    "mflr 10\n"
    "stw 10,0(11)\n"
    "mfctr 10\n"
    "stw 10,4(11)\n"
    "mfcr 10\n"
    "stw 10,8(11)\n"
    "mfxer 10\n"
    "stw 10,12(11)\n"
    "mfspr 10,512\n"
    "stw 10,16(11)\n"
    "lis 11,observed_cookies@ha\n"
    "addi 11,11,observed_cookies@l\n"
    "lwz 10,688(1)\n"
    "stw 10,0(11)\n"
    "lwz 10,692(1)\n"
    "stw 10,4(11)\n"
    "evxor 0,0,0\n"
    "evmwumiaa 0,0,0\n"
    "lis 11,observed_acc@ha\n"
    "addi 11,11,observed_acc@l\n"
    "evstdd 0,0(11)\n"
    "lis 11,observed_path@ha\n"
    "addi 11,11,observed_path@l\n"
    "li 10,2\n"
    "stw 10,0(11)\n"
    "b restore_caller\n"
    "restore_caller:\n"
    "lis 12,state_sp@ha\n"
    "addi 12,12,state_sp@l\n"
    "lwz 12,0(12)\n"
    "lwz 0,272(12)\n"
    "mtlr 0\n"
    "lwz 0,276(12)\n"
    "mtctr 0\n"
    "lwz 0,280(12)\n"
    "mtcr 0\n"
    "lwz 0,284(12)\n"
    "mtxer 0\n"
    "lwz 0,288(12)\n"
    "mtspr 512,0\n"
    "addi 11,12,256\n"
    "evldd 0,0(11)\n"
    "evmra 0,0\n"
    "evldd 0,0(12)\n"
    "evldd 1,8(12)\n"
    "evldd 2,16(12)\n"
    "evldd 3,24(12)\n"
    "evldd 4,32(12)\n"
    "evldd 5,40(12)\n"
    "evldd 6,48(12)\n"
    "evldd 7,56(12)\n"
    "evldd 8,64(12)\n"
    "evldd 9,72(12)\n"
    "evldd 10,80(12)\n"
    "evldd 11,88(12)\n"
    "evldd 13,104(12)\n"
    "evldd 14,112(12)\n"
    "evldd 15,120(12)\n"
    "evldd 16,128(12)\n"
    "evldd 17,136(12)\n"
    "evldd 18,144(12)\n"
    "evldd 19,152(12)\n"
    "evldd 20,160(12)\n"
    "evldd 21,168(12)\n"
    "evldd 22,176(12)\n"
    "evldd 23,184(12)\n"
    "evldd 24,192(12)\n"
    "evldd 25,200(12)\n"
    "evldd 26,208(12)\n"
    "evldd 27,216(12)\n"
    "evldd 28,224(12)\n"
    "evldd 29,232(12)\n"
    "evldd 30,240(12)\n"
    "evldd 31,248(12)\n"
    "evldd 12,96(12)\n"
    "lwz 1,296(1)\n"
    "blr\n"
    ".size state_probe,.-state_probe\n"
);

static long raw(long number,long a,long b,long c,long d)
{
    register long r0 __asm__("r0")=number,r3 __asm__("r3")=a,r4 __asm__("r4")=b,r5 __asm__("r5")=c,r6 __asm__("r6")=d;
    unsigned cr;
    __asm__ volatile("sc; mfcr %0" : "=r"(cr), "+r"(r3), "+r"(r0), "+r"(r4), "+r"(r5), "+r"(r6) : : "r7","r8","r9","r10","r11","r12","cr0","ctr","memory");
    return cr&0x10000000u ? -r3:r3;
}
static __attribute__((noinline,noreturn)) void fail(int code)
{
    if(!failure)failure=code;
    static const char pattern[]="SIGNAL_PPC_FAIL code=000 mode=00 rt=0\n";
    char text[sizeof(pattern)];
    for(unsigned i=0;i<sizeof(pattern);++i)((volatile char*)text)[i]=pattern[i];
    unsigned at=sizeof("SIGNAL_PPC_FAIL code=")-1;
    text[at]='0'+failure/100%10;text[at+1]='0'+failure/10%10;text[at+2]='0'+failure%10;
    at=sizeof("SIGNAL_PPC_FAIL code=000 mode=")-1;text[at]='0'+mode/10;text[at+1]='0'+mode%10;
    text[sizeof("SIGNAL_PPC_FAIL code=000 mode=00 rt=")-1]='0'+realtime;
    raw(SYS_write,1,(long)text,sizeof(text)-1,0);raw(SYS_exit_group,1,0,0,0);for(;;){}
}
#define CHECK(c,n) do { if(!(c))fail(n); } while(0)
static long mask(int how,const struct mask64 *set,struct mask64 *old) { return raw(SYS_rt_sigprocmask,how,(long)set,(long)old,8); }
static long action(int sig,const struct action *set,struct action *old) { return raw(SYS_rt_sigaction,sig,(long)set,(long)old,8); }
static int has(const struct mask64 *m,int sig) { return (m->word[(sig-1)/32]>>((sig-1)%32))&1; }
static int same(const struct mask64 *a,const struct mask64 *b) { return a->word[0]==b->word[0] && a->word[1]==b->word[1]; }
static struct mask64 bit(int sig) { struct mask64 r={{0}};r.word[(sig-1)/32]=1u<<((sig-1)%32);return r; }
static uint32_t edited_gpr(unsigned i) { return i==1?(uintptr_t)(edited_stack+1024):0xc1230000u+i*0x101u; }
static uint32_t edited_upper(unsigned i) { return 0xa1b20000u+i*0x101u; }
static int state_mode(void) { return mode>=STATE_KEEP && mode<=STATE_PRIVILEGE; }
static void copy_context(struct context *to,const struct context *from) { volatile unsigned char *d=(void*)to;const unsigned char *s=(const void*)from;for(unsigned i=0;i<992;++i)d[i]=s[i]; }
void entry_common(int sig,void *second,void *third,void *fourth,uintptr_t sp,uintptr_t lr,uint32_t r2,uint32_t r13)
{
    const unsigned lower=realtime?80:64,prefix=realtime?320:32;
    const uintptr_t frame=sp+lower;
    struct legacy *sc=(void*)frame;
    ucontext_t *uc=(void*)(frame+128);
    CHECK(!(sp&15) && (uintptr_t)second==frame,101);
    if(realtime)CHECK((uintptr_t)third==frame+128 && (uintptr_t)fourth==frame,102);
    struct context *mc=(void*)(uintptr_t)(realtime?(uintptr_t)uc->uc_regs:sc->regs);
    CHECK((uintptr_t)mc==frame+prefix,103);
    CHECK(*(const uint32_t*)sp==mc->gpr[1],104);
    CHECK(lr && !(lr&3) && lr!=(uintptr_t)action_restorer && !(lr>=sp && lr<sp+(realtime?1616:1312)),105);
    const volatile uint32_t *tramp=(void*)lr;
    CHECK(tramp[0]==(0x38000000u|(realtime?172:119)) && tramp[1]==0x44000002u,106);
    CHECK(!restorers[realtime] || restorers[realtime]==lr,107);restorers[realtime]=lr;
    if(realtime) {
        siginfo_t *info=second;
        CHECK(info->si_signo==sig && info->si_errno==0 && info->si_code==SI_TKILL && info->si_pid==pid && info->si_uid==uid,108);
        CHECK(uc->uc_flags==0 && !uc->uc_link && !uc->uc_stack.ss_sp && !uc->uc_stack.ss_size && uc->uc_stack.ss_flags==SS_DISABLE,109);
    } else CHECK(sc->signal==(unsigned)sig && sc->handler==(uintptr_t)signal_entry,110);
    CHECK((mc->gpr[33]&0x4000) && !(mc->gpr[33]&0x80802901),111);
    struct mask64 current={{0}};
    CHECK(mask(SIG_SETMASK,0,&current)==0 && (current.word[0]&high_mask.word[0])==high_mask.word[0] && (current.word[1]&high_mask.word[1])==high_mask.word[1],112);
    if(sig==SIGUSR2) { CHECK(has(&current,SIGUSR1) && has(&current,SIGUSR2),113);++nested;return; }
    CHECK(sig==SIGUSR1 && has(&current,SIGUSR1)==(mode!=NODEFER) && has(&current,SIGUSR2),114);
    ++handled;++active_depth;
    if(mode==NODEFER) {
        if(active_depth==1)CHECK(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0,115);
        else { CHECK(active_depth==2,116);++nested_nodefer; }
    }
    if(mode==NESTED) { struct mask64 one=bit(SIGUSR2);CHECK(mask(SIG_UNBLOCK,&one,0)==0 && raw(SYS_tgkill,pid,tid,SIGUSR2,0)==0,117); }
    if(mode==RESET) { struct action old={0};CHECK(action(SIGUSR1,0,&old)==0 && !old.handler && (old.flags&SA_RESETHAND),118); }
    if(state_mode() || mode>=BAD_SP) {
        CHECK(r2==0x23456789 && r13==0x3456789a,119);
        CHECK(mc->gpr[32]==(uintptr_t)state_resume && mc->gpr[34]==(uint32_t)pid && mc->gpr[40]==0xc00,120);
        for(unsigned i=0;i<32;++i) {
            CHECK(mc->gpr[i]==(i==3?0:initial_spe[i][1]),121);
            CHECK(mc->upper[i]==initial_spe[i][0],122);
        }
        CHECK(mc->gpr[35]==0x55667788 && mc->gpr[36]==0xabcdef00 && mc->gpr[37]==0xa000007f && mc->gpr[38]==0x4a6b7c8d,123);
        CHECK(mc->acc[0]==initial_acc[0] && mc->acc[1]==initial_acc[1] && mc->spefscr==0x80000001,124);
        const volatile uint32_t *gap=(void*)(state_sp-224);
        for(unsigned i=0;i<56;++i)CHECK(gap[i]==0x6b7c8d9e,125);
        CHECK(sp+(realtime?1616:1312)==state_sp,126);
        for(unsigned i=0;i<264;++i)CHECK(mc->fp[i]==0,127);
        for(unsigned i=0;i<388;++i)CHECK(mc->tail[i]==0,128);
        struct mask64 saved=realtime?*(struct mask64*)&uc->uc_sigmask:(struct mask64){{sc->low_mask,sc->unused[3]}};
        CHECK(same(&saved,&high_mask),129);
        saved.word[0]|=(1u<<(SIGKILL-1))|(1u<<(SIGSTOP-1));
        if(realtime)*(struct mask64*)&uc->uc_sigmask=saved;else { sc->low_mask=saved.word[0];sc->unused[3]=saved.word[1]; }
    }
    if(mode==STATE_EDIT || mode==STATE_RELOC) {
        if(mode==STATE_RELOC) { copy_context(&relocated,mc);mc=&relocated;if(realtime)uc->uc_regs=(void*)mc;else sc->regs=(uintptr_t)mc; }
        for(unsigned i=0;i<32;++i) { mc->gpr[i]=edited_gpr(i);mc->upper[i]=edited_upper(i); }
        mc->gpr[32]=(uintptr_t)state_resume_edited;mc->gpr[35]=0x778899aa;mc->gpr[36]=0xbadcfed0;
        mc->gpr[37]=0x8000003f;mc->gpr[38]=0x9b8a7654;mc->acc[0]=0xfedcba98;mc->acc[1]=0x76543210;mc->spefscr=0x40000002;
    }
    if(mode==STATE_NOSPE) { mc->gpr[33]&=~0x02000000u;mc->spefscr=0x40000002; }
    if(mode==STATE_PRIVILEGE)mc->gpr[33]=(mc->gpr[33]&~0x4000u)|0x1000u;
    if(mode==BAD_SP)mc->gpr[1]=0;
    if(mode==BAD_PC)mc->gpr[32]=0;
    if(mode==BAD_CONTEXT) { if(realtime)uc->uc_regs=0;else sc->regs=0; }
    if(mode==BAD_ALIGNMENT) { if(realtime)uc->uc_regs=(void*)((uintptr_t)mc+4);else sc->regs=(uintptr_t)mc+4; }
    if(mode==BAD_MSR)mc->gpr[33]|=0x2000;
    if(mode==BAD_SPEFSCR)mc->spefscr|=0x80;
    if(mode==BAD_FP)mc->fp[0]=1;
    if(mode==BAD_TAIL)mc->tail[0]=1;
    if(mode==BAD_GREG)mc->gpr[44]=1;
    if(mode==BAD_UCLINK)uc->uc_link=(void*)16;
    if(mode==BAD_PC_ALIGNMENT)mc->gpr[32]|=2;
    if(mode==BAD_RETURN)invalid_return(realtime?172:119);
    --active_depth;
}
static void install(int rt,unsigned flags)
{
    realtime=rt;
    struct action one={(uintptr_t)signal_entry,flags|SA_RESTORER|(rt?SA_SIGINFO:0),(uintptr_t)action_restorer,{{0}}};
    one.mask=bit(SIGUSR2);struct action two=one;two.mask=(struct mask64){{0}};two.flags=SA_RESTORER|(rt?SA_SIGINFO:0);
    CHECK(action(SIGUSR1,&one,0)==0 && action(SIGUSR2,&two,0)==0,201);
}
static void seed(void)
{
    for(unsigned i=0;i<32;++i) { initial_spe[i][0]=0x61720000u+i*0x101;initial_spe[i][1]=0x12340000u+i*0x101; }
    initial_spe[0][1]=250;initial_spe[2][1]=0x23456789;initial_spe[3][1]=pid;initial_spe[4][1]=tid;initial_spe[5][1]=SIGUSR1;initial_spe[13][1]=0x3456789a;
    *(uint32_t*)(edited_stack+1024+304)=0x13572468;*(uint32_t*)(edited_stack+1024+308)=0x24681357;
    observed_path=0;
}
static void core(int rt)
{
    int before=handled;struct mask64 one=bit(SIGUSR1),current={{0}};
    mode=ORDINARY;install(rt,0);CHECK(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==before+1,202);
    CHECK(mask(SIG_BLOCK,&one,0)==0,203);for(int i=0;i<3;++i)CHECK(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0,204);
    CHECK(handled==before+1 && mask(SIG_UNBLOCK,&one,0)==0 && handled==before+2,205);
    mode=NODEFER;install(rt,SA_NODEFER);CHECK(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==before+4,206);
    mode=NESTED;install(rt,0);CHECK(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==before+5,207);
    mode=RESET;install(rt,SA_RESETHAND);CHECK(raw(SYS_tgkill,pid,tid,SIGUSR1,0)==0 && handled==before+6,208);
    CHECK(mask(SIG_SETMASK,0,&current)==0 && same(&current,&high_mask),209);
}
static void state(int rt,int selected)
{
    mode=selected;install(rt,0);seed();state_probe();
    const int edit=selected==STATE_EDIT || selected==STATE_RELOC,clear=selected==STATE_NOSPE;
    CHECK(observed_path==(unsigned)(edit?2:1) && observed_cookies[0]==0x13572468 && observed_cookies[1]==0x24681357,210);
    for(unsigned i=0;i<32;++i) {
        CHECK(observed_spe[i][1]==(edit?edited_gpr(i):i==3?0:initial_spe[i][1]),211);
        CHECK(observed_spe[i][0]==(edit?edited_upper(i):clear?0:initial_spe[i][0]),212);
    }
    CHECK(observed_control[0]==(edit?0xbadcfed0:0xabcdef00) && observed_control[1]==(edit?0x778899aa:0x55667788),213);
    CHECK(observed_control[2]==(edit?0x9b8a7654:0x4a6b7c8d) && observed_control[3]==(edit?0x8000003f:0xa000007f),214);
    CHECK(observed_control[4]==(edit||clear?0x40000002:0x80000001),215);
    CHECK(observed_acc[0]==(edit?0xfedcba98:clear?0:initial_acc[0]) && observed_acc[1]==(edit?0x76543210:clear?0:initial_acc[1]),216);
    struct mask64 current={{0}};CHECK(mask(SIG_SETMASK,0,&current)==0 && same(&current,&high_mask),217);
}
static void corrupt(int rt,int selected)
{
    mode=selected;install(rt,0);long child=raw(SYS_fork,0,0,0,0);CHECK(child>=0,218);
    if(!child) { pid=raw(SYS_getpid,0,0,0,0);tid=raw(SYS_gettid,0,0,0,0);seed();state_probe();raw(SYS_exit_group,99,0,0,0); }
    int status=0;CHECK(waitpid(child,&status,0)==child && WIFSIGNALED(status) && WTERMSIG(status)==SIGSEGV,219);
}
static void highest(void)
{
    struct action zero={0};struct mask64 one=bit(64);CHECK(action(64,&zero,0)==0 && mask(SIG_UNBLOCK,&one,0)==0,220);
    long child=raw(SYS_fork,0,0,0,0);CHECK(child>=0,221);
    if(!child) { raw(SYS_tgkill,raw(SYS_getpid,0,0,0,0),raw(SYS_gettid,0,0,0,0),64,0);raw(SYS_exit_group,99,0,0,0); }
    int status=0;CHECK(waitpid(child,&status,0)==child && WIFSIGNALED(status) && WTERMSIG(status)==64,222);
}
static int equal(const char *a,const char *b) { while(*a && *a==*b){++a;++b;}return *a==*b; }
static void line(const char *s) { unsigned n=0;while(s[n])++n;CHECK(raw(SYS_write,1,(long)s,n,0)==(long)n,223); }
int main(int argc,char **argv)
{
    pid=raw(SYS_getpid,0,0,0,0);tid=raw(SYS_gettid,0,0,0,0);uid=raw(SYS_getuid,0,0,0,0);CHECK(mask(SIG_SETMASK,&high_mask,0)==0,224);
    const char *names[]={"keep","edit","relocate","nospe","privilege","unused","bad-sp","bad-pc","bad-context","bad-alignment","bad-msr","bad-spefscr","bad-fp","bad-tail","bad-greg","bad-uclink","bad-pc-alignment","bad-return"};
    if(argc==2) {
        int found=0;
        for(int rt=0;rt<2;++rt) {
            if(equal(argv[1],rt?"core-rt":"core-legacy")) {core(rt);found=1;}
            for(int selected=STATE_KEEP;selected<=BAD_RETURN;++selected) if(selected!=9 && !(selected==BAD_UCLINK && !rt)) {
                const char *a=argv[1],*b=names[selected-STATE_KEEP];while(*b && *a==*b){++a;++b;}
                if(!*b && equal(a,rt?"-rt":"-legacy")) {if(selected<BAD_SP)state(rt,selected);else corrupt(rt,selected);found=1;}
            }
        }
        if(equal(argv[1],"highest")){highest();found=1;}CHECK(found,225);line("SIGNAL_PPC_CASE_PASS ");line(argv[1]);line("\n");return 0;
    }
    CHECK(argc==1,226);
    for(int rt=0;rt<2;++rt) {core(rt);for(int selected=STATE_KEEP;selected<=STATE_PRIVILEGE;++selected)state(rt,selected);for(int selected=BAD_SP;selected<=BAD_RETURN;++selected)if(selected!=BAD_UCLINK || rt)corrupt(rt,selected);}
    highest();CHECK(handled==22 && nested==2 && nested_nodefer==2 && restorers[0]==restorers[1]+16,227);
    line("SIGNAL_PPC_PASS ppc legacy=1 rt=1 handlers=22 nested=2 nodefer_nested=2 states=10 relocated=2 full_spe=1 masks=10 fatal=24 restorer_ignored=1\n");return 0;
}

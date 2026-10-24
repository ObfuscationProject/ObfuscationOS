#define _GNU_SOURCE
#include <stdint.h>
#include <signal.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <sys/syscall.h>
#include <ucontext.h>
#if defined(__riscv) && __riscv_xlen == 32
#define ARCH "rv32"
#define FRAME_BYTES "944"
#define MMAP_NR "222"
#elif defined(__riscv) && __riscv_xlen == 64
#define ARCH "rv64"
#define FRAME_BYTES "1088"
#define MMAP_NR "222"
#else
#error "Private signal entry probe requires RV32 or RV64"
#endif
static volatile int mode;
static void *data;
static void handle(int signal, siginfo_t *info, void *context)
{
    if (signal != SIGUSR1 || !info || !context) _exit(91);
    ucontext_t *uc = context;
    if (mode == 1) uc->uc_mcontext.__gregs[REG_PC] = (uintptr_t)data;
    if (mode == 2) uc->uc_mcontext.__gregs[REG_SP] = (uintptr_t)data + 4096;
}
// This child-only wrapper has its own executable page. It replaces the first
// ELF page without executing from that page, then deliberately makes the frame
// destination exactly user_begin. No C or stack instruction runs after SP moves.
extern void boundary(long, long);
__asm__(".text\n.balign 4096\n.global boundary\n.type boundary,@function\nboundary:\n"
        "mv s0,a0\nmv s1,a1\nli a0,0x40000000\nli a1,4096\nli a2,3\nli a3,0x32\nli a4,-1\nli a5,0\n"
        "li a7," MMAP_NR "\necall\nli t0,0x40000000\nbne a0,t0,1f\n"
        "mv a0,s0\nmv a1,s1\nli a2,10\nli sp,0x40000000\naddi sp,sp," FRAME_BYTES "\nli a7,131\necall\n"
        "1: li a0,99\nli a7,94\necall\nebreak\n.size boundary,.-boundary\n");
#define CHECK(x,n) do { if (!(x)) { printf("SIGNAL_ENTRY_FAIL code=%d status=%d\n",n,status); return 1; } } while (0)
int main(void)
{
    int status = -1;
    data = mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    CHECK(data != MAP_FAILED,101);
    for (mode=0;mode!=4;++mode) {
        pid_t child=fork();
        CHECK(child>=0,102);
        if (!child) {
            struct sigaction action={0};
            action.sa_sigaction=handle;action.sa_flags=SA_SIGINFO;
            if (mode==0) action.sa_handler=(void (*)(int))data;
            if (mode==3) action.sa_handler=(void (*)(int))boundary;
            if (sigemptyset(&action.sa_mask) || sigaction(SIGUSR1,&action,0)) _exit(92);
            if (mode==2 && mprotect(data,4096,PROT_READ)) _exit(93);
            if (mode==3) boundary(getpid(),syscall(SYS_gettid));
            raise(SIGUSR1);
            _exit(94);
        }
        CHECK(waitpid(child,&status,0)==child && WIFSIGNALED(status) && WTERMSIG(status)==SIGSEGV,103+mode);
    }
    CHECK(munmap(data,4096)==0,107);
    puts("SIGNAL_ENTRY_PASS " ARCH " handler_nx=1 return_nx=1 return_sp=1 frame_boundary=1 fault_children=4");
    return 0;
}

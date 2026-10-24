#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <signal.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <sys/syscall.h>
#include <ucontext.h>
#if !defined(__i386__)
#error "This entry and segmented-stack probe requires i386"
#endif
struct action { uint32_t handler, flags, restorer; uint64_t mask; };
_Static_assert(sizeof(struct action) == 20, "Linux i386 action");
static _Alignas(16) unsigned char alternate[32768];
static volatile int mode, realtime, failed, handled;
static void *data;
uintptr_t entry_good_sp, entry_tls_base;
uint32_t entry_flat_ss, entry_tls_ss, entry_segmented;
extern void legacy_entry(void), legacy_restore(void), rt_restore(void);
extern int enter_segmented(long, long);
extern void readonly_stack_landing(void);
void legacy_handle(void *frame);
// Each success must read the cookies using the returned SS:ESP before the
// wrapper switches back to the caller's flat stack. The userland TLS self
// pointer supplies its own descriptor base; no OS-private selector is assumed.
__asm__(".text\n.global legacy_entry\n.type legacy_entry,@function\nlegacy_entry:\n"
        "mov %esp,%eax\nsub $8,%esp\npush %eax\ncall legacy_handle\nadd $12,%esp\nret\n"
        ".size legacy_entry,.-legacy_entry\n"
        ".global legacy_restore\n.type legacy_restore,@function\nlegacy_restore:\n"
        "pop %eax\nmov $119,%eax\nint $0x80\nud2\n.size legacy_restore,.-legacy_restore\n"
        ".global rt_restore\n.type rt_restore,@function\nrt_restore:\n"
        "mov $173,%eax\nint $0x80\nud2\n.size rt_restore,.-rt_restore\n"
        ".global enter_segmented\n.type enter_segmented,@function\nenter_segmented:\n"
        "push %ebx\npush %esi\npush %edi\nsub $16,%esp\n"
        "movl $0x13572468,(%esp)\nmovl $0x23456789,4(%esp)\nmov %esp,entry_good_sp\n"
        "mov 32(%esp),%ebx\nmov 36(%esp),%ecx\n"
        "cmpl $0,entry_segmented\nje 1f\n"
        "mov %esp,%esi\nsub entry_tls_base,%esi\nmov entry_tls_ss,%eax\n"
        "mov %ax,%ss\nmov %esi,%esp\n"
        "1: mov $10,%edx\nmov $270,%eax\nint $0x80\n"
        "mov (%esp),%ecx\nmov 4(%esp),%edx\n"
        "mov %eax,%edi\nxor %eax,%eax\nmov %ss,%ax\n"
        "cmp entry_tls_ss,%eax\njne 2f\ntest %edi,%edi\njne 2f\n"
        "cmp $0x13572468,%ecx\njne 2f\ncmp $0x23456789,%edx\njne 2f\n"
        "xor %edi,%edi\njmp 3f\n2: mov $1,%edi\n"
        "3: mov entry_good_sp,%esi\nmov entry_flat_ss,%eax\nmov %ax,%ss\nmov %esi,%esp\n"
        "mov %edi,%eax\nadd $16,%esp\npop %edi\npop %esi\npop %ebx\nret\n"
        ".size enter_segmented,.-enter_segmented\n"
        // The restored SS:ESP supplies the addressing segment for this first
        // instruction. No call/return or libc stack is needed after the store.
        ".global readonly_stack_landing\n.type readonly_stack_landing,@function\nreadonly_stack_landing:\n"
        "movl $0x3456789a,-4(%esp)\nmov $1,%eax\nmov $95,%ebx\nint $0x80\nud2\n"
        ".size readonly_stack_landing,.-readonly_stack_landing\n");
static long raw(long n, long a, long b, long c, long d)
{
    long result;
    __asm__ volatile("int $0x80" : "=a"(result) : "a"(n), "b"(a), "c"(b), "d"(c), "S"(d) : "memory", "cc");
    return result;
}
static void handle_context(int signal, greg_t *registers)
{
    if (signal != SIGUSR1 || !registers) _exit(91);
    if (mode == 1) registers[REG_EIP] = (uintptr_t)data;
    if (mode == 2 || mode == 3) registers[REG_EIP] = (uintptr_t)readonly_stack_landing;
    if (mode == 2) registers[REG_ESP] = (uintptr_t)data+4096;
    if (mode == 3) {
        // Only the effective SS.base+ESP address is the stack. The raw offset
        // need not be mapped in the process's flat virtual-address window.
        registers[REG_SS] = entry_tls_ss;
        registers[REG_ESP] = (uintptr_t)data+4096-entry_tls_base;
    }
    if (mode >= 4) {
        volatile unsigned char local = 0x5a;
        uintptr_t sp = registers[REG_ESP];
        uint32_t ss = registers[REG_SS] & 0xffff;
        uint16_t live_ss;
        __asm__ volatile("mov %%ss,%0" : "=rm"(live_ss));
        if ((uintptr_t)&local < (uintptr_t)alternate || (uintptr_t)&local >= (uintptr_t)alternate+sizeof(alternate) ||
            live_ss != entry_flat_ss || !entry_good_sp || entry_good_sp <= entry_tls_base ||
            sp != entry_good_sp-(entry_segmented ? entry_tls_base : 0) ||
            ss != (entry_segmented ? entry_tls_ss : entry_flat_ss)) failed = 1;
        registers[REG_SS] = entry_tls_ss;
        registers[REG_ESP] = entry_good_sp-entry_tls_base;
        ++handled;
    }
}
void legacy_handle(void *frame)
{
    uint32_t *words = frame;
    handle_context(words[1], (greg_t *)(words+2));
}
static void rt_handle(int signal, siginfo_t *info, void *context)
{
    if (!info || info->si_signo != signal || info->si_code != SI_TKILL || info->si_pid != getpid()) _exit(92);
    handle_context(signal, ((ucontext_t *)context)->uc_mcontext.gregs);
}
#define CHECK(x,n) do { if (!(x) || failed) { printf("SIGNAL_I386_ENTRY_FAIL code=%d mode=%d rt=%d status=%d\n",n,mode,realtime,status); return 1; } } while (0)
int main(void)
{
    int status = -1;
    uint16_t ss, gs;
    __asm__ volatile("mov %%ss,%0\nmov %%gs,%1\nmov %%gs:0,%2" : "=rm"(ss), "=rm"(gs), "=r"(entry_tls_base));
    entry_flat_ss = ss; entry_tls_ss = gs;
    CHECK(entry_tls_ss != entry_flat_ss && entry_tls_base != 0,101);
    data = mmap(0,4096,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    CHECK(data != MAP_FAILED,102);
    // If NX is missing, this page exits normally with status 95. Zero-filled
    // instruction bytes could instead fault and falsely satisfy the NX check.
    static const unsigned char nx_exit[] = {
        0xb8, 1, 0, 0, 0,       // mov $SYS_exit,%eax
        0xbb, 95, 0, 0, 0,      // mov $95,%ebx
        0xcd, 0x80, 0x0f, 0x0b  // int $0x80; ud2
    };
    for (size_t i=0;i!=sizeof(nx_exit);++i) ((unsigned char *)data)[i] = nx_exit[i];
    stack_t stack = {.ss_sp=alternate,.ss_size=sizeof(alternate)};
    CHECK(sigaltstack(&stack,0) == 0,103);
    for (realtime=0;realtime!=2;++realtime) {
        struct action action = {realtime ? (uint32_t)rt_handle : (uint32_t)legacy_entry,
            0x04000000u | (realtime ? SA_SIGINFO : 0),
            (uint32_t)(realtime ? rt_restore : legacy_restore),0};
        for (mode=0;mode!=4;++mode) {
            pid_t child = fork();
            CHECK(child>=0,104);
            if (!child) {
                if (mode==0) action.handler = (uintptr_t)data;
                if (raw(SYS_rt_sigaction,SIGUSR1,(long)&action,0,8)) _exit(93);
                if (mode>=2 && mprotect(data,4096,PROT_READ)) _exit(94);
                raise(SIGUSR1); _exit(95);
            }
            CHECK(waitpid(child,&status,0)==child && WIFSIGNALED(status) && WTERMSIG(status)==SIGSEGV,105+mode);
        }
        action.flags |= SA_ONSTACK;
        CHECK(raw(SYS_rt_sigaction,SIGUSR1,(long)&action,0,8) == 0,109);
        for (mode=4;mode!=6;++mode) {
            entry_segmented = mode==5;
            CHECK(enter_segmented(getpid(),syscall(SYS_gettid)) == 0,110);
        }
    }
    CHECK(handled==4 && munmap(data,4096)==0,111);
    puts("SIGNAL_I386_ENTRY_PASS i386 legacy=1 rt=1 handler_nx=2 return_nx=2 return_sp=2 segmented_sp=2 segmented_delivery=2 segmented_readonly=2 fault_children=8");
    return 0;
}

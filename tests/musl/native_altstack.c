#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <signal.h>
#include <ucontext.h>
#include <pthread.h>
#include <errno.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>

#if defined(__i386__)
#define ARCH "i386"
static long raw(long n, long a, long b, long c, long d)
{
    long result;
    __asm__ volatile("int $0x80" : "=a"(result) : "a"(n), "b"(a), "c"(b), "d"(c), "S"(d) : "memory", "cc");
    return result;
}
extern void restore(void);
__asm__(".text\n.global restore\n.type restore,@function\nrestore:\nmov $173,%eax\nint $0x80\nud2\n.size restore,.-restore\n");
#elif defined(__arm__)
#define ARCH "arm32"
static long raw(long n, long a, long b, long c, long d)
{
    register long r7 __asm__("r7") = n;
    register long r0 __asm__("r0") = a;
    register long r1 __asm__("r1") = b;
    register long r2 __asm__("r2") = c;
    register long r3 __asm__("r3") = d;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r7), "r"(r1), "r"(r2), "r"(r3) : "memory", "cc");
    return r0;
}
extern void restore(void);
__asm__(".syntax unified\n.text\n.arm\n.align 2\n.global restore\n.type restore,%function\nrestore:\nmov r7,#173\nsvc 0\nudf 0\n.size restore,.-restore\n");
#elif defined(__x86_64__)
#define ARCH "x86_64"
static long raw(long n, long a, long b, long c, long d)
{
    register long r10 __asm__("r10") = d;
    long result;
    __asm__ volatile("syscall" : "=a"(result) : "a"(n), "D"(a), "S"(b), "d"(c), "r"(r10) : "rcx", "r11", "memory");
    return result;
}
__attribute__((naked)) static void restore(void)
{
    __asm__ volatile("mov $15,%rax; syscall; ud2");
}
#elif defined(__aarch64__)
#define ARCH "aarch64"
static long raw(long n, long a, long b, long c, long d)
{
    register long x8 __asm__("x8") = n;
    register long x0 __asm__("x0") = a;
    register long x1 __asm__("x1") = b;
    register long x2 __asm__("x2") = c;
    register long x3 __asm__("x3") = d;
    __asm__ volatile("svc 0" : "+r"(x0) : "r"(x8), "r"(x1), "r"(x2), "r"(x3) : "memory", "cc");
    return x0;
}
extern void restore(void);
__asm__(".text\n.global restore\n.type restore,%function\nrestore:\nmov x8,139\nsvc 0\nbrk 0\n.size restore,.-restore\n");
#elif defined(__powerpc__) || defined(__PPC__)
#define ARCH "ppc"
#if __SIZEOF_POINTER__ != 4 || __BYTE_ORDER__ != __ORDER_BIG_ENDIAN__ || !defined(__SPE__)
#error "This PPC fixture requires the native big-endian PPC32 e500/SPE profile"
#endif
_Static_assert(sizeof(long) == 4 && sizeof(void *) == 4, "PPC32 native words");
static long raw(long n, long a, long b, long c, long d)
{
    register long r0 __asm__("r0") = n;
    register long r3 __asm__("r3") = a;
    register long r4 __asm__("r4") = b;
    register long r5 __asm__("r5") = c;
    register long r6 __asm__("r6") = d;
    // Linux PPC reports positive errno in r3 only when CR0.SO is set.
    __asm__ volatile("sc ; bns+ 1f ; neg %1, %1 ; 1:"
                     : "+r"(r0), "+r"(r3), "+r"(r4), "+r"(r5), "+r"(r6)
                     : : "memory", "cr0", "r7", "r8", "r9", "r10", "r11", "r12");
    return r3;
}
extern void restore(void);
__asm__(".text\n.balign 4\n.global restore\n.type restore,@function\nrestore:\nli 0,172\nsc\ntrap\n.size restore,.-restore\n");
#elif defined(__mips__) && defined(_ABI64) && _MIPS_SIM == _ABI64
#define ARCH "mips64"
#if !defined(__MIPSEB__) || __mips_fpr != 64 || __mips_isa_rev != 2
#error "This MIPS64 fixture requires the native big-endian MIPS64r2 n64 FR1 profile"
#endif
#ifdef SA_RESTORER
#error "MIPS64 Linux kernel action records have no restorer member"
#endif
_Static_assert(sizeof(long) == 8 && sizeof(void *) == 8, "native n64 words");
static long raw(long n, long a, long b, long c, long d)
{
	register long r4 __asm__("$4") = a;
	register long r5 __asm__("$5") = b;
	register long r6 __asm__("$6") = c;
	register long r7 __asm__("$7") = d;
	register long r2 __asm__("$2");

	__asm__ __volatile__ (
		"daddu $2,$0,%2 ; syscall"
		: "=&r"(r2), "+r"(r7)
		: "ir"(n), "0"(r2), "r"(r4), "r"(r5), "r"(r6)
		: "$1", "$3", "$10", "$11", "$12", "$13", "$14", "$15", "$24", "$25", "hi", "lo", "memory");
	return r7 && r2>0 ? -r2 : r2;
}
#elif defined(__mips__) && defined(_ABIO32) && _MIPS_SIM == _ABIO32
#define ARCH "mips"
#if !defined(__MIPSEB__) || __mips_fpr != 32 || __mips_isa_rev != 2
#error "This MIPS fixture requires the native big-endian MIPS32r2 o32 FR0 profile"
#endif
#ifdef SA_RESTORER
#error "MIPS Linux kernel action records have no restorer member"
#endif
static long raw(long n, long a, long b, long c, long d)
{
    register long r4 __asm__("$4") = a;
    register long r5 __asm__("$5") = b;
    register long r6 __asm__("$6") = c;
    register long r7 __asm__("$7") = d;
    register long r2 __asm__("$2");
    // a3 is both the fourth argument and the Linux syscall error flag.
    __asm__ volatile("addu $2,$0,%2 ; syscall"
                     : "=&r"(r2), "+r"(r7)
                     : "ir"(n), "0"(r2), "r"(r4), "r"(r5), "r"(r6)
                     : "$1", "$3", "$8", "$9", "$10", "$11", "$12", "$13",
                       "$14", "$15", "$24", "$25", "hi", "lo", "memory");
    return r7 && r2 > 0 ? -r2 : r2;
}
#elif defined(__loongarch64)
#define ARCH "loongarch64"
#ifdef SA_RESTORER
#error "LoongArch64 Linux kernel action records have no restorer member"
#endif
static long raw(long n, long a, long b, long c, long d)
{
    register long a7 __asm__("$a7") = n;
    register long a0 __asm__("$a0") = a;
    register long a1 __asm__("$a1") = b;
    register long a2 __asm__("$a2") = c;
    register long a3 __asm__("$a3") = d;
    __asm__ volatile("syscall 0" : "+r"(a0) : "r"(a7), "r"(a1), "r"(a2), "r"(a3)
                     : "$t0", "$t1", "$t2", "$t3", "$t4", "$t5", "$t6", "$t7", "$t8", "memory");
    return a0;
}
#elif defined(__riscv) && (__riscv_xlen == 32 || __riscv_xlen == 64)
#if __riscv_xlen == 32
#define ARCH "rv32"
#define STORE "sw"
#define LOAD "lw"
#else
#define ARCH "rv64"
#define STORE "sd"
#define LOAD "ld"
#endif
#ifdef SA_RESTORER
#error "RISC-V Linux kernel action records have no restorer member"
#endif
static long raw(long n, long a, long b, long c, long d)
{
    register long a7 __asm__("a7") = n;
    register long a0 __asm__("a0") = a;
    register long a1 __asm__("a1") = b;
    register long a2 __asm__("a2") = c;
    register long a3 __asm__("a3") = d;
    __asm__ volatile("ecall" : "+r"(a0) : "r"(a7), "r"(a1), "r"(a2), "r"(a3) : "memory");
    return a0;
}
#else
#error "This alternate-stack execution fixture supports i386, x86_64, AArch64, ARM32, RV32, RV64, LoongArch64, MIPS o32, MIPS64 n64 and PPC32"
#endif

#define AUTO 0x80000000u
#define RESTORER 0x04000000ul
#if defined(__mips__)
#define SIGNAL_MASK_BYTES 16
#else
#define SIGNAL_MASK_BYTES 8
#endif
#if defined(__mips__) && defined(_ABI64) && _MIPS_SIM == _ABI64
struct action { unsigned flags; uintptr_t handler; unsigned long mask[2]; };
_Static_assert(offsetof(struct action, flags) == 0, "n64 action flags offset");
_Static_assert(offsetof(struct action, handler) == 8, "n64 action handler offset");
_Static_assert(offsetof(struct action, mask) == 16, "n64 action mask offset");
_Static_assert(sizeof(struct action) == 32, "n64 action copy length");
_Static_assert(sizeof(stack_t) == 24 && offsetof(stack_t, ss_size) == 8 && offsetof(stack_t, ss_flags) == 16, "n64 stack record");
_Static_assert(offsetof(ucontext_t, uc_mcontext) == 40 && offsetof(ucontext_t, uc_mcontext.gregs[29]) == 272, "n64 saved SP");
_Static_assert(SYS_tgkill == 5225 && SYS_rt_sigreturn == 5211, "n64 signal syscall numbers");
#elif defined(__mips__) && defined(_ABIO32) && _MIPS_SIM == _ABIO32
struct action { unsigned flags; uintptr_t handler; unsigned long mask[4]; };
_Static_assert(offsetof(struct action, flags) == 0, "MIPS action flags offset");
_Static_assert(offsetof(struct action, handler) == 4, "MIPS action handler offset");
_Static_assert(offsetof(struct action, mask) == 8, "MIPS action mask offset");
_Static_assert(sizeof(struct action) == 24, "MIPS action copy length");
#elif defined(__riscv) || defined(__loongarch64)
struct action { uintptr_t handler, flags; unsigned long mask[8 / sizeof(unsigned long)]; };
_Static_assert(offsetof(struct action, mask) == 2*sizeof(uintptr_t), "Linux action mask offset");
_Static_assert(sizeof(struct action) == 2*sizeof(uintptr_t)+8, "Linux action copy length");
#else
// ARM and PPC align uint64_t to eight bytes; Linux kernel sigaction places the
// eight-byte mask at offset 12. The wire record needs four-byte alignment.
#if defined(__arm__) || defined(__powerpc__) || defined(__PPC__)
struct __attribute__((packed, aligned(4))) action { uintptr_t handler, flags, restorer; uint64_t mask; };
#else
struct action { uintptr_t handler, flags, restorer; uint64_t mask; };
#endif
_Static_assert(offsetof(struct action, mask) == 3*sizeof(uintptr_t), "Linux action mask offset");
_Static_assert(sizeof(struct action) == 3*sizeof(uintptr_t)+8, "Linux action copy length");
#endif
#if defined(__powerpc__) || defined(__PPC__)
_Static_assert(sizeof(stack_t) == 12 && offsetof(stack_t, ss_flags) == 4 && offsetof(stack_t, ss_size) == 8, "PPC32 stack record");
_Static_assert(offsetof(ucontext_t, uc_regs) == 48 && offsetof(ucontext_t, uc_sigmask) == 52 && offsetof(ucontext_t, uc_mcontext) == 192, "PPC32 ucontext layout");
_Static_assert(offsetof(mcontext_t, gregs[1]) == 4, "PPC32 saved r1");
_Static_assert(SYS_tgkill == 250 && SYS_rt_sigreturn == 172 && SYS_rt_sigaction == 173 && SYS_sigaltstack == 185, "PPC32 signal syscall numbers");
#endif
static _Alignas(16) unsigned char alternate[65536];
static volatile int failure, mode, outer_count, inner_count, depth;
static volatile uintptr_t outer_sp;
static int checks;
static long process_id, thread_id;
static stack_t expected;

static long alt(stack_t *set, stack_t *old)
{
    return raw(SYS_sigaltstack, (long)set, (long)old, 0, 0);
}
static int same(const stack_t *a, const stack_t *b)
{
    return a->ss_sp == b->ss_sp && a->ss_size == b->ss_size &&
           (unsigned)a->ss_flags == (unsigned)b->ss_flags;
}
static int contains(uintptr_t pointer)
{
    return pointer > (uintptr_t)alternate && pointer - (uintptr_t)alternate <= sizeof(alternate);
}
static void child_exit(int code)
{
    raw(SYS_exit_group, code, 0, 0, 0);
    for (;;) {}
}
static void fail(int code)
{
    char text[] = "ALTSTACK_FAIL code=000 handler=000\n";
    size_t at = sizeof("ALTSTACK_FAIL code=") - 1;
    text[at] = '0' + code/100%10; text[at+1] = '0' + code/10%10; text[at+2] = '0' + code%10;
    at = sizeof("ALTSTACK_FAIL code=000 handler=") - 1;
    text[at] = '0' + failure/100%10; text[at+1] = '0' + failure/10%10; text[at+2] = '0' + failure%10;
    raw(SYS_write, 1, (long)text, sizeof(text)-1, 0);
    child_exit(1);
}
#define CHECK(condition, code) do { ++checks; if (!(condition) || failure) fail(code); } while (0)
#define HCHECK(condition, code) do { if (!(condition) && !failure) failure = code; } while (0)

static void handler(int signal, siginfo_t *info, void *context)
{
    volatile unsigned char local[1024];
    local[0] = 1; local[sizeof(local)-1] = 2;
    uintptr_t sp = (uintptr_t)&local[0];
    if (mode == 9) {
        if (++depth >= 32) child_exit(99);
        raw(SYS_tgkill, process_id, thread_id, SIGUSR1, 0);
        if (local[0] != 1 || local[sizeof(local)-1] != 2) child_exit(98);
        return;
    }
    ucontext_t *uc = context;
    stack_t current = {0};
    HCHECK(info && info->si_signo == signal && uc, 201);
    HCHECK(alt(0, &current) == 0, 202);
    HCHECK(contains(sp) == (mode != 3 && mode != 4 && mode != 5), 203);
    if (signal == SIGUSR2) {
        ++inner_count;
        HCHECK(sp < outer_sp && outer_sp - sp >= sizeof(local), 204);
        HCHECK(current.ss_flags == (mode == 2 ? SS_DISABLE : SS_ONSTACK), 205);
        // AUTODISARM is already disabled before nested delivery; its saved
        // stack record must therefore describe the disabled state.
        if (mode == 2)
            HCHECK(uc->uc_stack.ss_sp == 0 && uc->uc_stack.ss_size == 0 && uc->uc_stack.ss_flags == SS_DISABLE, 206);
        else
            HCHECK(same(&uc->uc_stack, &expected), 207);
        return;
    }
    ++outer_count; outer_sp = sp;
    HCHECK(signal == SIGUSR1 && same(&uc->uc_stack, &expected), 208);
    if (mode == 2 || mode == 3) {
        HCHECK(current.ss_sp == 0 && current.ss_size == 0 && current.ss_flags == SS_DISABLE, 209);
    } else if (mode == 1) {
        HCHECK(current.ss_sp == expected.ss_sp && current.ss_size == expected.ss_size && current.ss_flags == SS_ONSTACK, 210);
        stack_t disable = { .ss_flags = SS_DISABLE };
        stack_t invalid = { .ss_flags = 0x10, .ss_size = 1 };
        HCHECK(alt(&disable, 0) == -EPERM && alt(&invalid, 0) == -EPERM, 211);
    } else {
        HCHECK(same(&current, &expected), 212);
    }
    if (mode == 1 || mode == 2)
        HCHECK(raw(SYS_tgkill, process_id, thread_id, SIGUSR2, 0) == 0, 213);
    if (mode == 4) uc->uc_stack.ss_flags = 0x10;
    if (mode == 5) uc->uc_stack.ss_size = 1;
    HCHECK(local[0] == 1 && local[sizeof(local)-1] == 2, 214);
}
static long install(int onstack, int nodefer)
{
#if defined(__mips__)
    struct action a = {SA_SIGINFO | (onstack ? SA_ONSTACK : 0) |
                       (nodefer ? SA_NODEFER : 0), (uintptr_t)handler, {0}};
#elif defined(__riscv) || defined(__loongarch64)
    struct action a = {(uintptr_t)handler, SA_SIGINFO |
                       (onstack ? SA_ONSTACK : 0) | (nodefer ? SA_NODEFER : 0), {0}};
#else
    struct action a = {(uintptr_t)handler, RESTORER | SA_SIGINFO |
                       (onstack ? SA_ONSTACK : 0) | (nodefer ? SA_NODEFER : 0),
                       (uintptr_t)restore, 0};
#endif
    long first = raw(SYS_rt_sigaction, SIGUSR1, (long)&a, 0, SIGNAL_MASK_BYTES);
    return first ? first : raw(SYS_rt_sigaction, SIGUSR2, (long)&a, 0, SIGNAL_MASK_BYTES);
}
static long fork_child(void)
{
#ifdef SYS_fork
    return raw(SYS_fork, 0, 0, 0, 0);
#else
    return raw(SYS_clone, SIGCHLD, 0, 0, 0);
#endif
}
static void *peer(void *unused)
{
    (void)unused;
    stack_t stack = {0};
    return (void *)(uintptr_t)(alt(0, &stack) == 0 && stack.ss_sp == 0 &&
                              stack.ss_size == 0 && stack.ss_flags == SS_DISABLE ? 0x1357 : 0);
}
static int equal_text(const char *a, const char *b)
{
    while (*a && *a == *b) { ++a; ++b; }
    return *a == *b;
}

int main(int argc, char **argv)
{
    stack_t current = {0}, disable = {.ss_flags = SS_DISABLE};
    if (argc == 2 && equal_text(argv[1], "--exec-child")) {
        CHECK(alt(0, &current) == 0 && !current.ss_sp && !current.ss_size &&
              (unsigned)current.ss_flags == (AUTO | SS_DISABLE), 150);
        const char success[] = "ALTSTACK_EXEC_CHILD_PASS " ARCH " flags=autodisarm_disabled\n";
        raw(SYS_write, 1, (long)success, sizeof(success)-1, 0);
        return 0;
    }
    process_id = raw(SYS_getpid, 0, 0, 0, 0);
    thread_id = raw(SYS_gettid, 0, 0, 0, 0);
    CHECK(alt(0, &current) == 0 && current.ss_sp == 0 && current.ss_size == 0 && current.ss_flags == SS_DISABLE, 101);
    expected = (stack_t){ .ss_sp = alternate, .ss_size = sizeof(alternate), .ss_flags = 0 };
    stack_t bad = expected;
    bad.ss_size = 1;
    CHECK(alt(&bad, 0) == -ENOMEM, 102);
    bad = expected; bad.ss_flags = 0x10;
    CHECK(alt(&bad, 0) == -EINVAL, 103);
    // Poison every output field so an omitted or partial old-state copy cannot
    // reuse the earlier disabled-state query as a passing observation.
    current = (stack_t){ .ss_sp = (void *)(uintptr_t)0x1234, .ss_size = 123, .ss_flags = 0x40 };
    CHECK(alt(&expected, &current) == 0 && current.ss_sp == 0 && current.ss_size == 0 &&
          current.ss_flags == SS_DISABLE, 104);
    CHECK(alt(0, &current) == 0 && same(&current, &expected), 105);
    CHECK(install(1, 0) == 0, 106);
    mode = 1;
    CHECK(raw(SYS_tgkill, process_id, thread_id, SIGUSR1, 0) == 0 && outer_count == 1 && inner_count == 1, 107);
    CHECK(alt(0, &current) == 0 && same(&current, &expected), 108);

    expected.ss_flags = AUTO;
    CHECK(alt(&expected, 0) == 0, 109);
    mode = 2;
    CHECK(raw(SYS_tgkill, process_id, thread_id, SIGUSR1, 0) == 0 && outer_count == 2 && inner_count == 2, 110);
    CHECK(alt(0, &current) == 0 && same(&current, &expected), 111);
    CHECK(install(0, 0) == 0, 112);
    mode = 3;
    CHECK(raw(SYS_tgkill, process_id, thread_id, SIGUSR1, 0) == 0 && outer_count == 3, 113);
    CHECK(alt(0, &current) == 0 && same(&current, &expected), 114);

    expected.ss_flags = 0;
    CHECK(alt(&expected, 0) == 0, 115);
    for (int invalid = 4; invalid <= 5; ++invalid) {
        mode = invalid;
        CHECK(raw(SYS_tgkill, process_id, thread_id, SIGUSR1, 0) == 0 && outer_count == invalid, 116);
        CHECK(alt(0, &current) == 0 && same(&current, &expected), 117);
    }

    expected.ss_flags = AUTO;
    CHECK(alt(&expected, 0) == 0, 118);
    long child = fork_child();
    CHECK(child >= 0, 119);
    if (!child) child_exit(alt(0, &current) == 0 && same(&current, &expected) ? 0 : 97);
    int status = -1;
    CHECK(waitpid((pid_t)child, &status, 0) == child && status == 0, 120);
    pthread_t thread;
    CHECK(pthread_create(&thread, 0, peer, 0) == 0, 121);
    void *result = 0;
    CHECK(pthread_join(thread, &result) == 0 && result == (void *)(uintptr_t)0x1357, 122);
    CHECK(alt(0, &current) == 0 && same(&current, &expected), 123);
    char *failed_argv[] = {"/missing-altstack-probe", 0}, *empty_env[] = {0};
    CHECK(raw(SYS_execve, (long)failed_argv[0], (long)failed_argv, (long)empty_env, 0) == -ENOENT, 124);
    CHECK(alt(0, &current) == 0 && same(&current, &expected), 125);

    // Successful self-exec is separately selected: Linux qemu-user without a
    // binfmt handler cannot exec a target ELF through the host execve syscall.
    if (argc == 2 && equal_text(argv[1], "--exec")) {
        child = fork_child();
        CHECK(child >= 0, 151);
        if (!child) {
            char *args[] = {argv[0], "--exec-child", 0};
            raw(SYS_execve, (long)argv[0], (long)args, (long)empty_env, 0);
            child_exit(96);
        }
        status = -1;
        CHECK(waitpid((pid_t)child, &status, 0) == child && status == 0, 152);
    }

    for (int fault = 0; fault != 2; ++fault) {
        child = fork_child();
        CHECK(child >= 0, 126);
        if (!child) {
            process_id = raw(SYS_getpid, 0, 0, 0, 0);
            thread_id = raw(SYS_gettid, 0, 0, 0, 0);
            stack_t selected = {.ss_sp = fault ? alternate : (void *)(UINTPTR_MAX-4095),
                                .ss_size = fault ? 8192 : sizeof(alternate), .ss_flags = 0};
            if (alt(&selected, 0) != 0 || install(1, 1) != 0) child_exit(95);
            mode = 9;
            raw(SYS_tgkill, process_id, thread_id, SIGUSR1, 0);
            child_exit(94);
        }
        status = -1;
        CHECK(waitpid((pid_t)child, &status, 0) == child && (status & 0x7f) == SIGSEGV, 127);
    }
    CHECK(alt(0, &current) == 0 && same(&current, &expected), 128);
    CHECK(alt(&disable, 0) == 0 && alt(0, &current) == 0 && same(&current, &disable), 129);
    CHECK(outer_count == 5 && inner_count == 2, 130);
    const char success[] = "ALTSTACK_PASS " ARCH " handlers=5 nested=2 onstack=1 autodisarm=2 restore_ignored=2 fork=1 pthread_reset=1 failed_exec=1 fault_children=2\n";
    CHECK(raw(SYS_write, 1, (long)success, sizeof(success)-1, 0) == sizeof(success)-1, 131);
    char count[] = "ALTSTACK_CHECKS count=00\n";
    size_t at = sizeof("ALTSTACK_CHECKS count=")-1;
    count[at] = '0' + checks/10; count[at+1] = '0' + checks%10;
    raw(SYS_write, 1, (long)count, sizeof(count)-1, 0);
    return 0;
}

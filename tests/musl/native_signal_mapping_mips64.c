#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <sys/syscall.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/wait.h>

#if defined(__mips64) && defined(_ABI64) && _MIPS_SIM == _ABI64 && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__ && __mips_fpr == 64 && __mips_isa_rev == 2
#define ARCH "mips64"
#else
#error "Private reserved signal mapping fixture requires big-endian MIPS64r2 n64 FR1"
#endif
_Static_assert(sizeof(uintptr_t)==8 && sizeof(long)==8 && SYS_rt_sigreturn==5211,"native n64 mapping ABI");
// This probes the experimental OS reservation policy, not Linux vDSO policy.
static volatile uintptr_t restorer;
static volatile sig_atomic_t calls, bad;
static unsigned checks;
static int valid_code(uintptr_t address)
{
    if (!address || (address & 4095)) return 0;
    const volatile uint32_t *code = (const volatile uint32_t *)address;
    // Native n64 has one RT-only 16-byte entry: addiu v0,zero,5211;
    // syscall; break; break. Both SA_SIGINFO settings return through it.
    return code[0] == 0x2402145b && code[1] == 0x0000000c &&
           code[2] == 0x0000000d && code[3] == 0x0000000d;
}
static void handler(int signal, siginfo_t *info, void *context)
{
    (void)info; (void)context;
    uintptr_t address = (uintptr_t)__builtin_return_address(0);
    if (signal != SIGUSR1 || (restorer && address != restorer) || !valid_code(address)) bad = 1;
    restorer = address;
    ++calls;
}
#define CHECK(condition, code) do { ++checks; if (!(condition) || bad) { \
    printf("SIGNAL_MAP_FAIL code=%d checks=%u calls=%d bad=%d\n", code, checks, (int)calls, (int)bad); return 1; } } while (0)
// Each failed range operation must preserve both bytes and writability.
// Volatile accesses require actual stores even under the optimized guest build.
static int adjacent_writable(volatile unsigned char *page)
{
    if(page[0]!=41 || page[4095]!=42)return 0;
    page[0]=91;page[4095]=92;
    if(page[0]!=91 || page[4095]!=92)return 0;
    page[0]=41;page[4095]=42;
    return page[0]==41 && page[4095]==42;
}

int main(int argc, char **argv)
{
    struct sigaction action = {0};
    action.sa_sigaction = handler;
    action.sa_flags = SA_SIGINFO;
    CHECK(sigemptyset(&action.sa_mask) == 0 && sigaction(SIGUSR1, &action, 0) == 0, 101);
    CHECK(raise(SIGUSR1) == 0 && calls == 1 && valid_code(restorer), 102);
    if (argc == 2 && !strcmp(argv[1], "--exec-child")) {
        puts("SIGNAL_MAP_EXEC_CHILD_PASS " ARCH " fresh=1 restorer=1");
        return 0;
    }
    CHECK(argc == 1 && argv[0][0] == '/' && sysconf(_SC_PAGESIZE) == 4096, 103);
    void *page = (void *)restorer;
    errno = 0;
    CHECK(munmap(page, 4096) == -1 && errno == EACCES, 104);
    const int protections[] = {PROT_NONE, PROT_READ, PROT_READ | PROT_WRITE};
    for (unsigned i = 0; i < sizeof(protections)/sizeof(protections[0]); ++i) {
        errno = 0;
        CHECK(mprotect(page, 4096, protections[i]) == -1 && errno == EACCES, 105+i);
    }
    errno = 0;
    CHECK(mmap(page, 4096, PROT_READ | PROT_WRITE, MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) == MAP_FAILED && errno == EACCES, 108);
    unsigned char *hint = mmap(page, 4096, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK(hint != MAP_FAILED && (uintptr_t)hint != restorer, 109);
    CHECK(hint[0] == 0 && hint[4095] == 0, 110);
    hint[0] = 31; hint[4095] = 32;
    CHECK(munmap(hint, 4096) == 0, 111);
    unsigned char *adjacent = (unsigned char *)(restorer - 4096);
    CHECK(mmap(adjacent, 4096, PROT_READ | PROT_WRITE, MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) == adjacent, 112);
    adjacent[0] = 41; adjacent[4095] = 42;
    errno = 0;
    CHECK(mprotect(adjacent, 8192, PROT_READ) == -1 && errno == EACCES && adjacent_writable(adjacent), 113);
    errno = 0;
    CHECK(munmap(adjacent, 4097) == -1 && errno == EACCES && adjacent_writable(adjacent), 114);
    errno = 0;
    CHECK(mmap(adjacent, 8192, PROT_READ | PROT_WRITE, MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) == MAP_FAILED && errno == EACCES && adjacent_writable(adjacent), 115);
    CHECK(adjacent[0] == 41 && adjacent[4095] == 42 && valid_code(restorer), 116);
    CHECK(munmap(adjacent, 4096) == 0, 117);
    // Native n64 plain handlers also receive an RT frame and use the same PC.
    action.sa_flags = 0;
    CHECK(sigaction(SIGUSR1, &action, 0) == 0, 131);
    CHECK(raise(SIGUSR1) == 0 && calls == 2 && valid_code(restorer), 118);
    pid_t child = fork();
    CHECK(child >= 0, 119);
    if (!child) {
        *(volatile uint32_t *)restorer = 0;
        _exit(99);
    }
    int status = 0;
    CHECK(waitpid(child, &status, 0) == child && WIFSIGNALED(status) && WTERMSIG(status) == SIGSEGV, 120);
    char *empty_env[] = {0};
    char *missing[] = {"/missing-private-signal-map", 0};
    errno = 0;
    CHECK(execve(missing[0], missing, empty_env) == -1 && errno == ENOENT, 121);
    CHECK(raise(SIGUSR1) == 0 && calls == 3 && valid_code(restorer), 122);
    child = fork();
    CHECK(child >= 0, 123);
    if (!child) {
        CHECK(raise(SIGUSR1) == 0 && calls == 4 && valid_code(restorer), 130);
        char *arguments[] = {argv[0], "--exec-child", 0};
        execve(argv[0], arguments, empty_env);
        _exit(98);
    }
    CHECK(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0, 124);
    CHECK(raise(SIGUSR1) == 0 && calls == 4 && valid_code(restorer), 125);
    puts("SIGNAL_MAP_PASS " ARCH " handlers=4 protected=8 hint=1 adjacent=1 fork=1 exec=1 write_fault=1 rt_only=1 plain=1 siginfo=1");
    printf("SIGNAL_MAP_CHECKS count=%u\n", checks);
    return 0;
}

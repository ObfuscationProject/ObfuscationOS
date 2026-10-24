#define _GNU_SOURCE
#include <stdint.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/wait.h>

#if defined(__loongarch64)
#define ARCH "loongarch64"
#else
#error "Private reserved signal mapping fixture requires LoongArch64"
#endif
// This probes the experimental OS reservation policy, not Linux vDSO policy.
static volatile uintptr_t restorer;
static volatile sig_atomic_t calls, bad;
static unsigned checks;
static int valid_code(uintptr_t address)
{
    if (!address || (address & 4095)) return 0;
    const volatile uint32_t *code = (const volatile uint32_t *)address;
    return code[0] == 0x02822c0b && code[1] == 0x002b0000 &&
           code[2] == 0x002a0000 && code[3] == 0x002a0000;
}
static void handler(int signal)
{
    uintptr_t address = (uintptr_t)__builtin_return_address(0);
    if (signal != SIGUSR1 || (restorer && address != restorer) || !valid_code(address)) bad = 1;
    restorer = address;
    ++calls;
}
#define CHECK(condition, code) do { ++checks; if (!(condition) || bad) { \
    printf("SIGNAL_MAP_FAIL code=%d checks=%u calls=%d bad=%d\n", code, checks, (int)calls, (int)bad); return 1; } } while (0)
int main(int argc, char **argv)
{
    struct sigaction action = {0};
    action.sa_handler = handler;
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
    CHECK(mprotect(adjacent, 8192, PROT_READ) == -1 && errno == EACCES, 113);
    errno = 0;
    CHECK(munmap(adjacent, 4097) == -1 && errno == EACCES, 114);
    errno = 0;
    CHECK(mmap(adjacent, 8192, PROT_READ | PROT_WRITE, MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) == MAP_FAILED && errno == EACCES, 115);
    CHECK(adjacent[0] == 41 && adjacent[4095] == 42 && valid_code(restorer), 116);
    CHECK(munmap(adjacent, 4096) == 0, 117);
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
    puts("SIGNAL_MAP_PASS " ARCH " handlers=4 protected=8 hint=1 adjacent=1 fork=1 exec=1 write_fault=1");
    printf("SIGNAL_MAP_CHECKS count=%u\n", checks);
    return 0;
}

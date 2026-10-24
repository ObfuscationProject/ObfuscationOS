#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <unistd.h>

#if defined(__x86_64__)
#define ACCESS_PROFILE "x86_64"
#elif defined(__aarch64__)
#define ACCESS_PROFILE "aarch64"
#elif defined(__riscv) && __riscv_xlen == 64
#define ACCESS_PROFILE "rv64"
#elif defined(__loongarch__) && __loongarch_grlen == 64
#define ACCESS_PROFILE "loongarch64"
#else
#error "Native access execution requires an explicit supplied musl profile"
#endif

static unsigned checks;
static void fail(unsigned line)
{
    dprintf(1, "ACCESS_NATIVE_FAIL line=%u checks=%u errno=%d\n", line, checks, errno);
    _exit(1);
}
#define CHECK(x) do { ++checks; if (!(x)) fail(__LINE__); } while (0)
static long query(int fd, const char *path, unsigned mode, unsigned flags)
{
    return syscall(SYS_faccessat2, (long)fd, (long)path, (long)mode, (long)flags);
}
static void denied(long value, int error)
{
    CHECK(value == -1 && errno == error);
}
static void root(void)
{
    CHECK(setresuid(-1, 0, -1) == 0);
    CHECK(setresgid(0, 0, 0) == 0 && setresuid(0, 0, 0) == 0);
}

int main(void)
{
    CHECK(getuid() == 0 && geteuid() == 0 && getgid() == 0 && getegid() == 0);
    int directory = open("/access/search", O_RDONLY | O_DIRECTORY);
    int file = open("/access/owner", O_RDONLY);
    CHECK(directory >= 0 && file >= 0);
    CHECK(access("/access/none", F_OK) == 0);
    CHECK(access("/access/none", R_OK | W_OK) == 0);
    denied(access("/access/none", X_OK), EACCES);
    CHECK(access("/access/execute", X_OK) == 0);
    CHECK(query(-999, "/access/root", R_OK, 0) == 0);

    CHECK(setresgid(2000, 0, 0) == 0 && setresuid(1000, 0, 0) == 0);
    CHECK(access("/access/owner", R_OK) == 0);
    denied(access("/access/root", R_OK), EACCES);
    CHECK(faccessat(AT_FDCWD, "/access/root", R_OK, AT_EACCESS) == 0);
    CHECK(faccessat(-999, "/access/owner", R_OK, 0) == 0);
    CHECK(getuid() == 1000 && geteuid() == 0 && getgid() == 2000 && getegid() == 0);
    root();
    CHECK(setresgid(2000, 4000, 0) == 0 && setresuid(5000, 5000, 0) == 0);
    CHECK(access("/access/group", R_OK) == 0);
    denied(faccessat(AT_FDCWD, "/access/group", R_OK, AT_EACCESS), EACCES);
    root();
    CHECK(setresgid(2000, 2000, 0) == 0 && setresuid(3000, 3000, 0) == 0);
    denied(access("/access/group", R_OK), EACCES); /* Owner bits take precedence. */
    root();
    CHECK(setresuid(5000, 1000, 0) == 0);
    denied(access("/access/search/child", F_OK), EACCES);
    CHECK(faccessat(AT_FDCWD, "/access/search/child", F_OK, AT_EACCESS) == 0);
    root();
    CHECK(setresuid(0, 1000, 0) == 0);
    CHECK(access("/access/root", R_OK) == 0);
    denied(faccessat(AT_FDCWD, "/access/root", R_OK, AT_EACCESS), EACCES);
    root();
    CHECK(setresgid(2000, 2000, 0) == 0 && setresuid(1000, 1000, 0) == 0);
    CHECK(faccessat(directory, "child", R_OK, 0) == 0);
    CHECK(syscall(SYS_faccessat, (long)directory, (long)"child", (long)R_OK, ~0UL) == 0);
    denied(syscall(SYS_faccessat, (long)-999, (long)1, (long)8, ~0UL), EINVAL);
    CHECK(query(file, "", R_OK, AT_EMPTY_PATH) == 0);
    denied(query(file, "", W_OK, AT_EMPTY_PATH), EACCES);
    denied(query(-999, "", F_OK, AT_EMPTY_PATH), EBADF);
    denied(query(file, "", F_OK, 0), ENOENT);
    int pair[2];
    CHECK(pipe(pair) == 0);
    CHECK(query(pair[0], "", F_OK, AT_EMPTY_PATH) == 0);
    CHECK(query(pair[1], "", F_OK, AT_EMPTY_PATH) == 0);
    denied(query(pair[0], "", R_OK, AT_EMPTY_PATH), ENOSYS);
    denied(query(pair[1], "", W_OK, AT_EMPTY_PATH), ENOSYS);
    denied(query(1, "", W_OK, AT_EMPTY_PATH), ENOSYS);
    CHECK(query(1, "", F_OK, AT_EMPTY_PATH) == 0);
    CHECK(close(pair[0]) == 0 && close(pair[1]) == 0);
    denied(query(pair[0], "", F_OK, AT_EMPTY_PATH), EBADF);
    denied(query(file, "child", F_OK, 0), ENOTDIR);
    denied(query(-999, "child", F_OK, 0), EBADF);
    CHECK(chdir("/access/search") == 0);
    CHECK(access("child", R_OK) == 0 && query(AT_FDCWD, "", X_OK, AT_EMPTY_PATH) == 0);
    CHECK(chdir("/") == 0);
    denied(access("/access/dangling", F_OK), ENOENT);
    CHECK(faccessat(AT_FDCWD, "/access/dangling", R_OK | W_OK | X_OK, AT_SYMLINK_NOFOLLOW) == 0);
    denied(access("/access/owner/", F_OK), ENOTDIR);
    denied(query(-999, (const char *)1, 8, 0), EINVAL);
    denied(query(-999, (const char *)1, F_OK, 0x80000000u), EINVAL);
    denied(query(file, 0, F_OK, AT_EMPTY_PATH), EFAULT);
    unsigned char *pages = mmap(0, 8192, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK(pages != MAP_FAILED && mprotect(pages + 4096, 4096, PROT_NONE) == 0);
    pages[4095] = 0;
    CHECK(query(file, (char *)pages + 4095, R_OK, AT_EMPTY_PATH) == 0);
    pages[4095] = 'x';
    denied(query(file, (char *)pages + 4095, F_OK, AT_EMPTY_PATH), EFAULT);
    CHECK(munmap(pages, 8192) == 0 && close(file) == 0 && close(directory) == 0);
    denied(query(file, "", F_OK, AT_EMPTY_PATH), EBADF);
    root();
    dprintf(1, "ACCESS_NATIVE_PASS checks=%u profile=" ACCESS_PROFILE " real_effective=1 primary_group=1 checked_copy=1 dac_only=1\n", checks);
    return 0;
}

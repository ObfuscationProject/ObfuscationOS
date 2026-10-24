#define _GNU_SOURCE
#include <errno.h>
#include <time.h>
#include <unistd.h>

static int musl_file_tests(void);
static int musl_heap_tests(void);

static _Thread_local volatile int tls_value = 7;

int heap_probe_main(int argc, char **argv, char **envp)
{
    if (argc != 1 || !argv || !argv[0] || argv[1] || !envp || !envp[0])
        return 10;
    if (tls_value != 7)
        return 11;
    tls_value += 5;
    if (tls_value != 12)
        return 12;
    errno = 0;
    if (close(-1) != -1 || errno != EBADF)
        return 13;
    struct timespec first, second;
    if (clock_gettime(CLOCK_MONOTONIC, &first) || clock_gettime(CLOCK_MONOTONIC, &second))
        return 14;
    if (first.tv_sec < 0 || first.tv_nsec < 0 || first.tv_nsec >= 1000000000 ||
        second.tv_sec < first.tv_sec || (second.tv_sec == first.tv_sec && second.tv_nsec < first.tv_nsec))
        return 15;
    static const char marker[] = "OK_MUSL_NATIVE scope=hardware libc=musl-1.2.5 startup=pass tls=pass errno=pass clock=pass\n";
    if (write(1, marker, sizeof(marker) - 1) != sizeof(marker) - 1)
        return 16;
    int result = musl_file_tests();
    return result ? result : musl_heap_tests();
}

#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/uio.h>
#include <unistd.h>

static int failure(int code, int detail)
{
    int saved_errno = errno;
    char line[96];
    unsigned position = 0;
    const char *labels[3] = {"MUSL_PROBE_FAIL code=", " errno=", " detail="};
    const unsigned values[3] = {(unsigned)code, (unsigned)saved_errno, (unsigned)detail};
    for (unsigned field = 0; field < 3; ++field) {
        for (const char *label = labels[field]; *label; ++label) line[position++] = *label;
        char digits[16]; unsigned count = 0, value = values[field];
        do { digits[count++] = (char)('0' + value % 10); value /= 10; } while (value);
        while (count) line[position++] = digits[--count];
    }
    line[position++] = '\n';
    (void)write(2, line, position);
    return code;
}
#define REQUIRE(condition, code) do { if (!(condition)) return failure((code), 0); } while (0)

/* The native harness supplies /home/musl-link -> musl-file on a scratch root. */
static int musl_file_tests(void)
{
    int directory = openat(AT_FDCWD, "/home", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    REQUIRE(directory >= 0, 20);
    int fd = openat(directory, "musl-file", O_CREAT | O_TRUNC | O_RDWR | O_CLOEXEC | O_NOFOLLOW, 0600);
    REQUIRE(fd >= 0, 21);
    char buffer[8] = {0};
    REQUIRE(read(fd, buffer, sizeof buffer) == 0, 22);
    REQUIRE(write(fd, "abc", 3) == 3 && close(fd) == 0, 23);
    errno = 0;
    REQUIRE(openat(directory, "musl-file", O_CREAT | O_EXCL | O_WRONLY, 0600) == -1 && errno == EEXIST, 24);
    fd = openat(directory, "musl-file", O_WRONLY | O_APPEND);
    REQUIRE(fd >= 0, 25);
    errno = 0;
    REQUIRE(read(fd, buffer, 1) == -1 && errno == EBADF, 26);
    REQUIRE(close(fd) == 0, 45);
    /* O_APPEND redirects writes, while reads start at offset zero. */
    fd = openat(directory, "musl-file", O_RDONLY | O_APPEND);
    buffer[0] = 0;
    REQUIRE(fd >= 0 && read(fd, buffer, 1) == 1 && buffer[0] == 'a' && close(fd) == 0, 46);
    fd = openat(directory, "musl-file", O_RDWR | O_APPEND);
    buffer[0] = 0;
    REQUIRE(fd >= 0 && read(fd, buffer, 1) == 1 && buffer[0] == 'a', 47);
    /* The current offset is one, but this writev must still append at EOF. */
    struct iovec output[2] = {{(void *)"de", 2}, {(void *)"f", 1}};
    REQUIRE(writev(fd, output, 2) == 3 && close(fd) == 0, 27);
    fd = openat(directory, "musl-file", O_RDONLY);
    REQUIRE(fd >= 0, 28);
    errno = 0;
    REQUIRE(write(fd, "x", 1) == -1 && errno == EBADF, 29);
    struct iovec input[2] = {{buffer, 2}, {buffer + 2, 6}};
    REQUIRE(readv(fd, input, 2) == 6 && memcmp(buffer, "abcdef", 6) == 0, 30);
    REQUIRE(read(fd, buffer, 1) == 0 && close(fd) == 0, 31);
    errno = 0;
    REQUIRE(openat(directory, "musl-file", O_RDONLY | O_DIRECTORY) == -1 && errno == ENOTDIR, 32);
    errno = 0;
    REQUIRE(openat(directory, ".", O_WRONLY) == -1 && errno == EISDIR, 33);
    errno = 0;
    REQUIRE(openat(directory, ".", O_RDONLY | O_TRUNC) == -1 && errno == EISDIR, 34);
    errno = 0;
    REQUIRE(openat(directory, "musl-link", O_RDONLY | O_NOFOLLOW) == -1 && errno == ELOOP, 35);
    memset(buffer, 0, sizeof buffer);
    fd = openat(directory, "musl-link", O_RDONLY);
    REQUIRE(fd >= 0 && read(fd, buffer, sizeof buffer) == 6 && memcmp(buffer, "abcdef", 6) == 0 && close(fd) == 0, 36);

    int opened[64];
    unsigned count = 0;
    for (; count < sizeof opened / sizeof opened[0]; ++count) {
        opened[count] = openat(directory, "musl-file", O_RDONLY);
        if (opened[count] == -1)
            break;
    }
    if (!(count > 0 && count < sizeof opened / sizeof opened[0] && errno == EMFILE)) return failure(37, (int)count);
    errno = 0;
    REQUIRE(openat(directory, "musl-file", O_WRONLY | O_TRUNC) == -1 && errno == EMFILE, 38);
    errno = 0;
    REQUIRE(openat(directory, "musl-no-create", O_CREAT | O_EXCL | O_WRONLY, 0600) == -1 && errno == EMFILE, 39);
    for (unsigned i = 0; i < count; ++i)
        REQUIRE(close(opened[i]) == 0, 40);
    memset(buffer, 0, sizeof buffer);
    fd = openat(directory, "musl-file", O_RDONLY);
    REQUIRE(fd >= 0 && read(fd, buffer, sizeof buffer) == 6 && memcmp(buffer, "abcdef", 6) == 0 && close(fd) == 0, 41);
    errno = 0;
    REQUIRE(openat(directory, "musl-no-create", O_RDONLY) == -1 && errno == ENOENT, 42);
    fd = openat(directory, "musl-file", O_RDONLY);
    REQUIRE(fd >= 0 && fsync(fd) == 0 && fdatasync(fd) == 0 && close(fd) == 0, 48);
    errno = 0;
    REQUIRE(fsync(-1) == -1 && errno == EBADF, 49);
    errno = 0;
    REQUIRE(fdatasync(-1) == -1 && errno == EBADF, 50);
    REQUIRE(close(directory) == 0, 43);
    static const char marker[] = "OK_MUSL_FILES scope=hardware openat=pass flags=pass append=pass vector_io=pass symlink=pass limits=pass sync=pass\n";
    REQUIRE(write(1, marker, sizeof marker - 1) == sizeof marker - 1, 44);
    return 0;
}

#include <stdlib.h>
#include <stdint.h>
#include <sys/mman.h>

static int heap_tests(void)
{
    unsigned char *p = malloc(4097);
    REQUIRE(p != 0, 60);
    memset(p, 0x35, 4097);
    unsigned char *q = realloc(p, 12000);
    REQUIRE(q != 0, 61);
    for (unsigned i = 0; i < 4097; ++i) REQUIRE(q[i] == 0x35, 62);
    free(q);
    p = calloc(255, 17);
    REQUIRE(p != 0, 63);
    for (unsigned i = 0; i < 255*17; ++i) REQUIRE(p[i] == 0, 64);
    free(p);
    void *aligned = 0;
    REQUIRE(posix_memalign(&aligned, 4096, 8192) == 0 && aligned && !((uintptr_t)aligned & 4095), 65);
    memset(aligned, 0x69, 8192);
    free(aligned);
    for (unsigned run = 0; run < 32; ++run) {
        p = malloc(24576);
        REQUIRE(p != 0, 66);
        memset(p, (unsigned char)run, 24576);
        for (unsigned i = 0; i < 24576; ++i) REQUIRE(p[i] == (unsigned char)run, 67);
        free(p);
    }
    static const char marker[] = "OK_MUSL_HEAP malloc=pass calloc=pass realloc=pass alignment=pass reuse=pass\n";
    REQUIRE(write(1, marker, sizeof marker-1) == sizeof marker-1, 68);
    return 0;
}
#include <sys/syscall.h>
static int musl_heap_tests(void)
{
    unsigned long initial = (unsigned long)syscall(SYS_brk, 0);
    REQUIRE(initial > 4096 && initial != (unsigned long)-1, 70);
    REQUIRE((unsigned long)syscall(SYS_brk, initial + 8193) == initial + 8193, 71);
    unsigned char *heap = (void *)initial;
    for (unsigned i = 0; i < 8193; ++i) REQUIRE(heap[i] == 0, 72);
    memset(heap, 0x81, 8193);
    REQUIRE((unsigned long)syscall(SYS_brk, initial + 1) == initial + 1 && heap[0] == 0x81, 73);
    REQUIRE((unsigned long)syscall(SYS_brk, initial) == initial, 74);
    errno = 0;
    REQUIRE((unsigned long)syscall(SYS_brk, initial - 1) == initial && errno == 0, 75);
    REQUIRE((unsigned long)syscall(SYS_brk, initial + 0x40000000UL) == initial, 76);
    unsigned char *mapped = mmap(0, 3*4096, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    REQUIRE(mapped != MAP_FAILED, 77);
    memset(mapped, 0x6a, 3*4096);
    REQUIRE(mmap(mapped+4096, 4096, PROT_NONE, MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED, -1, 0) == mapped+4096, 78);
    REQUIRE(mapped[0] == 0x6a && mapped[8192] == 0x6a, 79);
    REQUIRE(mprotect(mapped+4096,4096,PROT_READ|PROT_WRITE) == 0 && mapped[4096] == 0, 80);
    REQUIRE(munmap(mapped, 3*4096) == 0, 81);
    int result = heap_tests();
    if (result) return result;
    void *allocations[64];
    unsigned count = 0;
    for (; count < 64; ++count) {
        errno = 0;
        allocations[count] = malloc(8192);
        if (!allocations[count]) break;
        memset(allocations[count], (unsigned char)count, 8192);
    }
    if (!(count > 0 && count < 64 && errno == ENOMEM)) return failure(82, (int)count);
    for (unsigned i=0; i<count; ++i) {
        unsigned char *ptr=allocations[i];
        for (unsigned j=0; j<8192; ++j) REQUIRE(ptr[j] == (unsigned char)i, 83);
        free(ptr);
    }
    void *again=malloc(8192); REQUIRE(again!=0,84); free(again);
    static const char marker[]="OK_MUSL_HEAP_VM brk=pass fixed=pass pressure=pass reclaim=pass\n";
    REQUIRE(write(1,marker,sizeof marker-1)==sizeof marker-1,85);
    return 0;
}

#include <sys/wait.h>
#if defined(__riscv) && __riscv_xlen == 32
#include <signal.h>
#include <stddef.h>
_Static_assert(sizeof(siginfo_t) == 128, "RV32 siginfo size");
_Static_assert(offsetof(siginfo_t, si_pid) == 12, "RV32 siginfo pid offset");
_Static_assert(offsetof(siginfo_t, si_uid) == 16, "RV32 siginfo uid offset");
_Static_assert(offsetof(siginfo_t, si_status) == 20, "RV32 siginfo status offset");
#endif
extern char **environ;
static volatile unsigned isolation_word = 0x24;
static int process_probe_main(int argc, char **argv, char **envp)
{
    if (argc == 2 && !strcmp(argv[1], "child-exec")) {
        if (getpid() <= 0 || getppid() <= 0 || syscall(SYS_gettid) != getpid() || isolation_word != 0x24) return 99;
        return 42;
    }
    int result = heap_probe_main(argc, argv, envp);
    if (result) return result;
    pid_t parent = getpid();
    REQUIRE(parent > 0 && getppid() > 0 && (pid_t)syscall(SYS_gettid) == parent, 90);
    REQUIRE(syscall(SYS_set_tid_address, 0) == parent, 111);
    REQUIRE(getuid() == 0 && geteuid() == 0 && getgid() == 0 && getegid() == 0, 91);
    int fd = openat(AT_FDCWD,"/home/musl-process", O_CREAT|O_TRUNC|O_RDWR,0600);
    REQUIRE(fd >= 0 && write(fd,"parent",6) == 6,92);
    pid_t child = fork();
    REQUIRE(child >= 0,93);
    if (!child) {
        if (getpid() == parent || getppid() != parent || syscall(SYS_gettid) != getpid() || isolation_word != 0x24) _exit(94);
        isolation_word = 0x81;
        if (write(fd,"child",5) != 5) _exit(95);
        char *child_args[] = {"/bin/musl-bootstrap", "child-exec", 0};
        execve(child_args[0],child_args,environ);
        _exit(96);
    }
#if defined(__riscv) && __riscv_xlen == 32
    errno = 0;
    REQUIRE(syscall(SYS_waitid, P_PID, child, (void *)-1, WEXITED, 0) == -1 && errno == EFAULT, 110);
#endif
    int status = -1;
#if __SIZEOF_LONG__ == 8 && defined(SYS_wait4)
    /* Raw Linux pid_t/options remain 32-bit scalars on LP64. */
    REQUIRE(syscall(SYS_wait4, (unsigned long)child | (1UL << 32), &status, 1UL << 32, 0) == child, 112);
#else
    REQUIRE(waitpid(child,&status,0) == child,97);
#endif
    REQUIRE(WIFEXITED(status) && WEXITSTATUS(status) == 42,97);
    REQUIRE(isolation_word == 0x24 && getpid() == parent,98);
    REQUIRE(write(fd,"!",1)==1 && fsync(fd)==0 && close(fd)==0,100);
    fd=openat(AT_FDCWD,"/home/musl-process",O_RDONLY);
    char bytes[16]={0};
    REQUIRE(fd>=0 && read(fd,bytes,sizeof bytes)==12 && !memcmp(bytes,"parentchild!",12) && close(fd)==0,101);
    errno=0;REQUIRE(waitpid(child,&status,0)==-1 && errno==ECHILD,102);
    /* Reap every child before retrying; a full native page/table pool may
       report ENOMEM before the common child/process limit reports EAGAIN. */
    pid_t children[64]; unsigned child_count = 0;
    for (; child_count < 64; ++child_count) {
        errno = 0;
        pid_t next = fork();
        if (next == -1) break;
        if (!next) _exit(19);
        children[child_count] = next;
    }
    if (!(child_count > 0 && child_count < 64 && (errno == EAGAIN || errno == ENOMEM)))
        return failure(104, (int)child_count);
    {
        char line[80]; unsigned length = 0;
        const char *prefix = errno == EAGAIN ? "OK_MUSL_PROCESS_LIMIT errno=EAGAIN children=" : "OK_MUSL_PROCESS_LIMIT errno=ENOMEM children=";
        for (; *prefix; ++prefix) line[length++] = *prefix;
        char digits[8]; unsigned n = 0, value = child_count;
        do { digits[n++] = (char)('0' + value % 10); value /= 10; } while (value);
        while (n) line[length++] = digits[--n];
        line[length++] = '\n';
        REQUIRE(write(1, line, length) == (ssize_t)length, 109);
    }
    for (unsigned i = 0; i < child_count; ++i)
        REQUIRE(waitpid(children[i], &status, 0) == children[i] && WIFEXITED(status) && WEXITSTATUS(status) == 19, 105);
    child = fork();
    REQUIRE(child >= 0, 106);
    if (!child) _exit(23);
    REQUIRE(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 23, 107);
    static const char capacity_marker[]="OK_MUSL_PROCESS_CAPACITY bounded=pass reap=pass retry=pass\n";
    REQUIRE(write(1, capacity_marker, sizeof capacity_marker-1) == sizeof capacity_marker-1, 108);
    static const char marker[]="OK_MUSL_PROCESS identity=pass fork=pass isolation=pass exec=pass wait=pass shared_fd=pass\n";
    REQUIRE(write(1,marker,sizeof marker-1)==sizeof marker-1,103);
    return 0;
}

static int paths_probe_main(int argc, char **argv, char **envp)
{
    int result = process_probe_main(argc, argv, envp);
    if (result || argc != 1) return result;
    char cwd[256];
    REQUIRE(getcwd(cwd, sizeof cwd) == cwd && !strcmp(cwd, "/"), 120);
    REQUIRE(syscall(SYS_getcwd, cwd, sizeof cwd) == 2, 121);
    errno = 0;
    REQUIRE(getcwd(cwd, 1) == 0 && errno == ERANGE, 122);
    int home = openat(AT_FDCWD, "/home", O_RDONLY | O_DIRECTORY);
    REQUIRE(home >= 0 && chdir("/home") == 0, 123);
    REQUIRE(getcwd(cwd, sizeof cwd) == cwd && !strcmp(cwd, "/home"), 124);
    REQUIRE(chdir("..") == 0 && fchdir(home) == 0, 125);
    REQUIRE(syscall(SYS_getcwd, cwd, (size_t)-1) == 6 && !strcmp(cwd, "/home"), 126);
    errno = 0;
    REQUIRE(chdir("musl-file") == -1 && errno == ENOTDIR, 127);
    errno = 0;
    REQUIRE(fchdir(-1) == -1 && errno == EBADF, 128);
    char link[32]; memset(link, 0x55, sizeof link);
    REQUIRE(readlinkat(home, "musl-link", link, 2) == 2 && !memcmp(link, "mu", 2) && link[2] == 0x55, 129);
    REQUIRE(readlink("musl-link", link, sizeof link) == 9 && !memcmp(link, "musl-file", 9), 130);
    errno = 0;
    REQUIRE(readlinkat(home, "musl-file", link, sizeof link) == -1 && errno == EINVAL, 131);
    REQUIRE(syscall(SYS_readlinkat, -1, "/home/musl-link", link, sizeof link) == 9, 132);
    errno = 0;
    REQUIRE(syscall(SYS_readlinkat, home, "musl-link", link, 0x80000000u) == -1 && errno == EINVAL, 133);
#if __SIZEOF_LONG__ == 8
    REQUIRE(syscall(SYS_readlinkat, home, "musl-link", link, (1UL << 32) | 2) == 2, 134);
#endif
    REQUIRE(close(home) == 0 && chdir("/") == 0, 135);
    char *edge = mmap(0, 8192, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    REQUIRE(edge != MAP_FAILED && mprotect(edge + 4096, 4096, PROT_NONE) == 0, 137);
    REQUIRE(syscall(SYS_getcwd, edge + 4094, 4096) == 2 && !strcmp(edge + 4094, "/"), 138);
    REQUIRE(readlinkat(-1, "/home/musl-link", edge + 4087, 4096) == 9 && !memcmp(edge + 4087, "musl-file", 9), 139);
    REQUIRE(munmap(edge, 8192) == 0, 140);
    static const char marker[] = "OK_MUSL_PATHS cwd=pass chdir=pass fchdir=pass readlink=pass boundaries=pass\n";
    REQUIRE(write(1, marker, sizeof marker - 1) == sizeof marker - 1, 136);
    return 0;
}


#ifdef SYS_fcntl64
#define DESCRIPTOR_SYSCALL SYS_fcntl64
#else
#define DESCRIPTOR_SYSCALL SYS_fcntl
#endif
static int descriptors_probe_main(int argc, char **argv, char **envp)
{
    if (argc == 2 && !strcmp(argv[1], "fd-exec")) {
        if (fcntl(24, F_GETFD) != 0 || !(fcntl(24, F_GETFL) & O_APPEND)) return 181;
        errno = 0;
        if (fcntl(25, F_GETFD) != -1 || errno != EBADF) return 182;
        errno = 0;
        if (fcntl(26, F_GETFD) != -1 || errno != EBADF) return 183;
        errno = 0;
        if (fcntl(3, F_GETFD) != -1 || errno != EBADF) return 184;
        if (write(24, "x", 1) != 1) return 185;
        return 37;
    }
    int result = paths_probe_main(argc, argv, envp);
    if (result || argc != 1) return result;
    int fd = openat(AT_FDCWD, "/home/musl-fds", O_CREAT | O_TRUNC | O_RDWR | O_CLOEXEC, 0600);
    REQUIRE(fd == 3 && write(fd, "abcdef", 6) == 6 && close(fd) == 0, 150);
    fd = openat(AT_FDCWD, "/home/musl-fds", O_RDWR | O_CLOEXEC | O_NOFOLLOW);
    REQUIRE(fd == 3 && fcntl(fd, F_GETFD) == FD_CLOEXEC, 151);
    int flags = fcntl(fd, F_GETFL);
    REQUIRE(flags >= 0 && (flags & O_ACCMODE) == O_RDWR && (flags & O_NOFOLLOW) &&
        !(flags & (O_CREAT | O_EXCL | O_TRUNC | O_CLOEXEC)), 152);
    int copied = dup(fd);
    REQUIRE(copied == 4 && fcntl(copied, F_GETFD) == 0, 153);
    char byte = 0;
    REQUIRE(read(fd, &byte, 1) == 1 && byte == 'a' && read(copied, &byte, 1) == 1 && byte == 'b', 154);
    REQUIRE(fcntl(copied, F_SETFD, FD_CLOEXEC) == 0 && fcntl(copied, F_GETFD) == FD_CLOEXEC, 155);
    REQUIRE(dup2(fd, copied) == copied && fcntl(copied, F_GETFD) == 0, 156);
    REQUIRE(dup2(fd, fd) == fd && fcntl(fd, F_GETFD) == FD_CLOEXEC, 157);
    REQUIRE(fcntl(copied, F_SETFL, flags | O_APPEND | O_NONBLOCK) == 0 &&
        (fcntl(fd, F_GETFL) & (O_APPEND | O_NONBLOCK)) == (O_APPEND | O_NONBLOCK), 158);
    REQUIRE(write(copied, "!", 1) == 1, 159);
    REQUIRE(fcntl(fd, F_DUPFD, 24) == 24 && fcntl(24, F_GETFD) == 0, 160);
    REQUIRE(fcntl(fd, F_DUPFD_CLOEXEC, 25) == 25 && fcntl(25, F_GETFD) == FD_CLOEXEC, 161);
    REQUIRE(dup3(fd, 26, O_CLOEXEC) == 26 && fcntl(26, F_GETFD) == FD_CLOEXEC, 162);
    errno = 0;
    REQUIRE(dup3(fd, fd, 0) == -1 && errno == EINVAL, 163);
    errno = 0;
    REQUIRE(dup2(-1, copied) == -1 && errno == EBADF && fcntl(copied, F_GETFD) == 0, 164);
    errno = 0;
    REQUIRE(fcntl(fd, F_DUPFD, 32) == -1 && errno == EINVAL, 165);
#if __SIZEOF_LONG__ == 8
    REQUIRE(syscall(DESCRIPTOR_SYSCALL, (1UL << 32) | fd, (1UL << 32) | F_GETFD, 0) == FD_CLOEXEC, 186);
    REQUIRE(syscall(DESCRIPTOR_SYSCALL, fd, F_DUPFD_CLOEXEC, (1UL << 32) | 27) == 27 && close(27) == 0, 187);
#endif
    pid_t child = fork();
    REQUIRE(child >= 0, 166);
    if (!child) {
        char *args[] = {"/bin/musl-bootstrap", "fd-exec", 0};
        execve(args[0], args, environ);
        _exit(180);
    }
    int status = -1;
    REQUIRE(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 37, 167);
    REQUIRE(fcntl(25, F_GETFD) == FD_CLOEXEC && fcntl(26, F_GETFD) == FD_CLOEXEC, 168);
    int opened[64]; unsigned count = 0;
    for (; count < sizeof opened / sizeof opened[0]; ++count) {
        opened[count] = dup(fd);
        if (opened[count] == -1) break;
    }
    REQUIRE(count > 0 && count < 64 && errno == EMFILE, 169);
    errno = 0;
    REQUIRE(fcntl(fd, F_DUPFD_CLOEXEC, 0) == -1 && errno == EMFILE, 170);
    REQUIRE(dup2(fd, copied) == copied, 171);
    int released = opened[--count];
    REQUIRE(close(released) == 0 && fcntl(fd, F_DUPFD_CLOEXEC, 0) == released, 172);
    REQUIRE(fcntl(released, F_GETFD) == FD_CLOEXEC && close(released) == 0, 173);
    for (unsigned i = 0; i < count; ++i) REQUIRE(close(opened[i]) == 0, 174);
    REQUIRE(fsync(fd) == 0 && close(copied) == 0 && close(24) == 0 && close(25) == 0 && close(26) == 0 && close(fd) == 0, 175);
    fd = openat(AT_FDCWD, "/home/musl-fds", O_RDONLY);
    char data[9] = {0};
    REQUIRE(fd >= 0 && read(fd, data, sizeof data) == 8 && !memcmp(data, "abcdef!x", 8) && close(fd) == 0, 176);
    static const char marker[] = "OK_MUSL_FDS dup=pass fcntl=pass shared_offset=pass flags=pass exec=pass pressure=pass\n";
    REQUIRE(write(1, marker, sizeof marker - 1) == sizeof marker - 1, 177);
    return 0;
}

static int pipes_probe_main(int argc, char **argv, char **envp)
{
    if (argc == 2 && !strcmp(argv[1], "pipe-exec")) {
        errno = 0;
        if (fcntl(25, F_GETFD) != -1 || errno != EBADF) return 231;
        errno = 0;
        if (fcntl(3, F_GETFD) != -1 || errno != EBADF) return 232;
        errno = 0;
        if (fcntl(4, F_GETFD) != -1 || errno != EBADF) return 233;
        if (fcntl(24, F_GETFD) != 0 || write(24, "e", 1) != 1) return 234;
        return 52;
    }
    int result = descriptors_probe_main(argc, argv, envp);
    if (result || argc != 1) return result;
    int fd[2]; char byte = 0;
    REQUIRE(pipe(fd) == 0 && fd[0] == 3 && fd[1] == 4, 190);
    REQUIRE(write(fd[1], "a", 1) == 1 && read(fd[0], &byte, 1) == 1 && byte == 'a', 191);
    REQUIRE(close(fd[0]) == 0 && close(fd[1]) == 0, 192);
    REQUIRE(pipe2(fd, O_NONBLOCK | O_CLOEXEC) == 0, 193);
    REQUIRE(fcntl(fd[0], F_GETFD) == FD_CLOEXEC && fcntl(fd[1], F_GETFD) == FD_CLOEXEC, 194);
    REQUIRE((fcntl(fd[0], F_GETFL) & (O_ACCMODE | O_NONBLOCK)) == (O_RDONLY | O_NONBLOCK) &&
            (fcntl(fd[1], F_GETFL) & (O_ACCMODE | O_NONBLOCK)) == (O_WRONLY | O_NONBLOCK), 195);
    errno = 0;
    REQUIRE(read(fd[0], &byte, 1) == -1 && errno == EAGAIN, 196);
    static char capacity[4096];
    memset(capacity, 'p', sizeof capacity);
    REQUIRE(write(fd[1], capacity, sizeof capacity) == sizeof capacity, 197);
    errno = 0;
    REQUIRE(write(fd[1], "x", 1) == -1 && errno == EAGAIN, 198);
    REQUIRE(read(fd[0], capacity, sizeof capacity) == sizeof capacity && capacity[0] == 'p' && capacity[4095] == 'p', 199);
    int writer = dup(fd[1]);
    REQUIRE(writer == 5 && fcntl(writer, F_GETFD) == 0 && close(fd[1]) == 0, 200);
    errno = 0;
    REQUIRE(read(fd[0], &byte, 1) == -1 && errno == EAGAIN, 201);
    REQUIRE(write(writer, "d", 1) == 1 && read(fd[0], &byte, 1) == 1 && byte == 'd', 202);
    REQUIRE(close(writer) == 0 && read(fd[0], &byte, 1) == 0 && close(fd[0]) == 0, 203);
    // Only the current errno behavior is tested. The admitted runtime has no
    // signal delivery and this probe does not claim POSIX SIGPIPE semantics.
    REQUIRE(pipe2(fd, O_NONBLOCK) == 0 && close(fd[0]) == 0, 204);
    errno = 0;
    REQUIRE(write(fd[1], "x", 1) == -1 && errno == EPIPE, 205);
    REQUIRE(write(fd[1], "", 0) == 0 && close(fd[1]) == 0, 206);
    errno = 0;
    REQUIRE(syscall(SYS_pipe2, fd, O_APPEND) == -1 && errno == EINVAL, 207);
    char *edge = mmap(0, 8192, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    REQUIRE(edge != MAP_FAILED && mprotect(edge + 4096, 4096, PROT_NONE) == 0, 208);
    for (unsigned i = 0; i < 40; ++i) {
        errno = 0;
        REQUIRE(syscall(SYS_pipe2, edge + 4092, O_NONBLOCK) == -1 && errno == EFAULT, 209);
    }
    REQUIRE(munmap(edge, 8192) == 0 && pipe(fd) == 0 && fd[0] == 3 && fd[1] == 4, 210);
    int reply[2];
    REQUIRE(pipe(reply) == 0, 211);
    pid_t child = fork();
    REQUIRE(child >= 0, 212);
    if (!child) {
        if (close(fd[1]) || close(reply[0])) _exit(236);
        if (read(fd[0], &byte, 1) != 1 || byte != 'q') _exit(237);
        if (write(reply[1], "r", 1) != 1) _exit(238);
        if (close(fd[0]) || close(reply[1])) _exit(239);
        _exit(51);
    }
    REQUIRE(close(fd[0]) == 0 && close(reply[1]) == 0, 213);
    REQUIRE(write(fd[1], "q", 1) == 1 && close(fd[1]) == 0, 214);
    REQUIRE(read(reply[0], &byte, 1) == 1 && byte == 'r', 215);
    int status = -1;
    REQUIRE(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 51, 216);
    REQUIRE(read(reply[0], &byte, 1) == 0 && close(reply[0]) == 0, 217);
    REQUIRE(pipe2(fd, O_CLOEXEC) == 0 && dup3(fd[1], 24, 0) == 24 && dup3(fd[0], 25, O_CLOEXEC) == 25, 218);
    child = fork();
    REQUIRE(child >= 0, 219);
    if (!child) {
        char *args[] = {"/bin/musl-bootstrap", "pipe-exec", 0};
        execve(args[0], args, environ);
        _exit(240);
    }
    REQUIRE(close(24) == 0 && close(25) == 0 && close(fd[1]) == 0, 220);
    REQUIRE(read(fd[0], &byte, 1) == 1 && byte == 'e', 221);
    REQUIRE(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 52, 222);
    REQUIRE(read(fd[0], &byte, 1) == 0 && close(fd[0]) == 0, 223);
    int held[14][2];
    for (unsigned i = 0; i < 14; ++i) REQUIRE(pipe(held[i]) == 0, 224);
    errno = 0;
    REQUIRE(pipe(fd) == -1 && errno == EMFILE, 225);
    errno = 0;
    REQUIRE(syscall(SYS_pipe2, (void *)-1, 0) == -1 && errno == EMFILE, 241);
    child = fork();
    REQUIRE(child >= 0, 242);
    if (!child) {
        for (unsigned i = 0; i < 14; ++i) {
            if (i != 1 && close(held[i][0])) _exit(243);
            if (i != 0 && close(held[i][1])) _exit(243);
        }
        int extra[2][2];
        if (pipe(extra[0]) || pipe(extra[1])) _exit(244);
        if (write(held[0][1], "g", 1) != 1 || read(held[1][0], &byte, 1) != 1 || byte != 'a') _exit(245);
        _exit(53); // Teardown releases the two globally retained pipes.
    }
    REQUIRE(read(held[0][0], &byte, 1) == 1 && byte == 'g', 246);
    errno = 0;
    REQUIRE(syscall(SYS_pipe2, fd, 0) == -1 && errno == ENFILE, 247);
    errno = 0;
    REQUIRE(syscall(SYS_pipe2, (void *)-1, 0) == -1 && errno == ENFILE, 248);
    REQUIRE(write(held[1][1], "a", 1) == 1 && waitpid(child, &status, 0) == child &&
            WIFEXITED(status) && WEXITSTATUS(status) == 53, 249);
    errno = 0;
    REQUIRE(syscall(SYS_pipe2, (void *)-1, 0) == -1 && errno == EMFILE, 250);
    for (unsigned i = 0; i < 14; ++i) REQUIRE(close(held[i][0]) == 0 && close(held[i][1]) == 0, 226);
    REQUIRE(pipe(fd) == 0 && fd[0] == 3 && fd[1] == 4 && close(fd[0]) == 0 && close(fd[1]) == 0, 227);
    static const char marker[] = "OK_MUSL_PIPES pipe=pass pipe2=pass io=pass nonblock=pass eof=pass dup=pass fork=pass exec=pass rollback=pass pressure=pass epipe=errno-only\n";
    REQUIRE(write(1, marker, sizeof marker - 1) == sizeof marker - 1, 228);
    return 0;
}

#include <limits.h>
static int files_probe_main(int argc, char **argv, char **envp)
{
    int result=pipes_probe_main(argc,argv,envp);
    if(result || argc!=1) return result;
    int fd=openat(AT_FDCWD,"/home/musl-seek",O_CREAT|O_TRUNC|O_RDWR,0600);
    REQUIRE(fd>=0 && write(fd,"abcdef",6)==6,300);
    int copy=dup(fd);REQUIRE(copy>=0,301);
    REQUIRE(lseek(fd,0,SEEK_CUR)==6 && lseek(copy,2,SEEK_SET)==2,302);
    char byte=0;REQUIRE(read(fd,&byte,1)==1 && byte=='c',303);
    REQUIRE(lseek(copy,-2,SEEK_CUR)==1 && read(fd,&byte,1)==1 && byte=='b',304);
    REQUIRE(lseek(fd,-1,SEEK_END)==5 && read(copy,&byte,1)==1 && byte=='f',305);
    REQUIRE(lseek(fd,32,SEEK_SET)==32 && read(copy,&byte,1)==0,306);
    errno=0;REQUIRE(lseek(fd,-33,SEEK_CUR)==-1 && errno==EINVAL && lseek(copy,0,SEEK_CUR)==32,307);
    errno=0;REQUIRE(lseek(-1,0,99)==-1 && errno==EBADF,308);
    errno=0;REQUIRE(lseek(fd,0,99)==-1 && errno==EINVAL,309);
    errno=0;REQUIRE(lseek(1,0,99)==-1 && errno==EINVAL,310);
    errno=0;REQUIRE(lseek(1,0,SEEK_SET)==-1 && errno==ESPIPE,311);
    errno=0;REQUIRE(lseek(0,0,SEEK_CUR)==-1 && errno==ESPIPE,312);
    errno=0;REQUIRE(lseek(fd,0,SEEK_DATA)==-1 && errno==EINVAL,313);
    errno=0;REQUIRE(lseek(fd,0,SEEK_HOLE)==-1 && errno==EINVAL,314);
    REQUIRE(lseek(fd,0,SEEK_SET)==0,315);
#ifdef SYS__llseek
    unsigned char result_bytes[10];memset(result_bytes,0x55,sizeof result_bytes);
    /* Unaligned result pointers are valid: the kernel must use checked copy. */
    REQUIRE(syscall(SYS__llseek,fd,0,0x12345678u,result_bytes+1,SEEK_SET)==0,316);
    off_t got=0;memcpy(&got,result_bytes+1,8);
    REQUIRE(got==0x12345678 && result_bytes[0]==0x55 && result_bytes[9]==0x55,317);
    errno=0;
    REQUIRE(syscall(SYS__llseek,fd,0,3,(void *)-1,SEEK_SET)==-1 && errno==EFAULT,318);
    REQUIRE(lseek(copy,0,SEEK_CUR)==3,319);
    errno=0;
    REQUIRE(syscall(SYS__llseek,-1,0,3,(void *)-1,99)==-1 && errno==EBADF,320);
    errno=0;
    REQUIRE(syscall(SYS__llseek,fd,0,3,(void *)-1,99)==-1 && errno==EINVAL,321);
    errno=0;
    REQUIRE(syscall(SYS__llseek,1,0,3,(void *)-1,SEEK_SET)==-1 && errno==ESPIPE,322);
    char *edge=mmap(0,8192,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    REQUIRE(edge!=MAP_FAILED && mprotect(edge+4096,4096,PROT_NONE)==0,323);
    errno=0;
    REQUIRE(syscall(SYS__llseek,fd,0,4,edge+4092,SEEK_SET)==-1 && errno==EFAULT,324);
    REQUIRE(lseek(copy,0,SEEK_CUR)==4 && munmap(edge,8192)==0,325);
#endif
#ifdef SYS_lseek
    REQUIRE(syscall(SYS_lseek,fd,2L,SEEK_SET)==2,326);
#if __SIZEOF_LONG__ == 4
    errno=0;
    REQUIRE(syscall(SYS_lseek,fd,0x80000000UL,SEEK_SET)==-1 && errno==EINVAL,327);
#else
    REQUIRE(syscall(SYS_lseek,(1UL<<32)|(unsigned)fd,3L,(1UL<<32)|SEEK_SET)==3,327);
#endif
#endif
#if __SIZEOF_LONG__ == 4
    REQUIRE(lseek(fd,INT32_MAX,SEEK_SET)==INT32_MAX,328);
    errno=0;REQUIRE(lseek(fd,1,SEEK_CUR)==-1 && errno==EOVERFLOW,329);
    REQUIRE(lseek(copy,0,SEEK_CUR)==INT32_MAX,330);
    errno=0;REQUIRE(lseek(fd,(off_t)INT32_MAX+1,SEEK_SET)==-1 && errno==EOVERFLOW,331);
    errno=0;REQUIRE(lseek(fd,((off_t)1<<32)+2,SEEK_SET)==-1 && errno==EOVERFLOW,332);
    REQUIRE(lseek(copy,0,SEEK_CUR)==INT32_MAX,333);
#else
    REQUIRE(lseek(fd,((off_t)1<<32)+2,SEEK_SET)==((off_t)1<<32)+2,328);
    REQUIRE(lseek(fd,INT64_MAX,SEEK_SET)==INT64_MAX,329);
    errno=0;REQUIRE(lseek(fd,1,SEEK_CUR)==-1 && errno==EOVERFLOW,330);
    REQUIRE(lseek(copy,0,SEEK_CUR)==INT64_MAX,331);
#endif
    REQUIRE(lseek(fd,0,SEEK_SET)==0,334);
    pid_t child=fork();REQUIRE(child>=0,335);
    if(!child) _exit(lseek(copy,4,SEEK_SET)==4?0:1);
    int status=-1;
    REQUIRE(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0,336);
    REQUIRE(lseek(fd,0,SEEK_CUR)==4 && read(fd,&byte,1)==1 && byte=='e',337);
    REQUIRE(lseek(copy,0,SEEK_END)==6 && write(fd,"!",1)==1 && fsync(fd)==0,338);
    REQUIRE(close(copy)==0 && close(fd)==0,339);
    static const char marker[]="OK_MUSL_SEEK seek=pass shared=pass errors=pass bounded=pass\n";
    REQUIRE(write(1,marker,sizeof marker-1)==sizeof marker-1,340);
    return 0;
}

#if defined(SYS_clock_nanosleep)
#define RAW_CLOCK_SLEEP SYS_clock_nanosleep
#elif defined(SYS_clock_nanosleep_time32)
#define RAW_CLOCK_SLEEP SYS_clock_nanosleep_time32
#else
#define RAW_CLOCK_SLEEP SYS_clock_nanosleep_time64
#endif
#if defined(SYS_clock_getres)
#define RAW_CLOCK_RES SYS_clock_getres
#elif defined(SYS_clock_getres_time32)
#define RAW_CLOCK_RES SYS_clock_getres_time32
#else
#define RAW_CLOCK_RES SYS_clock_getres_time64
#endif
#if !defined(SYS_nanosleep) && defined(SYS_nanosleep_time32)
#define SYS_nanosleep SYS_nanosleep_time32
#endif
int sleep_probe_main(int argc, char **argv, char **envp)
{
    int result=files_probe_main(argc,argv,envp);
    if(result || argc!=1)return result;
    struct timespec resolution, before, after, request={0,20000000}, remainder={123,456};
    REQUIRE(clock_getres(CLOCK_MONOTONIC,&resolution)==0 && resolution.tv_sec==0 &&
            resolution.tv_nsec>0 && resolution.tv_nsec<1000000000,400);
    REQUIRE(clock_gettime(CLOCK_MONOTONIC,&before)==0 && nanosleep(&request,&remainder)==0 &&
            clock_gettime(CLOCK_MONOTONIC,&after)==0,401);
    long long elapsed=(after.tv_sec-before.tv_sec)*1000000000LL+after.tv_nsec-before.tv_nsec;
    REQUIRE(elapsed>=20000000 && remainder.tv_sec==123 && remainder.tv_nsec==456,402);
    request=after;request.tv_nsec+=20000000;
    if(request.tv_nsec>=1000000000){++request.tv_sec;request.tv_nsec-=1000000000;}
    errno=47;
    REQUIRE(clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&request,(void *)-1)==0 && errno==47,403);
    REQUIRE(clock_gettime(CLOCK_MONOTONIC,&after)==0 && (after.tv_sec>request.tv_sec ||
            (after.tv_sec==request.tv_sec && after.tv_nsec>=request.tv_nsec)),404);
    request=(struct timespec){0,0};
    REQUIRE(clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&request,(void *)-1)==0,405);
    request=(struct timespec){0,1000000};
    REQUIRE(clock_nanosleep(CLOCK_REALTIME,0,&request,&remainder)==0 &&
            remainder.tv_sec==123 && remainder.tv_nsec==456,406);
    request=(struct timespec){-1,0};
    errno=0;REQUIRE(nanosleep(&request,0)==-1 && errno==EINVAL,407);
    request=(struct timespec){0,1000000000};errno=49;
    REQUIRE(clock_nanosleep(CLOCK_MONOTONIC,0,&request,0)==EINVAL && errno==49,408);
    request=(struct timespec){0,0};
    REQUIRE(clock_nanosleep(CLOCK_REALTIME,TIMER_ABSTIME,&request,0)==EINVAL,409);
    REQUIRE(clock_nanosleep(99,0,&request,0)==EINVAL,410);
#ifdef SYS_nanosleep
    long legacy[2]={0,0};
    REQUIRE(syscall(SYS_nanosleep,legacy,(void *)-1)==0,411);
    errno=0;REQUIRE(syscall(SYS_nanosleep,(void *)-1,0)==-1 && errno==EFAULT,412);
#endif
    long raw_request[2]={0,0};
#if __SIZEOF_LONG__ == 4
    /* musl's RV32 aliases are time64; other 32-bit clock syscalls are legacy. */
#ifdef SYS_clock_nanosleep_time64
    if(RAW_CLOCK_SLEEP==SYS_clock_nanosleep_time64) {
        long long wide[2]={0,0};
        REQUIRE(syscall(RAW_CLOCK_SLEEP,1,2,wide,(void *)-1)==0,413);
    } else
#endif
#endif
    REQUIRE(syscall(RAW_CLOCK_SLEEP,1,2,raw_request,(void *)-1)==0,414);
#ifdef SYS_clock_nanosleep_time64
    unsigned long long wide[2]={0,0x1234567800000000ULL};
    REQUIRE(syscall(SYS_clock_nanosleep_time64,1,0,wide,(void *)-1)==0,415);
    wide[0]=~0ULL;wide[1]=0;
    errno=0;REQUIRE(syscall(SYS_clock_nanosleep_time64,1,0,wide,0)==-1 && errno==EINVAL,416);
#endif
    errno=0;REQUIRE(syscall(RAW_CLOCK_SLEEP,99,0,(void *)-1,0)==-1 && errno==EINVAL,417);
    errno=0;REQUIRE(syscall(RAW_CLOCK_SLEEP,1,0,(void *)-1,0)==-1 && errno==EFAULT,418);
    REQUIRE(syscall(RAW_CLOCK_RES,1,0)==0,419);
    errno=0;REQUIRE(syscall(RAW_CLOCK_RES,99,0)==-1 && errno==EINVAL,420);
#if __SIZEOF_LONG__ == 8
    REQUIRE(syscall(RAW_CLOCK_RES,(1UL<<32)|1,0)==0,421);
    REQUIRE(syscall(RAW_CLOCK_SLEEP,(1UL<<32)|1,(1UL<<32)|1,raw_request,0)==0,422);
#endif
    char *edge=mmap(0,8192,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    REQUIRE(edge!=MAP_FAILED && mprotect(edge+4096,4096,PROT_NONE)==0,423);
    memset(edge+4092,0,4);errno=0;
    REQUIRE(syscall(RAW_CLOCK_SLEEP,1,0,edge+4092,0)==-1 && errno==EFAULT,424);
    errno=0;REQUIRE(syscall(RAW_CLOCK_RES,1,edge+4092)==-1 && errno==EFAULT,425);
    REQUIRE(munmap(edge,8192)==0,426);
    int p[2];REQUIRE(pipe2(p,O_NONBLOCK)==0,427);
    pid_t child=fork();REQUIRE(child>=0,428);
    if(!child) {
        struct timespec pause={0,10000000};
        _exit(nanosleep(&pause,0)==0 && write(p[1],"x",1)==1?0:1);
    }
    request=(struct timespec){0,80000000};
    REQUIRE(nanosleep(&request,&remainder)==0,429);
    char byte=0;REQUIRE(read(p[0],&byte,1)==1 && byte=='x',430);
    int status=-1;REQUIRE(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0,431);
    REQUIRE(close(p[0])==0 && close(p[1])==0 && remainder.tv_sec==123 && remainder.tv_nsec==456,432);
    static const char marker[]="OK_MUSL_SLEEP relative=pass absolute=pass resolution=pass time64=pass errors=pass peer=pass\n";
    REQUIRE(write(1,marker,sizeof marker-1)==sizeof marker-1,433);
    return 0;
}

#include <poll.h>
#include <signal.h>

#if defined(SYS_ppoll)
#define RAW_PPOLL SYS_ppoll
#else
#define RAW_PPOLL SYS_ppoll_time64
#endif

static int raw_poll_checks(long number, int wide)
{
    long legacy[2]={0,0};long long wide_time[2]={0,0};
    void *time=wide?(void *)wide_time:(void *)legacy;
    struct pollfd entry={999,0,123};
    REQUIRE(syscall(number,&entry,1,time,0,0)==1 && entry.revents==POLLNVAL,500);
    if(wide){wide_time[0]=-1;wide_time[1]=0;}else{legacy[0]=-1;legacy[1]=0;}
    errno=0;REQUIRE(syscall(number,0,33,time,0,0)==-1 && errno==EINVAL,501);
    errno=0;REQUIRE(syscall(number,0,33,(void *)-1,(void *)-1,0)==-1 && errno==EFAULT,502);
    errno=0;REQUIRE(syscall(number,0,33,0,(void *)-1,1)==-1 && errno==EINVAL,503);
#if defined(__mips__)
    const long mask_size=16;
#else
    const long mask_size=8;
#endif
    errno=0;REQUIRE(syscall(number,0,33,0,(void *)-1,mask_size)==-1 && errno==EFAULT,504);
    unsigned char mask[16]={0};errno=0;
    REQUIRE(syscall(number,0,33,0,mask,mask_size)==-1 && errno==ENOSYS,505);
    if(wide){wide_time[0]=0;wide_time[1]=0;}else{legacy[0]=0;legacy[1]=0;}
    REQUIRE(syscall(number,0,0,time,0,123)==0,506);
    if(wide){wide_time[0]=1;wide_time[1]=0;}else{legacy[0]=1;legacy[1]=0;}
    entry.revents=123;REQUIRE(syscall(number,&entry,1,time,0,0)==1 && entry.revents==POLLNVAL,507);
    long long seconds=wide?wide_time[0]:legacy[0], nanos=wide?wide_time[1]:legacy[1];
    REQUIRE(seconds>=0 && seconds<=1 && nanos>=0 && nanos<1000000000 && (!seconds || !nanos),508);
    char *page=mmap(0,8192,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    REQUIRE(page!=MAP_FAILED,509);
    if(wide){wide_time[0]=1;wide_time[1]=0;memcpy(page,wide_time,sizeof wide_time);}
    else{legacy[0]=1;legacy[1]=0;memcpy(page,legacy,sizeof legacy);}
    REQUIRE(mprotect(page,4096,PROT_READ)==0,510);
    REQUIRE(syscall(number,&entry,1,page,0,0)==1,511); // Timeout copyout failure is ignored.
    REQUIRE(memcmp(page,time,wide?sizeof wide_time:sizeof legacy)==0,512);
    struct pollfd *readonly=(void *)(page+4096);*readonly=entry;
    REQUIRE(mprotect(page+4096,4096,PROT_READ)==0,513);
    errno=0;REQUIRE(syscall(number,readonly,1,time,0,0)==-1 && errno==EFAULT,514);
    REQUIRE(mprotect(page+4096,4096,PROT_NONE)==0,515);
    errno=0;REQUIRE(syscall(number,page+4092,1,time,0,0)==-1 && errno==EFAULT,516);
    REQUIRE(munmap(page,8192)==0,517);
#if __SIZEOF_LONG__ == 8
    if(wide){wide_time[0]=0;wide_time[1]=0;}
    REQUIRE(syscall(number,&entry,(1UL<<32)|1,time,0,0)==1,518);
#endif
    return 0;
}

int poll_probe_main(int argc,char **argv,char **envp)
{
    int result=sleep_probe_main(argc,argv,envp);
    if(result || argc!=1)return result;
    struct pollfd entries[3]={{-1,(short)~0U,77},{999,0,88},{1,POLLOUT|POLLWRNORM,99}};
    REQUIRE(poll(entries,3,0)==2 && entries[0].revents==0 && entries[1].revents==POLLNVAL &&
            entries[2].revents==(POLLOUT|POLLWRNORM),520);
    struct timespec before,after,timeout={0,20000000};
    REQUIRE(clock_gettime(CLOCK_MONOTONIC,&before)==0 && poll(0,0,20)==0 && clock_gettime(CLOCK_MONOTONIC,&after)==0,521);
    long long elapsed=(after.tv_sec-before.tv_sec)*1000000000LL+after.tv_nsec-before.tv_nsec;
    REQUIRE(elapsed>=20000000,522);
    REQUIRE(clock_gettime(CLOCK_MONOTONIC,&before)==0 && ppoll(0,0,&timeout,0)==0 && clock_gettime(CLOCK_MONOTONIC,&after)==0,523);
    elapsed=(after.tv_sec-before.tv_sec)*1000000000LL+after.tv_nsec-before.tv_nsec;
    REQUIRE(elapsed>=20000000 && timeout.tv_sec==0 && timeout.tv_nsec==20000000,524);
    sigset_t mask={0};timeout=(struct timespec){0,0};errno=0;
    REQUIRE(ppoll(0,0,&timeout,&mask)==-1 && errno==ENOSYS,525);
    result=raw_poll_checks(RAW_PPOLL,sizeof(long)==8
#ifdef SYS_ppoll_time64
            || RAW_PPOLL==SYS_ppoll_time64
#endif
    );if(result)return result;
#ifdef SYS_ppoll_time64
    result=raw_poll_checks(SYS_ppoll_time64,1);if(result)return result;
#if __SIZEOF_LONG__ == 4
    unsigned long long padded[2]={0,0x1234567800000000ULL};
    REQUIRE(syscall(SYS_ppoll_time64,0,0,padded,0,0)==0,526);
#endif
#endif
    int p[2],gate[2];REQUIRE(pipe(p)==0 && pipe(gate)==0,527);
    pid_t child=fork();REQUIRE(child>=0,528);
    if(!child) {
        close(p[0]);close(gate[1]);char go=0;struct timespec delay={0,20000000};
        int good=read(gate[0],&go,1)==1 && go=='g' && nanosleep(&delay,0)==0 && write(p[1],"P",1)==1;
        close(p[1]);close(gate[0]);_exit(good?0:1);
    }
    REQUIRE(close(p[1])==0 && close(gate[0])==0,529);
    entries[0]=(struct pollfd){p[0],POLLIN|POLLRDNORM,99};entries[1]=(struct pollfd){p[0],POLLRDNORM,99};
    REQUIRE(poll(entries,2,0)==0 && entries[0].revents==0 && entries[1].revents==0,530);
    REQUIRE(clock_gettime(CLOCK_MONOTONIC,&before)==0 && write(gate[1],"g",1)==1 && poll(entries,2,2000)==2 &&
            clock_gettime(CLOCK_MONOTONIC,&after)==0,531);
    elapsed=(after.tv_sec-before.tv_sec)*1000000000LL+after.tv_nsec-before.tv_nsec;
    REQUIRE(elapsed>=20000000 && (entries[0].revents&(POLLIN|POLLRDNORM))==(POLLIN|POLLRDNORM) &&
            (entries[1].revents&POLLRDNORM)==POLLRDNORM,532);
    char byte=0;REQUIRE(read(p[0],&byte,1)==1 && byte=='P',533);
    int status=-1;REQUIRE(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0,534);
    timeout=(struct timespec){0,0};REQUIRE(ppoll(entries,2,&timeout,0)==2 && entries[0].revents==POLLHUP && entries[1].revents==POLLHUP,535);
    REQUIRE(close(p[0])==0 && close(gate[1])==0,536);
    REQUIRE(pipe(p)==0 && close(p[0])==0,537);
    entries[0]=(struct pollfd){p[1],POLLOUT|POLLWRNORM,99};
    REQUIRE(poll(entries,1,0)==1 && entries[0].revents==(POLLERR|POLLOUT|POLLWRNORM) && close(p[1])==0,538);
    int fd=openat(AT_FDCWD,"/home/musl-seek",O_RDONLY);REQUIRE(fd>=0,539);
    entries[0]=(struct pollfd){fd,POLLIN|POLLRDNORM|POLLOUT|POLLWRNORM,99};
    REQUIRE(poll(entries,1,0)==1 && entries[0].revents==entries[0].events && close(fd)==0,540);
    static const char marker[]="OK_MUSL_POLL poll=pass ppoll=pass layouts=pass timeout=pass wake=pass eof=pass errors=pass mask=unsupported\n";
    REQUIRE(write(1,marker,sizeof marker-1)==sizeof marker-1,541);
    return 0;
}

#include <stdint.h>

int open_probe_main(int argc,char **argv,char **envp)
{
    int result=poll_probe_main(argc,argv,envp);
    if(result || argc!=1)return result;
    int cwd=open(".",O_RDONLY|O_DIRECTORY|O_CLOEXEC);
    REQUIRE(cwd>=0 && (fcntl(cwd,F_GETFD)&FD_CLOEXEC),560);
    REQUIRE(chdir("/home")==0,561);
    int fd=open("musl-open",O_CREAT|O_TRUNC|O_RDWR|O_CLOEXEC,0600);
    REQUIRE(fd>=0 && (fcntl(fd,F_GETFD)&FD_CLOEXEC),562);
    REQUIRE(write(fd,"longer-content",14)==14 && close(fd)==0,563);
#ifdef SYS_creat
    fd=(int)syscall(SYS_creat,"musl-open",(0x1234UL<<16)|0600UL);
    REQUIRE(fd>=0 && (fcntl(fd,F_GETFL)&O_ACCMODE)==O_WRONLY && !(fcntl(fd,F_GETFD)&FD_CLOEXEC),564);
    REQUIRE(write(fd,"raw",3)==3 && close(fd)==0,565);
#endif
    fd=creat("musl-open",0600);
    REQUIRE(fd>=0 && (fcntl(fd,F_GETFL)&O_ACCMODE)==O_WRONLY && !(fcntl(fd,F_GETFD)&FD_CLOEXEC),566);
    REQUIRE(write(fd,"created",7)==7 && close(fd)==0,567);
    fd=open("musl-open",O_RDWR|O_APPEND|O_NONBLOCK);
    REQUIRE(fd>=0 && (fcntl(fd,F_GETFL)&(O_APPEND|O_NONBLOCK))==(O_APPEND|O_NONBLOCK),568);
    char bytes[16]={0};REQUIRE(read(fd,bytes,1)==1 && bytes[0]=='c' && write(fd,"!",1)==1 && close(fd)==0,569);
#ifdef SYS_open
    unsigned long flags=O_RDONLY;
#if __SIZEOF_LONG__ == 8
    flags|=1UL<<40;
#endif
    fd=(int)syscall(SYS_open,"musl-open",flags,~0UL);
    REQUIRE(fd>=0 && read(fd,bytes,sizeof bytes)==8 && !memcmp(bytes,"created!",8) && close(fd)==0,570);
    errno=0;REQUIRE(syscall(SYS_open,(void *)(uintptr_t)-1,O_WRONLY|O_TRUNC,0600)==-1 && errno==EFAULT,571);
#endif
#ifdef SYS_creat
    errno=0;REQUIRE(syscall(SYS_creat,(void *)(uintptr_t)-1,0600)==-1 && errno==EFAULT,572);
#endif
    errno=0;REQUIRE(open("musl-open",O_CREAT|O_EXCL|O_WRONLY,0600)==-1 && errno==EEXIST,573);
    int opened[64];unsigned count=0;
    for(;count<64;++count) {opened[count]=open("musl-open",O_RDONLY);if(opened[count]<0)break;}
    REQUIRE(count>0 && count<64 && errno==EMFILE,574);
    errno=0;REQUIRE(creat("musl-open",0600)==-1 && errno==EMFILE,575);
    errno=0;REQUIRE(open("musl-open",O_TRUNC|O_WRONLY)==-1 && errno==EMFILE,576);
    errno=0;REQUIRE(creat("musl-open-absent",0600)==-1 && errno==EMFILE,577);
    for(unsigned i=0;i<count;++i)REQUIRE(close(opened[i])==0,578);
    errno=0;REQUIRE(open("musl-open-absent",O_RDONLY)==-1 && errno==ENOENT,579);
    fd=open("musl-open",O_RDONLY);memset(bytes,0,sizeof bytes);
    REQUIRE(fd>=0 && read(fd,bytes,sizeof bytes)==8 && !memcmp(bytes,"created!",8) && fsync(fd)==0 && close(fd)==0,580);
    REQUIRE(fchdir(cwd)==0 && close(cwd)==0,581);
    static const char marker[]="OK_MUSL_OPEN open=pass creat=pass flags=pass cwd=pass copies=pass pressure=pass legacy=where-present\n";
    REQUIRE(write(1,marker,sizeof marker-1)==sizeof marker-1,582);
    return 0;
}

int positional_probe_main(int argc,char **argv,char **envp)
{
    int result=open_probe_main(argc,argv,envp);
    if(result || argc!=1)return result;
    int fd=open("/home/musl-positional",O_CREAT|O_TRUNC|O_RDWR,0600);
    REQUIRE(fd>=0 && write(fd,"abcdef",6)==6 && lseek(fd,2,SEEK_SET)==2,590);
    int copy=dup(fd);REQUIRE(copy>=0,591);
    char bytes[16]={0};
    REQUIRE(pread(fd,bytes,3,1)==3 && !memcmp(bytes,"bcd",3) && lseek(copy,0,SEEK_CUR)==2,592);
    REQUIRE(pread(fd,bytes,8,4)==2 && !memcmp(bytes,"ef",2) && pread(fd,bytes,1,8)==0,593);
    REQUIRE(pwrite(fd,"XY",2,1)==2 && lseek(copy,0,SEEK_CUR)==2,594);
    REQUIRE(pread(fd,0,0,0x7fffffffLL)==0 && pwrite(fd,0,0,0x7fffffffLL)==0,595);
    errno=0;REQUIRE(pread(-1,bytes,1,-1)==-1 && errno==EINVAL,596);
    errno=0;REQUIRE(pwrite(-1,bytes,1,-1)==-1 && errno==EINVAL,597);
    errno=0;REQUIRE(pread(-1,bytes,1,0)==-1 && errno==EBADF,598);
    errno=0;REQUIRE(pwrite(-1,bytes,1,0)==-1 && errno==EBADF,599);
#if __SIZEOF_LONG__ == 4
    errno=0;REQUIRE(pread(fd,bytes,0,0x100000001LL)==-1 && errno==EOVERFLOW,600);
    errno=0;REQUIRE(pwrite(fd,bytes,0,0x100000001LL)==-1 && errno==EOVERFLOW,601);
#endif
    errno=0;REQUIRE(pread(fd,bytes,1,(-0x7fffffffffffffffLL-1))==-1 && errno==EINVAL,602);
    errno=0;REQUIRE(pwrite(fd,bytes,1,0x7fffffffffffffffLL)==-1 && errno==EOVERFLOW,603);
    int p[2];REQUIRE(pipe(p)==0,604);
    for(unsigned i=0;i<2;++i) {
        errno=0;REQUIRE(pread(p[i],0,1,0)==-1 && errno==ESPIPE,605);
        errno=0;REQUIRE(pwrite(p[i],0,1,0)==-1 && errno==ESPIPE,606);
        REQUIRE(close(p[i])==0,607);
    }
    int directory=open("/home",O_RDONLY|O_DIRECTORY);REQUIRE(directory>=0,608);
    errno=0;REQUIRE(pread(directory,bytes,1,0)==-1 && errno==EISDIR && close(directory)==0,609);
    char *edge=mmap(0,8192,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    REQUIRE(edge!=MAP_FAILED && mprotect(edge+4096,4096,PROT_NONE)==0,610);
    edge[4095]='Q';errno=0;REQUIRE(pread(fd,edge+4095,2,0)==-1 && errno==EFAULT,611);
    errno=0;REQUIRE(pwrite(fd,edge+4095,2,0)==-1 && errno==EFAULT,612);
    REQUIRE(lseek(copy,0,SEEK_CUR)==2 && munmap(edge,8192)==0,613);
    REQUIRE(fcntl(fd,F_SETFL,O_APPEND)==0 && pwrite(fd,"!",1,0)==1 && lseek(copy,0,SEEK_CUR)==2,614);
    REQUIRE(pread(fd,bytes,sizeof bytes,0)==7 && !memcmp(bytes,"aXYdef!",7),615);
    REQUIRE(fcntl(copy,F_SETFL,0)==0,616);
    pid_t child=fork();REQUIRE(child>=0,617);
    if(!child) _exit(pwrite(copy,"Z",1,3)==1 && lseek(fd,0,SEEK_CUR)==2 ? 0:1);
    int status=-1;REQUIRE(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0,618);
    REQUIRE(lseek(copy,0,SEEK_CUR)==2 && pread(copy,bytes,sizeof bytes,0)==7 && !memcmp(bytes,"aXYZef!",7),619);
    REQUIRE(fsync(fd)==0 && close(fd)==0 && close(copy)==0,620);
    static const char marker[]="OK_MUSL_POSITIONAL pread=pass pwrite=pass offsets=pass shared=pass append=linux copies=pass bounded=pass\n";
    REQUIRE(write(1,marker,sizeof marker-1)==sizeof marker-1,621);
    return 0;
}

#include <sys/select.h>

#if defined(__riscv) && __riscv_xlen == 32
#define RAW_PSELECT SYS_pselect6_time64
#else
#define RAW_PSELECT SYS_pselect6
#endif

static int raw_pselect_checks(long number,int wide,int fd)
{
    long legacy[2]={0,0};long long wide_time[2]={0,0};
    void *time=wide?(void *)wide_time:(void *)legacy;
    unsigned long bit=1UL<<fd,r=bit,w=bit,e=bit;
    REQUIRE(syscall(number,fd+1,&r,&w,&e,time,0)==2 && r==bit && w==bit && e==0,710);
    unsigned long pack[2]={0,~0UL};
    REQUIRE(syscall(number,0,(void *)-1,(void *)-1,(void *)-1,time,pack)==0,711);
    errno=0;REQUIRE(syscall(number,-1,0,0,0,(void *)-1,(void *)-1)==-1 && errno==EFAULT,712);
    if(wide)wide_time[0]=-1;else legacy[0]=-1;
    errno=0;REQUIRE(syscall(number,-1,(void *)-1,0,0,time,0)==-1 && errno==EINVAL,713);
    if(wide)wide_time[0]=0;else legacy[0]=0;
    r=1UL<<30;w=bit;errno=0;REQUIRE(syscall(number,31,&r,&w,0,time,0)==-1 && errno==EBADF,714);
    unsigned char mask[16]={0};pack[0]=(unsigned long)mask;pack[1]=1;
    errno=0;REQUIRE(syscall(number,0,0,0,0,time,pack)==-1 && errno==EINVAL,715);
#if defined(__mips__)
    pack[1]=16;
#else
    pack[1]=8;
#endif
    pack[0]=(unsigned long)-1;errno=0;REQUIRE(syscall(number,0,0,0,0,time,pack)==-1 && errno==EFAULT,716);
    pack[0]=(unsigned long)mask;errno=0;REQUIRE(syscall(number,0,0,0,0,time,pack)==-1 && errno==ENOSYS,717);
    r=w=e=bit;REQUIRE(syscall(number,fd+1,&r,&r,&r,time,0)==2 && r==0,718);
    char *page=mmap(0,8192,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);REQUIRE(page!=MAP_FAILED,719);
    if(wide){wide_time[0]=1;wide_time[1]=0;memcpy(page,time,sizeof wide_time);}
    else{legacy[0]=1;legacy[1]=0;memcpy(page,time,sizeof legacy);}
    REQUIRE(mprotect(page,4096,PROT_READ)==0,720);
    w=bit;REQUIRE(syscall(number,fd+1,0,&w,0,page,0)==1 && memcmp(page,time,wide?sizeof wide_time:sizeof legacy)==0,721);
    unsigned long *readonly=(void *)(page+4096);*readonly=bit;REQUIRE(mprotect(page+4096,4096,PROT_READ)==0,722);
    errno=0;REQUIRE(syscall(number,fd+1,0,readonly,0,time,0)==-1 && errno==EFAULT,723);
    REQUIRE(mprotect(page+4096,4096,PROT_NONE)==0,724);
    errno=0;REQUIRE(syscall(number,1,page+4096-sizeof(long)/2,0,0,time,0)==-1 && errno==EFAULT,725);
    REQUIRE(munmap(page,8192)==0,726);
#if __SIZEOF_LONG__ == 8
    wide_time[0]=wide_time[1]=0;w=bit;REQUIRE(syscall(number,(1UL<<32)|(fd+1),0,&w,0,time,0)==1,727);
#endif
    return 0;
}

static long raw_select_call(long number,int old,long n,void *r,void *w,void *e,void *time)
{
    unsigned long record[5]={(unsigned long)n,(unsigned long)r,(unsigned long)w,(unsigned long)e,(unsigned long)time};
    return old?syscall(number,record):syscall(number,n,r,w,e,time);
}
static int raw_select_checks(long number,int old,int fd)
{
    unsigned long bit=1UL<<fd,r=bit,w=bit,e=bit;long time[2]={0,0};
    REQUIRE(raw_select_call(number,old,fd+1,&r,&w,&e,time)==2 && r==bit && w==bit && e==0,730);
    time[0]=-1;time[1]=1000000;
    REQUIRE(raw_select_call(number,old,0,(void *)-1,0,0,time)==0 && time[0]==-1 && time[1]==1000000,731);
    time[0]=1;time[1]=-1000000;
    REQUIRE(raw_select_call(number,old,0,0,0,0,time)==0 && time[0]==1 && time[1]==-1000000,732);
    time[0]=1;time[1]=-1;errno=0;REQUIRE(raw_select_call(number,old,0,0,0,0,time)==-1 && errno==EINVAL,733);
    time[0]=-1;time[1]=2000000;w=bit;
    REQUIRE(raw_select_call(number,old,fd+1,0,&w,0,time)==1 && time[0]>=0 && time[0]<=1 && time[1]>=0 && time[1]<1000000,734);
    return 0;
}

int select_probe_main(int argc,char **argv,char **envp)
{
    int result=positional_probe_main(argc,argv,envp);if(result || argc!=1)return result;
    struct timeval timeout={0,0};fd_set r,w,e;FD_ZERO(&w);FD_SET(1,&w);
    // Select boundary follows positional support; the ABI13 control stops earlier at pread.
    REQUIRE(select(2,0,&w,0,&timeout)==1 && FD_ISSET(1,&w),700);
    int fd=open("/home/musl-open",O_RDONLY);REQUIRE(fd>=0,701);
    FD_ZERO(&r);FD_ZERO(&w);FD_ZERO(&e);FD_SET(fd,&r);FD_SET(fd,&w);FD_SET(fd,&e);
    REQUIRE(select(fd+1,&r,&w,&e,&timeout)==2 && FD_ISSET(fd,&r) && FD_ISSET(fd,&w) && !FD_ISSET(fd,&e),702);
    struct timespec precise={0,0};FD_SET(fd,&r);FD_SET(fd,&w);FD_SET(fd,&e);
    REQUIRE(pselect(fd+1,&r,&w,&e,&precise,0)==2 && !FD_ISSET(fd,&e),703);
    sigset_t mask={0};errno=0;REQUIRE(pselect(0,0,0,0,&precise,&mask)==-1 && errno==ENOSYS,704);
    result=raw_pselect_checks(RAW_PSELECT,sizeof(long)==8
#ifdef SYS_pselect6_time64
        || RAW_PSELECT==SYS_pselect6_time64
#endif
    ,fd);if(result)return result;
#ifdef SYS_pselect6_time64
    result=raw_pselect_checks(SYS_pselect6_time64,1,fd);if(result)return result;
#if __SIZEOF_LONG__ == 4
    unsigned long long padded[2]={0,0x1234567800000000ULL};
    REQUIRE(syscall(SYS_pselect6_time64,0,0,0,0,padded,0)==0,705);
#endif
#endif
#ifdef SYS__newselect
    result=raw_select_checks(SYS__newselect,0,fd);if(result)return result;
#elif defined(__x86_64__)
    result=raw_select_checks(SYS_select,0,fd);if(result)return result;
#endif
#if defined(__i386__) || defined(__powerpc__)
    result=raw_select_checks(82,1,fd);if(result)return result;
#endif
    REQUIRE(close(fd)==0,706);
    struct timespec before,after;timeout=(struct timeval){0,20000};
    REQUIRE(clock_gettime(CLOCK_MONOTONIC,&before)==0 && select(0,0,0,0,&timeout)==0 && clock_gettime(CLOCK_MONOTONIC,&after)==0,740);
    long long elapsed=(after.tv_sec-before.tv_sec)*1000000000LL+after.tv_nsec-before.tv_nsec;
    REQUIRE(elapsed>=20000000 && timeout.tv_sec==0 && timeout.tv_usec==20000,741);
    precise=(struct timespec){0,20000000};
    REQUIRE(clock_gettime(CLOCK_MONOTONIC,&before)==0 && pselect(0,0,0,0,&precise,0)==0 && clock_gettime(CLOCK_MONOTONIC,&after)==0,742);
    elapsed=(after.tv_sec-before.tv_sec)*1000000000LL+after.tv_nsec-before.tv_nsec;
    REQUIRE(elapsed>=20000000 && precise.tv_sec==0 && precise.tv_nsec==20000000,743);
    int p[2],gate[2];REQUIRE(pipe(p)==0 && pipe(gate)==0,744);pid_t child=fork();REQUIRE(child>=0,745);
    if(!child) {
        close(p[0]);close(gate[1]);char go=0;struct timespec delay={0,20000000};
        int good=read(gate[0],&go,1)==1 && go=='g' && nanosleep(&delay,0)==0 && write(p[1],"S",1)==1;
        close(p[1]);close(gate[0]);_exit(good?0:1);
    }
    REQUIRE(close(p[1])==0 && close(gate[0])==0,746);FD_ZERO(&r);FD_SET(p[0],&r);timeout=(struct timeval){0,0};
    REQUIRE(select(p[0]+1,&r,0,0,&timeout)==0 && !FD_ISSET(p[0],&r),747);FD_SET(p[0],&r);timeout=(struct timeval){2,0};
    REQUIRE(clock_gettime(CLOCK_MONOTONIC,&before)==0 && write(gate[1],"g",1)==1 && select(p[0]+1,&r,0,0,&timeout)==1 &&
            clock_gettime(CLOCK_MONOTONIC,&after)==0,748);
    elapsed=(after.tv_sec-before.tv_sec)*1000000000LL+after.tv_nsec-before.tv_nsec;
    REQUIRE(elapsed>=20000000 && FD_ISSET(p[0],&r) && timeout.tv_sec==2 && timeout.tv_usec==0,749);
    char byte=0;int status=-1;REQUIRE(read(p[0],&byte,1)==1 && byte=='S' && waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0,750);
    FD_ZERO(&e);FD_SET(p[0],&e);FD_SET(p[0],&r);precise=(struct timespec){0,0};
    REQUIRE(pselect(p[0]+1,&r,0,&e,&precise,0)==1 && FD_ISSET(p[0],&r) && !FD_ISSET(p[0],&e),751);
    FD_SET(p[0],&e);precise=(struct timespec){0,20000000};
    REQUIRE(pselect(p[0]+1,0,0,&e,&precise,0)==0 && !FD_ISSET(p[0],&e),752);
    REQUIRE(close(p[0])==0 && close(gate[1])==0 && pipe(p)==0 && close(p[0])==0,753);
    FD_ZERO(&w);FD_ZERO(&e);FD_SET(p[1],&w);FD_SET(p[1],&e);timeout=(struct timeval){0,0};
    REQUIRE(select(p[1]+1,0,&w,&e,&timeout)==1 && FD_ISSET(p[1],&w) && !FD_ISSET(p[1],&e) && close(p[1])==0,754);
    static const char marker[]="OK_MUSL_SELECT select=pass pselect=pass layouts=pass timeout=pass wake=pass sets=pass errors=pass mask=unsupported\n";
    REQUIRE(write(1,marker,sizeof marker-1)==sizeof marker-1,755);return 0;
}

#include <dirent.h>

static int directory_inode_receipt(unsigned long long inode)
{
    char line[128]="OK_MUSL_DIRECTORY_INODE name=musl-positional inode=";
    unsigned size=(unsigned)strlen(line),count=0;char digits[32];
    do { digits[count++]=(char)('0'+inode%10);inode/=10; } while(inode);
    while(count)line[size++]=digits[--count];
    line[size++]='\n';
    return write(1,line,size)==(ssize_t)size;
}

int directory_probe_main(int argc,char **argv,char **envp)
{
    int result=select_probe_main(argc,argv,envp);if(result || argc!=1)return result;
    DIR *directory=opendir("/home");REQUIRE(directory!=0,800);
    errno=0;struct dirent *entry=readdir(directory);
    // Exact ABI14 lacks getdents64 and stops at this first directory read.
    REQUIRE(entry!=0 && errno==0,801);
    REQUIRE(entry->d_ino && entry->d_reclen>=24 && entry->d_reclen%8==0,802);
    char first[256],second[256];strcpy(first,entry->d_name);
    long cookie=telldir(directory);REQUIRE(cookie>0,803);
    entry=readdir(directory);REQUIRE(entry!=0,804);strcpy(second,entry->d_name);
    seekdir(directory,cookie);entry=readdir(directory);REQUIRE(entry && strcmp(entry->d_name,second)==0,805);
    rewinddir(directory);entry=readdir(directory);REQUIRE(entry && strcmp(entry->d_name,first)==0,806);
    rewinddir(directory);unsigned dots=0,parents=0,files=0,positioned=0,count=0;unsigned long long inode=0;
    errno=0;
    while((entry=readdir(directory))) {
        REQUIRE(++count<=66 && entry->d_ino && entry->d_reclen>=24 && entry->d_reclen%8==0,807);
        if(!strcmp(entry->d_name,".")){REQUIRE(entry->d_type==DT_DIR,808);++dots;}
        if(!strcmp(entry->d_name,"..")){REQUIRE(entry->d_type==DT_DIR,809);++parents;}
        if(!strcmp(entry->d_name,"musl-file")){REQUIRE(entry->d_type==DT_REG,810);++files;}
        if(!strcmp(entry->d_name,"musl-positional")){REQUIRE(entry->d_type==DT_REG,811);++positioned;inode=entry->d_ino;}
    }
    REQUIRE(errno==0 && dots==1 && parents==1 && files==1 && positioned==1 && inode,812);
    REQUIRE(directory_inode_receipt(inode),813);
    REQUIRE(closedir(directory)==0,814);
    errno=0;REQUIRE(opendir("/home/musl-file")==0 && errno==ENOTDIR,815);
    int fd=open("/home",O_RDONLY|O_DIRECTORY),other;REQUIRE(fd>=0 && (other=dup(fd))>=0,816);
    unsigned char bytes[256];memset(bytes,0xa5,sizeof bytes);
    errno=0;REQUIRE(syscall(SYS_getdents64,-1,(void *)-1,0)==-1 && errno==EBADF,817);
    errno=0;REQUIRE(syscall(SYS_getdents64,fd,(void *)-1,23)==-1 && errno==EINVAL,818);
    errno=0;REQUIRE(syscall(SYS_getdents64,fd,(void *)-1,24)==-1 && errno==EFAULT,819);
    REQUIRE(lseek(fd,0,SEEK_CUR)==0,820);
    REQUIRE(syscall(SYS_getdents64,fd,bytes,24)==24 && !strcmp((char *)bytes+19,".") && bytes[24]==0xa5,821);
    REQUIRE(syscall(SYS_getdents64,other,bytes,24)==24 && !strcmp((char *)bytes+19,".."),822);
    errno=0;REQUIRE(lseek(fd,0,SEEK_END)==-1 && errno==EINVAL && lseek(other,0,SEEK_CUR)==2,837);
    REQUIRE(lseek(fd,0,SEEK_SET)==0,823);
    long page=sysconf(_SC_PAGESIZE);REQUIRE(page>0,824);
    unsigned char *mapping=mmap(0,(size_t)page*2,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    REQUIRE(mapping!=MAP_FAILED && mprotect(mapping+page,(size_t)page,PROT_NONE)==0,825);
    REQUIRE(syscall(SYS_getdents64,fd,mapping+page-32,4096)==24 && lseek(other,0,SEEK_CUR)==1,826);
    REQUIRE(munmap(mapping,(size_t)page*2)==0,827);
    REQUIRE(syscall(SYS_getdents64,fd,bytes,24)==24 && !strcmp((char *)bytes+19,".."),828);
    long n;unsigned rounds=0;
    do { n=syscall(SYS_getdents64,fd,bytes,sizeof bytes);REQUIRE(n>=0 && ++rounds<=66,829); } while(n);
    REQUIRE(syscall(SYS_getdents64,fd,(void *)-1,0)==0 && syscall(SYS_getdents64,fd,(void *)-1,~0U)==0,830);
    REQUIRE(lseek(fd,0,SEEK_SET)==0,831);
    pid_t child=fork();REQUIRE(child>=0,832);
    if(!child)_Exit(syscall(SYS_getdents64,other,bytes,24)==24?0:1);
    int status=0;REQUIRE(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0,833);
    REQUIRE(lseek(fd,0,SEEK_CUR)==1 && syscall(SYS_getdents64,fd,bytes,24)==24 && !strcmp((char *)bytes+19,".."),834);
    REQUIRE(close(fd)==0 && close(other)==0,835);
    static const char marker[]="OK_MUSL_DIRECTORY opendir=pass readdir=pass cookies=pass shared=pass inode=pass copies=pass bounded=pass\n";
    REQUIRE(write(1,marker,sizeof marker-1)==sizeof marker-1,836);
    return 0;
}

#include <sys/stat.h>

static int mask_file(const char *path, int exclusive, const char *content)
{
    int fd=open(path,O_CREAT|O_WRONLY|(exclusive ? O_EXCL : O_TRUNC),0666);
    if(fd<0)return -1;
    size_t size=strlen(content);
    int okay=write(fd,content,size)==(ssize_t)size && fsync(fd)==0;
    if(close(fd))okay=0;
    return okay ? 0 : -1;
}


#include <sys/time.h>
#include <stdint.h>
#if defined(SYS_clock_gettime64)
#define RAW_REALTIME_GET SYS_clock_gettime64
#elif defined(SYS_clock_gettime)
#define RAW_REALTIME_GET SYS_clock_gettime
#else
#define RAW_REALTIME_GET SYS_clock_gettime32
#endif
#if defined(SYS_clock_getres_time64)
#define RAW_REALTIME_RES SYS_clock_getres_time64
#elif defined(SYS_clock_getres)
#define RAW_REALTIME_RES SYS_clock_getres
#else
#define RAW_REALTIME_RES SYS_clock_getres_time32
#endif
#if defined(SYS_clock_gettime)
#define RAW_REALTIME_LEGACY SYS_clock_gettime
#elif defined(SYS_clock_gettime32)
#define RAW_REALTIME_LEGACY SYS_clock_gettime32
#endif

static void realtime_number(int64_t value)
{
    char digits[24];unsigned n=0;uint64_t number=(uint64_t)value;
    if(value<0){(void)write(1,"-",1);number=0-number;}
    do{digits[n++]=(char)('0'+number%10);number/=10;}while(number);
    for(unsigned i=0;i<n/2;++i){char c=digits[i];digits[i]=digits[n-i-1];digits[n-i-1]=c;}
    (void)write(1,digits,n);
}
static void realtime_text(const char *text){(void)write(1,text,strlen(text));}
static int realtime_check(const char *role)
{
    struct timespec wall={71,92},mono={0,0},res={71,92};
    /* Legacy-time32 musl uses a temporary record even when its caller passes
       NULL. Test the raw identity-only syscall separately from that wrapper. */
    REQUIRE(syscall(RAW_REALTIME_RES,CLOCK_REALTIME,0)==0 && clock_getres(CLOCK_MONOTONIC,0)==0,1000);
    REQUIRE(clock_getres(-1,0)==-1 && errno==EINVAL,1001);
    REQUIRE(clock_gettime(CLOCK_MONOTONIC,&mono)==0,1002);
    errno=0;int available=clock_gettime(CLOCK_REALTIME,&wall)==0;
    if(!available){
        REQUIRE(errno==EIO && wall.tv_sec==71 && wall.tv_nsec==92,1003);
#if __SIZEOF_LONG__ == 4 && defined(SYS_clock_getres_time32)
        REQUIRE(clock_getres(CLOCK_REALTIME,0)==-1 && errno==EIO,1022);
#else
        REQUIRE(clock_getres(CLOCK_REALTIME,0)==0,1022);
#endif
        REQUIRE(clock_getres(CLOCK_REALTIME,&res)==-1 && errno==EIO && res.tv_sec==71 && res.tv_nsec==92,1004);
        REQUIRE(syscall(RAW_REALTIME_GET,0,1)==-1 && errno==EIO,1005);
        realtime_text("OK_MUSL_REALTIME role=");realtime_text(role);
        realtime_text(" capability=unavailable errors=pass copies=unchanged monotonic=pass\n");
        return 0;
    }
    REQUIRE(wall.tv_sec>=0 && wall.tv_nsec>=0 && wall.tv_nsec<1000000000,1006);
    REQUIRE(clock_getres(CLOCK_REALTIME,0)==0,1022);
    REQUIRE(clock_getres(CLOCK_REALTIME,&res)==0 && res.tv_sec==0 && res.tv_nsec>0 && res.tv_nsec<1000000000,1007);
    REQUIRE(syscall(RAW_REALTIME_GET,0,1)==-1 && errno==EFAULT,1008);
    /* Upstream wrappers ignore clock errors; run them only after successful preflight. */
    struct timeval tv={71,92};time_t seconds=time(0);
    REQUIRE(seconds>=wall.tv_sec && seconds<=wall.tv_sec+1 && gettimeofday(&tv,0)==0 && tv.tv_sec>=wall.tv_sec && tv.tv_sec<=wall.tv_sec+1 && tv.tv_usec>=0 && tv.tv_usec<1000000,1009);
    const char *legacy="not-declared";
#if defined(RAW_REALTIME_LEGACY) && __SIZEOF_LONG__ == 4
    long raw[2]={71,92};errno=0;
    long rc=syscall(RAW_REALTIME_LEGACY,0,raw);
    if(wall.tv_sec>2147483647LL){
        REQUIRE(rc==-1 && errno==EOVERFLOW && raw[0]==71 && raw[1]==92,1010);
        REQUIRE(syscall(RAW_REALTIME_LEGACY,0,1)==-1 && errno==EOVERFLOW,1011);
        legacy="overflow";
    }else{REQUIRE(rc==0 && raw[0]>=wall.tv_sec && raw[0]<=wall.tv_sec+1 && raw[1]>=0 && raw[1]<1000000000,1012);legacy="pass";}
#endif
    long page=sysconf(_SC_PAGESIZE);REQUIRE(page>0,1013);
    unsigned char *memory=mmap(0,(size_t)page*2,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    REQUIRE(memory!=MAP_FAILED && mprotect(memory+page,(size_t)page,PROT_NONE)==0,1014);
    memset(memory+page-16,0xa5,16);
    REQUIRE(syscall(RAW_REALTIME_GET,0,memory+page-1)==-1 && errno==EFAULT,1015);
    for(unsigned i=0;i<16;++i)REQUIRE(memory[page-16+i]==0xa5,1016);
    REQUIRE(syscall(RAW_REALTIME_GET,0,memory+page-16)==0 && munmap(memory,(size_t)page*2)==0,1017);
    realtime_text("OK_MUSL_REALTIME_SAMPLE role=");realtime_text(role);
    realtime_text(" seconds=");realtime_number(wall.tv_sec);
    realtime_text(" nanoseconds=");realtime_number(wall.tv_nsec);
    realtime_text(" monotonic_seconds=");realtime_number(mono.tv_sec);
    realtime_text(" monotonic_nanoseconds=");realtime_number(mono.tv_nsec);realtime_text("\n");
    struct timespec delay={0,20000000},later;
    REQUIRE(nanosleep(&delay,0)==0 && clock_gettime(CLOCK_REALTIME,&later)==0 &&
            (later.tv_sec>wall.tv_sec || (later.tv_sec==wall.tv_sec && later.tv_nsec>wall.tv_nsec)),1018);
    realtime_text("OK_MUSL_REALTIME role=");realtime_text(role);
    realtime_text(" capability=available wrappers=pass legacy=");realtime_text(legacy);realtime_text(" copies=pass sleep=pass\n");
    return 0;
}

static int realtime_probe(void)
{
    int rc=realtime_check("parent");if(rc)return rc;
    pid_t child=fork();REQUIRE(child>=0,1019);
    if(!child){
        int result=realtime_check("fork");if(result)_Exit(result);
        char *args[]={"/bin/musl-bootstrap","realtime-exec",0};
        execve(args[0],args,environ);_Exit(failure(1020,errno));
    }
    int status=0;REQUIRE(waitpid(child,&status,0)==child && WIFEXITED(status) && WEXITSTATUS(status)==0,1021);
    return 0;
}


/* Directory creation runs after every earlier gate, including public clocks. */
static int mkdir_probe(int slot)
{
    const char *tree = slot ? "/home/musl-mkdir-1" : "/home/musl-mkdir-0";
    const char *group_tree = slot ? "run-1" : "run-0";
    mode_t old = umask(0027);
    REQUIRE(old == 0022, 1100);
    REQUIRE(mkdir(tree, 07777) == 0, 1101);
    int directory = open(tree, O_RDONLY | O_DIRECTORY);
    REQUIRE(directory >= 0 && chdir(tree) == 0, 1102);
    REQUIRE(mkdirat(directory, "child/", 0777) == 0, 1103);
    REQUIRE(mkdir("cwd", 0777) == 0 && chdir("/") == 0, 1104);
    errno = 0; REQUIRE(mkdirat(directory, "child", 0700) == -1 && errno == EEXIST, 1105);
    REQUIRE(mkdirat(-1, tree, 0700) == -1 && errno == EEXIST, 1106);
    REQUIRE(mkdirat(-1, "missing", 0700) == -1 && errno == EBADF, 1107);
    REQUIRE(mkdirat(-1, "", 0700) == -1 && errno == ENOENT, 1108);
    REQUIRE(syscall(SYS_mkdirat, -1, 1, 0700) == -1 && errno == EFAULT, 1109);
    REQUIRE(mkdirat(directory, ".", 0700) == -1 && errno == EEXIST, 1110);
    REQUIRE(mkdirat(directory, "..", 0700) == -1 && errno == EEXIST, 1111);
    REQUIRE(mkdir("/home/musl-file/", 0700) == -1 && errno == EEXIST, 1112);
    REQUIRE(mkdir("/home/musl-link/", 0700) == -1 && errno == EEXIST, 1113);
    int regular = openat(directory, "data", O_CREAT | O_EXCL | O_RDWR, 0666);
    REQUIRE(regular >= 0 && write(regular, "created", 7) == 7 && fsync(regular) == 0, 1114);
    REQUIRE(mkdirat(regular, "bad", 0700) == -1 && errno == ENOTDIR, 1115);
    REQUIRE(close(regular) == 0, 1116);
    long page = sysconf(_SC_PAGESIZE);
    unsigned char *memory = mmap(0, (size_t)page * 2, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    REQUIRE(page > 0 && memory != MAP_FAILED && mprotect(memory + page, (size_t)page, PROT_NONE) == 0, 1117);
    memory[page - 1] = 'x';
    REQUIRE(syscall(SYS_mkdirat, directory, memory + page - 1, 0700) == -1 && errno == EFAULT, 1118);
    REQUIRE(munmap(memory, (size_t)page * 2) == 0, 1119);
#ifdef SYS_mkdir
    const char *legacy = slot ? "/home/musl-mkdir-1/legacy" : "/home/musl-mkdir-0/legacy";
    REQUIRE(syscall(SYS_mkdir, legacy, (unsigned long)0xdeadf1ff) == 0, 1120);
#else
    REQUIRE(mkdirat(directory, "legacy", 0777) == 0, 1120);
#endif
    int other = dup(directory); REQUIRE(other >= 0 && close(directory) == 0, 1121);
    REQUIRE(mkdirat(other, "retained", 0777) == 0 && close(other) == 0, 1122);
    DIR *stream = opendir(tree); REQUIRE(stream != 0, 1123);
    unsigned seen = 0; struct dirent *entry;
    errno = 0;
    while ((entry = readdir(stream))) {
        if (!strcmp(entry->d_name, "child")) seen |= 1;
        if (!strcmp(entry->d_name, "cwd")) seen |= 2;
        if (!strcmp(entry->d_name, "legacy")) seen |= 4;
        if (!strcmp(entry->d_name, "retained")) seen |= 8;
        if (!strcmp(entry->d_name, "data")) seen |= 16;
    }
    REQUIRE(errno == 0 && seen == 31 && closedir(stream) == 0, 1124);
    int group = open("/home/musl-mkdir-sgid", O_RDONLY | O_DIRECTORY);
    REQUIRE(group >= 0 && mkdirat(group, group_tree, 01777) == 0, 1125);
    int inherited = openat(group, group_tree, O_RDONLY | O_DIRECTORY);
    REQUIRE(inherited >= 0 && close(group) == 0 && mkdirat(inherited, "nested", 0777) == 0, 1126);
    regular = openat(inherited, "data", O_CREAT | O_EXCL | O_WRONLY, 0666);
    REQUIRE(regular >= 0 && write(regular, "group", 5) == 5 && fsync(regular) == 0 && close(regular) == 0, 1127);
    REQUIRE(close(inherited) == 0 && umask(old) == 0027, 1128);
    const char *marker = slot ?
        "OK_MUSL_MKDIR slot=1 mkdir=pass mkdirat=pass modes=offline inheritance=offline copies=pass dirfd=pass errors=pass readdir=pass\n" :
        "OK_MUSL_MKDIR slot=0 mkdir=pass mkdirat=pass modes=offline inheritance=offline copies=pass dirfd=pass errors=pass readdir=pass\n";
    REQUIRE(write(1, marker, strlen(marker)) == (ssize_t)strlen(marker), 1129);
    return 0;
}

int main(int argc,char **argv,char **envp)
{
    if(argc==2 && !strcmp(argv[1],"realtime-exec"))return realtime_check("exec");
    if(argc==3 && !strcmp(argv[1],"umask-exec")) {
        REQUIRE((!strcmp(argv[2],"0") || !strcmp(argv[2],"1")) && umask(0027)==0027,920);
        REQUIRE(mask_file(argv[2][0]=='0' ? "/home/musl-mask-0-exec" : "/home/musl-mask-1-exec",1,"exec")==0,921);
        return 0;
    }
    int result=directory_probe_main(argc,argv,envp);if(result || argc!=1)return result;
    errno=0;mode_t original=umask(0);REQUIRE(original==0022,900);
    REQUIRE(umask(01077)==0,901);
    REQUIRE(umask((mode_t)-1)==0077,902);
    REQUIRE(syscall(SYS_umask,(unsigned long)0xffffffff00000012ULL)==0777,903);
    REQUIRE(umask(0022)==0022,904);
    int slot=0;
    errno=0;
    int fd=open("/home/musl-mask-0-parent",O_CREAT|O_EXCL|O_WRONLY,0666);
    if(fd<0 && errno==EEXIST){slot=1;fd=open("/home/musl-mask-1-parent",O_CREAT|O_EXCL|O_WRONLY,0666);}
    REQUIRE(fd>=0 && write(fd,"parent",6)==6 && fsync(fd)==0 && close(fd)==0,905);
    REQUIRE(umask(0077)==0022,906);
    REQUIRE(mask_file(slot ? "/home/musl-mask-1-restricted" : "/home/musl-mask-0-restricted",1,"restricted")==0,907);
    REQUIRE(mask_file(slot ? "/home/musl-mask-1-parent" : "/home/musl-mask-0-parent",0,"parent")==0,908);
    pid_t child=fork();REQUIRE(child>=0,909);
    if(!child) {
        if(umask(0007)!=0077 || mask_file(slot ? "/home/musl-mask-1-child" : "/home/musl-mask-0-child",1,"child"))_Exit(91);
        if(umask(0027)!=0007)_Exit(92);
        char *args[]={"/bin/musl-bootstrap","umask-exec",slot ? "1" : "0",0};
        execve(args[0],args,environ);_Exit(failure(923,errno));
    }
    int status=0;
    if(waitpid(child,&status,0)!=child || !WIFEXITED(status) || WEXITSTATUS(status)!=0)return failure(910,status);
    REQUIRE(umask(original)==0077,911);
    static const char marker0[]="OK_MUSL_UMASK_FILES slot=0 parent=0644 restricted=0600 child=0660 exec=0640\n";
    static const char marker1[]="OK_MUSL_UMASK_FILES slot=1 parent=0644 restricted=0600 child=0660 exec=0640\n";
    REQUIRE(write(1,slot ? marker1 : marker0,sizeof marker0-1)==sizeof marker0-1,912);
    static const char marker[]="OK_MUSL_UMASK scalar=pass creation=pass existing=pass fork=pass exec=pass isolation=pass\n";
    REQUIRE(write(1,marker,sizeof marker-1)==sizeof marker-1,913);
    result=realtime_probe();if(result)return result;
    return mkdir_probe(slot);
}

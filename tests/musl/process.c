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
int main(int argc, char **argv, char **envp)
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

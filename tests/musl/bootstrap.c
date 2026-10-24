#include <errno.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

static int musl_file_tests(void);
static int musl_file_mapping_tests(void);
static int musl_shared_futex_tests(void);
static int musl_heap_tests(void);

static _Thread_local volatile int tls_value = 7;

int main(int argc, char **argv, char **envp)
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
    if (result) return result;
    result = musl_file_mapping_tests();
    if (result) return result;
    result = musl_shared_futex_tests();
    return result ? result : musl_heap_tests();
}

#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <sys/syscall.h>
#include <sys/wait.h>
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

static int musl_file_mapping_tests(void)
{
    const size_t page = 4096;
    const char *path = "/home/musl-map";
    int fd = open(path, O_CREAT | O_TRUNC | O_RDWR, 0600);
    REQUIRE(fd >= 0, 90);
    char bytes[256];
    memset(bytes, 0x4a, sizeof bytes);
    for (unsigned i = 0; i < 16; ++i)
        REQUIRE(write(fd, bytes, sizeof bytes) == sizeof bytes, 91);
    memset(bytes, 0x31, sizeof bytes);
    for (unsigned i = 0; i < 16; ++i)
        REQUIRE(write(fd, bytes, sizeof bytes) == sizeof bytes, 101);
    memset(bytes, 0x72, 37);
    REQUIRE(write(fd, bytes, 37) == 37 && fsync(fd) == 0, 102);
    int write_only = open(path, O_WRONLY);
    REQUIRE(write_only >= 0, 92);
    errno = 0;
    REQUIRE(mmap(0, 1, PROT_READ, MAP_PRIVATE, -1, 0) == MAP_FAILED && errno == EBADF, 93);
    errno = 0;
    REQUIRE(mmap(0, 1, PROT_READ, MAP_PRIVATE, write_only, 0) == MAP_FAILED && errno == EACCES, 94);
    REQUIRE(close(write_only) == 0, 95);
    const unsigned char *short_map = mmap(0, 1, PROT_READ, MAP_PRIVATE, fd, page);
    REQUIRE(short_map != MAP_FAILED, 96);
    REQUIRE(short_map[0] == 0x31 && short_map[1] == 0x31 && short_map[page - 1] == 0x31, 97);
    REQUIRE(munmap((void *)short_map, 1) == 0, 99);

    unsigned char *mapped = mmap(0, page + 100, PROT_READ | PROT_WRITE, MAP_PRIVATE, fd, page);
    REQUIRE(mapped != MAP_FAILED, 103);
    REQUIRE(mapped[0] == 0x31 && mapped[page - 1] == 0x31 && mapped[page] == 0x72 &&
            mapped[page + 36] == 0x72 && mapped[page + 37] == 0 && mapped[2 * page - 1] == 0, 104);
    REQUIRE(pwrite(fd, "Z", 1, page) == 1, 105);
    char disk = 0;
    REQUIRE(pread(fd, &disk, 1, page) == 1 && disk == 'Z' && mapped[0] == 0x31, 106);
    mapped[0] = 0x91;
    REQUIRE(close(fd) == 0 && mapped[0] == 0x91 && mapped[page] == 0x72, 98);
    REQUIRE(unlink(path) == 0 && mapped[0] == 0x91 && mapped[page + 37] == 0, 107);

    pid_t child = fork();
    REQUIRE(child >= 0, 108);
    if (child == 0) {
        if (mapped[0] != 0x91 || mapped[page] != 0x72) _exit(109);
        mapped[0] = 0x52;
        mapped[page] = 0x62;
        _exit(0);
    }
    int child_status = 0;
    REQUIRE(waitpid(child, &child_status, 0) == child && WIFEXITED(child_status) &&
            WEXITSTATUS(child_status) == 0, 110);
    REQUIRE(mapped[0] == 0x91 && mapped[page] == 0x72, 111);
    REQUIRE(munmap(mapped, page + 100) == 0, 112);
#ifdef SYS_mmap2
    static const char marker[] = "OK_MUSL_FILE_PRIVATE scope=hardware offset=pass short_length=pass tail_zero=pass errno=pass close=pass unlink=pass private_write=pass fork=pass syscall=mmap2\n";
#else
    static const char marker[] = "OK_MUSL_FILE_PRIVATE scope=hardware offset=pass short_length=pass tail_zero=pass errno=pass close=pass unlink=pass private_write=pass fork=pass syscall=mmap\n";
#endif
    REQUIRE(write(1, marker, sizeof marker - 1) == sizeof marker - 1, 100);
    return 0;
}

static int musl_shared_futex_tests(void)
{
    volatile unsigned *word = mmap(0, 4096, PROT_READ | PROT_WRITE,
                                   MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    REQUIRE((void *)word != MAP_FAILED, 113);
    *word = 1;
    errno = 0;
    REQUIRE(syscall(SYS_futex, word, 1, 1, 0) == -1 && errno == ENOSYS, 114);
    errno = 0;
    /* A mismatched value would return EAGAIN if the shared key were admitted. */
    REQUIRE(syscall(SYS_futex, word, 0, 2, 0) == -1 && errno == ENOSYS, 115);
    REQUIRE(*word == 1 && munmap((void *)word, 4096) == 0, 116);
    static const char marker[] = "OK_MUSL_SHARED_FUTEX scope=hardware wait=unsupported wake=unsupported cleanup=pass\n";
    REQUIRE(write(1, marker, sizeof marker - 1) == sizeof marker - 1, 117);
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
    // 512 eight-KiB blocks exceed the entire 1024-frame guest pool.
    void *allocations[512];
    unsigned count = 0;
    for (; count < 512; ++count) {
        errno = 0;
        allocations[count] = malloc(8192);
        if (!allocations[count]) break;
        memset(allocations[count], (unsigned char)count, 8192);
    }
    if (!(count > 0 && count < 512 && errno == ENOMEM)) return failure(82, (int)count);
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

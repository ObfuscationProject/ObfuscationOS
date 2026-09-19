#include <errno.h>
#include <fcntl.h>
#include <ok/syscall.h>
#include <ok/dirent.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <sys/uio.h>
#include <unistd.h>

_Static_assert(offsetof(struct dirent, d_reclen) == 16, "getdents64 record offset");
_Static_assert(offsetof(struct dirent, d_name) == 19, "getdents64 name offset");
static volatile int private_value = 7;
static const char readonly_value[] = "read only";
#define CHECK(condition)                                                                                               \
    do                                                                                                                 \
    {                                                                                                                  \
        if (!(condition))                                                                                              \
        {                                                                                                              \
            puts("POSIX_CHECK failed: " #condition);                                                                   \
            return 1;                                                                                                  \
        }                                                                                                              \
    } while (0)
static int child_status(pid_t pid)
{
    int status = 0;
    if (waitpid(pid, &status, 0) != pid)
        return -1;
    return WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status);
}
int main(int argc, char **argv)
{
    CHECK(argc == 1 && argv && strcmp(argv[0], "posix-check") == 0);
    CHECK(ok_syscall3(OK_SYS_WRITE, 1, 1, 4) == -EFAULT);
    CHECK(ok_syscall3(OK_SYS_READ, 0, (long)readonly_value, 1) == -EFAULT);
    CHECK(ok_syscall1(OK_SYS_OPEN, 1) == -EFAULT);
    int file = open("/tmp/posix-io", O_CREAT | O_RDWR | O_TRUNC, 0600);
    CHECK(file >= 0);
    int directory = open("/tmp", O_RDONLY | O_DIRECTORY);
    CHECK(directory >= 0);
    _Alignas(8) unsigned char dents[512];
    int found_file = 0;
    for (;;)
    {
        ssize_t size = getdents64(directory, dents, sizeof(dents));
        CHECK(size >= 0);
        if (!size) break;
        size_t position = 0;
        while (position < (size_t)size)
        {
            struct dirent *entry = (struct dirent *)(dents + position);
            CHECK(entry->d_ino > 0 && entry->d_off > 0);
            CHECK(entry->d_reclen >= 24 && entry->d_reclen <= (size_t)size - position);
            if (strcmp(entry->d_name, "posix-io") == 0) found_file = 1;
            position += entry->d_reclen;
        }
    }
    CHECK(found_file && close(directory) == 0);
    CHECK(fsync(-1) == -1 && errno == EBADF);
    CHECK(ftruncate(-1, 0) == -1 && errno == EBADF);
    char one;
    CHECK(pread(-1, &one, 1, 0) == -1 && errno == EBADF);
    CHECK(pwrite(-1, "x", 1, 0) == -1 && errno == EBADF);
    int seek_pipe[2];
    CHECK(pipe(seek_pipe) == 0);
    CHECK(pread(seek_pipe[0], &one, 1, 0) == -1 && errno == ESPIPE);
    CHECK(pwrite(seek_pipe[1], "x", 1, 0) == -1 && errno == ESPIPE);
    CHECK(close(seek_pipe[0]) == 0 && close(seek_pipe[1]) == 0);
    CHECK(write(file, "abcdef", 6) == 6);
    CHECK(lseek(file, 0, SEEK_SET) == 0);
    CHECK(write(file, "X", 1) == 1);
    CHECK(write(file, "", 0) == 0);
    CHECK(lseek(file, -1, SEEK_END) == 5);
    char io[16] = {0};
    CHECK(pread(file, io, 6, 0) == 6 && memcmp(io, "Xbcdef", 6) == 0);
    CHECK(lseek(file, 0, SEEK_CUR) == 5);
    CHECK(pwrite(file, "Y", 1, 2) == 1);
    CHECK(lseek(file, 0, SEEK_CUR) == 5);
    CHECK(ftruncate(file, 3) == 0 && ftruncate(file, 12) == 0);
    memset(io, 1, sizeof(io));
    CHECK(pread(file, io, sizeof(io), 3) == 9);
    for (int i = 0; i < 9; ++i) CHECK(io[i] == 0);
    CHECK(pread(file, io, sizeof(io), 200) == 0);
    CHECK(pread(file, io, sizeof(io), -1) == -1 && errno == EINVAL);
    CHECK(lseek(file, 0, SEEK_SET) == 0);
    struct iovec out[] = {{(void *)"vec", 3}, {(void *)"tor", 3}};
    CHECK(writev(file, out, 2) == 6);
    struct iovec in[] = {{io, 2}, {io + 2, 4}};
    CHECK(lseek(file, 0, SEEK_SET) == 0 && readv(file, in, 2) == 6);
    CHECK(memcmp(io, "vector", 6) == 0);
    struct iovec bad[] = {{(void *)1, 1}};
    CHECK(writev(file, bad, 1) == -1 && errno == EFAULT);
    CHECK(lseek(file, 0, SEEK_CUR) == 6);
    CHECK(fsync(file) == 0 && fdatasync(file) == 0);
    CHECK(truncate("/tmp/posix-io", 2) == 0);
    CHECK(lseek(file, 0, SEEK_END) == 2);
    CHECK(close(file) == 0 && unlink("/tmp/posix-io") == 0);
    pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        private_value = 99;
        _Exit(23);
    }
    CHECK(child_status(child) == 23);
    CHECK(private_value == 7);
    CHECK(waitpid(child, 0, 0) == -1 && errno == ECHILD);

    const int exit_codes[] = {-1, (-2147483647 - 1), 256};
    const int expected_codes[] = {255, 0, 0};
    for (unsigned i = 0; i < sizeof(exit_codes) / sizeof(exit_codes[0]); ++i)
    {
        child = fork();
        CHECK(child >= 0);
        if (child == 0)
            _Exit(exit_codes[i]);
        int status = 0;
        CHECK(waitpid(child, &status, 0) == child);
        CHECK(WIFEXITED(status) && WEXITSTATUS(status) == expected_codes[i]);
    }

    // Exceed the kernel process-table capacity without retaining orphan slots.
    for (unsigned i = 0; i < 65; ++i)
    {
        int done[2];
        CHECK(pipe(done) == 0);
        child = fork();
        CHECK(child >= 0);
        if (child == 0)
        {
            close(done[0]);
            pid_t orphan = fork();
            if (orphan < 0)
                _Exit(1);
            if (orphan > 0)
                _Exit(0);
            while (ok_syscall0(OK_SYS_GETPPID) != 0)
            {
            }
            if (write(done[1], "x", 1) != 1)
                _Exit(1);
            _Exit(0);
        }
        close(done[1]);
        CHECK(child_status(child) == 0);
        char value = 0;
        CHECK(read(done[0], &value, 1) == 1 && value == 'x');
        CHECK(read(done[0], &value, 1) == 0);
        close(done[0]);
    }

    int fds[2];
    CHECK(pipe(fds) == 0);
    child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        close(fds[0]);
        if (write(fds[1], "pipe-data", 9) != 9)
            _Exit(1);
        close(fds[1]);
        _Exit(0);
    }
    close(fds[1]);
    char bytes[16] = {0};
    CHECK(read(fds[0], bytes, sizeof(bytes)) == 9);
    CHECK(strcmp(bytes, "pipe-data") == 0);
    CHECK(read(fds[0], bytes, sizeof(bytes)) == 0);
    close(fds[0]);
    CHECK(child_status(child) == 0);
    CHECK(pipe(fds) == 0);
    close(fds[0]);
    CHECK(write(fds[1], "x", 1) == -1 && errno == EPIPE);
    close(fds[1]);

    child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        char *args[] = {"hello", 0};
        char *env[] = {0};
        execve("/bin/hello", args, env);
        _Exit(127);
    }
    CHECK(child_status(child) == 0);
    child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        *(volatile char *)readonly_value = 'X';
        _Exit(1);
    }
    CHECK(child_status(child) == 139);
    child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        *(volatile int *)0x100000 = 1;
        _Exit(1);
    }
    CHECK(child_status(child) == 139);
    child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        for (volatile unsigned long i = 0; i < 30000000UL; ++i)
        {
        }
        _Exit(0);
    }
    CHECK(child_status(child) == 0);
    puts("OK_POSIX scope=hardware fork=pass isolation=pass exec=pass wait=pass pipe=pass efault=pass readonly=pass "
         "orphan=pass exit_status=pass file_io=pass vector_io=pass sync=pass");
    return 0;
}

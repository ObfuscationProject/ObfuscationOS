#include <errno.h>
#include <fcntl.h>
#include <ok/syscall.h>
#include <ok/dirent.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <sys/uio.h>
#include <unistd.h>
#include <time.h>
#include <poll.h>

_Static_assert(offsetof(struct dirent, d_reclen) == 16, "getdents64 record offset");
_Static_assert(offsetof(struct dirent, d_name) == 19, "getdents64 name offset");
static volatile int private_value = 7;
static const char readonly_value[] = "read only";
int check_fat_media(const char *phase);
#define CHECK(condition)                                                                                               \
    do                                                                                                                 \
    {                                                                                                                  \
        if (!(condition))                                                                                              \
        {                                                                                                              \
            printf("POSIX_CHECK failed: " #condition " errno=%d\n", errno);                                            \
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

static int64_t monotonic_ns(void)
{
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0)
        return -1;
    return now.tv_sec * 1000000000 + now.tv_nsec;
}

static int check_native_time(void)
{
    struct timespec value, invalid = {0, 1000000000}, delay = {0, 20000000};
    struct timespec remainder = {71, 92};
    CHECK(clock_getres(CLOCK_MONOTONIC, &value) == 0);
    CHECK(value.tv_sec == 0 && value.tv_nsec > 0 && value.tv_nsec < 1000000000);
    CHECK(clock_getres(CLOCK_MONOTONIC, 0) == 0);
    CHECK(clock_gettime(-1, &value) == -1 && errno == EINVAL);
    CHECK(clock_getres(-1, 0) == -1 && errno == EINVAL);
    CHECK(ok_syscall2(OK_SYS_CLOCK_GETTIME, CLOCK_MONOTONIC, 1) == -EFAULT);
    CHECK(ok_syscall2(OK_SYS_NANOSLEEP, 1, 0) == -EFAULT);
    CHECK(nanosleep(&invalid, 0) == -1 && errno == EINVAL);
    invalid.tv_sec = -1; invalid.tv_nsec = 0;
    CHECK(nanosleep(&invalid, 0) == -1 && errno == EINVAL);
    invalid.tv_sec = INT64_MAX;
    CHECK(nanosleep(&invalid, 0) == -1 && errno == EOVERFLOW);
    errno = EBUSY;
    CHECK(clock_nanosleep(CLOCK_MONOTONIC, 2, &delay, 0) == EINVAL && errno == EBUSY);
    int64_t before = monotonic_ns();
    CHECK(before >= 0);
    for (int i = 0; i < 1000; ++i)
        CHECK(getpid() > 0);
    CHECK(monotonic_ns() > before);
    before = monotonic_ns();
    CHECK(nanosleep(&delay, &remainder) == 0);
    CHECK(monotonic_ns() - before >= delay.tv_nsec);
    CHECK(remainder.tv_sec == 71 && remainder.tv_nsec == 92);
    int64_t deadline = monotonic_ns() + 20000000;
    value.tv_sec = deadline / 1000000000;
    value.tv_nsec = deadline % 1000000000;
    CHECK(clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &value, 0) == 0);
    CHECK(monotonic_ns() >= deadline);
    value.tv_sec = value.tv_nsec = 0;
    CHECK(clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &value, (void *)1) == 0);
    int timestamps[2], acknowledgement[2];
    CHECK(pipe(timestamps) == 0 && pipe(acknowledgement) == 0);
    pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        close(timestamps[0]); close(acknowledgement[1]);
        delay.tv_nsec = 200000000;
        int64_t start = monotonic_ns();
        if (write(timestamps[1], &start, sizeof(start)) != sizeof(start))
            _Exit(1);
        if (nanosleep(&delay, 0) != 0 || monotonic_ns() - start < delay.tv_nsec)
            _Exit(1);
        int64_t progress;
        if (read(acknowledgement[0], &progress, sizeof(progress)) != sizeof(progress) ||
            progress < start || progress >= start + delay.tv_nsec)
            _Exit(2);
        _Exit(0);
    }
    CHECK(close(timestamps[1]) == 0 && close(acknowledgement[0]) == 0);
    int64_t child_start;
    CHECK(read(timestamps[0], &child_start, sizeof(child_start)) == sizeof(child_start));
    CHECK(nanosleep(&delay, 0) == 0);
    for (int i = 0; i < 100; ++i)
        CHECK(getpid() > 0);
    int64_t progress = monotonic_ns();
    CHECK(progress >= child_start && write(acknowledgement[1], &progress, sizeof(progress)) == sizeof(progress));
    CHECK(close(timestamps[0]) == 0 && close(acknowledgement[1]) == 0);
    CHECK(child_status(child) == 0);
    puts("OK_TIME_NATIVE scope=hardware monotonic=pass sleep=pass absolute=pass sibling=pass validation=pass");
    return 0;
}

static int check_native_poll(void)
{
    int descriptors[2];
    char bytes[4097];
    memset(bytes, 'p', sizeof(bytes));
    CHECK(pipe2(descriptors, O_NONBLOCK | O_CLOEXEC) == 0);
    CHECK(fcntl(descriptors[0], F_GETFD) == FD_CLOEXEC);
    CHECK((fcntl(descriptors[0], F_GETFL) & O_NONBLOCK) != 0);
    CHECK(read(descriptors[0], bytes, 1) == -1 && errno == EAGAIN);
    int duplicate = dup(descriptors[0]);
    CHECK(duplicate >= 0 && fcntl(duplicate, F_SETFL, 0) == 0);
    CHECK((fcntl(descriptors[0], F_GETFL) & O_NONBLOCK) == 0);
    CHECK(fcntl(duplicate, F_SETFL, O_NONBLOCK) == 0 && close(duplicate) == 0);
    struct pollfd fds[4] = {{descriptors[0], POLLIN, -1}, {descriptors[1], POLLOUT, -1}, {-1, POLLIN, -1}, {1234, 0, -1}};
    CHECK(poll(fds, 4, 0) == 2);
    CHECK(fds[0].revents == 0 && fds[1].revents == POLLOUT && fds[2].revents == 0 && fds[3].revents == POLLNVAL);
    CHECK(poll((void *)1, 1, 0) == -1 && errno == EFAULT);
    CHECK(poll(fds, 33, 0) == -1 && errno == EINVAL);
    CHECK(pipe2(descriptors, 0x40000000) == -1 && errno == EINVAL);
    int64_t before = monotonic_ns();
    CHECK(poll(0, 0, 20) == 0 && monotonic_ns() - before >= 20000000);
    before = monotonic_ns();
    CHECK(poll(fds, 1, 20) == 0 && fds[0].revents == 0 && monotonic_ns() - before >= 20000000);
    CHECK(write(descriptors[1], bytes, 4096) == 4096);
    CHECK(write(descriptors[1], bytes, 1) == -1 && errno == EAGAIN);
    CHECK(poll(fds, 2, 0) == 1 && fds[0].revents == POLLIN && fds[1].revents == 0);
    CHECK(read(descriptors[0], bytes, 100) == 100);
    CHECK(write(descriptors[1], bytes, 101) == -1 && errno == EAGAIN);
    CHECK(write(descriptors[1], bytes, sizeof(bytes)) == 100);
    CHECK(read(descriptors[0], bytes, 100) == 100);
    struct iovec large_vectors[2] = {{bytes, 2048}, {bytes + 2048, 2049}};
    CHECK(writev(descriptors[1], large_vectors, 2) == 100);
    CHECK(read(descriptors[0], bytes, 4096) == 4096);
    pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0) {
        close(descriptors[0]);
        struct timespec delay = {0, 20000000};
        if (nanosleep(&delay, 0) != 0 || write(descriptors[1], "r", 1) != 1)
            _Exit(1);
        _Exit(0);
    }
    CHECK(close(descriptors[1]) == 0);
    CHECK(poll(fds, 1, -1) == 1 && (fds[0].revents & POLLIN) != 0);
    CHECK(read(descriptors[0], bytes, 1) == 1 && bytes[0] == 'r');
    CHECK(child_status(child) == 0);
    CHECK(poll(fds, 1, -1) == 1 && (fds[0].revents & POLLHUP) != 0);
    CHECK(read(descriptors[0], bytes, 1) == 0 && close(descriptors[0]) == 0);
    CHECK(pipe2(descriptors, O_NONBLOCK) == 0 && close(descriptors[0]) == 0);
    fds[0].fd = descriptors[1]; fds[0].events = 0;
    CHECK(poll(fds, 1, -1) == 1 && (fds[0].revents & POLLERR) != 0);
    CHECK(close(descriptors[1]) == 0);
    puts("OK_POLL_NATIVE scope=hardware nonblock=pass readiness=pass timeout=pass wake=pass peer_close=pass");
    return 0;
}

static int check_file_names(void)
{
    const char *source = "/tmp/posix-names/left/source";
    const char *target = "/tmp/posix-names/right/target";
    CHECK(mkdir("/tmp/posix-names", 0700) == 0);
    CHECK(mkdir("/tmp/posix-names/left", 0700) == 0);
    CHECK(mkdir("/tmp/posix-names/right", 0700) == 0);
    int left = open("/tmp/posix-names/left", O_RDONLY | O_DIRECTORY);
    int right = open("/tmp/posix-names/right", O_RDONLY | O_DIRECTORY);
    CHECK(left >= 0 && right >= 0);
    int original = open(source, O_CREAT | O_EXCL | O_RDWR, 0600);
    int replaced = open(target, O_CREAT | O_EXCL | O_RDWR, 0600);
    CHECK(original >= 0 && replaced >= 0);
    CHECK(write(original, "source", 6) == 6 && write(replaced, "old", 3) == 3);

    // Both pathname slots must be copied before any namespace mutation.
    CHECK(ok_syscall2(OK_SYS_RENAME, 1, (long)target) == -EFAULT);
    CHECK(ok_syscall2(OK_SYS_RENAME, (long)source, 1) == -EFAULT);
    CHECK(ok_syscall2(OK_SYS_LINK, 1, (long)target) == -EFAULT);
    CHECK(ok_syscall2(OK_SYS_LINK, (long)source, 1) == -EFAULT);
    CHECK(ok_syscall4(OK_SYS_RENAMEAT, left, 1, right, (long)"target") == -EFAULT);
    CHECK(ok_syscall4(OK_SYS_RENAMEAT, left, (long)"source", right, 1) == -EFAULT);
    CHECK(ok_syscall5(OK_SYS_LINKAT, left, 1, right, (long)"unused", 0) == -EFAULT);
    CHECK(ok_syscall5(OK_SYS_LINKAT, left, (long)"source", right, 1, 0) == -EFAULT);
    CHECK(linkat(left, "source", right, "bad-flags", 1) == -1 && errno == EINVAL);
    CHECK(renameat(-1, "source", right, "unused") == -1 && errno == EBADF);
    CHECK(linkat(left, "source", -1, "unused", 0) == -1 && errno == EBADF);
    struct stat st;
    CHECK(stat("/tmp/posix-names/right/bad-flags", &st) == -1 && errno == ENOENT);

    CHECK(renameat(left, "source", right, "target") == 0);
    CHECK(stat(source, &st) == -1 && errno == ENOENT);
    CHECK(stat(target, &st) == 0 && st.st_nlink == 1 && st.st_size == 6);
    CHECK(fstat(replaced, &st) == 0 && st.st_nlink == 0 && st.st_size == 3);
    char bytes[8] = {0};
    CHECK(pread(replaced, bytes, sizeof(bytes), 0) == 3 && memcmp(bytes, "old", 3) == 0);
    CHECK(pwrite(replaced, "OLD", 3, 0) == 3);
    CHECK(pread(original, bytes, sizeof(bytes), 0) == 6 && memcmp(bytes, "source", 6) == 0);

    CHECK(chdir("/tmp/posix-names") == 0);
    CHECK(rename("right/target", "left/moved") == 0);
    CHECK(stat("right/target", &st) == -1 && errno == ENOENT);
    CHECK(link("left/moved", "left/alias") == 0);
    CHECK(fstat(original, &st) == 0 && st.st_nlink == 2);
    CHECK(linkat(left, "alias", right, "linked", 0) == 0);
    CHECK(fstat(original, &st) == 0 && st.st_nlink == 3);
    CHECK(renameat(right, "linked", AT_FDCWD, "right/from-cwd") == 0);
    CHECK(linkat(AT_FDCWD, "left/moved", right, "extra", 0) == 0);
    CHECK(fstat(original, &st) == 0 && st.st_nlink == 4);
    CHECK(link("left/moved", "left/alias") == -1 && errno == EEXIST);

    // Renaming between two names of one inode leaves both names intact.
    CHECK(rename("left/moved", "left/alias") == 0);
    CHECK(stat("left/moved", &st) == 0 && st.st_nlink == 4);
    CHECK(stat("left/alias", &st) == 0 && st.st_nlink == 4);
    CHECK(pwrite(original, "S", 1, 0) == 1);
    int alias = open("right/from-cwd", O_RDONLY);
    CHECK(alias >= 0);
    CHECK(read(alias, bytes, sizeof(bytes)) == 6 && memcmp(bytes, "Source", 6) == 0);
    CHECK(close(alias) == 0);
    CHECK(unlink("left/moved") == 0 && fstat(original, &st) == 0 && st.st_nlink == 3);
    CHECK(unlink("left/alias") == 0 && fstat(original, &st) == 0 && st.st_nlink == 2);
    CHECK(unlink("right/from-cwd") == 0 && fstat(original, &st) == 0 && st.st_nlink == 1);
    CHECK(unlink("right/extra") == 0 && fstat(original, &st) == 0 && st.st_nlink == 0);
    CHECK(pwrite(original, "!", 1, 6) == 1);
    CHECK(pread(original, bytes, sizeof(bytes), 0) == 7 && memcmp(bytes, "Source!", 7) == 0);
    CHECK(pread(replaced, bytes, sizeof(bytes), 0) == 3 && memcmp(bytes, "OLD", 3) == 0);
    CHECK(close(original) == 0 && close(replaced) == 0);
    CHECK(chdir("left") == 0);
    CHECK(rename("/tmp/posix-names/left", "/tmp/posix-names/moved") == 0);
    char cwd[64];
    CHECK(getcwd(cwd, sizeof(cwd)) == cwd && strcmp(cwd, "/tmp/posix-names/moved") == 0);
    int created = (int)ok_syscall4(OK_SYS_OPENAT, left, (long)"created", O_CREAT | O_RDWR, 0600);
    CHECK(created >= 0 && write(created, "directory", 9) == 9 && close(created) == 0);
    CHECK(chdir("/") == 0 && ok_syscall1(OK_SYS_FCHDIR, left) == 0);
    CHECK(getcwd(cwd, sizeof(cwd)) == cwd && strcmp(cwd, "/tmp/posix-names/moved") == 0);
    CHECK(stat("missing/../created", &st) == -1 && errno == ENOENT);
    CHECK(stat("created/../created", &st) == -1 && errno == ENOTDIR);
    CHECK(stat("created/", &st) == -1 && errno == ENOTDIR);
    CHECK(link("/bin/hello", "launch") == 0);
    pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        char *args[] = {"hello", 0};
        char *env[] = {0};
        execve("./launch", args, env);
        _Exit(127);
    }
    CHECK(child_status(child) == 0);
    CHECK(unlink("launch") == 0);
    CHECK(unlink("created") == 0);
    CHECK(close(left) == 0 && close(right) == 0);
    CHECK(chdir("/") == 0);
    CHECK(rmdir("/tmp/posix-names/moved") == 0);
    CHECK(rmdir("/tmp/posix-names/right") == 0);
    CHECK(rmdir("/tmp/posix-names") == 0);
    int parent = open("/tmp", O_RDONLY | O_DIRECTORY);
    CHECK(parent >= 0 && fsync(parent) == 0 && close(parent) == 0);
    return 0;
}

static int check_symbolic_links(void)
{
    CHECK(mkdir("/tmp/posix-links", 0700) == 0);
    int directory = open("/tmp/posix-links", O_RDONLY | O_DIRECTORY);
    CHECK(directory >= 0);
    CHECK(ok_syscall2(OK_SYS_SYMLINK, 1, (long)"/tmp/posix-links/bad") == -EFAULT);
    CHECK(ok_syscall2(OK_SYS_SYMLINK, (long)"target", 1) == -EFAULT);
    CHECK(ok_syscall3(OK_SYS_SYMLINKAT, 1, directory, (long)"bad") == -EFAULT);
    CHECK(ok_syscall3(OK_SYS_SYMLINKAT, (long)"target", directory, 1) == -EFAULT);
    int result = symlinkat("target", directory, "relative");
    if (result < 0 && errno == ENOSYS)
    {
        // The non-journalled ext4 subset does not yet create symbolic links.
        struct stat missing;
        CHECK(lstat("/tmp/posix-links/relative", &missing) == -1 && errno == ENOENT);
        CHECK(close(directory) == 0 && rmdir("/tmp/posix-links") == 0);
        puts("OK_PATH scope=hardware relative_exec=pass symlink=unsupported-filesystem");
        return 0;
    }
    CHECK(result == 0);
    CHECK(chdir("/tmp/posix-links") == 0);
    char bytes[16];
    memset(bytes, '!', sizeof(bytes));
    CHECK(readlink("relative", bytes, sizeof(bytes)) == 6);
    CHECK(memcmp(bytes, "target", 6) == 0 && bytes[6] == '!');
    memset(bytes, '!', sizeof(bytes));
    CHECK(readlinkat(directory, "relative", bytes, 3) == 3);
    CHECK(memcmp(bytes, "tar", 3) == 0 && bytes[3] == '!');
    CHECK(readlink("relative", bytes, 0) == -1 && errno == EINVAL);
    CHECK(ok_syscall3(OK_SYS_READLINK, (long)"relative", 1, 4) == -EFAULT);
    CHECK(ok_syscall4(OK_SYS_READLINKAT, directory, (long)"relative", 1, 4) == -EFAULT);
    CHECK(ok_syscall3(OK_SYS_READLINK, 1, (long)bytes, sizeof(bytes)) == -EFAULT);
    CHECK(ok_syscall4(OK_SYS_READLINKAT, directory, 1, (long)bytes, sizeof(bytes)) == -EFAULT);
    CHECK(ok_syscall3(OK_SYS_READLINK, (long)"relative", (long)readonly_value, 4) == -EFAULT);
    CHECK(readlinkat(-1, "relative", bytes, sizeof(bytes)) == -1 && errno == EBADF);
    CHECK(symlinkat("target", -1, "bad") == -1 && errno == EBADF);
    CHECK(symlink("target", "relative") == -1 && errno == EEXIST);
    char *boundary = mmap(0, 8192, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK(boundary != MAP_FAILED && munmap(boundary + 4096, 4096) == 0);
    memset(boundary + 4090, '!', 6);
    CHECK(readlink("relative", boundary + 4090, 16) == 6);
    CHECK(memcmp(boundary + 4090, "target", 6) == 0);
    CHECK(readlink("relative", boundary + 4091, 16) == -1 && errno == EFAULT);
    CHECK(munmap(boundary, 4096) == 0);
    struct stat st;
    CHECK(lstat("bad", &st) == -1 && errno == ENOENT);
    CHECK(lstat("relative", &st) == 0 && S_ISLNK(st.st_mode) && st.st_size == 6);
    CHECK(stat("relative", &st) == -1 && errno == ENOENT);
    CHECK(open("relative", O_CREAT | O_EXCL | O_RDWR, 0600) == -1 && errno == EEXIST);
    int target = open("relative", O_CREAT | O_RDWR, 0600);
    CHECK(target >= 0 && write(target, "payload", 7) == 7 && close(target) == 0);
    CHECK(stat("relative", &st) == 0 && S_ISREG(st.st_mode) && st.st_size == 7);
    CHECK(open("relative", O_NOFOLLOW | O_RDONLY) == -1 && errno == ELOOP);
    CHECK(readlink("target", bytes, sizeof(bytes)) == -1 && errno == EINVAL);
    CHECK(symlink("/tmp/posix-links", "absolute") == 0);
    CHECK(stat("absolute/relative", &st) == 0 && st.st_size == 7);
    CHECK(symlink("cycle-b", "cycle-a") == 0 && symlink("cycle-a", "cycle-b") == 0);
    CHECK(stat("cycle-a", &st) == -1 && errno == ELOOP);
    CHECK(symlink("/bin/hello", "launch") == 0);
    CHECK(rename("/tmp/posix-links", "/tmp/posix-links-moved") == 0);
    CHECK(readlinkat(directory, "relative", bytes, sizeof(bytes)) == 6);
    pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        char *args[] = {"hello", 0};
        char *env[] = {0};
        execve("launch", args, env);
        _Exit(127);
    }
    CHECK(child_status(child) == 0);
    CHECK(unlink("relative") == 0 && stat("target", &st) == 0);
    CHECK(unlink("target") == 0 && unlink("absolute") == 0);
    CHECK(unlink("cycle-a") == 0 && unlink("cycle-b") == 0 && unlink("launch") == 0);
    CHECK(chdir("/") == 0 && close(directory) == 0 && rmdir("/tmp/posix-links-moved") == 0);
    puts("OK_PATH scope=hardware relative_exec=pass symlink=pass");
    return 0;
}

static int check_native_memory(void)
{
    const size_t page = 4096;
    volatile unsigned char *memory = mmap(0, 3 * page, PROT_READ | PROT_WRITE,
                                          MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK((void *)memory != MAP_FAILED);
    for (size_t i = 0; i < 3 * page; ++i) CHECK(memory[i] == 0);
    memory[0] = 11;
    memory[page] = 22;
    memory[2 * page] = 33;
    CHECK(mprotect((void *)(memory + 1), page, PROT_READ) == -1 && errno == EINVAL);
    CHECK(mprotect((void *)memory, page, PROT_READ) == 0);
    CHECK(memory[0] == 11);
    CHECK(ok_syscall3(OK_SYS_READ, 0, (long)memory, 1) == -EFAULT);
    pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        memory[0] = 99;
        _Exit(1);
    }
    CHECK(child_status(child) == 139 && memory[0] == 11);
    CHECK(mprotect((void *)memory, page, PROT_NONE) == 0);
    CHECK(ok_syscall3(OK_SYS_WRITE, 1, (long)memory, 1) == -EFAULT);
    child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        _Exit(memory[0]);
    }
    CHECK(child_status(child) == 139);
    CHECK(mprotect((void *)memory, page, PROT_READ | PROT_WRITE) == 0 && memory[0] == 11);
    child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        memory[2 * page] = 77;
        _Exit(memory[2 * page] == 77 ? 0 : 1);
    }
    CHECK(child_status(child) == 0 && memory[2 * page] == 33);
    CHECK(munmap((void *)(memory + page), page) == 0);
    CHECK(memory[0] == 11 && memory[2 * page] == 33);
    child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        _Exit(memory[page]);
    }
    CHECK(child_status(child) == 139);
    const size_t bulk_pages = 192;
    volatile unsigned char *bulk = mmap(0, bulk_pages * page, PROT_READ | PROT_WRITE,
                                        MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK((void *)bulk != MAP_FAILED);
    for (size_t i = 0; i < bulk_pages; ++i)
    {
        CHECK(bulk[i * page] == 0 && bulk[i * page + page - 1] == 0);
        bulk[i * page] = (unsigned char)(i ^ 0x5a);
    }
    child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        for (size_t i = 0; i < bulk_pages; ++i)
            if (bulk[i * page] != (unsigned char)(i ^ 0x5a)) _Exit(1);
        bulk[0] = 99;
        bulk[(bulk_pages - 1) * page] = 77;
        _Exit(0);
    }
    CHECK(child_status(child) == 0);
    CHECK(bulk[0] == 0x5a && bulk[(bulk_pages - 1) * page] == (unsigned char)(191 ^ 0x5a));
    CHECK(mprotect((void *)(bulk + 170 * page), page, PROT_NONE) == 0);
    CHECK(ok_syscall3(OK_SYS_WRITE, 1, (long)(bulk + 170 * page), 1) == -EFAULT);
    child = fork();
    CHECK(child >= 0);
    if (child == 0) _Exit(bulk[170 * page]);
    CHECK(child_status(child) == 139);
    CHECK(mprotect((void *)(bulk + 170 * page), page, PROT_READ | PROT_WRITE) == 0);
    CHECK(bulk[170 * page] == (unsigned char)(170 ^ 0x5a));
    CHECK(munmap((void *)(bulk + 171 * page), page) == 0);
    CHECK(bulk[170 * page] == (unsigned char)(170 ^ 0x5a) &&
          bulk[172 * page] == (unsigned char)(172 ^ 0x5a));
    CHECK(mmap((void *)(bulk + 171 * page), page, PROT_READ | PROT_WRITE,
               MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED, -1, 0) == (void *)(bulk + 171 * page));
    CHECK(bulk[171 * page] == 0);
    CHECK(mmap(0, 1024 * page, PROT_READ | PROT_WRITE,
               MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) == MAP_FAILED && errno == ENOMEM);
    CHECK(bulk[0] == 0x5a && bulk[170 * page] == (unsigned char)(170 ^ 0x5a) &&
          bulk[172 * page] == (unsigned char)(172 ^ 0x5a) && memory[0] == 11 && memory[2 * page] == 33);
    CHECK(munmap((void *)bulk, bulk_pages * page) == 0);
    CHECK(munmap((void *)memory, 3 * page) == 0);
    memory = mmap(0, page, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK((void *)memory != MAP_FAILED && memory[0] == 0 && munmap((void *)memory, page) == 0);
    puts("OK_VM_NATIVE scope=hardware map=pass zero=pass protect=pass unmap=pass fork=pass pressure=pass");
    puts("OK_VM_PAGED scope=hardware pages=192 fork=pass none=pass remap=pass rollback=pass cleanup=pass");
    return 0;
}

static int check_shared_anonymous_memory(void)
{
    const size_t page = 4096;
    CHECK(mmap(0, page, PROT_READ, MAP_SHARED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0) == MAP_FAILED &&
          errno == EINVAL);
    CHECK(mmap(0, page, PROT_READ, MAP_ANONYMOUS, -1, 0) == MAP_FAILED && errno == EINVAL);
    CHECK(mmap(0, page, PROT_READ, MAP_SHARED | MAP_ANONYMOUS, -1, page) == MAP_FAILED && errno == EINVAL);
    volatile unsigned char *shared = mmap(0, 3 * page, PROT_READ | PROT_WRITE,
                                          MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    volatile unsigned char *private_pages = mmap(0, page, PROT_READ | PROT_WRITE,
                                                 MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK((void *)shared != MAP_FAILED && (void *)private_pages != MAP_FAILED);
    CHECK(shared[0] == 0 && shared[page] == 0 && shared[2 * page] == 0);
    shared[0] = 10;
    shared[page] = 20;
    shared[2 * page] = 30;
    private_pages[0] = 7;
    pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        if (shared[0] != 10 || private_pages[0] != 7)
            _Exit(1);
        shared[0] = 41;
        private_pages[0] = 99;
        if (mprotect((void *)shared, page, PROT_READ) != 0 || shared[0] != 41)
            _Exit(2);
        _Exit(0);
    }
    CHECK(child_status(child) == 0 && shared[0] == 41 && private_pages[0] == 7);
    shared[0] = 42; // Child mprotect did not change the parent's translation.

    CHECK(mprotect((void *)(shared + 2 * page), page, PROT_NONE) == 0);
    child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        if (mprotect((void *)(shared + 2 * page), page, PROT_READ | PROT_WRITE) != 0 ||
            shared[2 * page] != 30)
            _Exit(3);
        shared[2 * page] = 31;
        _Exit(0);
    }
    CHECK(child_status(child) == 0);
    CHECK(ok_syscall3(OK_SYS_WRITE, 1, (long)(shared + 2 * page), 1) == -EFAULT);
    CHECK(mprotect((void *)(shared + 2 * page), page, PROT_READ | PROT_WRITE) == 0 &&
          shared[2 * page] == 31);

    int go[2], answer[2];
    CHECK(pipe(go) == 0 && pipe(answer) == 0);
    child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        char byte;
        close(go[1]); close(answer[0]);
        if (read(go[0], &byte, 1) != 1 || shared[page] != 20)
            _Exit(4);
        shared[page] = 77;
        byte = shared[page];
        if (write(answer[1], &byte, 1) != 1)
            _Exit(5);
        _Exit(0);
    }
    close(go[0]); close(answer[1]);
    CHECK(munmap((void *)(shared + page), page) == 0);
    CHECK(write(go[1], "x", 1) == 1);
    char value = 0;
    CHECK(read(answer[0], &value, 1) == 1 && value == 77);
    CHECK(child_status(child) == 0);
    CHECK(close(go[1]) == 0 && close(answer[0]) == 0);
    CHECK(mmap((void *)(shared + page), page, PROT_READ | PROT_WRITE,
               MAP_SHARED | MAP_ANONYMOUS | MAP_FIXED, -1, 0) == (void *)(shared + page));
    CHECK(shared[page] == 0 && shared[0] == 42 && shared[2 * page] == 31);

    CHECK(pipe(go) == 0 && pipe(answer) == 0);
    child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        char byte;
        close(go[1]); close(answer[0]);
        if (read(go[0], &byte, 1) != 1 || shared[0] != 42)
            _Exit(6);
        shared[0] = 88;
        byte = shared[0];
        if (write(answer[1], &byte, 1) != 1)
            _Exit(7);
        _Exit(0);
    }
    close(go[0]); close(answer[1]);
    CHECK(mmap((void *)shared, page, PROT_READ | PROT_WRITE,
               MAP_SHARED | MAP_ANONYMOUS | MAP_FIXED, -1, 0) == (void *)shared);
    CHECK(shared[0] == 0 && write(go[1], "x", 1) == 1);
    CHECK(read(answer[0], &value, 1) == 1 && value == 88);
    CHECK(child_status(child) == 0 && shared[0] == 0);
    CHECK(close(go[1]) == 0 && close(answer[0]) == 0);

    shared[2 * page] = 51;
    child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        char *args[] = {"hello", 0};
        char *env[] = {0};
        execve("/bin/hello", args, env);
        _Exit(127);
    }
    CHECK(child_status(child) == 0 && shared[2 * page] == 51);
    // Pressure runs against this process's own address-space quota. A 3 MiB
    // soft RLIMIT_AS (common UAPI resource 9) lies below both the per-space
    // mapping capacity and the shared page pool, so the refusal is the quota.
    enum { pressure_pages = 64, pressure_slots = 32, rlimit_as = 9 };
    struct ok_rlimit saved_limit, quota;
    CHECK(ok_syscall4(OK_SYS_PRLIMIT64, 0, rlimit_as, 0, (long)&saved_limit) == 0);
    quota.current = 3 * 1024 * 1024;
    quota.maximum = saved_limit.maximum;
    CHECK(ok_syscall4(OK_SYS_PRLIMIT64, 0, rlimit_as, (long)&quota, 0) == 0);
    volatile unsigned char *pressure[pressure_slots];
    size_t pressure_count = 0;
    for (; pressure_count < pressure_slots; ++pressure_count)
    {
        pressure[pressure_count] = mmap(0, pressure_pages * page, PROT_READ | PROT_WRITE,
                                       MAP_SHARED | MAP_ANONYMOUS, -1, 0);
        if ((void *)pressure[pressure_count] == MAP_FAILED)
        {
            CHECK(errno == ENOMEM);
            break;
        }
        for (size_t i = 0; i < pressure_pages; ++i)
        {
            CHECK(pressure[pressure_count][i * page] == 0 &&
                  pressure[pressure_count][(i + 1) * page - 1] == 0);
            pressure[pressure_count][i * page] = (unsigned char)(pressure_count + 1);
            pressure[pressure_count][(i + 1) * page - 1] = (unsigned char)(i + 65);
        }
    }
    CHECK(pressure_count > 0 && pressure_count < pressure_slots);
    for (size_t allocation = 0; allocation < pressure_count; ++allocation)
        for (size_t i = 0; i < pressure_pages; ++i)
            CHECK(pressure[allocation][i * page] == (unsigned char)(allocation + 1) &&
                  pressure[allocation][(i + 1) * page - 1] == (unsigned char)(i + 65));
    // Restoring the saved limit reads back the quota and admits the refused size.
    struct ok_rlimit current;
    CHECK(ok_syscall4(OK_SYS_PRLIMIT64, 0, rlimit_as, (long)&saved_limit, (long)&current) == 0);
    CHECK(current.current == quota.current && current.maximum == quota.maximum);
    volatile unsigned char *admitted = mmap(0, pressure_pages * page, PROT_READ | PROT_WRITE,
                                            MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK((void *)admitted != MAP_FAILED && admitted[0] == 0);
    CHECK(munmap((void *)admitted, pressure_pages * page) == 0);
    puts("OK_VM_QUOTA scope=hardware resource=address-space refused=enomem restored=pass");
    CHECK(shared[2 * page] == 51);
    CHECK(munmap((void *)pressure[pressure_count - 1], pressure_pages * page) == 0);
    pressure[pressure_count - 1] = mmap(0, pressure_pages * page, PROT_READ | PROT_WRITE,
                                       MAP_SHARED | MAP_ANONYMOUS, -1, 0);
    CHECK((void *)pressure[pressure_count - 1] != MAP_FAILED);
    for (size_t i = 0; i < pressure_pages * page; ++i)
        CHECK(pressure[pressure_count - 1][i] == 0);
    pressure[pressure_count - 1][0] = 63;
    CHECK(pressure[pressure_count - 1][0] == 63 && shared[2 * page] == 51);
    for (size_t allocation = 0; allocation < pressure_count; ++allocation)
        CHECK(munmap((void *)pressure[allocation], pressure_pages * page) == 0);
    CHECK(munmap((void *)shared, 3 * page) == 0 && munmap((void *)private_pages, page) == 0);
    puts("OK_VM_SHARED scope=hardware fork=pass private_isolation=pass protect=pass none=pass "
         "partial_unmap=pass fixed=pass exec_exit=pass pressure=pass cleanup=pass");
    return 0;
}

// Parent and child each write a private page that fork left shared, once by a
// CPU store and once by a kernel copy, and must observe only their own values.
// This holds for eager and copy-on-write fork alike.
static int check_fork_private_copies(void)
{
    const size_t page = 4096;
    volatile unsigned char *data = mmap(0, 4 * page, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK((void *)data != MAP_FAILED);
    for (size_t i = 0; i < 4; ++i)
        data[i * page] = (unsigned char)(i + 1);
    int go[2], answer[2], local[2];
    CHECK(pipe(go) == 0 && pipe(answer) == 0 && pipe(local) == 0);
    pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        char byte;
        close(go[1]); close(answer[0]);
        if (read(go[0], &byte, 1) != 1 || data[0] != 1 || data[page] != 2)
            _Exit(1);
        if (read(go[0], (void *)(data + 2 * page), 1) != 1 || data[2 * page] != 'k')
            _Exit(2);
        data[3 * page] = 44;
        byte = (char)data[3 * page];
        if (write(answer[1], &byte, 1) != 1)
            _Exit(3);
        _Exit(0);
    }
    close(go[0]); close(answer[1]);
    data[0] = 101;
    CHECK(write(local[1], "p", 1) == 1 && read(local[0], (void *)(data + page), 1) == 1);
    CHECK(write(go[1], "x", 1) == 1 && write(go[1], "k", 1) == 1);
    char value = 0;
    CHECK(read(answer[0], &value, 1) == 1 && value == 44 && child_status(child) == 0);
    CHECK(data[0] == 101 && data[page] == 'p' && data[2 * page] == 3 && data[3 * page] == 4);
    // After the child exits the parent is the sole owner of every page again.
    data[2 * page] = 103;
    data[3 * page] = 104;
    CHECK(data[2 * page] == 103 && data[3 * page] == 104);
    CHECK(close(go[1]) == 0 && close(answer[0]) == 0 && close(local[0]) == 0 && close(local[1]) == 0);
    CHECK(munmap((void *)data, 4 * page) == 0);
    puts("OK_VM_FORK_COPY scope=hardware parent_store=pass parent_kernel_copy=pass child_kernel_copy=pass "
         "child_store=pass");
    return 0;
}

static int check_private_file_mapping(void)
{
    const size_t page = 4096;
    const char *path = "/tmp/posix-file-map";
    unsigned char source[4096];
    int file = open(path, O_CREAT | O_TRUNC | O_RDWR, 0600);
    CHECK(file >= 0);
    if (ftruncate(file, 2 * page + 37) != 0)
    {
        // RAM-root files have a one-page capacity. Keep their existing native
        // acceptance lane; ext4 qualification requires the pass marker below.
        CHECK(close(file) == 0 && unlink(path) == 0);
        puts("OK_VM_FILE_PRIVATE scope=hardware ext4=unsupported-filesystem");
        return 0;
    }
    memset(source, 0x11, sizeof(source));
    CHECK(write(file, source, sizeof(source)) == (ssize_t)sizeof(source));
    memset(source, 0x31, sizeof(source));
    CHECK(write(file, source, sizeof(source)) == (ssize_t)sizeof(source));
    memset(source, 0x72, 37);
    CHECK(write(file, source, 37) == 37);
    CHECK(fsync(file) == 0);

    CHECK(mmap(0, page, PROT_READ, MAP_PRIVATE, -1, 0) == MAP_FAILED && errno == EBADF);
    CHECK(mmap(0, page, PROT_READ, MAP_PRIVATE, file, 1) == MAP_FAILED && errno == EINVAL);
    CHECK(mmap(0, 2 * page, PROT_READ, MAP_PRIVATE, file, 2 * page) == MAP_FAILED);
    int write_only = open(path, O_WRONLY);
    CHECK(write_only >= 0);
    CHECK(mmap(0, page, PROT_READ, MAP_PRIVATE, write_only, 0) == MAP_FAILED && errno == EACCES);
    CHECK(close(write_only) == 0);

    volatile unsigned char *short_map = mmap(0, 1, PROT_READ, MAP_PRIVATE, file, page);
    CHECK((void *)short_map != MAP_FAILED);
    CHECK(short_map[0] == 0x31 && short_map[1] == 0x31 && short_map[page - 1] == 0x31);
    CHECK(munmap((void *)short_map, 1) == 0);

    volatile unsigned char *mapped = mmap(0, page + 100, PROT_READ | PROT_WRITE,
                                          MAP_PRIVATE, file, page);
    CHECK((void *)mapped != MAP_FAILED);
    CHECK(mapped[0] == 0x31 && mapped[page - 1] == 0x31);
    CHECK(mapped[page] == 0x72 && mapped[page + 36] == 0x72);
    for (size_t i = 37; i < page; ++i) CHECK(mapped[page + i] == 0);
    mapped[0] = 0x91;
    CHECK(pwrite(file, "Z", 1, page) == 1);
    unsigned char disk = 0;
    CHECK(pread(file, &disk, 1, page) == 1 && disk == 'Z');
    CHECK(mapped[0] == 0x91);
    CHECK(unlink(path) == 0 && close(file) == 0);
    CHECK(mapped[0] == 0x91 && mapped[page] == 0x72 && mapped[page + 37] == 0);

    pid_t child = fork();
    CHECK(child >= 0);
    if (child == 0)
    {
        if (mapped[0] != 0x91 || mapped[page] != 0x72) _Exit(1);
        mapped[0] = 0x52;
        mapped[page] = 0x62;
        _Exit(0);
    }
    CHECK(child_status(child) == 0);
    CHECK(mapped[0] == 0x91 && mapped[page] == 0x72);
    CHECK(munmap((void *)mapped, page + 100) == 0);
    puts("OK_VM_FILE_PRIVATE scope=hardware ext4=pass offset=pass short_length=pass tail_zero=pass errno=pass unlink=pass private_write=pass fork=pass");
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 2 && argv && (!strcmp(argv[1], "--fat-write") ||
                             !strcmp(argv[1], "--fat-read") || !strcmp(argv[1], "--fat-delete")))
        return check_fat_media(argv[1]);
    CHECK(argc == 1 && argv && strcmp(argv[0], "posix-check") == 0);
    CHECK(check_native_time() == 0);
    CHECK(check_native_poll() == 0);
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
    CHECK(check_file_names() == 0);
    CHECK(check_native_memory() == 0);
    CHECK(check_shared_anonymous_memory() == 0);
    CHECK(check_fork_private_copies() == 0);
    CHECK(check_private_file_mapping() == 0);
    CHECK(check_symbolic_links() == 0);
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

    // PID 1 adopts and reaps live orphans. Exercise more than one table's worth
    // while allowing its reaper to run, and bound failures instead of spinning.
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
            int64_t deadline = monotonic_ns() + 2000000000LL;
            while (ok_syscall0(OK_SYS_GETPPID) != 1) {
                struct timespec pause = {0, 1000000};
                if (monotonic_ns() >= deadline || nanosleep(&pause, 0) != 0)
                    _Exit(2);
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
         "orphan=pass exit_status=pass file_io=pass vector_io=pass sync=pass rename=pass hardlink=pass");
    return 0;
}

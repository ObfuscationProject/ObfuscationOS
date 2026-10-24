#define _POSIX_C_SOURCE 200809L
#include "commands.h"
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

extern int __real_open(const char *, int, ...);
extern int __real_openat(int, const char *, int, ...);
extern int __real_close(int);
extern int __real_fsync(int);
extern int __real_renameat(int, const char *, int, const char *);
extern int __real_unlinkat(int, const char *, int);
extern int __real_rename(const char *, const char *);
extern int __real_unlink(const char *);

static const char *fault;
static int trace_fd = -1, directories[16], opens;

static int selected(const char *value)
{ return fault && !strcmp(fault, value); }

static void trace(const char *name, int index)
{
    int error = errno;
    char text[64];
    int count = index ? snprintf(text, sizeof text, "%s-%d\n", name, index) :
                       snprintf(text, sizeof text, "%s\n", name);
    if (trace_fd >= 0 && count > 0 && count < (int)sizeof text)
        (void)write(trace_fd, text, (size_t)count);
    errno = error;
}

static int index_of(int fd)
{
    for (int i = opens - 1; i >= 0; --i)
        if (directories[i] == fd)
            return i + 1;
    return 0;
}

int __wrap_open(const char *path, int flags, ...)
{
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list arguments;
        va_start(arguments, flags); mode = (mode_t)va_arg(arguments, int); va_end(arguments);
    }
    if (!(flags & O_DIRECTORY))
        return __real_open(path, flags, mode);
    int index = opens + 1;
    trace("open", index);
    if (!(flags & O_CLOEXEC) || opens == 16) { errno = EINVAL; return -1; }
    if ((index == 1 && selected("open-1")) || (index == 2 && selected("open-2"))) {
        errno = EIO; return -1;
    }
    if ((index == 1 && selected("unreadable-1")) || (index == 2 && selected("unreadable-2"))) {
        errno = EACCES; return -1;
    }
    int fd = __real_open(path, flags, mode);
    if (fd >= 0) {
        directories[opens++] = fd;
        if (index == 2 && (selected("source-parent-moved") || selected("destination-parent-moved"))) {
            const char *old = getenv("FILES_MOVE_PARENT"), *moved = getenv("FILES_MOVE_TO");
            const char *decoy = getenv("FILES_DECOY");
            if (!old || !moved || !decoy || __real_renameat(AT_FDCWD, old, AT_FDCWD, moved) < 0 ||
                mkdir(old, 0700) < 0)
                exit(90);
            int competitor = __real_open(decoy, O_CREAT | O_EXCL | O_WRONLY, 0600);
            if (competitor < 0 || write(competitor, "decoy\n", 6) != 6 || __real_close(competitor) < 0)
                exit(91);
            trace("parent-moved", 0);
        }
    }
    return fd;
}

int __wrap_renameat(int fromfd, const char *from, int tofd, const char *to)
{
    int fallback = tofd == AT_FDCWD && selected("unreadable-2");
    trace(fallback ? "rename-unreadable-destination" : "rename", 0);
    if (!index_of(fromfd) || (!index_of(tofd) && !fallback)) { errno = EINVAL; return -1; }
    if (selected("rename")) { errno = EIO; return -1; }
    if (selected("cross-device")) { errno = EXDEV; return -1; }
    return __real_renameat(fromfd, from, tofd, to);
}

int __wrap_unlinkat(int directory, const char *path, int flags)
{
    trace("unlink", 0);
    if (!index_of(directory) || flags) { errno = EINVAL; return -1; }
    if (selected("unlink")) { errno = EIO; return -1; }
    if (selected("unlink-unsupported")) { errno = ENOSYS; return -1; }
    return __real_unlinkat(directory, path, flags);
}

int __wrap_rename(const char *from, const char *to)
{
    trace("rename-unreadable-source", 0);
    if (!selected("unreadable-1")) { errno = EINVAL; return -1; }
    return __real_rename(from, to);
}

int __wrap_unlink(const char *path)
{
    trace("unlink-unreadable-parent", 0);
    if (!selected("unreadable-1")) { errno = EINVAL; return -1; }
    return __real_unlink(path);
}

int __wrap_fsync(int fd)
{
    int index = index_of(fd);
    trace("sync", index);
    if (!index) { errno = EINVAL; return -1; }
    if ((index == 1 && (selected("sync-1") || selected("sync-and-close"))) ||
        (index == 2 && selected("sync-2"))) { errno = EIO; return -1; }
    return __real_fsync(fd);
}

int __wrap_close(int fd)
{
    int index = index_of(fd);
    trace("close", index);
    int result = __real_close(fd);
    if (index) directories[index - 1] = -1;
    if (selected("sync-and-close")) { errno = ENOSPC; return -1; }
    if ((index == 1 && selected("close-1")) || (index == 2 && selected("close-2"))) {
        errno = EIO; return -1;
    }
    return result;
}

/* ASan retains the unrelated command table. Raw project syscalls are never
   admitted by this host fixture; fail if an unrelated command reaches them. */
long ok_syscall1(long number, long argument)
{
    (void)number; (void)argument;
    _Exit(98);
}

long ok_syscall_ret(long value)
{
    (void)value;
    _Exit(99);
}

int main(int argc, char **argv)
{
    fault = getenv("FILES_FAULT");
    const char *path = getenv("FILES_TRACE");
    if (path) trace_fd = __real_open(path, O_CREAT | O_EXCL | O_WRONLY, 0600);
    if (argc < 2) return 2;
    if (!strcmp(argv[1], "mv")) return cmd_mv(argc - 1, argv + 1);
    if (!strcmp(argv[1], "rm")) return cmd_rm(argc - 1, argv + 1);
    return 2;
}

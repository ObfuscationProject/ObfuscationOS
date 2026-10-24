#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

extern int notes_main(int argc, char **argv);
extern int __real_openat(int, const char *, int, ...);
extern ssize_t __real_write(int, const void *, size_t);

static int stage_fd = -1, trace_fd = -1;
static const char *fault;
static unsigned int attempts;
static int partial_second;

static int is_fault(const char *name)
{
    return fault && !strcmp(fault, name);
}

int __wrap_openat(int directory, const char *name, int flags, ...)
{
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode = (mode_t)va_arg(args, int);
        va_end(args);
    }
    int result = __real_openat(directory, name, flags, mode);
    if (result >= 0 && (flags & O_CREAT) && (flags & O_EXCL))
        stage_fd = result;
    return result;
}

ssize_t __wrap_write(int fd, const void *bytes, size_t size)
{
    if (fd != stage_fd)
        return __real_write(fd, bytes, size);
    off_t offset = lseek(fd, 0, SEEK_CUR);
    if (offset < 0)
        exit(91);
    ++attempts;
    ssize_t result;
    if (size > 1024 || size > 1024 - (size_t)(offset % 1024)) {
        errno = EOPNOTSUPP;
        result = -1;
    } else if (is_fault("short-eintr") && (attempts == 1 || attempts == 17)) {
        errno = EINTR;
        result = -1;
    } else if (is_fault("second-error") && offset >= 1024) {
        errno = ENOSPC;
        result = -1;
    } else if (is_fault("second-zero") && offset >= 1024) {
        result = 0;
    } else if (is_fault("oversized") && offset >= 964 && offset < 1024) {
        result = (ssize_t)(size + 1);
    } else if (is_fault("partial-error") && offset >= 1024 && partial_second) {
        errno = ENOSPC;
        result = -1;
    } else {
        size_t returned = size;
        if (is_fault("short-eintr") && returned > 7)
            returned = 7;
        if (is_fault("partial-error") && offset >= 1024) {
            partial_second = 1;
            if (returned > 3)
                returned = 3;
        }
        result = __real_write(fd, bytes, returned);
    }
    int saved_error = errno;
    char line[128];
    int length = snprintf(line, sizeof(line), "offset=%lld requested=%zu returned=%lld error=%d\n",
                          (long long)offset, size, (long long)result, result < 0 ? saved_error : 0);
    if (length < 0 || (size_t)length >= sizeof(line) ||
        __real_write(trace_fd, line, (size_t)length) != length)
        exit(92);
    errno = saved_error;
    return result;
}

int main(int argc, char **argv)
{
    const char *trace = getenv("NOTES_BOUNDARY_TRACE");
    fault = getenv("NOTES_BOUNDARY_FAULT");
    if (!trace || (trace_fd = open(trace, O_CREAT | O_EXCL | O_WRONLY, 0600)) < 0)
        return 93;
    return notes_main(argc, argv);
}

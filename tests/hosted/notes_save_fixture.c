#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

extern int notes_main(int argc, char **argv);
extern int __real_open(const char *, int, ...);
extern int __real_openat(int, const char *, int, ...);
extern int __real_close(int);
extern int __real_fstat(int, struct stat *);
extern int __real_fstatat(int, const char *, struct stat *, int);
extern int __real_fsync(int);
extern int __real_renameat(int, const char *, int, const char *);
extern int __real_unlinkat(int, const char *, int);
extern ssize_t __real_write(int, const void *, size_t);
extern ssize_t __real_read(int, void *, size_t);

static const char *fault;
static int trace_fd = -1, dir_fd = -1, stage_fd = -1;
static unsigned int stage_writes, stats_at, input_reads, output_writes;
static int parent_moved;
static const char rival_bytes[] = "Intruder English note.\n";

static int is_fault(const char *name)
{
    return fault && !strcmp(fault, name);
}

static void trace(const char *event)
{
    int error = errno;
    if (trace_fd >= 0) {
        __real_write(trace_fd, event, strlen(event));
        __real_write(trace_fd, "\n", 1);
    }
    errno = error;
}

int __wrap_open(const char *path, int flags, ...)
{
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode = (mode_t)va_arg(args, int);
        va_end(args);
    }
    if (flags & O_DIRECTORY) {
        trace("parent-open");
        if (is_fault("parent-open")) { errno = EACCES; return -1; }
    }
    int fd = __real_open(path, flags, mode);
    if (fd >= 0 && (flags & O_DIRECTORY))
        dir_fd = fd;
    return fd;
}

int __wrap_openat(int directory, const char *path, int flags, ...)
{
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list args;
        va_start(args, flags);
        mode = (mode_t)va_arg(args, int);
        va_end(args);
    }
    trace("stage-open");
    if (directory != dir_fd || !(flags & O_EXCL) || !(flags & O_NOFOLLOW) || !(flags & O_CLOEXEC)) {
        errno = EINVAL;
        return -1;
    }
    if (is_fault("stage-open")) { errno = EACCES; return -1; }
    if (is_fault("all-collisions")) { errno = EEXIST; return -1; }
    if (is_fault("first-collision") && strstr(path, "-0.tmp")) {
        int collision = __real_openat(directory, path, O_CREAT | O_EXCL | O_WRONLY, 0600);
        if (collision < 0 || __real_write(collision, "sentinel\n", 9) != 9 || __real_close(collision) < 0)
            exit(94);
        trace("collision-created");
    }
    stage_fd = __real_openat(directory, path, flags, mode);
    if (stage_fd >= 0 && is_fault("parent-renamed") && !parent_moved) {
        const char *parent = getenv("NOTES_MOVE_PARENT");
        const char *moved = getenv("NOTES_MOVE_TO");
        if (!parent || !moved || __real_renameat(AT_FDCWD, parent, AT_FDCWD, moved) < 0)
            exit(91);
        parent_moved = 1;
        trace("parent-renamed");
    }
    return stage_fd;
}

int __wrap_fstat(int fd, struct stat *value)
{
    const char *event = fd == dir_fd ? "parent-stat" : "stage-stat";
    trace(event);
    if (is_fault(event)) { errno = EIO; return -1; }
    int result = __real_fstat(fd, value);
    if (result == 0 && fd == stage_fd && is_fault("stage-metadata"))
        value->st_mode ^= S_IRGRP;
    return result;
}

int __wrap_fstatat(int directory, const char *path, struct stat *value, int flags)
{
    ++stats_at;
    const char *event = stats_at == 1 ? "destination-stat" : "destination-recheck";
    trace(event);
    if (directory != dir_fd || flags != AT_SYMLINK_NOFOLLOW) { errno = EINVAL; return -1; }
    if (is_fault(event)) { errno = EIO; return -1; }
    if (stats_at == 2 && is_fault("destination-disappeared")) {
        if (__real_unlinkat(directory, path, 0) < 0)
            exit(92);
    }
    if (stats_at == 2 && is_fault("destination-created")) {
        int created = __real_openat(directory, path, O_CREAT | O_EXCL | O_WRONLY, 0600);
        if (created < 0 || __real_write(created, "competing\n", 10) != 10 || __real_close(created) < 0)
            exit(93);
    }
    if (stats_at == 2 && is_fault("destination-identity")) {
        struct stat original, rival;
        const char rival_name[] = ".notes-rival";
        if (__real_fstatat(directory, path, &original, flags) < 0)
            exit(95);
        int replacement = __real_openat(directory, rival_name, O_CREAT | O_EXCL | O_WRONLY,
                                        original.st_mode & 07777);
        if (replacement < 0 ||
            __real_write(replacement, rival_bytes, sizeof(rival_bytes) - 1) !=
                (ssize_t)(sizeof(rival_bytes) - 1) ||
            fchmod(replacement, original.st_mode & 07777) < 0 ||
            __real_fstat(replacement, &rival) < 0 ||
            rival.st_ino == original.st_ino || rival.st_mode != original.st_mode ||
            rival.st_size != original.st_size || rival.st_uid != original.st_uid ||
            rival.st_gid != original.st_gid || rival.st_nlink != original.st_nlink ||
            __real_close(replacement) < 0 ||
            __real_renameat(directory, rival_name, directory, path) < 0)
            exit(95);
        trace("identity-substituted");
    }
    int result = __real_fstatat(directory, path, value, flags);
    if (result == 0 && stats_at == 2 && is_fault("destination-metadata"))
        value->st_mode ^= S_IRGRP;
    return result;
}

ssize_t __wrap_write(int fd, const void *bytes, size_t size)
{
    if (fd == stage_fd) {
        ++stage_writes;
        trace("stage-write");
        if (is_fault("write")) { errno = ENOSPC; return -1; }
        if (is_fault("write-cleanup")) { errno = ENOSPC; return -1; }
        if (is_fault("write-zero"))
            return 0;
        if (is_fault("short-eintr") && stage_writes == 1) { errno = EINTR; return -1; }
        if (is_fault("short-eintr") && size > 2)
            size = 2;
    } else if (fd == STDOUT_FILENO && is_fault("read-short-eintr")) {
        ++output_writes;
        if (output_writes == 1) { errno = EINTR; return -1; }
        if (size > 3)
            size = 3;
    }
    return __real_write(fd, bytes, size);
}

ssize_t __wrap_read(int fd, void *bytes, size_t size)
{
    if (is_fault("read-short-eintr")) {
        ++input_reads;
        if (input_reads == 1) { errno = EINTR; return -1; }
        if (size > 7)
            size = 7;
    }
    if (is_fault("read")) { errno = EIO; return -1; }
    return __real_read(fd, bytes, size);
}

int __wrap_fsync(int fd)
{
    const char *event = fd == dir_fd ? "parent-fsync" : "stage-fsync";
    trace(event);
    if (is_fault(event)) { errno = EIO; return -1; }
    return __real_fsync(fd);
}

int __wrap_close(int fd)
{
    const char *event = fd == dir_fd ? "parent-close" : "stage-close";
    trace(event);
    int result = __real_close(fd);
    if (is_fault(event)) { errno = EIO; return -1; }
    return result;
}

int __wrap_renameat(int olddir, const char *oldpath, int newdir, const char *newpath)
{
    trace("rename");
    if (olddir != dir_fd || newdir != dir_fd) { errno = EINVAL; return -1; }
    if (is_fault("rename")) { errno = EIO; return -1; }
    return __real_renameat(olddir, oldpath, newdir, newpath);
}

int __wrap_unlinkat(int directory, const char *path, int flags)
{
    trace("cleanup");
    if (directory != dir_fd || flags) { errno = EINVAL; return -1; }
    if (is_fault("write-cleanup")) { errno = EACCES; return -1; }
    return __real_unlinkat(directory, path, flags);
}

int main(int argc, char **argv)
{
    fault = getenv("NOTES_FAULT");
    const char *mask = getenv("NOTES_TEST_UMASK");
    if (mask)
        umask((mode_t)strtoul(mask, NULL, 8));
    const char *trace_path = getenv("NOTES_TRACE");
    if (trace_path)
        trace_fd = __real_open(trace_path, O_CREAT | O_EXCL | O_WRONLY, 0600);
    return notes_main(argc, argv);
}

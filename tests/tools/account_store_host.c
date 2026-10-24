/* Host namespace/error-injection harness. Ownership and persistent sync are
 * explicit substitutes; these tests establish no native disk durability. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static char root_path[1024], trace[32768], owner_target[128];
static unsigned events, failure, reads, writes, read_limit, write_limit;
static int failure_errno, unsupported, owner_bad, rename_uncertain, zero_write;

void account_test_root(const char *path)
{
    snprintf(root_path, sizeof(root_path), "%s", path);
    trace[0] = owner_target[0] = 0;
    events = failure = reads = writes = read_limit = write_limit = 0;
    failure_errno = EIO; unsupported = owner_bad = rename_uncertain = zero_write = 0;
}

void account_test_fault(unsigned index, int error)
{
    trace[0] = 0; events = 0; failure = index; failure_errno = error;
}

void account_test_options(unsigned rlimit, unsigned wlimit, int no_sync, int wrong_owner,
                          int rename_error_after_effect, int write_zero)
{
    read_limit = rlimit; write_limit = wlimit; unsupported = no_sync; owner_bad = wrong_owner;
    rename_uncertain = rename_error_after_effect; zero_write = write_zero;
}

const char *account_test_trace(void) { return trace; }

/* Limit substituted bad ownership to one role while keeping the canonical
 * database valid, so the real staging checks are exercised independently. */
void account_test_owner_target(const char *name)
{
    snprintf(owner_target, sizeof(owner_target), "%s", name);
    owner_bad = 1;
}

static void descriptor_name(int fd, char *result, size_t capacity)
{
    char proc[64], path[2048];
    snprintf(proc, sizeof(proc), "/proc/self/fd/%d", fd);
    ssize_t size = readlink(proc, path, sizeof(path) - 1);
    if (size < 0) { snprintf(result, capacity, "invalid"); return; }
    path[size] = 0;
    const char *name = strrchr(path, '/');
    const char *source = name ? name + 1 : path;
    size_t used = strlen(source);
    if (used >= capacity) used = capacity - 1;
    memcpy(result, source, used);
    result[used] = 0;
}

static int event(const char *operation, const char *name)
{
    size_t used = strlen(trace);
    if (used < sizeof(trace)) snprintf(trace + used, sizeof(trace) - used, "%s:%s\n", operation, name);
    if (++events != failure) return 0;
    errno = failure_errno;
    return -1;
}

static int fd_event(const char *operation, int fd)
{
    char name[1024];
    descriptor_name(fd, name, sizeof(name));
    return event(operation, name);
}

int account_test_open(const char *path, int flags, ...)
{
    if (strcmp(path, "/")) { errno = EACCES; return -1; }
    if (event("open", "root") < 0) return -1;
    return open(root_path, flags);
}

int account_test_openat(int directory, const char *path, int flags, ...)
{
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list ap; va_start(ap, flags); mode = (mode_t)va_arg(ap, int); va_end(ap);
    }
    if (event("openat", path) < 0) return -1;
    return openat(directory, path, flags, mode);
}

static void model_ownership(struct stat *info, const char *name)
{
    if (info->st_uid == getuid()) info->st_uid = 0;
    if (info->st_gid == getgid()) info->st_gid = 0;
    if (owner_bad && S_ISREG(info->st_mode) &&
        (!owner_target[0] || !strcmp(owner_target, name))) info->st_uid = 1000;
}

int account_test_fstat(int fd, struct stat *info)
{
    char name[1024];
    if (fd_event("fstat", fd) < 0 || fstat(fd, info) < 0) return -1;
    descriptor_name(fd, name, sizeof(name));
    model_ownership(info, name);
    return 0;
}

int account_test_fstatat(int fd, const char *path, struct stat *info, int flags)
{
    if (event("fstatat", path) < 0 || fstatat(fd, path, info, flags) < 0) return -1;
    model_ownership(info, path);
    return 0;
}

ssize_t account_test_read(int fd, void *data, size_t size)
{
    ++reads;
    if (fd_event("read", fd) < 0) return -1;
    if (read_limit && size > read_limit) size = read_limit;
    return read(fd, data, size);
}

ssize_t account_test_write(int fd, const void *data, size_t size)
{
    ++writes;
    if (fd_event("write", fd) < 0) return -1;
    if (zero_write) return 0;
    if (write_limit && size > write_limit) size = write_limit;
    return write(fd, data, size);
}

int account_test_close(int fd)
{
    int failed = fd_event("close", fd), saved = errno;
    int result = close(fd);
    if (failed < 0) { errno = saved; return -1; }
    return result;
}

int account_test_renameat(int oldfd, const char *old, int newfd, const char *name)
{
    if (event("rename", name) < 0) return -1;
    int result = renameat(oldfd, old, newfd, name);
    if (!result && rename_uncertain) { errno = EIO; return -1; }
    return result;
}

int ok_sync_persistent(int fd)
{
    if (fd_event("sync", fd) < 0) return -1;
    if (unsupported) { errno = EOPNOTSUPP; return -1; }
    return fsync(fd);
}

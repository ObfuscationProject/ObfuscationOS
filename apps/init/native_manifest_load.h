#ifndef OK_NATIVE_MANIFEST_LOAD_H
#define OK_NATIVE_MANIFEST_LOAD_H

#include "service_manifest.h"
#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

enum { NS_CONFIG_PRESENT = 0, NS_CONFIG_MISSING = 1 };

/* Native stat exposes no st_dev and currently has no meaningful timestamps. */
static inline int ns_same_file(const struct stat *before, const struct stat *after)
{
    return before->st_ino == after->st_ino && before->st_mode == after->st_mode &&
        before->st_uid == after->st_uid && before->st_gid == after->st_gid &&
        before->st_nlink == after->st_nlink && before->st_size == after->st_size;
}

static inline int ns_manifest_load(struct service_manifest *manifest)
{
    if (!manifest) { errno = EINVAL; return -1; }
    int directory = open("/etc", O_RDONLY | O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
    if (directory < 0) return -1;
    int descriptor = -1, outcome = -1, error = 0;
    struct stat before, after;
    if (fstat(directory, &before) < 0) { error = errno; goto done; }
    if (!S_ISDIR(before.st_mode) || before.st_uid != 0 || (before.st_mode & 0022)) {
        error = EACCES; goto done;
    }
    descriptor = openat(directory, "services.conf", O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
    if (descriptor < 0) {
        error = errno;
        if (error == ENOENT) { outcome = NS_CONFIG_MISSING; error = 0; }
        goto done;
    }
    if (fstat(descriptor, &before) < 0) { error = errno; goto done; }
    if (!S_ISREG(before.st_mode) || before.st_uid != 0 || (before.st_mode & 0022)) {
        error = EACCES; goto done;
    }
    if (before.st_size < 0 || (uint64_t)before.st_size > SM_BYTE_LIMIT) { error = EFBIG; goto done; }
    char bytes[SM_BYTE_LIMIT + 1];
    size_t size = 0;
    for (;;) {
        ssize_t count = read(descriptor, bytes + size, sizeof(bytes) - size);
        if (count < 0) { if (errno == EINTR) continue; error = errno; goto done; }
        if (!count) break;
        size += (size_t)count;
        if (size > SM_BYTE_LIMIT) { error = EFBIG; goto done; }
    }
    if (fstat(descriptor, &after) < 0) { error = errno; goto done; }
    if (!ns_same_file(&before, &after) || size != (size_t)before.st_size) { error = EIO; goto done; }
    struct service_manifest prepared;
    if (sm_parse(&prepared, bytes, size)) { error = EINVAL; goto done; }
    if (close(descriptor) < 0) { descriptor = -1; error = errno; goto done; }
    descriptor = -1;
    if (close(directory) < 0) { directory = -1; error = errno; goto done; }
    directory = -1;
    *manifest = prepared;
    return NS_CONFIG_PRESENT;
done:
    if (descriptor >= 0 && close(descriptor) < 0 && !error) { error = errno; outcome = -1; }
    if (directory >= 0 && close(directory) < 0 && !error) { error = errno; outcome = -1; }
    if (error) { errno = error; return -1; }
    return outcome;
}

#endif

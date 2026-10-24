#ifndef OK_SERVICE_GENERATION_FIXTURE_H
#define OK_SERVICE_GENERATION_FIXTURE_H

#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>

/* This privileged test channel is a preinstalled, fixed-size marker. It does
 * not create or truncate a file and does not qualify storage durability. */
static int generation_valid(const struct stat *value)
{
    return S_ISREG(value->st_mode) && (value->st_mode & 07777) == 0600 &&
        value->st_uid == 0 && value->st_gid == 0 && value->st_size == 1 &&
        value->st_nlink == 1 && value->st_ino != 0 && value->st_dev != 0;
}

static int generation_same(const struct stat *before, const struct stat *after)
{
    /* Concurrent legitimate writes can advance timestamps. Identity, security
     * attributes and geometry must remain fixed on the pinned descriptor. */
    return generation_valid(after) && before->st_dev == after->st_dev &&
        before->st_ino == after->st_ino && before->st_mode == after->st_mode &&
        before->st_uid == after->st_uid && before->st_gid == after->st_gid &&
        before->st_size == after->st_size && before->st_nlink == after->st_nlink;
}

static int generation_finish(int fd, int error)
{
    /* Consume the fd after one close attempt; an EINTR close is not retried. */
    if (close(fd) < 0 && !error) error = errno;
    if (error) { errno = error; return -1; }
    return 0;
}

static int generation_transfer(char *value, int writing)
{
    if (!value || (writing && *value != '0' && *value != '1' && *value != '2'))
    { errno = EINVAL; return -1; }
    int fd = open("/service-generation", (writing ? O_WRONLY : O_RDONLY) |
        O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
    if (fd < 0) return -1;
    struct stat before, after;
    int error = 0;
    if (fstat(fd, &before) < 0) error = errno;
    else if (!generation_valid(&before)) error = EPERM;
    char bytes[2] = {0, 0};
    ssize_t size = -1;
    if (!error) {
        for (unsigned tries = 0; tries < 8; ++tries) {
            size = writing ? write(fd, value, 1) : read(fd, bytes, sizeof(bytes));
            if (size >= 0) break;
            error = errno;
            if (error != EINTR) break;
            if (tries != 7) error = 0;
        }
        if (!error && size != 1) error = EIO;
        if (!error && !writing && bytes[0] != '0' && bytes[0] != '1' && bytes[0] != '2')
            error = EIO;
    }
    if (!error) {
        if (fstat(fd, &after) < 0) error = errno;
        else if (!generation_same(&before, &after)) error = EIO;
    }
    if (generation_finish(fd, error)) return -1;
    if (!writing) *value = bytes[0];
    return 0;
}

static int generation_write(char value) { return generation_transfer(&value, 1); }
static int generation_read(char *value) { return generation_transfer(value, 0); }

/* The restart protocol permits only the immediately preceding generation. */
static int generation_progress(char value, char expected)
{
    if (expected != '1' && expected != '2') { errno = EINVAL; return -1; }
    if (value == expected) return 1;
    if (value == expected - 1) return 0;
    errno = EPROTO;
    return -1;
}

#endif

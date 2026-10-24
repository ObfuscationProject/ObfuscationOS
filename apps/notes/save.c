#define _POSIX_C_SOURCE 200809L
#include "save.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#define NOTES_PATH_CAPACITY 256
#define NOTES_TEMP_ATTEMPTS 32

int notes_write_all(int fd, const char *bytes, size_t size)
{
    while (size) {
        ssize_t written = write(fd, bytes, size);
        if (written < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        if (written == 0 || (size_t)written > size) {
            errno = EIO;
            return -1;
        }
        bytes += written;
        size -= (size_t)written;
    }
    return 0;
}

/* The qualified staged-file provider accepts one 1 KiB block per write. */
#define NOTES_STAGING_CHUNK 1024

struct notes_staged_writer {
    int fd;
    size_t block_offset;
};

static int notes_staged_write_all(struct notes_staged_writer *writer,
                                  const char *bytes, size_t size)
{
    while (size) {
        size_t capacity = NOTES_STAGING_CHUNK - writer->block_offset;
        size_t requested = size < capacity ? size : capacity;
        ssize_t written = write(writer->fd, bytes, requested);
        if (written < 0) {
            if (errno == EINTR)
                continue;
            return -1;
        }
        if (written == 0 || (size_t)written > requested) {
            errno = EIO;
            return -1;
        }
        writer->block_offset = (writer->block_offset + (size_t)written) % NOTES_STAGING_CHUNK;
        bytes += written;
        size -= (size_t)written;
    }
    return 0;
}

static char *append_number(char *out, unsigned long number)
{
    char digits[3 * sizeof(number)];
    size_t count = 0;
    do {
        digits[count++] = (char)('0' + number % 10);
        number /= 10;
    } while (number);
    while (count)
        *out++ = digits[--count];
    return out;
}

static void temporary_name(char name[64], unsigned long pid, unsigned int attempt)
{
    char *out = name;
    memcpy(out, ".notes-", 7);
    out += 7;
    out = append_number(out, pid);
    *out++ = '-';
    out = append_number(out, attempt);
    memcpy(out, ".tmp", 5);
}

static int ordinary_destination(const struct stat *st, uid_t uid, gid_t gid)
{
    if (!S_ISREG(st->st_mode)) {
        errno = S_ISDIR(st->st_mode) ? EISDIR : EINVAL;
        return -1;
    }
    if (st->st_nlink != 1 || st->st_uid != uid || st->st_gid != gid ||
        (st->st_mode & 07000) || !(st->st_mode & S_IWUSR)) {
        errno = EACCES;
        return -1;
    }
    return 0;
}

static int same_metadata(const struct stat *before, const struct stat *now)
{
    /* Native stat-v2 exposes inode identity; this precheck remains advisory. */
    return before->st_ino == now->st_ino &&
           before->st_mode == now->st_mode && before->st_size == now->st_size &&
           before->st_uid == now->st_uid && before->st_gid == now->st_gid &&
           before->st_nlink == now->st_nlink;
}

enum notes_save_result notes_save_words(const char *path, int count, char *const words[])
{
    char parent[NOTES_PATH_CAPACITY];
    char temporary[64];
    struct stat before, staging, now;
    const char *leaf;
    size_t length, parent_length;
    int dirfd = -1, fd = -1, created = 0, existed = 0, replaced = 0;
    int error;
    mode_t mode = 0600;
    uid_t uid = geteuid();
    gid_t gid = getegid();

    if (!path || !words || count < 1) {
        errno = EINVAL;
        return NOTES_SAVE_FAILED;
    }
    length = strlen(path);
    if (!length || length >= NOTES_PATH_CAPACITY) {
        errno = length ? ENAMETOOLONG : EINVAL;
        return NOTES_SAVE_FAILED;
    }
    leaf = strrchr(path, '/');
    if (!leaf) {
        parent[0] = '.';
        parent[1] = 0;
        leaf = path;
    } else {
        parent_length = (size_t)(leaf - path);
        if (!parent_length)
            parent_length = 1;
        memcpy(parent, path, parent_length);
        parent[parent_length] = 0;
        ++leaf;
    }
    if (!*leaf || !strcmp(leaf, ".") || !strcmp(leaf, "..")) {
        errno = EINVAL;
        return NOTES_SAVE_FAILED;
    }
    dirfd = open(parent, O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (dirfd < 0)
        return NOTES_SAVE_FAILED;
    if (fstat(dirfd, &staging) < 0)
        goto fail;
    if (!S_ISDIR(staging.st_mode) || staging.st_uid != uid ||
        !(staging.st_mode & S_IWUSR) || (staging.st_mode & 0022)) {
        errno = EACCES;
        goto fail;
    }
    if (fstatat(dirfd, leaf, &before, AT_SYMLINK_NOFOLLOW) == 0) {
        existed = 1;
        if (ordinary_destination(&before, uid, gid) < 0)
            goto fail;
        mode = before.st_mode & 0777;
    } else if (errno != ENOENT) {
        goto fail;
    }
    for (unsigned int attempt = 0; attempt < NOTES_TEMP_ATTEMPTS; ++attempt) {
        temporary_name(temporary, (unsigned long)getpid(), attempt);
        if (!strcmp(temporary, leaf))
            continue;
        fd = openat(dirfd, temporary, O_CREAT | O_EXCL | O_WRONLY | O_CLOEXEC | O_NOFOLLOW, mode);
        if (fd >= 0) {
            created = 1;
            break;
        }
        if (errno != EEXIST)
            goto fail;
    }
    if (fd < 0) {
        errno = EEXIST;
        goto fail;
    }
    if (fstat(fd, &staging) < 0)
        goto fail;
    if (!S_ISREG(staging.st_mode) || staging.st_nlink != 1 ||
        staging.st_uid != uid || staging.st_gid != gid || (staging.st_mode & 07777) != mode) {
        errno = EACCES;
        goto fail;
    }
    struct notes_staged_writer writer = { fd, 0 };
    for (int i = 0; i < count; ++i) {
        if (!words[i]) {
            errno = EINVAL;
            goto fail;
        }
        if ((i && notes_staged_write_all(&writer, " ", 1) < 0) ||
            notes_staged_write_all(&writer, words[i], strlen(words[i])) < 0)
            goto fail;
    }
    if (notes_staged_write_all(&writer, "\n", 1) < 0 || fsync(fd) < 0)
        goto fail;
    {
        int closed = close(fd);
        fd = -1;
        if (closed < 0)
            goto fail;
    }
    if (fstatat(dirfd, leaf, &now, AT_SYMLINK_NOFOLLOW) == 0) {
        if (!existed || !same_metadata(&before, &now)) {
            errno = EAGAIN;
            goto fail;
        }
    } else if (errno != ENOENT || existed) {
        if (errno == ENOENT)
            errno = EAGAIN;
        goto fail;
    }
    if (renameat(dirfd, temporary, dirfd, leaf) < 0)
        goto fail;
    created = 0;
    replaced = 1;
    if (fsync(dirfd) < 0)
        goto fail;
    {
        int closed = close(dirfd);
        dirfd = -1;
        if (closed < 0)
            goto fail;
    }
    return NOTES_SAVE_DONE;

fail:
    error = errno;
    if (fd >= 0)
        (void)close(fd);
    if (created)
        (void)unlinkat(dirfd, temporary, 0);
    if (dirfd >= 0)
        (void)close(dirfd);
    errno = error;
    return replaced ? NOTES_SAVE_REPLACED_ERROR : NOTES_SAVE_FAILED;
}

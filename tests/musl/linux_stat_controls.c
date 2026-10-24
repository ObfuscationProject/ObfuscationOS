#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <unistd.h>
#include "../stat_fixture.h"
#include "../stat_probe_log.h"

static unsigned checks;
static int64_t epoch;

static void failure(unsigned line)
{
    unsigned error = (unsigned)errno;
    stat_probe_text("LINUX_STAT_CONTROLS_MUSL_FAIL line="); stat_probe_unsigned(line);
    stat_probe_text(" errno="); stat_probe_unsigned(error);
    stat_probe_text(" checks="); stat_probe_unsigned(checks); stat_probe_text("\n");
    exit(1);
}
#define CHECK(x) do { ++checks; if (!(x)) failure(__LINE__); } while (0)

static int filled(const void *data, size_t size, unsigned char value)
{
    const unsigned char *bytes = data;
    for (size_t i = 0; i < size; ++i) if (bytes[i] != value) return 0;
    return 1;
}

static long raw(int fd, const char *path, unsigned flags, unsigned mask, void *out)
{
    return syscall(SYS_statx, (long)fd, (long)path, (long)flags, (long)mask, (long)out);
}

static struct statx query(int fd, const char *path, unsigned flags, unsigned mask)
{
    struct { unsigned char before[32]; struct statx value; unsigned char after[32]; } out;
    memset(&out, 0xa5, sizeof out);
    CHECK(raw(fd, path, flags, mask, &out.value) == 0);
    CHECK(filled(out.before, sizeof out.before, 0xa5) && filled(out.after, sizeof out.after, 0xa5));
    const struct statx *s = &out.value;
    CHECK(s->stx_mask == STAT_BASIC_MASK && s->stx_ino != 0 &&
          (s->stx_dev_major != 0 || s->stx_dev_minor != 0));
    CHECK(s->stx_uid == 1000 && s->stx_gid == 1000);
    CHECK(s->stx_blksize == 4096 && s->stx_blocks % 8 == 0);
    const struct statx_timestamp *times[] = {&s->stx_atime, &s->stx_mtime, &s->stx_ctime};
    for (unsigned i = 0; i < 3; ++i)
        CHECK(times[i]->tv_sec == epoch && times[i]->tv_nsec == 123456789U && times[i]->__pad == 0);
    CHECK(s->stx_attributes == 0 && s->stx_attributes_mask == 0 &&
          s->stx_rdev_major == 0 && s->stx_rdev_minor == 0);
    CHECK(filled(&s->stx_btime, sizeof s->stx_btime, 0) &&
          filled((const unsigned char *)s + 30, 2, 0) &&
          filled((const unsigned char *)s + 144, 112, 0));
    return out.value;
}

static void equal(const struct stat *s, const struct statx *x)
{
    CHECK((uint64_t)s->st_ino == x->stx_ino && (uint32_t)s->st_mode == x->stx_mode);
    CHECK((uint64_t)s->st_nlink == x->stx_nlink && s->st_uid == x->stx_uid && s->st_gid == x->stx_gid);
    CHECK((uint64_t)s->st_size == x->stx_size && (uint64_t)s->st_blocks == x->stx_blocks);
    CHECK((uint64_t)s->st_blksize == x->stx_blksize && s->st_rdev == 0);
    CHECK(major(s->st_dev) == x->stx_dev_major && minor(s->st_dev) == x->stx_dev_minor);
    CHECK(s->st_atim.tv_sec == x->stx_atime.tv_sec && (int64_t)s->st_atim.tv_nsec == (int64_t)x->stx_atime.tv_nsec);
    CHECK(s->st_mtim.tv_sec == x->stx_mtime.tv_sec && (int64_t)s->st_mtim.tv_nsec == (int64_t)x->stx_mtime.tv_nsec);
    CHECK(s->st_ctim.tv_sec == x->stx_ctime.tv_sec && (int64_t)s->st_ctim.tv_nsec == (int64_t)x->stx_ctime.tv_nsec);
}

static const char *const labels[] = {"file", "alias", "link", "dangling", "loop", "empty", "hole", "directory", "child"};
static const char *const paths[] = {STAT_FILE, STAT_ALIAS, STAT_LINK, STAT_DANGLING, STAT_LOOP,
                                  STAT_EMPTY, STAT_HOLE, STAT_DIR, STAT_DIR "/child"};

static void readonly_checks(void)
{
    struct stat s;
    struct statx file = query(AT_FDCWD, STAT_FILE, 0, STAT_BASIC_MASK);
    CHECK(file.stx_size == STAT_CONTENT_SIZE && file.stx_nlink == 2 && file.stx_blocks == 8);
    CHECK(stat(STAT_FILE, &s) == 0); equal(&s, &file);
    CHECK(lstat(STAT_FILE, &s) == 0); equal(&s, &file);
    CHECK(stat(STAT_ALIAS, &s) == 0); equal(&s, &file);
    CHECK(stat(STAT_LINK, &s) == 0); equal(&s, &file);
    CHECK(fstatat(-1, STAT_FILE, &s, 0) == 0); equal(&s, &file);
    int fd = open(STAT_FILE, O_RDONLY);
    CHECK(fd >= 0 && fstat(fd, &s) == 0); equal(&s, &file);
    CHECK(fstatat(fd, "", &s, STAT_EMPTY_PATH) == 0); equal(&s, &file);
    struct statx empty_fd = query(fd, "", STAT_EMPTY_PATH, 0);
    CHECK(!memcmp(&empty_fd, &file, sizeof file) && close(fd) == 0);
    CHECK(stat(STAT_DANGLING, &s) == -1 && errno == ENOENT);
    CHECK(stat(STAT_LOOP, &s) == -1 && errno == ELOOP);
    int directory = open(STAT_DIR, O_RDONLY | O_DIRECTORY);
    CHECK(directory >= 0 && fstat(directory, &s) == 0 && S_ISDIR(s.st_mode));
    struct statx child = query(directory, "child", 0, STAT_BASIC_MASK);
    CHECK(fstatat(directory, "child", &s, 0) == 0); equal(&s, &child);
    DIR *stream = fdopendir(directory);
    CHECK(stream != 0 && dirfd(stream) == directory);
    unsigned children = 0, count = 0;
    errno = 0;
    struct dirent *entry;
    while ((entry = readdir(stream)) != 0) {
        CHECK(++count <= 16);
        if (!strcmp(entry->d_name, "child")) { ++children; CHECK(entry->d_ino == child.stx_ino); }
    }
    CHECK(errno == 0 && children == 1 && closedir(stream) == 0);
    for (unsigned i = 0; i < sizeof paths / sizeof paths[0]; ++i) {
        struct statx x = query(AT_FDCWD, paths[i], AT_SYMLINK_NOFOLLOW, STAT_BASIC_MASK);
        CHECK(lstat(paths[i], &s) == 0); equal(&s, &x);
        CHECK(fstatat(AT_FDCWD, paths[i], &s, AT_SYMLINK_NOFOLLOW) == 0); equal(&s, &x);
        if (i == 5) CHECK(x.stx_size == 0 && x.stx_blocks == 0);
        if (i == 6) CHECK(x.stx_size == STAT_HOLE_SIZE && x.stx_blocks == 0);
        stat_probe_snapshot(labels[i], &x);
    }
}

static void refused(int fd, const char *path, unsigned flags, unsigned mask)
{
    unsigned char out[320];
    memset(out, 0xa5, sizeof out);
    CHECK(raw(fd, path, flags, mask, out + 32) == -1 && errno == EOPNOTSUPP);
    CHECK(filled(out, sizeof out, 0xa5));
}

static void unqualified_checks(void)
{
    struct stat s;
    memset(&s, 0xa5, sizeof s);
    CHECK(stat(STAT_FILE, &s) == -1 && errno == EOPNOTSUPP && filled(&s, sizeof s, 0xa5));
    CHECK(lstat(STAT_FILE, &s) == -1 && errno == EOPNOTSUPP && filled(&s, sizeof s, 0xa5));
    CHECK(fstatat(AT_FDCWD, STAT_FILE, &s, 0) == -1 && errno == EOPNOTSUPP && filled(&s, sizeof s, 0xa5));
    int fd = open(STAT_FILE, O_RDONLY);
    CHECK(fd >= 0);
    CHECK(fstat(fd, &s) == -1 && errno == EOPNOTSUPP && filled(&s, sizeof s, 0xa5));
    CHECK(fstatat(fd, "", &s, STAT_EMPTY_PATH) == -1 && errno == EOPNOTSUPP && filled(&s, sizeof s, 0xa5));
    refused(fd, "", STAT_EMPTY_PATH, 0);
    refused(fd, 0, STAT_EMPTY_PATH, STAT_BASIC_MASK);
    for (unsigned i = 0; i < sizeof paths / sizeof paths[0]; ++i) {
        refused(AT_FDCWD, paths[i], AT_SYMLINK_NOFOLLOW, STAT_BASIC_MASK);
        refused(AT_FDCWD, paths[i], AT_SYMLINK_NOFOLLOW, 0);
    }
    CHECK(close(fd) == 0);
}

int main(int argc, char **argv)
{
    CHECK(argc == 3);
    CHECK(!strcmp(argv[1], "readonly") || !strcmp(argv[1], "unqualified"));
    CHECK(!strcmp(argv[2], "negative") || !strcmp(argv[2], "post2038"));
    epoch = !strcmp(argv[2], "negative") ? -123456789LL : 2208988800LL;
    CHECK(getuid() == 1000 && geteuid() == 1000 && getgid() == 1000 && getegid() == 1000);
    if (!strcmp(argv[1], "readonly")) readonly_checks(); else unqualified_checks();
    struct stat s;
    memset(&s, 0xa5, sizeof s);
    CHECK(fstat(1, &s) == -1 && errno == EOPNOTSUPP && filled(&s, sizeof s, 0xa5));
    refused(1, "", STAT_EMPTY_PATH, 0);
    stat_probe_text("LINUX_STAT_CONTROLS_MUSL_PASS mode="); stat_probe_text(argv[1]);
    stat_probe_text(" epoch="); stat_probe_text(argv[2]);
    stat_probe_text(" checks="); stat_probe_unsigned(checks); stat_probe_text("\n");
    return 0;
}

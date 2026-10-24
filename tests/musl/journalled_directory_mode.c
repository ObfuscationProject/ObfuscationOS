#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include "../chmod_probe_log.h"

static unsigned checks, operations;
static void fail(unsigned line)
{
    unsigned error = (unsigned)errno;
    chmod_probe_text("JDMODE_USER_FAIL line="); chmod_probe_unsigned(line);
    chmod_probe_text(" errno="); chmod_probe_unsigned(error);
    chmod_probe_text(" checks="); chmod_probe_unsigned(checks); chmod_probe_text("\n");
    _Exit(1);
}
#define CHECK(x) do { ++checks; if (!(x)) fail(__LINE__); } while (0)
_Static_assert(sizeof(struct statx) == 256, "statx wire size");
_Static_assert(sizeof(time_t) == 8, "musl time64 required");
static struct statx query(int fd, const char *path, unsigned flags)
{
    struct statx out;
    memset(&out, 0xa5, sizeof out);
    CHECK(syscall(SYS_statx, (long)fd, (long)path, (long)flags,
                  (long)STATX_BASIC_STATS, (long)&out) == 0);
    CHECK(out.stx_mask == STATX_BASIC_STATS && out.stx_ino && out.stx_blksize == 1024);
    return out;
}
static void begin(const char *name)
{
    chmod_probe_text("JDMODE_OP_BEGIN ordinal="); chmod_probe_unsigned(++operations);
    chmod_probe_text(" name="); chmod_probe_text(name); chmod_probe_text("\n");
}
static void end(unsigned mutation)
{
    chmod_probe_text("JDMODE_OP_END ordinal="); chmod_probe_unsigned(operations);
    chmod_probe_text(" mutation="); chmod_probe_unsigned(mutation); chmod_probe_text("\n");
}
static struct timespec now(void)
{
    struct timespec value; CHECK(clock_gettime(CLOCK_REALTIME, &value) == 0); return value;
}
static void changed(const struct statx *before, const struct statx *after,
                    unsigned permissions, struct timespec lower)
{
    struct timespec upper = now();
    CHECK(after->stx_mode == (S_IFDIR | permissions));
    CHECK(after->stx_ino == before->stx_ino && after->stx_uid == before->stx_uid &&
          after->stx_gid == before->stx_gid && after->stx_nlink == before->stx_nlink);
    CHECK(after->stx_dev_major == before->stx_dev_major && after->stx_dev_minor == before->stx_dev_minor);
    CHECK(after->stx_size == before->stx_size && after->stx_blocks == before->stx_blocks);
    CHECK(memcmp(&after->stx_atime, &before->stx_atime, sizeof before->stx_atime) == 0);
    CHECK(memcmp(&after->stx_mtime, &before->stx_mtime, sizeof before->stx_mtime) == 0);
    CHECK(after->stx_ctime.tv_sec >= lower.tv_sec && after->stx_ctime.tv_sec <= upper.tv_sec);
    if (after->stx_ctime.tv_sec == lower.tv_sec) CHECK(after->stx_ctime.tv_nsec >= (unsigned long)lower.tv_nsec);
    if (after->stx_ctime.tv_sec == upper.tv_sec) CHECK(after->stx_ctime.tv_nsec <= (unsigned long)upper.tv_nsec);
}
static void denied(long result, int error) { CHECK(result == -1 && errno == error); }
static void entries(int fd)
{
    int copy = dup(fd); CHECK(copy >= 0);
    CHECK(lseek(copy, 0, SEEK_SET) == 0);
    DIR *dir = fdopendir(copy); CHECK(dir != NULL);
    unsigned names = 0;
    struct dirent *entry;
    errno = 0;
    while ((entry = readdir(dir)))
    {
        if (!strcmp(entry->d_name, ".")) { CHECK(!(names & 1) && entry->d_ino == 14 && entry->d_type == DT_DIR); names |= 1; }
        else if (!strcmp(entry->d_name, "..")) { CHECK(!(names & 2) && entry->d_ino == 2 && entry->d_type == DT_DIR); names |= 2; }
        else if (!strcmp(entry->d_name, "leaf")) { CHECK(!(names & 4) && entry->d_ino == 16 && entry->d_type == DT_REG); names |= 4; }
        else CHECK(0);
    }
    CHECK(errno == 0 && names == 7);
    CHECK(closedir(dir) == 0);
}
static void restored(int fd, int alias, const struct statx *expected)
{
    struct statx a = query(alias, "", AT_EMPTY_PATH);
    struct statx b = query(AT_FDCWD, "/alias/child", 0);
    CHECK(memcmp(&a, expected, sizeof a) == 0 && memcmp(&b, expected, sizeof b) == 0);
    entries(fd);
    int seed = openat(fd, "../seed", O_RDONLY); CHECK(seed >= 0);
    unsigned char bytes[4096]; CHECK(read(seed, bytes, sizeof bytes) == (ssize_t)sizeof bytes);
    for (unsigned i = 0; i < sizeof bytes; ++i) CHECK(bytes[i] == (unsigned char)(i * 17 + 29));
    CHECK(close(seed) == 0);
    int leaf = openat(fd, "leaf", O_RDONLY); CHECK(leaf >= 0);
    const char expected_leaf[] = "directory child payload\n";
    CHECK(read(leaf, bytes, sizeof bytes) == (ssize_t)sizeof expected_leaf - 1);
    CHECK(memcmp(bytes, expected_leaf, sizeof expected_leaf - 1) == 0);
    CHECK(read(leaf, bytes, 1) == 0 && close(leaf) == 0);
}
int main(void)
{
    const unsigned uid = getuid();
    CHECK((uid == 0 || uid == 1000) && geteuid() == uid && getgid() == uid && getegid() == uid);
    chmod_probe_text("JDMODE_USER_BEGIN uid="); chmod_probe_unsigned(uid);
    chmod_probe_text(" sdk=31 scope=actual-musl-syscalls\n");
    const int negative_clock = now().tv_sec < 0;
    struct statx before = query(AT_FDCWD, "/journal/child", 0);
    CHECK(before.stx_mode == (S_IFDIR | 0755) && before.stx_uid == 1000 && before.stx_gid == 1000);
    CHECK(before.stx_ino == 14 && before.stx_size == 1024 && before.stx_blocks == 2 && before.stx_nlink == 2);
    int fd = open("/journal/child", O_RDONLY | O_DIRECTORY | O_CLOEXEC); CHECK(fd >= 0);
    int alias = open("/alias/child", O_RDONLY | O_DIRECTORY); CHECK(alias >= 0);
    int directory = open("/journal", O_RDONLY | O_DIRECTORY); CHECK(directory >= 0);
    restored(fd, alias, &before);
    if (negative_clock)
    {
        CHECK(uid == 0);
        begin("ctime-negative"); denied(fchmod(fd, 0700), EOVERFLOW); end(0);
        struct statx unchanged = query(fd, "", AT_EMPTY_PATH);
        CHECK(memcmp(&before, &unchanged, sizeof before) == 0);
    }
    else
    {
        struct timespec lower = now();
        begin("chmod"); CHECK(chmod("/alias/child", 02750) == 0); end(1);
        struct statx after = query(fd, "", AT_EMPTY_PATH);
        changed(&before, &after, 02750, lower); before = after; restored(fd, alias, &before);
        lower = now(); begin("same-mode"); CHECK(fchmod(fd, 02750) == 0); end(1);
        after = query(fd, "", AT_EMPTY_PATH); changed(&before, &after, 02750, lower); before = after;
        lower = now(); begin("remove-search"); CHECK(fchmod(alias, 0000) == 0); end(1);
        after = query(fd, "", AT_EMPTY_PATH); changed(&before, &after, 0000, lower); before = after;
        struct statx through_alias = query(AT_FDCWD, "/alias/child", 0);
        CHECK(memcmp(&before, &through_alias, sizeof before) == 0);
        begin("search-permission");
        entries(fd);
        entries(alias);
        if (uid)
        {
            denied(open("/journal/child/../seed", O_RDONLY), EACCES);
            denied(open("/alias/child/../seed", O_RDONLY), EACCES);
            denied(openat(fd, "../seed", O_RDONLY), EACCES);
            denied(openat(fd, "leaf", O_RDONLY), EACCES);
            denied(open("/journal/child", O_RDONLY | O_DIRECTORY), EACCES);
            denied(fchdir(fd), EACCES);
            denied(fchmodat(fd, ".", 0700, 0), EACCES);
        }
        else
        {
            int seed = openat(fd, "../seed", O_RDONLY); CHECK(seed >= 0); CHECK(close(seed) == 0);
        }
        end(0);
        lower = now(); begin("retained-fd-restore"); CHECK(fchmod(fd, 0755) == 0); end(1);
        after = query(alias, "", AT_EMPTY_PATH); changed(&before, &after, 0755, lower); before = after;
        restored(fd, alias, &before);
        CHECK(fcntl(fd, F_GETFD) == FD_CLOEXEC);
        lower = now(); begin("fchmodat-relative"); CHECK(fchmodat(directory, "child", 01750, 0) == 0); end(1);
        after = query(fd, "", AT_EMPTY_PATH); changed(&before, &after, 01750, lower); before = after;
        lower = now(); begin("fork-retained-fd");
        pid_t child = fork(); CHECK(child >= 0);
        if (!child) _Exit(fchmod(alias, 0700) == 0 ? 0 : 77);
        int status = -1; CHECK(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0);
        end(1); after = query(fd, "", AT_EMPTY_PATH); changed(&before, &after, 0700, lower); before = after;
        restored(fd, alias, &before);
        if (!uid)
        {
            struct timespec invalid = {2147483648LL, 123456789};
            CHECK(clock_settime(CLOCK_REALTIME, &invalid) == 0);
            begin("ctime-post2038"); denied(fchmod(fd, 0600), EOVERFLOW); end(0);
            after = query(fd, "", AT_EMPTY_PATH); CHECK(memcmp(&before, &after, sizeof before) == 0);
            struct timespec epoch = {1700000000, 123456789};
            CHECK(clock_settime(CLOCK_REALTIME, &epoch) == 0);
        }
    }
    if (uid)
    {
        struct statx other = query(AT_FDCWD, "/journal/lost+found", 0);
        CHECK(other.stx_uid == 0 && (other.stx_mode & S_IFMT) == S_IFDIR);
        begin("other-owner"); denied(chmod("/journal/lost+found", 0755), EPERM); end(0);
        struct statx unchanged = query(AT_FDCWD, "/journal/lost+found", 0);
        CHECK(memcmp(&other, &unchanged, sizeof other) == 0);
    }
    begin("unsupported-root"); denied(fchmod(directory, 0700), EOPNOTSUPP); end(0);
    struct statx link = query(AT_FDCWD, "/journal/seed-link", AT_SYMLINK_NOFOLLOW);
    begin("unsupported-symlink"); denied(fchmodat(directory, "seed-link", 0600, AT_SYMLINK_NOFOLLOW), EOPNOTSUPP); end(0);
    struct statx link_after = query(AT_FDCWD, "/journal/seed-link", AT_SYMLINK_NOFOLLOW);
    CHECK(memcmp(&link, &link_after, sizeof link) == 0);
    begin("fsync"); CHECK(fsync(fd) == 0 && fsync(directory) == 0); end(0);
    CHECK(close(alias) == 0 && close(fd) == 0 && close(directory) == 0);
    begin("stale-fd"); denied(fchmod(fd, 0600), EBADF); end(0);
    chmod_probe_snapshot("journal-child", &before);
    chmod_probe_text("JDMODE_USER_PASS uid="); chmod_probe_unsigned(uid);
    chmod_probe_text(" operations="); chmod_probe_unsigned(operations);
    chmod_probe_text(" checks="); chmod_probe_unsigned(checks); chmod_probe_text("\n");
    return 0;
}

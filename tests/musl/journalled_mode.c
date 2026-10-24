#define _GNU_SOURCE
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
    chmod_probe_text("JMODE_USER_FAIL line="); chmod_probe_unsigned(line);
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
    chmod_probe_text("JMODE_OP_BEGIN ordinal="); chmod_probe_unsigned(++operations);
    chmod_probe_text(" name="); chmod_probe_text(name); chmod_probe_text("\n");
}
static void end(unsigned mutation)
{
    chmod_probe_text("JMODE_OP_END ordinal="); chmod_probe_unsigned(operations);
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
    CHECK(after->stx_mode == ((before->stx_mode & S_IFMT) | permissions));
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
int main(void)
{
    const unsigned uid = getuid();
    CHECK((uid == 0 || uid == 1000) && geteuid() == uid && getgid() == uid && getegid() == uid);
    chmod_probe_text("JMODE_USER_BEGIN uid="); chmod_probe_unsigned(uid);
    chmod_probe_text(" sdk=31 scope=actual-musl-syscalls\n");
    const int negative_clock = now().tv_sec < 0;
    struct statx before = query(AT_FDCWD, "/journal/seed", 0);
    CHECK(before.stx_mode == (S_IFREG | 0600) && before.stx_uid == 1000 && before.stx_gid == 1001);
    CHECK(before.stx_size == 4096 && before.stx_blocks == 8 && before.stx_nlink == 1);
    struct statx alias = query(AT_FDCWD, "/alias/seed", 0);
    CHECK(memcmp(&before, &alias, sizeof before) == 0);
    int fd = open("/journal/seed", O_RDONLY | O_CLOEXEC); CHECK(fd >= 0);
    int duplicate = dup(fd); CHECK(duplicate >= 0);
    CHECK(lseek(fd, 7, SEEK_SET) == 7);
    const int flags = fcntl(fd, F_GETFL); CHECK(flags >= 0);
    if (negative_clock)
    {
        CHECK(uid == 0);
        begin("ctime-negative"); denied(fchmod(fd, 0644), EOVERFLOW); end(0);
        struct statx unchanged = query(fd, "", AT_EMPTY_PATH);
        CHECK(memcmp(&before, &unchanged, sizeof before) == 0);
        int directory = open("/journal", O_RDONLY | O_DIRECTORY); CHECK(directory >= 0);
        begin("fsync"); CHECK(fsync(fd) == 0 && fsync(directory) == 0); end(0);
        CHECK(close(duplicate) == 0 && close(fd) == 0 && close(directory) == 0);
        begin("stale-fd"); denied(fchmod(fd, 0600), EBADF); end(0);
        chmod_probe_snapshot("journal-seed", &before);
        chmod_probe_text("JMODE_USER_PASS uid=0 operations=3 checks=");
        chmod_probe_unsigned(checks); chmod_probe_text("\n");
        return 0;
    }
    struct timespec lower = now();
    begin("chmod"); CHECK(chmod("/alias/seed", 06750) == 0); end(1);
    struct statx after = query(duplicate, "", AT_EMPTY_PATH);
    changed(&before, &after, uid ? 04750 : 06750, lower); before = after;
    lower = now(); begin("same-mode"); CHECK(fchmod(fd, before.stx_mode & 07777) == 0); end(1);
    after = query(fd, "", AT_EMPTY_PATH); changed(&before, &after, before.stx_mode & 07777, lower); before = after;
    CHECK(lseek(duplicate, 0, SEEK_CUR) == 7 && fcntl(fd, F_GETFL) == flags && fcntl(fd, F_GETFD) == FD_CLOEXEC);
    unsigned char bytes[16]; CHECK(read(duplicate, bytes, sizeof bytes) == (ssize_t)sizeof bytes);
    for (unsigned i = 0; i < sizeof bytes; ++i) CHECK(bytes[i] == (unsigned char)((i + 7) * 17 + 29));
    after = query(fd, "", AT_EMPTY_PATH); CHECK(memcmp(&before, &after, sizeof before) == 0);
    int directory = open("/journal", O_RDONLY | O_DIRECTORY); CHECK(directory >= 0);
    lower = now(); begin("fchmodat-relative"); CHECK(fchmodat(directory, "seed", 0640, 0) == 0); end(1);
    after = query(fd, "", AT_EMPTY_PATH); changed(&before, &after, 0640, lower); before = after;
    lower = now(); begin("absolute-ignores-dirfd"); CHECK(fchmodat(-999, "/alias/seed", 0604, 0) == 0); end(1);
    after = query(fd, "", AT_EMPTY_PATH); changed(&before, &after, 0604, lower); before = after;
    struct stat ordinary; CHECK(fstat(fd, &ordinary) == 0);
    CHECK((uint64_t)ordinary.st_ino == before.stx_ino && ordinary.st_blocks == 8 && ordinary.st_size == 4096);
    CHECK((unsigned)ordinary.st_mode == before.stx_mode && ordinary.st_uid == 1000 && ordinary.st_gid == 1001);
    struct statx other = query(AT_FDCWD, "/journal/other-owner", 0);
    begin("other-owner");
    if (uid) denied(chmod("/journal/other-owner", 0600), EPERM);
    else CHECK(chmod("/journal/other-owner", 0600) == 0);
    end(uid ? 0 : 1);
    struct statx other_after = query(AT_FDCWD, "/journal/other-owner", 0);
    if (uid) CHECK(memcmp(&other, &other_after, sizeof other) == 0);
    else CHECK(other_after.stx_mode == (S_IFREG | 0600) && other_after.stx_uid == 2000 && other_after.stx_gid == 2000);
    begin("unsupported-directory"); denied(fchmod(directory, 0700), EOPNOTSUPP); end(0);
    struct statx link = query(AT_FDCWD, "/journal/seed-link", AT_SYMLINK_NOFOLLOW);
    CHECK((link.stx_mode & S_IFMT) == S_IFLNK && link.stx_blocks == 0);
    begin("unsupported-symlink"); denied(fchmodat(directory, "seed-link", 0600, AT_SYMLINK_NOFOLLOW), EOPNOTSUPP); end(0);
    struct statx link_after = query(AT_FDCWD, "/journal/seed-link", AT_SYMLINK_NOFOLLOW);
    CHECK(memcmp(&link, &link_after, sizeof link) == 0);
    begin("missing"); denied(chmod("/journal/missing", 0600), ENOENT); end(0);
    lower = now(); begin("fork-retained-fd");
    pid_t child = fork(); CHECK(child >= 0);
    if (!child) _Exit(fchmod(duplicate, 0644) == 0 ? 0 : 77);
    int status = -1; CHECK(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    end(1); after = query(fd, "", AT_EMPTY_PATH); changed(&before, &after, 0644, lower); before = after;
    if (!uid)
    {
        struct timespec invalid = {-1, 123456789};
        lower = now();
        begin("negative-clock-rejected"); denied(clock_settime(CLOCK_REALTIME, &invalid), EINVAL); end(0);
        CHECK(now().tv_sec >= lower.tv_sec);
        after = query(fd, "", AT_EMPTY_PATH); CHECK(memcmp(&before, &after, sizeof before) == 0);
        invalid.tv_sec = 2147483648LL;
        CHECK(clock_settime(CLOCK_REALTIME, &invalid) == 0);
        begin("ctime-post2038"); denied(fchmod(fd, 0600), EOVERFLOW); end(0);
        after = query(fd, "", AT_EMPTY_PATH); CHECK(memcmp(&before, &after, sizeof before) == 0);
        struct timespec epoch = {1700000000, 123456789};
        CHECK(clock_settime(CLOCK_REALTIME, &epoch) == 0);
        lower = now(); begin("clock-restored"); CHECK(fchmod(fd, 0644) == 0); end(1);
        after = query(fd, "", AT_EMPTY_PATH); changed(&before, &after, 0644, lower); before = after;
    }
    begin("fsync"); CHECK(fsync(fd) == 0 && fsync(directory) == 0); end(0);
    CHECK(close(duplicate) == 0 && close(fd) == 0 && close(directory) == 0);
    begin("stale-fd"); denied(fchmod(fd, 0600), EBADF); end(0);
    chmod_probe_snapshot("journal-seed", &before);
    chmod_probe_text("JMODE_USER_PASS uid="); chmod_probe_unsigned(uid);
    chmod_probe_text(" operations="); chmod_probe_unsigned(operations);
    chmod_probe_text(" checks="); chmod_probe_unsigned(checks); chmod_probe_text("\n");
    return 0;
}

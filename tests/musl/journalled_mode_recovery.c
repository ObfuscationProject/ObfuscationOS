#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
#include "../chmod_probe_log.h"

static unsigned checks;
static void fail(unsigned line)
{
    chmod_probe_text("JREC_USER_FAIL line="); chmod_probe_unsigned(line);
    chmod_probe_text(" errno="); chmod_probe_unsigned((unsigned)errno);
    chmod_probe_text(" checks="); chmod_probe_unsigned(checks); chmod_probe_text("\n");
    _Exit(1);
}
#define CHECK(x) do { ++checks; if (!(x)) fail(__LINE__); } while (0)
static struct statx query(int fd, const char *path, unsigned flags)
{
    struct statx value;
    memset(&value, 0xa5, sizeof value);
    CHECK(syscall(SYS_statx, (long)fd, (long)path, (long)flags,
                  (long)STATX_BASIC_STATS, (long)&value) == 0);
    CHECK(value.stx_mask == STATX_BASIC_STATS && value.stx_blksize == 1024);
    return value;
}
int main(void)
{
    CHECK(getuid() == 1000 && geteuid() == 1000 && getgid() == 1000 && getegid() == 1000);
    chmod_probe_text("JREC_USER_BEGIN uid=1000 scope=actual-musl-syscalls\n");
    struct statx seed = query(AT_FDCWD, "/journal/seed", 0);
    CHECK(seed.stx_ino == 12 && seed.stx_uid == 1000 && seed.stx_gid == 1001 && seed.stx_nlink == 1);
    CHECK(seed.stx_mode == (S_IFREG | 0600) || seed.stx_mode == (S_IFREG | 04750));
    CHECK(seed.stx_size == 4096 && seed.stx_blocks == 8);
    /* The outer collector binds the exact old/new metadata to the selected cut. */
    struct statx alias = query(AT_FDCWD, "/alias/seed", 0);
    CHECK(memcmp(&seed, &alias, sizeof seed) == 0);
    int fd = open("/journal/seed", O_RDONLY | O_CLOEXEC); CHECK(fd >= 0);
    struct statx opened = query(fd, "", AT_EMPTY_PATH);
    CHECK(memcmp(&seed, &opened, sizeof seed) == 0);
    struct stat ordinary; CHECK(fstat(fd, &ordinary) == 0);
    CHECK((uint64_t)ordinary.st_ino == seed.stx_ino && (unsigned)ordinary.st_mode == seed.stx_mode &&
          ordinary.st_uid == seed.stx_uid && ordinary.st_gid == seed.stx_gid &&
          ordinary.st_nlink == seed.stx_nlink && ordinary.st_size == 4096 && ordinary.st_blocks == 8);
    unsigned char bytes[257]; unsigned total = 0;
    for (;;) {
        ssize_t got = read(fd, bytes, sizeof bytes); CHECK(got >= 0);
        if (!got) break;
        CHECK((unsigned)got <= 4096 - total);
        for (unsigned i = 0; i < (unsigned)got; ++i)
            CHECK(bytes[i] == (unsigned char)((total + i) * 17 + 29));
        total += (unsigned)got;
    }
    CHECK(total == 4096 && lseek(fd, 0, SEEK_CUR) == 4096);
    opened = query(fd, "", AT_EMPTY_PATH); CHECK(memcmp(&seed, &opened, sizeof seed) == 0);
    struct statx other = query(AT_FDCWD, "/journal/other-owner", 0);
    CHECK(other.stx_ino == 13 && other.stx_mode == (S_IFREG | 0644) && other.stx_uid == 2000 && other.stx_gid == 2000);
    CHECK(other.stx_size == 29 && other.stx_blocks == 2 && other.stx_nlink == 1);
    int other_fd = open("/alias/other-owner", O_RDONLY); CHECK(other_fd >= 0);
    CHECK(read(other_fd, bytes, sizeof bytes) == 29 && memcmp(bytes, "other owner metadata fixture\n", 29) == 0);
    CHECK(read(other_fd, bytes, sizeof bytes) == 0 && close(other_fd) == 0);
    struct statx link = query(AT_FDCWD, "/journal/seed-link", AT_SYMLINK_NOFOLLOW);
    CHECK(link.stx_ino == 15 && link.stx_mode == (S_IFLNK | 0777) && link.stx_uid == 1000 && link.stx_gid == 1001 && link.stx_size == 4);
    char target[16]; CHECK(readlink("/alias/seed-link", target, sizeof target) == 4 && memcmp(target, "seed", 4) == 0);
    alias = query(AT_FDCWD, "/alias/seed-link", 0); CHECK(memcmp(&seed, &alias, sizeof seed) == 0);
    chmod_probe_snapshot("recovery-seed", &seed);
    chmod_probe_snapshot("recovery-other", &other);
    chmod_probe_snapshot("recovery-link", &link);
    int directory = open("/journal", O_RDONLY | O_DIRECTORY); CHECK(directory >= 0);
    chmod_probe_text("JREC_FSYNC_BEGIN calls=2\n");
    CHECK(fsync(fd) == 0 && fsync(directory) == 0);
    chmod_probe_text("JREC_FSYNC_END calls=2\n");
    opened = query(fd, "", AT_EMPTY_PATH); CHECK(memcmp(&seed, &opened, sizeof seed) == 0);
    CHECK(close(fd) == 0 && close(directory) == 0);
    chmod_probe_text("JREC_USER_PASS uid=1000 bytes=4096 checks=");
    chmod_probe_unsigned(checks); chmod_probe_text("\n");
    return 0;
}

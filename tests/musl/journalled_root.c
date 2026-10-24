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
    chmod_probe_text("JROOT_USER_FAIL line="); chmod_probe_unsigned(line);
    chmod_probe_text(" errno="); chmod_probe_unsigned((unsigned)errno);
    chmod_probe_text(" checks="); chmod_probe_unsigned(checks); chmod_probe_text("\n");
    _Exit(1);
}
#define CHECK(value) do { ++checks; if (!(value)) fail(__LINE__); } while (0)

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
    chmod_probe_text("JROOT_USER_BEGIN source=disk path=/init uid=1000\n");
    struct statx root = query(AT_FDCWD, "/", 0);
    CHECK(root.stx_ino == 2 && root.stx_mode == (S_IFDIR | 0755));
    struct statx executable = query(AT_FDCWD, "/init", 0);
    CHECK(executable.stx_mode == (S_IFREG | 0555) && executable.stx_size > 4096);
    struct statx seed = query(AT_FDCWD, "/seed", 0);
    struct statx child = query(AT_FDCWD, "/child", 0);
    CHECK(seed.stx_ino == 12 && seed.stx_uid == 1000 && seed.stx_gid == 1001 &&
          seed.stx_size == 4096 && seed.stx_blocks == 8);
    CHECK(child.stx_ino == 14 && child.stx_uid == 1000 && child.stx_gid == 1000 &&
          (child.stx_mode == (S_IFDIR | 0755) || child.stx_mode == (S_IFDIR | 0750)));
    int fd = open("/seed", O_RDONLY | O_CLOEXEC); CHECK(fd >= 0);
    unsigned char bytes[257]; unsigned total = 0;
    for (;;) {
        ssize_t got = read(fd, bytes, sizeof bytes); CHECK(got >= 0);
        if (!got) break;
        CHECK((unsigned)got <= 4096 - total);
        for (unsigned i = 0; i < (unsigned)got; ++i)
            CHECK(bytes[i] == (unsigned char)((total + i) * 17 + 29));
        total += (unsigned)got;
    }
    CHECK(total == 4096);
    int directory = open("/child", O_RDONLY | O_DIRECTORY | O_CLOEXEC); CHECK(directory >= 0);
    struct statx other = query(AT_FDCWD, "/other-owner", 0);
    CHECK(other.stx_ino == 13 && other.stx_size == 29 && other.stx_mode == (S_IFREG | 0644));
    int other_fd = open("/other-owner", O_RDONLY); CHECK(other_fd >= 0);
    CHECK(read(other_fd, bytes, sizeof bytes) == 29 &&
          memcmp(bytes, "other owner metadata fixture\n", 29) == 0);
    CHECK(close(other_fd) == 0);
    unsigned mutations = 0;
    CHECK(seed.stx_mode == (S_IFREG | 0600) || seed.stx_mode == (S_IFREG | 0640));
    if (seed.stx_mode == (S_IFREG | 0600)) {
        chmod_probe_text("JROOT_OP_BEGIN name=seed-chmod\n");
        CHECK(fchmod(fd, 0640) == 0); ++mutations;
    }
    CHECK(fsync(fd) == 0);
    if (seed.stx_mode == (S_IFREG | 0600))
        chmod_probe_text("JROOT_OP_END name=seed-chmod durable=1\n");
    if (child.stx_mode == (S_IFDIR | 0755)) {
        chmod_probe_text("JROOT_OP_BEGIN name=child-chmod\n");
        CHECK(fchmod(directory, 0750) == 0); ++mutations;
    }
    CHECK(fsync(directory) == 0);
    if (child.stx_mode == (S_IFDIR | 0755))
        chmod_probe_text("JROOT_OP_END name=child-chmod durable=1\n");
    struct statx updated_seed = query(fd, "", AT_EMPTY_PATH);
    struct statx updated_child = query(directory, "", AT_EMPTY_PATH);
    CHECK(updated_seed.stx_mode == (S_IFREG | 0640) && updated_seed.stx_ino == seed.stx_ino &&
          updated_seed.stx_size == seed.stx_size && updated_seed.stx_blocks == seed.stx_blocks);
    CHECK(updated_child.stx_mode == (S_IFDIR | 0750) && updated_child.stx_ino == child.stx_ino &&
          updated_child.stx_size == child.stx_size && updated_child.stx_blocks == child.stx_blocks);
    CHECK(lseek(fd, 0, SEEK_SET) == 0 && read(fd, bytes, sizeof bytes) == sizeof bytes);
    for (unsigned i = 0; i < sizeof bytes; ++i) CHECK(bytes[i] == (unsigned char)(i * 17 + 29));
    CHECK(close(fd) == 0 && close(directory) == 0);
    chmod_probe_text("JROOT_USER_PASS source=disk mutations=");
    chmod_probe_unsigned(mutations); chmod_probe_text(" checks=");
    chmod_probe_unsigned(checks); chmod_probe_text("\n");
    return 0;
}

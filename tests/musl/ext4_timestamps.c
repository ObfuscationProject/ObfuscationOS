#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
#include "ext4_timestamp_log.h"

#define CHECK(x) do { if (!(x)) return timestamp_failure("MUSL", __LINE__, (unsigned)errno); } while (0)
#define begin timestamp_begin
#define record(event, path, mask) timestamp_record("musl", event, path, mask)

int main(void)
{
    CHECK(getuid() == 1000 && geteuid() == 1000 && getgid() == 1000 && getegid() == 1000);
    struct timespec value = {2208988800LL, 1};
    CHECK(clock_settime(CLOCK_REALTIME, &value) == -1 && errno == EPERM);
    CHECK(begin() == 0);
    int fd = open("/home/musl-time", O_CREAT | O_EXCL | O_RDWR, 0600);
    CHECK(fd >= 0 && record("create", "/home/musl-time", 7) == 0);
    CHECK(begin() == 0 && write(fd, "abcdef", 6) == 6 && record("write", "/home/musl-time", 6) == 0);
    CHECK(begin() == 0 && pwrite(fd, "Z", 1, 2) == 1 && record("pwrite", "/home/musl-time", 6) == 0);
    char buffer[8] = {0};
    CHECK(begin() == 0 && pread(fd, buffer, 6, 0) == 6 && !memcmp(buffer, "abZdef", 6) &&
          record("pread", "/home/musl-time", 1) == 0);
    CHECK(begin() == 0 && read(fd, buffer, 1) == 0 && record("read-eof", "/home/musl-time", 1) == 0);
    CHECK(write(fd, buffer, 0) == 0 && read(fd, buffer, 0) == 0 && fsync(fd) == 0);
    struct stat metadata;
    memset(&metadata, 0xa5, sizeof metadata);
    CHECK(fstat(fd, &metadata) == 0);
    struct statx projected;
    memset(&projected, 0xa5, sizeof projected);
    CHECK(syscall(SYS_statx, fd, "", 0x1000, 0x7ff, &projected) == 0);
    CHECK(projected.stx_mask == 0x7ff && projected.stx_ino != 0 &&
          (projected.stx_dev_major != 0 || projected.stx_dev_minor != 0));
    CHECK(S_ISREG(metadata.st_mode) && (metadata.st_mode & 07777) == 0600 &&
          metadata.st_nlink == 1 && metadata.st_uid == 1000 && metadata.st_gid == 1000 &&
          metadata.st_size == 6 && metadata.st_ino == projected.stx_ino);
    CHECK((metadata.st_blksize == 1024 || metadata.st_blksize == 2048 || metadata.st_blksize == 4096) &&
          metadata.st_blocks == metadata.st_blksize / 512 &&
          projected.stx_blocks == (uint64_t)metadata.st_blocks &&
          projected.stx_size == (uint64_t)metadata.st_size);
    CHECK(metadata.st_atim.tv_sec == projected.stx_atime.tv_sec &&
          (int64_t)metadata.st_atim.tv_nsec == (int64_t)projected.stx_atime.tv_nsec &&
          metadata.st_mtim.tv_sec == projected.stx_mtime.tv_sec &&
          (int64_t)metadata.st_mtim.tv_nsec == (int64_t)projected.stx_mtime.tv_nsec &&
          metadata.st_ctim.tv_sec == projected.stx_ctime.tv_sec &&
          (int64_t)metadata.st_ctim.tv_nsec == (int64_t)projected.stx_ctime.tv_nsec);
    CHECK(metadata.st_atim.tv_sec >= 2208988800LL && metadata.st_mtim.tv_sec >= 2208988800LL &&
          metadata.st_ctim.tv_sec >= 2208988800LL &&
          metadata.st_atim.tv_nsec >= 0 && metadata.st_atim.tv_nsec < 1000000000 &&
          metadata.st_mtim.tv_nsec >= 0 && metadata.st_mtim.tv_nsec < 1000000000 &&
          metadata.st_ctim.tv_nsec >= 0 && metadata.st_ctim.tv_nsec < 1000000000);
    /* Preserve no-output refusal coverage on an explicitly unqualified object. */
    memset(&metadata, 0xa5, sizeof metadata);
    CHECK(fstat(1, &metadata) == -1 && errno == EOPNOTSUPP);
    for (unsigned i = 0; i < sizeof metadata; ++i) CHECK(((unsigned char *)&metadata)[i] == 0xa5);
    CHECK(close(fd) == 0);

    CHECK(begin() == 0);
    fd = open("/home/musl-truncate", O_CREAT | O_EXCL | O_RDWR, 0600);
    CHECK(fd >= 0 && record("create", "/home/musl-truncate", 7) == 0);
    CHECK(write(fd, "removed", 7) == 7 && close(fd) == 0);
    CHECK(begin() == 0);
    fd = open("/home/musl-truncate", O_WRONLY | O_TRUNC);
    CHECK(fd >= 0 && record("open-truncate", "/home/musl-truncate", 6) == 0 && close(fd) == 0);

    CHECK(begin() == 0 && mkdir("/home/musl-dir", 0700) == 0 && record("mkdir", "/home/musl-dir", 7) == 0);
    int directory = open("/home/musl-dir", O_RDONLY | O_DIRECTORY);
    CHECK(directory >= 0);
    unsigned char entries[256];
    CHECK(begin() == 0 && syscall(SYS_getdents64, directory, entries, sizeof entries) > 0 &&
          record("getdents", "/home/musl-dir", 1) == 0);
    CHECK(begin() == 0 && syscall(SYS_getdents64, directory, entries, sizeof entries) == 0 &&
          record("getdents-eof", "/home/musl-dir", 1) == 0 && close(directory) == 0);

    char linktext[32] = {0};
    CHECK(begin() == 0 && readlink("/home/fixture-link", linktext, sizeof linktext) == 9 &&
          !memcmp(linktext, "musl-time", 9) && record("readlink", "/home/fixture-link", 1) == 0);
    puts("EXT4_TIME_MUSL_PASS authority=uid1000 clock-set=EPERM linux-stat=qualified");
    return 0;
}

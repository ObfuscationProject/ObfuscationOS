#include <errno.h>
#include <fcntl.h>
#include <ok/syscall.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define CHECK(x) do { if (!(x)) return timestamp_failure("NATIVE", __LINE__, (unsigned)errno); } while (0)
#include "ext4_timestamp_log.h"
#define begin timestamp_begin
#define record(event, path, mask) timestamp_record("native", event, path, mask)
int main(void)
{
    CHECK(getuid() == 1000 && geteuid() == 1000 && getgid() == 1000 && getegid() == 1000);
    struct timespec denied = {2208988800LL, 1};
    CHECK(clock_settime(CLOCK_REALTIME, &denied) == -1 && errno == EPERM);
    CHECK(begin() == 0);
    int fd = open("/home/native-time", O_CREAT | O_EXCL | O_RDWR, 0600);
    CHECK(fd >= 0 && record("create", "/home/native-time", 7) == 0);
    CHECK(begin() == 0 && write(fd, "native", 6) == 6 && record("write", "/home/native-time", 6) == 0);
    CHECK(begin() == 0 && ftruncate(fd, 6) == 0 && record("same-truncate", "/home/native-time", 6) == 0);
    CHECK(begin() == 0 && link("/home/native-time", "/home/native-alias") == 0 &&
          record("link", "/home/native-time", 4) == 0);
    CHECK(begin() == 0 && rename("/home/native-time", "/home/native-renamed") == 0 &&
          record("rename", "/home/native-renamed", 4) == 0);
    CHECK(begin() == 0 && unlink("/home/native-alias") == 0 &&
          record("unlink-alias", "/home/native-renamed", 4) == 0);
    char buffer[8] = {0};
    CHECK(begin() == 0 && pread(fd, buffer, 6, 0) == 6 && !memcmp(buffer, "native", 6) &&
          record("pread", "/home/native-renamed", 1) == 0);
    CHECK(read(fd, buffer, 0) == 0 && write(fd, buffer, 0) == 0 && fsync(fd) == 0 && close(fd) == 0);
    CHECK(begin() == 0 && symlink("native-renamed", "/home/native-link") == 0 &&
          record("symlink", "/home/native-link", 7) == 0);
    char linktext[32] = {0};
    CHECK(begin() == 0 && readlink("/home/native-link", linktext, sizeof linktext) == 14 &&
          !memcmp(linktext, "native-renamed", 14) && record("readlink", "/home/native-link", 1) == 0);
    CHECK(begin() == 0 && mkdir("/home/native-dir", 0700) == 0 &&
          record("mkdir", "/home/native-dir", 7) == 0);
    puts("EXT4_TIME_NATIVE_PASS authority=uid1000 clock-set=EPERM automatic-times=enabled");
    char *argv[] = {"musl-ext4-timestamps", 0}; char *env[] = {"PATH=/bin", 0};
    execve("/bin/musl-ext4-timestamps", argv, env);
    return timestamp_failure("NATIVE", __LINE__, (unsigned)errno);
}

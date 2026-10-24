#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include "../chmod_fixture.h"

#define CHECK(x) do { if (!(x)) { printf("LINUX_CHMOD_NATIVE_FAIL line=%d errno=%d\n", __LINE__, errno); return 1; } } while (0)

/* Native printf has no portable long-long conversion on the 32-bit profiles. */
static void decimal64(char out[32], int64_t value)
{
    char reverse[24];
    unsigned count = 0, offset = 0;
    uint64_t magnitude = value < 0 ? (uint64_t)(-(value + 1)) + 1 : (uint64_t)value;
    do { reverse[count++] = (char)('0' + magnitude % 10); magnitude /= 10; } while (magnitude);
    if (value < 0) out[offset++] = '-';
    while (count) out[offset++] = reverse[--count];
    out[offset] = 0;
}

/* Native ABI performs mutations which the bounded Linux adapter does not expose. */
int main(void)
{
    CHECK(getuid() == 1000 && geteuid() == 1000 && getgid() == 1000 && getegid() == 1000);
    struct timespec first, last;
    CHECK(clock_gettime(CLOCK_REALTIME, &first) == 0);
    CHECK(first.tv_sec > 2147483647LL || first.tv_sec < 0);
    struct timespec denied = {2208988800LL, 123456789};
    CHECK(clock_settime(CLOCK_REALTIME, &denied) == -1 && errno == EPERM);

    int fd = open(CHMOD_FILE, O_CREAT | O_EXCL | O_RDWR, 0600);
    CHECK(fd >= 0 && write(fd, CHMOD_CONTENT, CHMOD_CONTENT_SIZE) == (ssize_t)CHMOD_CONTENT_SIZE);
    CHECK(close(fd) == 0 && link(CHMOD_FILE, CHMOD_ALIAS) == 0);
    CHECK(symlink("chmod-file", CHMOD_LINK) == 0);
    CHECK(symlink("chmod-missing", CHMOD_DANGLING) == 0);
    CHECK(symlink("chmod-loop", CHMOD_LOOP) == 0);

    fd = open(CHMOD_EMPTY, O_CREAT | O_EXCL | O_RDWR, 0600);
    CHECK(fd >= 0 && close(fd) == 0);
    fd = open(CHMOD_HOLE, O_CREAT | O_EXCL | O_RDWR, 0600);
    CHECK(fd >= 0 && ftruncate(fd, CHMOD_HOLE_SIZE) == 0 && close(fd) == 0);

    fd = open(CHMOD_HELD_PATH, O_CREAT | O_EXCL | O_RDWR, 0600);
    CHECK(fd >= 0 && write(fd, CHMOD_CONTENT, CHMOD_CONTENT_SIZE) == (ssize_t)CHMOD_CONTENT_SIZE);
    CHECK(dup2(fd, CHMOD_HELD_FD) == CHMOD_HELD_FD);
    CHECK(fd == CHMOD_HELD_FD || close(fd) == 0);
    CHECK(unlink(CHMOD_HELD_PATH) == 0);

    CHECK(mkdir(CHMOD_DIR_OLD, 0700) == 0);
    fd = open(CHMOD_DIR_OLD "/child", O_CREAT | O_EXCL | O_RDWR, 0600);
    CHECK(fd >= 0 && close(fd) == 0);
    fd = open(CHMOD_DIR_OLD, O_RDONLY | O_DIRECTORY);
    CHECK(fd >= 0 && dup2(fd, CHMOD_DIR_FD) == CHMOD_DIR_FD);
    CHECK(fd == CHMOD_DIR_FD || close(fd) == 0);
    CHECK(rename(CHMOD_DIR_OLD, CHMOD_DIR) == 0);

    CHECK(mkdir(CHMOD_CWD, 0700) == 0 && chdir(CHMOD_CWD) == 0);
    CHECK(rmdir(CHMOD_CWD) == 0);
    struct stat native;
    CHECK(fstat(CHMOD_HELD_FD, &native) == 0 && native.st_nlink == 0 &&
          native.st_size == (off_t)CHMOD_CONTENT_SIZE);
    CHECK(fstat(CHMOD_DIR_FD, &native) == 0 && S_ISDIR(native.st_mode));
    CHECK(clock_gettime(CLOCK_REALTIME, &last) == 0 && last.tv_sec >= first.tv_sec);
    char lower[32], upper[32];
    decimal64(lower, first.tv_sec);
    decimal64(upper, last.tv_sec);
    puts("LINUX_CHMOD_NATIVE_PASS authority=uid1000 held-fd=10 renamed-dir-fd=11 cwd=detached");
    char *argv[] = {"musl-linux-chmod", lower, upper, 0};
    char *env[] = {"PATH=/bin", 0};
    execve(CHMOD_PROBE, argv, env);
    CHECK(0);
}

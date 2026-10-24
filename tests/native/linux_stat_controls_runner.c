#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "../stat_fixture.h"

#ifndef LINUX_STAT_READONLY
#define LINUX_STAT_READONLY 1
#endif
#ifndef LINUX_STAT_NEGATIVE
#define LINUX_STAT_NEGATIVE 0
#endif

static void emit(const char *text)
{
    size_t size = strlen(text);
    while (size) {
        ssize_t count = write(1, text, size);
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) exit(2);
        text += count; size -= (size_t)count;
    }
}

static void number(unsigned value)
{
    char text[16];
    unsigned end = sizeof text - 1;
    text[end] = 0;
    do { text[--end] = (char)('0' + value % 10); value /= 10; } while (value);
    emit(text + end);
}

static void failure(unsigned line)
{
    unsigned error = (unsigned)errno;
    emit("LINUX_STAT_CONTROLS_NATIVE_FAIL line="); number(line);
    emit(" errno="); number(error); emit("\n");
    exit(1);
}

#define CHECK(x) do { if (!(x)) failure(__LINE__); } while (0)

int main(void)
{
    CHECK(getuid() == 1000 && geteuid() == 1000 && getgid() == 1000 && getegid() == 1000);
    int fd = open(STAT_FILE, O_RDONLY);
    struct stat status;
    CHECK(fd >= 0 && fstat(fd, &status) == 0);
    CHECK(S_ISREG(status.st_mode) && status.st_nlink == 2 &&
          status.st_size == (off_t)STAT_CONTENT_SIZE && close(fd) == 0);
    fd = open(STAT_DIR, O_RDONLY | O_DIRECTORY);
    CHECK(fd >= 0 && fstat(fd, &status) == 0 && S_ISDIR(status.st_mode) && close(fd) == 0);
    emit("LINUX_STAT_CONTROLS_NATIVE_PASS authority=uid1000 native-stat=pass mutations=none\n");
    char *argv[] = {"musl-linux-stat-controls",
        LINUX_STAT_READONLY ? "readonly" : "unqualified",
        LINUX_STAT_NEGATIVE ? "negative" : "post2038", 0};
    char *env[] = {"PATH=/bin", 0};
    execve("/bin/musl-linux-stat-controls", argv, env);
    CHECK(0);
}

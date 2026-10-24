#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static void line(const char *text)
{
    size_t size = strlen(text);
    if (write(STDOUT_FILENO, text, size) != (ssize_t)size)
        _Exit(90);
}

static void fail(unsigned code)
{
    char text[] = "REMOVAL_FAIL code=000\n";
    unsigned offset = sizeof("REMOVAL_FAIL code=") - 1;
    text[offset] = '0' + code / 100 % 10;
    text[offset + 1] = '0' + code / 10 % 10;
    text[offset + 2] = '0' + code % 10;
    line(text);
    _Exit(1);
}

#define CHECK(test, code) do { if (!(test)) fail(code); } while (0)
#define ERROR(test, error, code) do { errno = 0; CHECK((test) == -1 && errno == (error), code); } while (0)

int main(void)
{
    const char *directory = "/tmp/removal-probe";
    const char *leaf = "/tmp/removal-probe/leaf";
    char bytes[4] = {0};
    line("REMOVAL_BEGIN cases=8\n");
    CHECK(mkdir(directory, 0700) == 0, 101);
    int dir = open(directory, O_RDONLY | O_DIRECTORY);
    CHECK(dir >= 0, 102);
    int old = openat(dir, "leaf", O_CREAT | O_EXCL | O_RDWR, 0600);
    CHECK(old >= 0 && write(old, "old", 3) == 3, 103);
    ERROR(unlinkat(dir, "leaf", 1), EINVAL, 104);
    int present = open(leaf, O_RDONLY);
    CHECK(present >= 0 && close(present) == 0, 105);
    line("REMOVAL_CASE index=0 name=flags pass=1\n");
    ERROR(unlinkat(-1, "leaf", 0), EBADF, 106);
    ERROR(unlinkat(dir, "", 0), ENOENT, 107);
    line("REMOVAL_CASE index=1 name=paths pass=1\n");
    CHECK(unlinkat(dir, "leaf", 0) == 0, 108);
    ERROR(open(leaf, O_RDONLY), ENOENT, 109);
    CHECK(lseek(old, 0, SEEK_SET) == 0 && read(old, bytes, 3) == 3 && memcmp(bytes, "old", 3) == 0, 110);
    line("REMOVAL_CASE index=2 name=retained pass=1\n");
    int replacement = openat(dir, "leaf", O_CREAT | O_EXCL | O_RDWR, 0600);
    CHECK(replacement >= 0 && write(replacement, "new", 3) == 3, 111);
    CHECK(lseek(old, 0, SEEK_SET) == 0 && read(old, bytes, 3) == 3 && memcmp(bytes, "old", 3) == 0, 112);
    CHECK(lseek(replacement, 0, SEEK_SET) == 0 && read(replacement, bytes, 3) == 3 && memcmp(bytes, "new", 3) == 0, 113);
    CHECK(close(old) == 0 && close(replacement) == 0, 114);
    CHECK(unlinkat(-1, leaf, 0) == 0, 115);
    ERROR(unlinkat(dir, "leaf", 0), ENOENT, 116);
    line("REMOVAL_CASE index=3 name=recreated pass=1\n");
    ERROR(unlink(directory), EISDIR, 117);
    CHECK(mkdirat(dir, "child", 0700) == 0, 118);
    ERROR(rmdir(directory), ENOTEMPTY, 119);
    CHECK(unlinkat(dir, "child", AT_REMOVEDIR) == 0, 120);
    line("REMOVAL_CASE index=4 name=directories pass=1\n");
    int legacy = openat(dir, "legacy", O_CREAT | O_EXCL | O_RDWR, 0600);
    CHECK(legacy >= 0 && close(legacy) == 0, 121);
    CHECK(unlink("/tmp/removal-probe/legacy") == 0, 122);
    ERROR(unlink("/tmp/removal-probe/legacy"), ENOENT, 123);
    line("REMOVAL_CASE index=5 name=libc_unlink pass=1\n");
    CHECK(close(dir) == 0 && rmdir(directory) == 0, 124);
    ERROR(open(directory, O_RDONLY | O_DIRECTORY), ENOENT, 125);
    line("REMOVAL_CASE index=6 name=libc_rmdir pass=1\n");
    CHECK(mkdir(directory, 0700) == 0 && unlinkat(-1, directory, AT_REMOVEDIR) == 0, 126);
    line("REMOVAL_CASE index=7 name=absolute pass=1\n");
    line("REMOVAL_PASS cases=8\n");
    return 0;
}

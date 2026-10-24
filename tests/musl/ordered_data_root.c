#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/auxv.h>
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

int main(void)
{
    CHECK(getuid() == 1000 && geteuid() == 1000 && getgid() == 1000 && getegid() == 1000);
    CHECK(getauxval(AT_UID) == 1000 && getauxval(AT_EUID) == 1000 &&
          getauxval(AT_GID) == 1000 && getauxval(AT_EGID) == 1000);
    chmod_probe_text("JROOT_USER_BEGIN source=disk path=/init uid=1000 ordered=1\n");
    int fd = open("/seed", O_RDWR | O_CLOEXEC); CHECK(fd >= 0);
    struct stat metadata;
    CHECK(fstat(fd, &metadata) == 0);
    CHECK(S_ISREG(metadata.st_mode) && (metadata.st_mode & 07777) == 0600 &&
          metadata.st_uid == 1000 && metadata.st_gid == 1001 && metadata.st_blocks == 8);
    if (metadata.st_size == 4096) {
        unsigned char first[4];
        CHECK(pread(fd, first, sizeof first, 100) == sizeof first);
        /* In-place data may survive a cut before its inode log commits. */
        int original = 1;
        for (unsigned i = 0; i < sizeof first; ++i)
            if (first[i] != (unsigned char)((100 + i) * 17 + 29)) original = 0;
        CHECK(original || memcmp(first, "CODE", 4) == 0);
        CHECK(pwrite(fd, "CODE", 4, 100) == 4);
        CHECK(ftruncate(fd, 4000) == 0);
        CHECK(lseek(fd, 0, SEEK_END) == 4000);
        CHECK(write(fd, "APPEN", 5) == 5);
        CHECK(fsync(fd) == 0);
        CHECK(fstat(fd, &metadata) == 0 && metadata.st_size == 4005 && metadata.st_blocks == 8);
        chmod_probe_text("JROOT_USER_PASS source=disk mutations=3 checks=");
    } else {
        CHECK(metadata.st_size == 4005);
        unsigned char changed[4], suffix[5], retained[5];
        CHECK(pread(fd, changed, sizeof changed, 100) == sizeof changed &&
              memcmp(changed, "CODE", 4) == 0);
        CHECK(pread(fd, suffix, sizeof suffix, 4000) == sizeof suffix &&
              memcmp(suffix, "APPEN", 5) == 0);
        CHECK(pread(fd, retained, sizeof retained, 3995) == sizeof retained);
        for (unsigned i = 0; i < sizeof retained; ++i)
            CHECK(retained[i] == (unsigned char)((3995 + i) * 17 + 29));
        CHECK(fsync(fd) == 0);
        chmod_probe_text("JROOT_USER_PASS source=disk mutations=0 checks=");
    }
    CHECK(close(fd) == 0);
    chmod_probe_unsigned(checks); chmod_probe_text("\n");
    return 0;
}

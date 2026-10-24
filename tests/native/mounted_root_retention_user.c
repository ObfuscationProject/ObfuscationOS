#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/auxv.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include "../chmod_probe_log.h"

static unsigned checks;
static void fail(unsigned line)
{
    chmod_probe_text("MROOT_USER_FAIL line="); chmod_probe_unsigned(line);
    chmod_probe_text(" errno="); chmod_probe_unsigned((unsigned)errno);
    chmod_probe_text(" checks="); chmod_probe_unsigned(checks); chmod_probe_text("\n");
    _Exit(1);
}
#define CHECK(value) do { ++checks; if (!(value)) fail(__LINE__); } while (0)

static void original(int fd)
{
    unsigned char data[32];
    CHECK(pread(fd, data, sizeof data, 64) == sizeof data);
    for (unsigned i = 0; i != sizeof data; ++i)
        CHECK(data[i] == (unsigned char)((64 + i) * 17 + 29));
}

int main(void)
{
    CHECK(getuid() == 1000 && geteuid() == 1000 && getgid() == 1000 && getegid() == 1000);
    CHECK(getauxval(AT_UID) == 1000 && getauxval(AT_EUID) == 1000 &&
          getauxval(AT_GID) == 1000 && getauxval(AT_EGID) == 1000);
    chmod_probe_text("MROOT_USER_BEGIN source=disk path=/init uid=1000\n");
    int fd = open("/seed", O_RDWR | O_CLOEXEC); CHECK(fd == 3);
    int duplicate = dup(fd); CHECK(duplicate == 4);
    int directory = open("/child", O_RDONLY | O_DIRECTORY | O_CLOEXEC); CHECK(directory == 5);
    struct stat metadata;
    CHECK(fstat(fd, &metadata) == 0 && S_ISREG(metadata.st_mode) && metadata.st_size == 4096 &&
          (metadata.st_mode & 07777) == 0600 && metadata.st_uid == 1000 && metadata.st_gid == 1001);
    CHECK(fstat(directory, &metadata) == 0 && S_ISDIR(metadata.st_mode));
    CHECK(chdir("/child") == 0 && fchdir(directory) == 0);
    original(fd);
    CHECK(lseek(fd, 64, SEEK_SET) == 64);
    unsigned char byte;
    CHECK(read(duplicate, &byte, 1) == 1 && byte == (unsigned char)(64 * 17 + 29));
    CHECK(lseek(fd, 0, SEEK_CUR) == 65);
    chmod_probe_text("MROOT_USER_READY fd=3 dup=4 directory=5 cwd=child shared-offset=1\n");
    pid_t child = fork(); CHECK(child >= 0);
    if (child == 0) {
        CHECK(fchdir(directory) == 0);
        original(fd); original(duplicate);
        int own = open("/seed", O_RDONLY | O_CLOEXEC); CHECK(own == 6);
        original(own);
        chmod_probe_text("MROOT_CHILD_LIVE inherited-fd=1 inherited-dup=1 inherited-cwd=1 own-ofd=1\n");
        CHECK(lseek(duplicate, 70, SEEK_SET) == 70);
        CHECK(read(fd, &byte, 1) == 1 && byte == (unsigned char)(70 * 17 + 29));
        chmod_probe_text("MROOT_CHILD_EXIT status=23 fd-close=exit cwd-release=exit\n");
        /* The native exit path must release both OFDs and this cloned cwd. */
        _Exit(23);
    }
    int status;
    CHECK(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 23);
    CHECK(lseek(fd, 0, SEEK_CUR) == 71);
    chmod_probe_text("MROOT_USER_WAIT child=23 inherited-offset=71 reaped=1\n");
    static const char payload[] = "ROOT-RETENTION-V1";
    CHECK(pwrite(fd, payload, sizeof payload - 1, 100) == sizeof payload - 1);
    CHECK(fsync(duplicate) == 0);
    char changed[sizeof payload - 1];
    CHECK(pread(fd, changed, sizeof changed, 100) == sizeof changed &&
          memcmp(changed, payload, sizeof changed) == 0);
    CHECK(fstat(fd, &metadata) == 0 && metadata.st_size == 4096 && metadata.st_blocks == 8);
    chmod_probe_text("MROOT_USER_PASS writes=1 fsync=1 bytes=17 child=23 checks=");
    chmod_probe_unsigned(checks); chmod_probe_text(" parent-fd-close=exit parent-cwd-release=exit\n");
    /* The fixture independently retains this real shared OFD and cwd for drain. */
    return 0;
}

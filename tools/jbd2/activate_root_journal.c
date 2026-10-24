#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <unistd.h>

static void fail(const char *operation)
{
    printf("LINUX_JOURNAL_ACTIVATION_FAIL operation=%s errno=%d\n", operation, errno);
    fflush(stdout);
    for (;;) pause();
}

int main(void)
{
    mkdir("/dev", 0755);
    if (mount("devtmpfs", "/dev", "devtmpfs", 0, "") != 0) fail("devtmpfs");
    mknod("/dev/console", S_IFCHR | 0600, makedev(5, 1));
    int console = open("/dev/console", O_RDWR);
    if (console < 0 || dup2(console, 0) < 0 || dup2(console, 1) < 0 || dup2(console, 2) < 0)
        fail("console");
    setvbuf(stdout, NULL, _IONBF, 0);
    mkdir("/mnt", 0755);
    for (int attempt = 0; access("/dev/vda", F_OK) != 0 && attempt < 100; ++attempt) usleep(50000);
    if (mount("/dev/vda", "/mnt", "ext4", MS_NOATIME,
              "data=ordered,journal_checksum,commit=600") != 0) fail("ext4 mount");
    int marker = open("/mnt/.journal-profile", O_RDWR);
    if (marker < 0 || fchmod(marker, 0600) != 0 || fsync(marker) != 0)
        fail("journal transaction");
    if (close(marker) != 0 || umount2("/mnt", 0) != 0) fail("clean unmount");
    puts("LINUX_JOURNAL_ACTIVATED clean=1 checksum=v3");
    for (;;) pause();
}

#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/utsname.h>
#include <unistd.h>

static void fail(const char *operation)
{
    printf("LINUX_JBD2_FIXTURE_FAIL operation=%s errno=%d\n", operation, errno);
    fflush(stdout);
    for (;;) pause();
}

int main(void)
{
    mkdir("/dev", 0755);
    mount("devtmpfs", "/dev", "devtmpfs", 0, "");
    mknod("/dev/console", S_IFCHR | 0600, makedev(5, 1));
    int console = open("/dev/console", O_RDWR);
    if (console >= 0)
    {
        dup2(console, 0); dup2(console, 1); dup2(console, 2);
    }
    setvbuf(stdout, NULL, _IONBF, 0);
    struct utsname name;
    if (uname(&name) != 0) fail("uname");
    printf("LINUX_JBD2_FIXTURE_BEGIN release=%s version=%s machine=%s\n", name.release, name.version, name.machine);
    mkdir("/proc", 0755); mkdir("/sys", 0755); mkdir("/mnt", 0755);
    mount("proc", "/proc", "proc", 0, "");
    mount("sysfs", "/sys", "sysfs", 0, "");
    for (int attempt = 0; access("/dev/vda", F_OK) != 0 && attempt < 100; ++attempt) usleep(50000);
    if (mount("/dev/vda", "/mnt", "ext4", MS_NOATIME, "data=ordered,journal_checksum,commit=600") != 0)
        fail("mount disposable vda");
    int seed = open("/mnt/seed", O_RDWR);
    if (seed < 0) fail("open seeded file");
    struct stat before;
    if (fstat(seed, &before) != 0 || before.st_size != 4096) fail("seed identity");
    printf("LINUX_JBD2_FIXTURE_SEED inode=%llu old_mode=%o old_uid=%u old_gid=%u size=%lld\n",
           (unsigned long long)before.st_ino, before.st_mode & 07777, before.st_uid, before.st_gid,
           (long long)before.st_size);
    if (fchmod(seed, 0600) != 0) fail("fchmod");
    if (fchown(seed, 1000, 1001) != 0) fail("fchown");
    if (fsync(seed) != 0) fail("fsync inode");
    struct stat after;
    if (fstat(seed, &after) != 0 || (after.st_mode & 07777) != 0600 || after.st_uid != 1000 || after.st_gid != 1001)
        fail("committed inode state");
    printf("LINUX_JBD2_FIXTURE_COMMITTED inode=%llu mode=600 uid=1000 gid=1001 bytes=4096 shutdown=unclean\n",
           (unsigned long long)after.st_ino);
    // The host terminates this one disposable VM after the durable-fsync marker.
    // Never unmount, call syncfs or request a clean shutdown here.
    for (;;) pause();
}

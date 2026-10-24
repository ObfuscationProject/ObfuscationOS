#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/utsname.h>
#include <unistd.h>

struct expected_node {
    const char *path;
    uint64_t inode;
    unsigned mode, uid, gid, links;
    uint64_t size;
    int64_t seconds[3];
    unsigned nanos[3];
};
#include "timestamp_expected.h"

static void fail(const char *operation)
{
    printf("JBD2_NATIVE_FAIL linux-ext4-time operation=%s errno=%d\n", operation, errno);
    for (;;) pause();
}

int main(void)
{
    mkdir("/dev", 0755); mount("devtmpfs", "/dev", "devtmpfs", 0, "");
    mknod("/dev/console", S_IFCHR | 0600, makedev(5, 1));
    int console = open("/dev/console", O_RDWR);
    if (console >= 0) { dup2(console, 0); dup2(console, 1); dup2(console, 2); }
    setvbuf(stdout, NULL, _IONBF, 0);
    struct utsname version; if (uname(&version)) fail("uname");
    printf("LINUX_EXT4_TIME_BEGIN release=%s version=%s machine=%s\n", version.release, version.version, version.machine);
    mkdir("/mnt", 0755);
    for (int i = 0; access("/dev/vda", F_OK) && i < 100; ++i) usleep(50000);
    if (mount("/dev/vda", "/mnt", "ext4", MS_RDONLY | MS_NOSUID | MS_NODEV | MS_NOEXEC, ""))
        fail("readonly mount");
    for (unsigned i = 0; i < sizeof expected / sizeof expected[0]; ++i) {
        const struct expected_node *want = &expected[i];
        struct stat st;
        if (lstat(want->path, &st) || st.st_ino != want->inode || st.st_mode != want->mode ||
            st.st_uid != want->uid || st.st_gid != want->gid || st.st_nlink != want->links ||
            (uint64_t)st.st_size != want->size) fail(want->path);
        const struct timespec times[] = {st.st_atim, st.st_mtim, st.st_ctim};
        for (unsigned field = 0; field < 3; ++field) {
            if (times[field].tv_sec != want->seconds[field] || times[field].tv_nsec != want->nanos[field])
                fail("exact stored A/M/C");
            printf("LINUX_EXT4_TIME_FIELD node=%u field=%u inode=%" PRIu64 " seconds=%" PRId64 " nanos=%u\n",
                   i, field, want->inode, (int64_t)times[field].tv_sec, (unsigned)times[field].tv_nsec);
        }
    }
    if (umount("/mnt")) fail("readonly unmount");
    puts("LINUX_EXT4_TIME_PASS nodes=7 fields=21 mount=readonly image=unchanged extra16=accepted");
    for (;;) pause();
}

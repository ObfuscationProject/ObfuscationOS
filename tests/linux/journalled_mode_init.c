#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/utsname.h>
#include <unistd.h>
#include "journalled_linux_expected.h"

static void fail(const char *operation)
{
    printf("JBD2_NATIVE_FAIL journalled-linux operation=%s errno=%d\n", operation, errno);
    for (;;) pause();
}

static void verify_node(const struct expected_node *node)
{
    struct stat st;
    if (lstat(node->path, &st)) fail("lstat");
    if ((uint64_t)st.st_ino != node->inode || (unsigned)st.st_mode != node->mode ||
        st.st_uid != node->uid || st.st_gid != node->gid || st.st_nlink != node->links ||
        (uint64_t)st.st_size != node->size || (uint64_t)st.st_blocks != node->blocks512 ||
        st.st_blksize != 1024) fail("node identity/metadata");
    if (st.st_atim.tv_sec != node->atime_sec || st.st_atim.tv_nsec != node->atime_nsec ||
        st.st_mtim.tv_sec != node->mtime_sec || st.st_mtim.tv_nsec != node->mtime_nsec ||
        st.st_ctim.tv_sec != node->ctime_sec || st.st_ctim.tv_nsec != node->ctime_nsec)
        fail("node timestamps");
}

int main(void)
{
    mkdir("/dev", 0755); mount("devtmpfs", "/dev", "devtmpfs", 0, "");
    mknod("/dev/console", S_IFCHR | 0600, makedev(5, 1));
    int console = open("/dev/console", O_RDWR);
    if (console >= 0) { dup2(console, 0); dup2(console, 1); dup2(console, 2); }
    setvbuf(stdout, NULL, _IONBF, 0);
    struct utsname version;
    if (uname(&version)) fail("uname");
    printf("JMODE_LINUX_BEGIN release=%s version=%s machine=%s\n", version.release, version.version, version.machine);
    mkdir("/proc", 0755); mkdir("/sys", 0755); mkdir("/mnt", 0755);
    if (mount("proc", "/proc", "proc", 0, "") || mount("sysfs", "/sys", "sysfs", 0, "")) fail("system mounts");
    for (int i = 0; access("/dev/vda", F_OK) && i < 100; ++i) usleep(50000);
    if (mount("/dev/vda", "/mnt", "ext4", MS_RDONLY | MS_NOSUID | MS_NODEV | MS_NOEXEC, ""))
        fail("readonly ext4 mount/recovery");
    for (unsigned i = 0; i < sizeof(expected_nodes) / sizeof(expected_nodes[0]); ++i)
        verify_node(&expected_nodes[i]);
    int fd = open("/mnt/seed", O_RDONLY);
    if (fd < 0) fail("seed open");
    unsigned char payload[4096]; size_t done = 0;
    while (done < sizeof(payload))
    {
        ssize_t count = read(fd, payload + done, sizeof(payload) - done);
        if (count <= 0) fail("seed read");
        done += (size_t)count;
    }
    for (size_t i = 0; i < sizeof(payload); ++i)
        if (payload[i] != (unsigned char)(i * 17 + 29)) fail("seed payload");
    if (read(fd, payload, 1) != 0 || close(fd)) fail("seed EOF/close");
    fd = open("/mnt/other-owner", O_RDONLY);
    if (fd < 0) fail("other owner open");
    const char other[] = "other owner metadata fixture\n";
    if (read(fd, payload, sizeof(payload)) != sizeof(other) - 1 ||
        memcmp(payload, other, sizeof(other) - 1) || close(fd)) fail("other owner payload");
    char target[32];
    if (readlink("/mnt/seed-link", target, sizeof(target)) != 4 || memcmp(target, "seed", 4))
        fail("symlink target");
    if (umount("/mnt")) fail("readonly unmount");
    printf("JMODE_LINUX_PASS nodes=5 payloads=2 symlink=1 mount=readonly unmount=pass\n");
    for (;;) pause();
}

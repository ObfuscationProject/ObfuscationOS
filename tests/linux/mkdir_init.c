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

static void fail(const char *operation)
{
    printf("JBD2_NATIVE_FAIL linux-mkdir operation=%s errno=%d\n", operation, errno);
    for (;;) pause();
}

static void check(const char *path, unsigned mode, uint32_t gid, unsigned links, const char *data)
{
    struct stat st;
    if (lstat(path, &st) || (unsigned)(st.st_mode & 07777) != mode || st.st_uid != 0 ||
        st.st_gid != gid || st.st_nlink != links || (data ? !S_ISREG(st.st_mode) : !S_ISDIR(st.st_mode)))
        fail(path);
    if (data) {
        int fd = open(path, O_RDONLY);
        char bytes[16]; size_t size = strlen(data);
        if (fd < 0 || st.st_size != (off_t)size || read(fd, bytes, sizeof bytes) != (ssize_t)size ||
            memcmp(bytes, data, size) || close(fd)) fail("contents");
    } else {
        char dot[192]; struct stat self;
        snprintf(dot, sizeof dot, "%s/.", path);
        if (stat(dot, &self) || self.st_ino != st.st_ino || self.st_dev != st.st_dev) fail("dot identity");
    }
}

int main(void)
{
    mkdir("/dev", 0755); mount("devtmpfs", "/dev", "devtmpfs", 0, "");
    mknod("/dev/console", S_IFCHR | 0600, makedev(5, 1));
    int console = open("/dev/console", O_RDWR);
    if (console >= 0) { dup2(console, 0); dup2(console, 1); dup2(console, 2); }
    setvbuf(stdout, NULL, _IONBF, 0);
    struct utsname version; if (uname(&version)) fail("uname");
    printf("LINUX_MKDIR_BEGIN release=%s version=%s machine=%s\n", version.release, version.version, version.machine);
    mkdir("/mnt", 0755);
    for (int i = 0; access("/dev/vda", F_OK) && i < 100; ++i) usleep(50000);
    if (mount("/dev/vda", "/mnt", "ext4", MS_RDONLY | MS_NOSUID | MS_NODEV | MS_NOEXEC, "")) fail("readonly mount");
    const uint32_t gid = UINT32_C(0x87654321);
    check("/mnt/home/musl-mkdir-sgid", 02777, gid, 4, NULL);
    for (int slot = 0; slot < 2; ++slot) {
        char path[128];
        snprintf(path, sizeof path, "/mnt/home/musl-mkdir-%d", slot);
        check(path, 01750, 0, 6, NULL);
        const char *children[] = {"child", "cwd", "legacy", "retained"};
        for (unsigned i = 0; i < sizeof children / sizeof children[0]; ++i) {
            snprintf(path, sizeof path, "/mnt/home/musl-mkdir-%d/%s", slot, children[i]);
            check(path, 0750, 0, 2, NULL);
        }
        snprintf(path, sizeof path, "/mnt/home/musl-mkdir-%d/data", slot); check(path, 0640, 0, 1, "created");
        snprintf(path, sizeof path, "/mnt/home/musl-mkdir-sgid/run-%d", slot); check(path, 03750, gid, 3, NULL);
        snprintf(path, sizeof path, "/mnt/home/musl-mkdir-sgid/run-%d/nested", slot); check(path, 02750, gid, 2, NULL);
        snprintf(path, sizeof path, "/mnt/home/musl-mkdir-sgid/run-%d/data", slot); check(path, 0640, gid, 1, "group");
    }
    if (umount("/mnt")) fail("readonly unmount");
    puts("LINUX_MKDIR_PASS nodes=19 files=4 mode=pass uid=pass gid32=pass links=pass contents=pass mount=readonly unmount=pass");
    for (;;) pause();
}

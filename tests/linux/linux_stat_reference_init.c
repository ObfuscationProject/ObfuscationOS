#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <sys/utsname.h>
#include <unistd.h>

struct expected_node {
    const char *name, *path, *relative;
    uint64_t inode, size, blocks;
    uint32_t mode, uid, gid, links, blksize;
    int64_t seconds[3];
    uint32_t nanos[3];
};
#include "linux_stat_expected.h"

_Static_assert(sizeof(struct statx) == 256, "Linux statx wire size");
_Static_assert(offsetof(struct statx, stx_atime) == 64, "Linux statx atime offset");
_Static_assert(offsetof(struct statx, stx_dev_major) == 136, "Linux statx device offset");
_Static_assert(sizeof(time_t) == 8, "reference preserves signed64 epochs");

static unsigned device_major, device_minor, observations;
static void fail(const char *operation)
{
    /* The inherited disposable-guest runner stops on this exact failure prefix. */
    printf("JBD2_NATIVE_FAIL linux-stat-reference operation=%s errno=%d\n", operation, errno);
    for (;;) pause();
}

static void emit(const struct expected_node *want, const char *api, uint64_t inode,
                 unsigned mode, unsigned uid, unsigned gid, uint64_t links,
                 uint64_t size, uint64_t blocks, uint64_t blksize,
                 const int64_t seconds[3], const uint32_t nanos[3],
                 unsigned dev_major, unsigned dev_minor, unsigned rdev_major, unsigned rdev_minor)
{
    printf("LINUX_STAT_REFERENCE_FIELD name=%s api=%s inode=%" PRIu64
           " mode=%u uid=%u gid=%u nlink=%" PRIu64 " size=%" PRIu64
           " blocks=%" PRIu64 " blksize=%" PRIu64
           " atime_s=%" PRId64 " atime_ns=%u mtime_s=%" PRId64 " mtime_ns=%u"
           " ctime_s=%" PRId64 " ctime_ns=%u dev_major=%u dev_minor=%u rdev_major=%u rdev_minor=%u\n",
           want->name, api, inode, mode, uid, gid, links, size, blocks, blksize,
           seconds[0], nanos[0], seconds[1], nanos[1], seconds[2], nanos[2],
           dev_major, dev_minor, rdev_major, rdev_minor);
    ++observations;
}

static void check_stat(const struct expected_node *want, const char *api, const struct stat *s)
{
    if ((uint64_t)s->st_ino != want->inode || (uint32_t)s->st_mode != want->mode ||
        s->st_uid != want->uid || s->st_gid != want->gid || (uint64_t)s->st_nlink != want->links ||
        s->st_size < 0 || (uint64_t)s->st_size != want->size || s->st_blocks < 0 ||
        (uint64_t)s->st_blocks != want->blocks || s->st_blksize < 0 ||
        (uint64_t)s->st_blksize != want->blksize || s->st_rdev != 0 ||
        major(s->st_dev) != device_major || minor(s->st_dev) != device_minor)
        fail(api);
    const struct timespec times[] = {s->st_atim, s->st_mtim, s->st_ctim};
    int64_t seconds[3]; uint32_t nanos[3];
    for (unsigned i = 0; i < 3; ++i) {
        if ((int64_t)times[i].tv_sec != want->seconds[i] || times[i].tv_nsec < 0 ||
            (uint64_t)times[i].tv_nsec != want->nanos[i]) fail("public-stat exact A/M/C");
        seconds[i] = (int64_t)times[i].tv_sec; nanos[i] = (uint32_t)times[i].tv_nsec;
    }
    emit(want, api, s->st_ino, s->st_mode, s->st_uid, s->st_gid, s->st_nlink,
         s->st_size, s->st_blocks, s->st_blksize, seconds, nanos,
         major(s->st_dev), minor(s->st_dev), major(s->st_rdev), minor(s->st_rdev));
}

static void check_statx(const struct expected_node *want, const char *api, const struct statx *s)
{
    /* Linux may return additional supported bits and mount-specific fields. */
    if ((s->stx_mask & STATX_BASIC_STATS) != STATX_BASIC_STATS || s->stx_ino != want->inode ||
        s->stx_mode != want->mode || s->stx_uid != want->uid || s->stx_gid != want->gid ||
        s->stx_nlink != want->links || s->stx_size != want->size || s->stx_blocks != want->blocks ||
        s->stx_blksize != want->blksize || s->stx_rdev_major || s->stx_rdev_minor ||
        s->stx_dev_major != device_major || s->stx_dev_minor != device_minor)
        fail(api);
    const struct statx_timestamp times[] = {s->stx_atime, s->stx_mtime, s->stx_ctime};
    int64_t seconds[3]; uint32_t nanos[3];
    for (unsigned i = 0; i < 3; ++i) {
        if (times[i].tv_sec != want->seconds[i] || times[i].tv_nsec != want->nanos[i])
            fail("raw-statx exact A/M/C");
        seconds[i] = times[i].tv_sec; nanos[i] = times[i].tv_nsec;
    }
    emit(want, api, s->stx_ino, s->stx_mode, s->stx_uid, s->stx_gid, s->stx_nlink,
         s->stx_size, s->stx_blocks, s->stx_blksize, seconds, nanos,
         s->stx_dev_major, s->stx_dev_minor, s->stx_rdev_major, s->stx_rdev_minor);
}

static void raw_record(const char *name, const struct statx *value)
{
    const unsigned char *bytes = (const unsigned char *)value;
    printf("LINUX_STAT_REFERENCE_STATX name=%s hex=", name);
    for (unsigned i = 0; i < sizeof *value; ++i) printf("%02x", bytes[i]);
    putchar('\n');
}

int main(void)
{
    mkdir("/dev", 0755);
    mount("devtmpfs", "/dev", "devtmpfs", 0, "");
    mknod("/dev/console", S_IFCHR | 0600, makedev(5, 1));
    int console = open("/dev/console", O_RDWR);
    if (console >= 0) { dup2(console, 0); dup2(console, 1); dup2(console, 2); }
    setvbuf(stdout, NULL, _IONBF, 0);
    struct utsname version;
    if (uname(&version)) fail("uname");
    printf("LINUX_STAT_REFERENCE_BEGIN release=%s version=%s machine=%s\n",
           version.release, version.version, version.machine);
    for (unsigned i = 0; access("/dev/vda", F_OK) && i < 100; ++i) usleep(50000);
    struct stat block_device;
    if (stat("/dev/vda", &block_device) || !S_ISBLK(block_device.st_mode)) fail("block-device identity");
    device_major = major(block_device.st_rdev); device_minor = minor(block_device.st_rdev);
    if (!device_major && !device_minor) fail("zero block-device identity");
    mkdir("/mnt", 0755);
    if (mount("/dev/vda", "/mnt", "ext4", MS_RDONLY | MS_NOSUID | MS_NODEV | MS_NOEXEC, "noload"))
        fail("readonly noload mount");
    struct statvfs mounted;
    if (statvfs("/mnt", &mounted) || !(mounted.f_flag & ST_RDONLY)) fail("readonly mount flags");
    printf("LINUX_STAT_REFERENCE_DEVICE dev_major=%u dev_minor=%u source=virtio-block-rdev\n",
           device_major, device_minor);
    int home = open("/mnt/home", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (home < 0) fail("home directory");
    for (unsigned i = 0; i < sizeof expected / sizeof expected[0]; ++i) {
        const struct expected_node *want = &expected[i];
        struct stat s;
        if (lstat(want->path, &s)) fail("lstat");
        check_stat(want, "lstat", &s);
        if (fstatat(home, want->relative, &s, AT_SYMLINK_NOFOLLOW)) fail("fstatat");
        check_stat(want, "fstatat", &s);
        int fd = openat(home, want->relative, O_PATH | O_NOFOLLOW | O_CLOEXEC);
        if (fd < 0 || fstat(fd, &s)) fail("held O_PATH fstat");
        check_stat(want, "fstat", &s);
        struct statx x;
        memset(&x, 0xa5, sizeof x);
        if (syscall(SYS_statx, home, want->relative, AT_SYMLINK_NOFOLLOW, STATX_BASIC_STATS, &x))
            fail("raw pathname statx");
        check_statx(want, "statx", &x); raw_record(want->name, &x);
        memset(&x, 0xa5, sizeof x);
        if (syscall(SYS_statx, fd, "", AT_EMPTY_PATH | AT_SYMLINK_NOFOLLOW, STATX_BASIC_STATS, &x))
            fail("raw held statx");
        check_statx(want, "statx-fd", &x);
        if (close(fd)) fail("close held descriptor");
    }
    if (close(home) || umount("/mnt")) fail("readonly unmount");
    printf("LINUX_STAT_REFERENCE_PASS nodes=%u observations=%u snapshots=%u mount=readonly-noload\n",
           (unsigned)(sizeof expected / sizeof expected[0]), observations,
           (unsigned)(sizeof expected / sizeof expected[0]));
    for (;;) pause();
}

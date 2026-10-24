#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <time.h>
#include <unistd.h>
#include "../stat_fixture.h"
#include "../stat_probe_log.h"

/* These assertions are compiled by each actual target's musl headers. */
_Static_assert(sizeof(struct statx) == 256, "Linux statx wire size");
_Static_assert(sizeof(struct statx_timestamp) == 16, "Linux statx time size");
_Static_assert(offsetof(struct statx, stx_mask) == 0, "statx mask");
_Static_assert(offsetof(struct statx, stx_blksize) == 4, "statx block size");
_Static_assert(offsetof(struct statx, stx_attributes) == 8, "statx attributes");
_Static_assert(offsetof(struct statx, stx_nlink) == 16, "statx links");
_Static_assert(offsetof(struct statx, stx_uid) == 20, "statx uid");
_Static_assert(offsetof(struct statx, stx_gid) == 24, "statx gid");
_Static_assert(offsetof(struct statx, stx_mode) == 28, "statx mode");
_Static_assert(offsetof(struct statx, stx_ino) == 32, "statx inode");
_Static_assert(offsetof(struct statx, stx_size) == 40, "statx size");
_Static_assert(offsetof(struct statx, stx_blocks) == 48, "statx blocks");
_Static_assert(offsetof(struct statx, stx_attributes_mask) == 56, "statx attribute mask");
_Static_assert(offsetof(struct statx, stx_atime) == 64, "statx atime");
_Static_assert(offsetof(struct statx, stx_btime) == 80, "statx btime");
_Static_assert(offsetof(struct statx, stx_ctime) == 96, "statx ctime");
_Static_assert(offsetof(struct statx, stx_mtime) == 112, "statx mtime");
_Static_assert(offsetof(struct statx, stx_rdev_major) == 128, "statx rdev");
_Static_assert(offsetof(struct statx, stx_dev_major) == 136, "statx dev");
_Static_assert(sizeof(time_t) == 8 && sizeof(off_t) == 8 && sizeof(blkcnt_t) == 8,
               "musl signed64 consumers");

static unsigned checks;
static int64_t epoch_start, fixture_end;
/* Avoid the unrelated MIPS64 quad-float printf runtime dependency. */
static void emit_text(const char *text)
{
    size_t left = strlen(text);
    while (left) {
        ssize_t wrote = write(1, text, left);
        if (wrote < 0 && errno == EINTR) continue;
        if (wrote <= 0) _Exit(2);
        text += wrote;
        left -= (size_t)wrote;
    }
}
static void emit_unsigned(unsigned value)
{
    char buffer[16];
    unsigned end = sizeof buffer - 1;
    buffer[end] = 0;
    do { buffer[--end] = (char)('0' + value % 10); value /= 10; } while (value);
    emit_text(buffer + end);
}
static void fail(int line)
{
    const unsigned error = (unsigned)errno;
    emit_text("LINUX_STAT_MUSL_FAIL line="); emit_unsigned((unsigned)line);
    emit_text(" errno="); emit_unsigned(error);
    emit_text(" checks="); emit_unsigned(checks); emit_text("\n");
    exit(1);
}
#define CHECK(x) do { ++checks; if (!(x)) fail(__LINE__); } while (0)

static int filled(const void *memory, size_t size, unsigned char value)
{
    const unsigned char *bytes = memory;
    for (size_t i = 0; i < size; ++i) if (bytes[i] != value) return 0;
    return 1;
}

/* Use musl's syscall trampoline, including the MIPS O32 fifth stack argument. */
static long raw_statx(int fd, const char *path, unsigned flags, unsigned mask, void *out)
{
    return syscall(SYS_statx, (long)fd, (long)path, (long)flags, (long)mask, (long)out);
}

static void qualified(const struct statx *s)
{
    struct timespec now;
    CHECK(clock_gettime(CLOCK_REALTIME, &now) == 0);
    CHECK(s->stx_mask == STAT_BASIC_MASK && s->stx_ino != 0);
    CHECK(s->stx_dev_major != 0 || s->stx_dev_minor != 0);
    CHECK(s->stx_uid == 1000 && s->stx_gid == 1000);
    CHECK(s->stx_size <= INT64_MAX && s->stx_blocks <= INT64_MAX);
    CHECK(s->stx_blksize == 1024 || s->stx_blksize == 2048 || s->stx_blksize == 4096);
    CHECK(s->stx_blocks % (s->stx_blksize / 512) == 0);
    CHECK(S_ISREG(s->stx_mode) || S_ISDIR(s->stx_mode) || S_ISLNK(s->stx_mode));
    const struct statx_timestamp *times[] = {&s->stx_atime, &s->stx_mtime, &s->stx_ctime};
    for (unsigned i = 0; i < 3; ++i) {
        CHECK(times[i]->tv_sec >= epoch_start && times[i]->tv_sec <= now.tv_sec);
        CHECK(times[i]->tv_nsec < 1000000000U && times[i]->__pad == 0);
    }
    CHECK(s->stx_attributes == 0 && s->stx_attributes_mask == 0);
    CHECK(s->stx_rdev_major == 0 && s->stx_rdev_minor == 0);
    CHECK(filled(&s->stx_btime, sizeof s->stx_btime, 0));
    CHECK(filled((const unsigned char *)s + 30, 2, 0));
    CHECK(filled((const unsigned char *)s + 144, 112, 0));
}

static struct statx query(int fd, const char *path, unsigned flags, unsigned mask)
{
    struct { unsigned char before[32]; struct statx value; unsigned char after[32]; } guarded;
    memset(&guarded, 0xa5, sizeof guarded);
    CHECK(raw_statx(fd, path, flags, mask, &guarded.value) == 0);
    CHECK(filled(guarded.before, sizeof guarded.before, 0xa5));
    CHECK(filled(guarded.after, sizeof guarded.after, 0xa5));
    qualified(&guarded.value);
    return guarded.value;
}

static void rejected(int fd, const char *path, unsigned flags, unsigned mask, int expected)
{
    unsigned char guarded[320];
    memset(guarded, 0xa5, sizeof guarded);
    errno = 0;
    CHECK(raw_statx(fd, path, flags, mask, guarded + 32) == -1 && errno == expected);
    CHECK(filled(guarded, sizeof guarded, 0xa5));
}

static void equal_public(const struct stat *s, const struct statx *x)
{
    CHECK((uint64_t)s->st_ino == x->stx_ino && (uint32_t)s->st_mode == x->stx_mode);
    CHECK((uint64_t)s->st_nlink == x->stx_nlink && s->st_uid == x->stx_uid && s->st_gid == x->stx_gid);
    CHECK((uint64_t)s->st_size == x->stx_size && (uint64_t)s->st_blocks == x->stx_blocks);
    CHECK((uint64_t)s->st_blksize == x->stx_blksize && s->st_rdev == 0);
    CHECK(major(s->st_dev) == x->stx_dev_major && minor(s->st_dev) == x->stx_dev_minor);
    CHECK(s->st_atim.tv_sec == x->stx_atime.tv_sec && (int64_t)s->st_atim.tv_nsec == (int64_t)x->stx_atime.tv_nsec);
    CHECK(s->st_mtim.tv_sec == x->stx_mtime.tv_sec && (int64_t)s->st_mtim.tv_nsec == (int64_t)x->stx_mtime.tv_nsec);
    CHECK(s->st_ctim.tv_sec == x->stx_ctime.tv_sec && (int64_t)s->st_ctim.tv_nsec == (int64_t)x->stx_ctime.tv_nsec);
}

static void public_calls(void)
{
    struct stat s;
    struct statx file = query(AT_FDCWD, STAT_FILE, 0, STAT_BASIC_MASK);
    CHECK(file.stx_size == STAT_CONTENT_SIZE && file.stx_nlink == 2);
    CHECK(file.stx_blocks == file.stx_blksize / 512 && (file.stx_mode & 07777) == 0600);
    CHECK(file.stx_mtime.tv_sec <= fixture_end && file.stx_ctime.tv_sec <= fixture_end);
    CHECK(stat(STAT_FILE, &s) == 0); equal_public(&s, &file);
    CHECK(lstat(STAT_FILE, &s) == 0); equal_public(&s, &file);
    CHECK(stat(STAT_ALIAS, &s) == 0); equal_public(&s, &file);
    CHECK(stat(STAT_LINK, &s) == 0); equal_public(&s, &file);
    CHECK(fstatat(-1, STAT_FILE, &s, 0) == 0); equal_public(&s, &file);
    int fd = open(STAT_FILE, O_RDONLY);
    CHECK(fd >= 0 && fstat(fd, &s) == 0); equal_public(&s, &file);
    CHECK(fstatat(fd, "", &s, STAT_EMPTY_PATH) == 0); equal_public(&s, &file);
    CHECK(close(fd) == 0);

    struct statx link = query(AT_FDCWD, STAT_LINK, AT_SYMLINK_NOFOLLOW, STAT_BASIC_MASK);
    CHECK(S_ISLNK(link.stx_mode) && link.stx_size == strlen("stat-file") && link.stx_blocks == 0);
    CHECK(lstat(STAT_LINK, &s) == 0); equal_public(&s, &link);
    CHECK(fstatat(AT_FDCWD, STAT_LINK, &s, AT_SYMLINK_NOFOLLOW) == 0); equal_public(&s, &link);
    struct statx dangling = query(AT_FDCWD, STAT_DANGLING, AT_SYMLINK_NOFOLLOW, STAT_BASIC_MASK);
    CHECK(S_ISLNK(dangling.stx_mode) && dangling.stx_size == strlen("stat-missing"));
    CHECK(lstat(STAT_DANGLING, &s) == 0); equal_public(&s, &dangling);
    CHECK(stat(STAT_DANGLING, &s) == -1 && errno == ENOENT);

    struct statx held = query(STAT_HELD_FD, "", STAT_EMPTY_PATH, STAT_BASIC_MASK);
    CHECK(S_ISREG(held.stx_mode) && held.stx_nlink == 0 && held.stx_size == STAT_CONTENT_SIZE);
    CHECK(held.stx_blocks == held.stx_blksize / 512);
    CHECK(fstat(STAT_HELD_FD, &s) == 0); equal_public(&s, &held);
    struct statx null_held = query(STAT_HELD_FD, 0, STAT_EMPTY_PATH | AT_SYMLINK_NOFOLLOW, 0);
    CHECK(!memcmp(&held, &null_held, sizeof held));

    struct statx directory = query(STAT_DIR_FD, "", STAT_EMPTY_PATH, STAT_BASIC_MASK);
    CHECK(S_ISDIR(directory.stx_mode));
    CHECK(stat(STAT_DIR, &s) == 0); equal_public(&s, &directory);
    CHECK(fstat(STAT_DIR_FD, &s) == 0); equal_public(&s, &directory);
    struct statx child = query(STAT_DIR_FD, "child", 0, STAT_BASIC_MASK);
    CHECK(fstatat(STAT_DIR_FD, "child", &s, 0) == 0); equal_public(&s, &child);
    struct statx cwd = query(AT_FDCWD, "", STAT_EMPTY_PATH, STAT_BASIC_MASK);
    struct statx null_cwd = query(AT_FDCWD, 0, STAT_EMPTY_PATH, STAT_BASIC_MASK);
    CHECK(S_ISDIR(cwd.stx_mode) && cwd.stx_nlink == 0 && cwd.stx_ino != directory.stx_ino);
    CHECK(!memcmp(&cwd, &null_cwd, sizeof cwd));
    CHECK(fstatat(AT_FDCWD, "", &s, STAT_EMPTY_PATH) == 0); equal_public(&s, &cwd);

    struct statx empty = query(AT_FDCWD, STAT_EMPTY, 0, 0);
    struct statx hole = query(AT_FDCWD, STAT_HOLE, 0, STAT_BASIC_MASK);
    CHECK(empty.stx_size == 0 && empty.stx_blocks == 0);
    CHECK(hole.stx_size == STAT_HOLE_SIZE && hole.stx_blocks == 0);
    CHECK(stat(STAT_HOLE, &s) == 0); equal_public(&s, &hole);

    int duplicate = dup(STAT_DIR_FD);
    CHECK(duplicate >= 0);
    DIR *stream = fdopendir(duplicate);
    CHECK(stream != 0 && dirfd(stream) == duplicate);
    unsigned found_child = 0, count = 0;
    struct dirent *entry;
    errno = 0;
    while ((entry = readdir(stream)) != 0) {
        ++count;
        CHECK(count <= 16);
        if (!strcmp(entry->d_name, "child")) { ++found_child; CHECK(entry->d_ino == child.stx_ino); }
    }
    CHECK(errno == 0 && found_child == 1 && closedir(stream) == 0);
    CHECK(fstat(STAT_DIR_FD, &s) == 0);
    CHECK((uint64_t)s.st_ino == directory.stx_ino && S_ISDIR(s.st_mode));

    memset(&s, 0xa5, sizeof s);
    CHECK(fstat(-1, &s) == -1 && errno == EBADF && filled(&s, sizeof s, 0xa5));
    CHECK(fstat(1, &s) == -1 && errno == EOPNOTSUPP && filled(&s, sizeof s, 0xa5));
    CHECK(stat(STAT_MISSING, &s) == -1 && errno == ENOENT && filled(&s, sizeof s, 0xa5));
    puts("LINUX_STAT_MUSL_PUBLIC_PASS stat=pass lstat=pass fstat=pass fstatat=pass fdopendir=pass");
}

static void flags_and_order(void)
{
    struct statx baseline = query(STAT_HELD_FD, "", STAT_EMPTY_PATH, STAT_BASIC_MASK);
    const unsigned flags[] = {0, STAT_NO_AUTOMOUNT, STAT_FORCE_SYNC, STAT_DONT_SYNC,
        AT_SYMLINK_NOFOLLOW, STAT_NO_AUTOMOUNT | AT_SYMLINK_NOFOLLOW,
        STAT_FORCE_SYNC | STAT_NO_AUTOMOUNT, STAT_DONT_SYNC | AT_SYMLINK_NOFOLLOW};
    const unsigned masks[] = {0, 1, STAT_BASIC_MASK, 0x40000000U, 0x7fffffffU};
    for (unsigned f = 0; f < sizeof flags / sizeof flags[0]; ++f)
        for (unsigned m = 0; m < sizeof masks / sizeof masks[0]; ++m) {
            struct statx got = query(STAT_HELD_FD, "", flags[f] | STAT_EMPTY_PATH, masks[m]);
            CHECK(!memcmp(&got, &baseline, sizeof got));
        }
    struct statx absolute = query(-1, STAT_FILE, 0, STAT_BASIC_MASK);
    CHECK(absolute.stx_size == STAT_CONTENT_SIZE);
    rejected(-1, (const char *)1, 1U, STAT_BASIC_MASK, EINVAL);
    rejected(-1, (const char *)1, STAT_FORCE_SYNC | STAT_DONT_SYNC, 0, EINVAL);
    rejected(-1, (const char *)1, 0, 0x80000000U, EINVAL);
    rejected(STAT_HELD_FD, "", STAT_EMPTY_PATH | 1U, 0, EINVAL);
    rejected(STAT_HELD_FD, 0, STAT_EMPTY_PATH | 1U, 0, EINVAL);
    rejected(AT_FDCWD, 0, 0, 0, EFAULT);
    rejected(AT_FDCWD, "", 0, 0, ENOENT);
    rejected(-1, (const char *)1, 0, 0, EFAULT);
    rejected(-1, "child", 0, 0, EBADF);
    rejected(STAT_HELD_FD, "child", 0, 0, ENOTDIR);
    rejected(-1, "", STAT_EMPTY_PATH, 0, EBADF);
    rejected(-1, 0, STAT_EMPTY_PATH, 0, EBADF);
    rejected(AT_FDCWD, STAT_MISSING, 0, 0, ENOENT);
    rejected(AT_FDCWD, STAT_HELD_PATH, 0, 0, ENOENT);
    rejected(AT_FDCWD, STAT_DIR_OLD, 0, 0, ENOENT);
    rejected(AT_FDCWD, STAT_CWD, 0, 0, ENOENT);
    rejected(AT_FDCWD, STAT_FILE "/", 0, 0, ENOTDIR);
    rejected(AT_FDCWD, STAT_LINK "/", AT_SYMLINK_NOFOLLOW, 0, ENOTDIR);
    rejected(AT_FDCWD, STAT_DANGLING "/", AT_SYMLINK_NOFOLLOW, 0, ENOENT);
    rejected(AT_FDCWD, STAT_DANGLING, 0, 0, ENOENT);
    rejected(AT_FDCWD, STAT_LOOP, 0, 0, ELOOP);
    rejected(1, "", STAT_EMPTY_PATH, 0, EOPNOTSUPP);

    CHECK(raw_statx(-1, (const char *)1, 1U, 0, (void *)1) == -1 && errno == EINVAL);
    CHECK(raw_statx(-1, "child", 0, 0, (void *)1) == -1 && errno == EBADF);
    CHECK(raw_statx(STAT_HELD_FD, "child", 0, 0, (void *)1) == -1 && errno == ENOTDIR);
    CHECK(raw_statx(AT_FDCWD, STAT_MISSING, 0, 0, (void *)1) == -1 && errno == ENOENT);
    CHECK(raw_statx(AT_FDCWD, STAT_LOOP, 0, 0, (void *)1) == -1 && errno == ELOOP);
    CHECK(raw_statx(1, "", STAT_EMPTY_PATH, 0, (void *)1) == -1 && errno == EOPNOTSUPP);
    CHECK(raw_statx(STAT_HELD_FD, "", STAT_EMPTY_PATH, 0, (void *)1) == -1 && errno == EFAULT);
    puts("LINUX_STAT_MUSL_ORDER_PASS policy=bounded-uniform flags=pass mask=pass late-copy=pass");
}

static void page_boundaries(void)
{
    unsigned char *pages = mmap(0, 2 * STAT_PAGE_SIZE, PROT_READ | PROT_WRITE,
                                MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK(pages != MAP_FAILED && mprotect(pages + STAT_PAGE_SIZE, STAT_PAGE_SIZE, PROT_NONE) == 0);
    char *edge_name = (char *)pages + STAT_PAGE_SIZE - sizeof STAT_FILE;
    memcpy(edge_name, STAT_FILE, sizeof STAT_FILE);
    struct statx value = query(-1, edge_name, 0, 0);
    CHECK(value.stx_size == STAT_CONTENT_SIZE);
    pages[STAT_PAGE_SIZE - 1] = 0;
    value = query(STAT_HELD_FD, (char *)pages + STAT_PAGE_SIZE - 1, STAT_EMPTY_PATH, 0);
    CHECK(value.stx_nlink == 0);
    pages[STAT_PAGE_SIZE - 1] = 'a';
    rejected(AT_FDCWD, (char *)pages + STAT_PAGE_SIZE - 1, 0, 0, EFAULT);
    rejected(AT_FDCWD, (char *)pages + STAT_PAGE_SIZE, 0, 0, EFAULT);
    memset(pages, 'a', 256);
    rejected(-1, (char *)pages, 0, 0, ENAMETOOLONG);

    memset(pages, 0xa5, STAT_PAGE_SIZE);
    unsigned char *edge_out = pages + STAT_PAGE_SIZE - sizeof(struct statx);
    CHECK(raw_statx(STAT_HELD_FD, "", STAT_EMPTY_PATH, 0, edge_out) == 0);
    memcpy(&value, edge_out, sizeof value); qualified(&value);
    CHECK(filled(pages, STAT_PAGE_SIZE - sizeof value, 0xa5));
    memset(pages, 0xa5, STAT_PAGE_SIZE);
    CHECK(raw_statx(STAT_HELD_FD, "", STAT_EMPTY_PATH, 0, edge_out + 1) == -1 && errno == EFAULT);
    CHECK(filled(pages, STAT_PAGE_SIZE, 0xa5));
    CHECK(raw_statx(AT_FDCWD, STAT_MISSING, 0, 0, edge_out + 1) == -1 && errno == ENOENT);
    CHECK(filled(pages, STAT_PAGE_SIZE, 0xa5));
    CHECK(mprotect(pages, STAT_PAGE_SIZE, PROT_READ) == 0);
    CHECK(raw_statx(STAT_HELD_FD, "", STAT_EMPTY_PATH, 0, edge_out) == -1 && errno == EFAULT);
    CHECK(filled(pages, STAT_PAGE_SIZE, 0xa5));
    CHECK(raw_statx(STAT_HELD_FD, "", STAT_EMPTY_PATH, 0,
                     (void *)(uintptr_t)(UINTPTR_MAX - 127)) == -1 && errno == EFAULT);
    CHECK(raw_statx(STAT_HELD_FD, "", STAT_EMPTY_PATH, 0, 0) == -1 && errno == EFAULT);
    CHECK(munmap(pages, 2 * STAT_PAGE_SIZE) == 0);
    puts("LINUX_STAT_MUSL_PAGES_PASS path-edge=pass output-edge=pass readonly=pass wrap=pass");
}

#if defined(__x86_64__) || defined(__aarch64__) || (defined(__riscv) && __riscv_xlen == 64)
#define HAS_KERNEL_STAT 1
#if defined(__x86_64__)
#define KERNEL_STAT_SIZE 144
#else
#define KERNEL_STAT_SIZE 128
#endif
static uint64_t word64(const unsigned char *p) { uint64_t v; memcpy(&v, p, sizeof v); return v; }
static uint32_t word32(const unsigned char *p) { uint32_t v; memcpy(&v, p, sizeof v); return v; }
static void kernel_stat_equal(const unsigned char *raw, const struct statx *s)
{
    uint64_t dev = (s->stx_dev_minor & 255U) | ((uint64_t)s->stx_dev_major << 8) |
                   ((uint64_t)(s->stx_dev_minor & ~255U) << 12);
    CHECK(word64(raw) == dev && word64(raw + 8) == s->stx_ino);
#if defined(__x86_64__)
    CHECK(word64(raw + 16) == s->stx_nlink && word32(raw + 24) == s->stx_mode);
    CHECK(word32(raw + 28) == s->stx_uid && word32(raw + 32) == s->stx_gid);
    CHECK(word64(raw + 56) == s->stx_blksize && filled(raw + 36, 4, 0));
#else
    CHECK(word32(raw + 16) == s->stx_mode && word32(raw + 20) == s->stx_nlink);
    CHECK(word32(raw + 24) == s->stx_uid && word32(raw + 28) == s->stx_gid);
    CHECK(word32(raw + 56) == s->stx_blksize && filled(raw + 32, 8, 0) && filled(raw + 60, 4, 0));
#endif
    CHECK(word64(raw + 40) == 0 && word64(raw + 48) == s->stx_size && word64(raw + 64) == s->stx_blocks);
    CHECK((int64_t)word64(raw + 72) == s->stx_atime.tv_sec && word64(raw + 80) == s->stx_atime.tv_nsec);
    CHECK((int64_t)word64(raw + 88) == s->stx_mtime.tv_sec && word64(raw + 96) == s->stx_mtime.tv_nsec);
    CHECK((int64_t)word64(raw + 104) == s->stx_ctime.tv_sec && word64(raw + 112) == s->stx_ctime.tv_nsec);
    CHECK(filled(raw + 120, KERNEL_STAT_SIZE - 120, 0));
}

static void raw_kernel_stat(void)
{
    unsigned char guarded[KERNEL_STAT_SIZE + 64];
    unsigned char *raw = guarded + 32;
    struct statx held = query(STAT_HELD_FD, "", STAT_EMPTY_PATH, 0);
    memset(guarded, 0xa5, sizeof guarded);
    CHECK(syscall(SYS_fstat, (long)STAT_HELD_FD, (long)raw) == 0);
    kernel_stat_equal(raw, &held);
    CHECK(filled(guarded, 32, 0xa5) && filled(raw + KERNEL_STAT_SIZE, 32, 0xa5));
    struct statx cwd = query(AT_FDCWD, "", STAT_EMPTY_PATH, 0);
    CHECK(syscall(SYS_newfstatat, (long)AT_FDCWD, 0L, (long)raw, (long)STAT_EMPTY_PATH) == 0);
    kernel_stat_equal(raw, &cwd);
    CHECK(syscall(SYS_newfstatat, (long)STAT_HELD_FD, 0L, (long)raw, (long)STAT_EMPTY_PATH) == 0);
    kernel_stat_equal(raw, &held);
#if defined(__x86_64__)
    struct statx file = query(AT_FDCWD, STAT_FILE, 0, 0);
    CHECK(syscall(SYS_stat, (long)STAT_FILE, (long)raw) == 0); kernel_stat_equal(raw, &file);
    struct statx link = query(AT_FDCWD, STAT_LINK, AT_SYMLINK_NOFOLLOW, 0);
    CHECK(syscall(SYS_lstat, (long)STAT_LINK, (long)raw) == 0); kernel_stat_equal(raw, &link);
#endif
    memset(guarded, 0xa5, sizeof guarded);
    CHECK(syscall(SYS_fstat, -1L, (long)raw) == -1 && errno == EBADF);
    CHECK(filled(guarded, sizeof guarded, 0xa5));
    CHECK(syscall(SYS_fstat, 1L, (long)raw) == -1 && errno == EOPNOTSUPP);
    CHECK(filled(guarded, sizeof guarded, 0xa5));
    CHECK(syscall(SYS_newfstatat, -1L, 1L, (long)raw, 1L) == -1 && errno == EINVAL);
    CHECK(filled(guarded, sizeof guarded, 0xa5));
    CHECK(syscall(SYS_newfstatat, (long)STAT_HELD_FD, (long)"", (long)raw,
                  (long)(STAT_EMPTY_PATH | STAT_FORCE_SYNC)) == -1 && errno == EINVAL);
    CHECK(filled(guarded, sizeof guarded, 0xa5));
    CHECK(syscall(SYS_newfstatat, (long)AT_FDCWD, (long)STAT_MISSING, 1L, 0L) == -1 && errno == ENOENT);
    CHECK(syscall(SYS_fstat, -1L, 1L) == -1 && errno == EBADF);
    unsigned char *pages = mmap(0, 2 * STAT_PAGE_SIZE, PROT_READ | PROT_WRITE,
                                MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    CHECK(pages != MAP_FAILED && mprotect(pages + STAT_PAGE_SIZE, STAT_PAGE_SIZE, PROT_NONE) == 0);
    unsigned char *edge = pages + STAT_PAGE_SIZE - KERNEL_STAT_SIZE;
    memset(pages, 0xa5, STAT_PAGE_SIZE);
    CHECK(syscall(SYS_fstat, (long)STAT_HELD_FD, (long)edge) == 0);
    kernel_stat_equal(edge, &held);
    CHECK(filled(pages, STAT_PAGE_SIZE - KERNEL_STAT_SIZE, 0xa5));
    memset(pages, 0xa5, STAT_PAGE_SIZE);
    CHECK(syscall(SYS_fstat, (long)STAT_HELD_FD, (long)(edge + 1)) == -1 && errno == EFAULT);
    CHECK(filled(pages, STAT_PAGE_SIZE, 0xa5));
    CHECK(syscall(SYS_newfstatat, (long)AT_FDCWD, (long)STAT_MISSING, (long)(edge + 1), 0L) == -1 && errno == ENOENT);
    CHECK(filled(pages, STAT_PAGE_SIZE, 0xa5));
    CHECK(mprotect(pages, STAT_PAGE_SIZE, PROT_READ) == 0);
    CHECK(syscall(SYS_fstat, (long)STAT_HELD_FD, (long)edge) == -1 && errno == EFAULT);
    CHECK(filled(pages, STAT_PAGE_SIZE, 0xa5));
    CHECK(syscall(SYS_fstat, (long)STAT_HELD_FD, (long)(uintptr_t)(UINTPTR_MAX - 63)) == -1 && errno == EFAULT);
    CHECK(munmap(pages, 2 * STAT_PAGE_SIZE) == 0);
    puts("LINUX_STAT_MUSL_LEGACY_PASS route=qualified-kernel-stat");
}
#else
#define HAS_KERNEL_STAT 0
static void raw_kernel_stat(void)
{
    /* Unsupported historical layouts must not become accidental libc fallbacks. */
#ifdef SYS_fstat
    unsigned char guarded[256];
    memset(guarded, 0xa5, sizeof guarded);
    CHECK(syscall(SYS_fstat, (long)STAT_HELD_FD, (long)guarded) == -1 && errno == ENOSYS);
    CHECK(filled(guarded, sizeof guarded, 0xa5));
#endif
    puts("LINUX_STAT_MUSL_LEGACY_PASS route=statx-only legacy=unavailable");
}
#endif

static void final_snapshots(void)
{
    const char *labels[] = {"file", "alias", "link", "dangling", "loop", "empty", "hole", "directory", "child"};
    const char *paths[] = {STAT_FILE, STAT_ALIAS, STAT_LINK, STAT_DANGLING, STAT_LOOP,
                          STAT_EMPTY, STAT_HOLE, STAT_DIR, STAT_DIR "/child"};
    for (unsigned i = 0; i < sizeof labels / sizeof labels[0]; ++i) {
        struct statx snapshot = query(AT_FDCWD, paths[i], AT_SYMLINK_NOFOLLOW, STAT_BASIC_MASK);
        stat_probe_snapshot(labels[i], &snapshot);
    }
}

int main(int argc, char **argv)
{
    CHECK(argc == 3);
    char *end;
    epoch_start = strtoll(argv[1], &end, 10); CHECK(*end == 0);
    fixture_end = strtoll(argv[2], &end, 10); CHECK(*end == 0 && fixture_end >= epoch_start);
    CHECK(epoch_start > INT32_MAX || epoch_start < 0);
    CHECK(getuid() == 1000 && geteuid() == 1000 && getgid() == 1000 && getegid() == 1000);
    public_calls();
    flags_and_order();
    page_boundaries();
    raw_kernel_stat();
    final_snapshots();
    CHECK(close(STAT_HELD_FD) == 0 && close(STAT_DIR_FD) == 0);
    emit_text("LINUX_STAT_MUSL_PASS checks="); emit_unsigned(checks);
    emit_text(epoch_start < 0 ? " epoch=negative" : " epoch=post2038");
    emit_text(" kernel-stat="); emit_unsigned(HAS_KERNEL_STAT);
    emit_text(" statx-size="); emit_unsigned((unsigned)sizeof(struct statx)); emit_text("\n");
    return 0;
}

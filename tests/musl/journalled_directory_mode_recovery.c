#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
#include "../chmod_probe_log.h"

static unsigned checks;
static void fail(unsigned line)
{
    chmod_probe_text("JDREC_USER_FAIL line="); chmod_probe_unsigned(line);
    chmod_probe_text(" errno="); chmod_probe_unsigned((unsigned)errno);
    chmod_probe_text(" checks="); chmod_probe_unsigned(checks); chmod_probe_text("\n");
    _Exit(1);
}
#define CHECK(x) do { ++checks; if (!(x)) fail(__LINE__); } while (0)
_Static_assert(sizeof(struct statx) == 256, "statx wire size");
_Static_assert(sizeof(time_t) == 8, "musl time64 required");
static struct statx query(int fd, const char *path, unsigned flags)
{
    struct statx value;
    memset(&value, 0xa5, sizeof value);
    CHECK(syscall(SYS_statx, (long)fd, (long)path, (long)flags,
                  (long)STATX_BASIC_STATS, (long)&value) == 0);
    CHECK(value.stx_mask == STATX_BASIC_STATS && value.stx_blksize == 1024);
    return value;
}
struct expected_entry { const char *name; unsigned inode, type; };
static void entries(int fd, const struct expected_entry *expected, unsigned count)
{
    int copy = dup(fd); CHECK(copy >= 0);
    CHECK(lseek(copy, 0, SEEK_SET) == 0);
    DIR *directory = fdopendir(copy); CHECK(directory != NULL);
    unsigned seen = 0;
    struct dirent *entry;
    errno = 0;
    while ((entry = readdir(directory)))
    {
        unsigned index = 0;
        while (index < count && strcmp(entry->d_name, expected[index].name)) ++index;
        CHECK(index < count && !(seen & (1u << index)) &&
              entry->d_ino == expected[index].inode && entry->d_type == expected[index].type);
        seen |= 1u << index;
    }
    CHECK(errno == 0 && seen == (1u << count) - 1);
    CHECK(closedir(directory) == 0);
}
int main(void)
{
    CHECK(getuid() == 1000 && geteuid() == 1000 && getgid() == 1000 && getegid() == 1000);
    chmod_probe_text("JDREC_USER_BEGIN uid=1000 scope=actual-musl-syscalls\n");
    struct statx child = query(AT_FDCWD, "/journal/child", 0);
    CHECK(child.stx_ino == 14 && child.stx_uid == 1000 && child.stx_gid == 1000 && child.stx_nlink == 2);
    CHECK(child.stx_mode == (S_IFDIR | 0755) || child.stx_mode == (S_IFDIR | 02750));
    CHECK(child.stx_size == 1024 && child.stx_blocks == 2);
    /* The outer collector binds the complete old/new metadata to the selected cut. */
    struct statx alias = query(AT_FDCWD, "/alias/child", 0);
    CHECK(memcmp(&child, &alias, sizeof child) == 0);
    int child_fd = open("/journal/child", O_RDONLY | O_DIRECTORY | O_CLOEXEC); CHECK(child_fd >= 0);
    struct statx opened = query(child_fd, "", AT_EMPTY_PATH);
    CHECK(memcmp(&child, &opened, sizeof child) == 0);
    struct stat ordinary; CHECK(fstat(child_fd, &ordinary) == 0);
    CHECK((uint64_t)ordinary.st_ino == child.stx_ino && (unsigned)ordinary.st_mode == child.stx_mode &&
          ordinary.st_uid == child.stx_uid && ordinary.st_gid == child.stx_gid &&
          ordinary.st_nlink == child.stx_nlink && ordinary.st_size == 1024 && ordinary.st_blocks == 2);
    const struct expected_entry child_entries[] = {{".", 14, DT_DIR}, {"..", 2, DT_DIR}, {"leaf", 16, DT_REG}};
    const struct expected_entry root_entries[] = {{".", 2, DT_DIR}, {"..", 2, DT_DIR},
        {"lost+found", 11, DT_DIR}, {"seed", 12, DT_REG}, {"other-owner", 13, DT_REG},
        {"child", 14, DT_DIR}, {"seed-link", 15, DT_LNK}};
    entries(child_fd, child_entries, 3);
    int root_fd = open("/journal", O_RDONLY | O_DIRECTORY); CHECK(root_fd >= 0);
    entries(root_fd, root_entries, 7);
    int alias_root = open("/alias", O_RDONLY | O_DIRECTORY); CHECK(alias_root >= 0);
    entries(alias_root, root_entries, 7);
    CHECK(close(alias_root) == 0);
    struct statx root = query(root_fd, "", AT_EMPTY_PATH);
    alias = query(AT_FDCWD, "/alias", 0); CHECK(memcmp(&root, &alias, sizeof root) == 0);

    struct statx seed = query(AT_FDCWD, "/journal/seed", 0);
    CHECK(seed.stx_ino == 12 && seed.stx_uid == 1000 && seed.stx_gid == 1001 && seed.stx_nlink == 1);
    CHECK(seed.stx_mode == (S_IFREG | 0600));
    CHECK(seed.stx_size == 4096 && seed.stx_blocks == 8);
    alias = query(AT_FDCWD, "/alias/seed", 0); CHECK(memcmp(&seed, &alias, sizeof seed) == 0);
    int fd = openat(child_fd, "../seed", O_RDONLY | O_CLOEXEC); CHECK(fd >= 0);
    opened = query(fd, "", AT_EMPTY_PATH); CHECK(memcmp(&seed, &opened, sizeof seed) == 0);
    CHECK(fstat(fd, &ordinary) == 0);
    CHECK((uint64_t)ordinary.st_ino == seed.stx_ino && (unsigned)ordinary.st_mode == seed.stx_mode &&
          ordinary.st_uid == seed.stx_uid && ordinary.st_gid == seed.stx_gid &&
          ordinary.st_nlink == seed.stx_nlink && ordinary.st_size == 4096 && ordinary.st_blocks == 8);
    unsigned char bytes[257]; unsigned total = 0;
    for (;;) {
        ssize_t got = read(fd, bytes, sizeof bytes); CHECK(got >= 0);
        if (!got) break;
        CHECK((unsigned)got <= 4096 - total);
        for (unsigned i = 0; i < (unsigned)got; ++i)
            CHECK(bytes[i] == (unsigned char)((total + i) * 17 + 29));
        total += (unsigned)got;
    }
    CHECK(total == 4096 && lseek(fd, 0, SEEK_CUR) == 4096);
    opened = query(fd, "", AT_EMPTY_PATH); CHECK(memcmp(&seed, &opened, sizeof seed) == 0);
    struct statx other = query(AT_FDCWD, "/journal/other-owner", 0);
    CHECK(other.stx_ino == 13 && other.stx_mode == (S_IFREG | 0644) && other.stx_uid == 2000 && other.stx_gid == 2000);
    CHECK(other.stx_size == 29 && other.stx_blocks == 2 && other.stx_nlink == 1);
    int other_fd = open("/alias/other-owner", O_RDONLY); CHECK(other_fd >= 0);
    CHECK(read(other_fd, bytes, sizeof bytes) == 29 && memcmp(bytes, "other owner metadata fixture\n", 29) == 0);
    CHECK(read(other_fd, bytes, sizeof bytes) == 0 && close(other_fd) == 0);
    struct statx link = query(AT_FDCWD, "/journal/seed-link", AT_SYMLINK_NOFOLLOW);
    CHECK(link.stx_ino == 15 && link.stx_mode == (S_IFLNK | 0777) && link.stx_uid == 1000 && link.stx_gid == 1001 && link.stx_size == 4);
    char target[16]; CHECK(readlink("/alias/seed-link", target, sizeof target) == 4 && memcmp(target, "seed", 4) == 0);
    alias = query(AT_FDCWD, "/alias/seed-link", 0); CHECK(memcmp(&seed, &alias, sizeof seed) == 0);
    struct statx leaf = query(AT_FDCWD, "/journal/child/leaf", 0);
    CHECK(leaf.stx_ino == 16 && leaf.stx_mode == (S_IFREG | 0600) && leaf.stx_uid == 1000 &&
          leaf.stx_gid == 1000 && leaf.stx_size == 24 && leaf.stx_blocks == 2 && leaf.stx_nlink == 1);
    alias = query(AT_FDCWD, "/alias/child/leaf", 0); CHECK(memcmp(&leaf, &alias, sizeof leaf) == 0);
    int leaf_fd = openat(child_fd, "leaf", O_RDONLY); CHECK(leaf_fd >= 0);
    opened = query(leaf_fd, "", AT_EMPTY_PATH); CHECK(memcmp(&leaf, &opened, sizeof leaf) == 0);
    CHECK(read(leaf_fd, bytes, sizeof bytes) == 24 && memcmp(bytes, "directory child payload\n", 24) == 0);
    CHECK(read(leaf_fd, bytes, 1) == 0 && close(leaf_fd) == 0);
    chmod_probe_snapshot("directory-recovery-child", &child);
    chmod_probe_snapshot("directory-recovery-root", &root);
    chmod_probe_snapshot("directory-recovery-seed", &seed);
    chmod_probe_snapshot("directory-recovery-other", &other);
    chmod_probe_snapshot("directory-recovery-link", &link);
    chmod_probe_snapshot("directory-recovery-leaf", &leaf);
    chmod_probe_text("JDREC_FSYNC_BEGIN calls=2\n");
    CHECK(fsync(child_fd) == 0 && fsync(root_fd) == 0);
    chmod_probe_text("JDREC_FSYNC_END calls=2\n");
    opened = query(child_fd, "", AT_EMPTY_PATH); CHECK(memcmp(&child, &opened, sizeof child) == 0);
    CHECK(close(fd) == 0 && close(child_fd) == 0 && close(root_fd) == 0);
    chmod_probe_text("JDREC_USER_PASS uid=1000 bytes=4096 checks=");
    chmod_probe_unsigned(checks); chmod_probe_text("\n");
    return 0;
}

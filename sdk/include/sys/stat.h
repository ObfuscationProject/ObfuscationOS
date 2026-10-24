#ifndef _SYS_STAT_H
#define _SYS_STAT_H

#include <ok/uapi/syscall.h>
#include <sys/types.h>

struct stat {
    uint64_t st_ino;
    mode_t st_mode;
    unsigned int st_nlink;
    unsigned int st_uid;
    unsigned int st_gid;
    unsigned int st_rdev;
    off_t st_size;
    unsigned int st_blksize;
    unsigned int st_blocks;
    struct ok_timespec st_atim;
    struct ok_timespec st_mtim;
    struct ok_timespec st_ctim;
};

#define S_IFMT OK_MODE_TYPE_MASK
#define S_IFCHR OK_MODE_CHARACTER_DEVICE
#define S_IFREG OK_MODE_REGULAR
#define S_IFDIR OK_MODE_DIRECTORY
#define S_IFLNK OK_MODE_SYMLINK
#define S_IRUSR 0400
#define S_IWUSR 0200
#define S_IXUSR 0100
#define S_IRGRP 0040
#define S_IWGRP 0020
#define S_IXGRP 0010
#define S_IROTH 0004
#define S_IWOTH 0002
#define S_IXOTH 0001

#define S_ISCHR(mode) (((mode) & S_IFMT) == S_IFCHR)
#define S_ISREG(mode) (((mode) & S_IFMT) == S_IFREG)
#define S_ISDIR(mode) (((mode) & S_IFMT) == S_IFDIR)
#define S_ISLNK(mode) (((mode) & S_IFMT) == S_IFLNK)

int stat(const char *path, struct stat *st);
int lstat(const char *path, struct stat *st);
int fstat(int fd, struct stat *st);
int fstatat(int dirfd, const char *path, struct stat *st, int flags);
int mkdir(const char *path, mode_t mode);
int chmod(const char *path, mode_t mode);
int fchmod(int fd, mode_t mode);
int fchmodat(int dirfd, const char *path, mode_t mode, int flags);

#endif

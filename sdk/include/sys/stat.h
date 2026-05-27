#ifndef _SYS_STAT_H
#define _SYS_STAT_H

#include <ok/uapi/types.h>
#include <sys/types.h>

struct stat {
    ok_ino_t st_ino;
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

#define S_IFMT OK_S_IFMT
#define S_IFREG OK_S_IFREG
#define S_IFDIR OK_S_IFDIR
#define S_IRUSR OK_S_IRUSR
#define S_IWUSR OK_S_IWUSR
#define S_IXUSR OK_S_IXUSR
#define S_IRGRP OK_S_IRGRP
#define S_IWGRP OK_S_IWGRP
#define S_IXGRP OK_S_IXGRP
#define S_IROTH OK_S_IROTH
#define S_IWOTH OK_S_IWOTH
#define S_IXOTH OK_S_IXOTH

#define S_ISREG(mode) (((mode) & S_IFMT) == S_IFREG)
#define S_ISDIR(mode) (((mode) & S_IFMT) == S_IFDIR)

int stat(const char *path, struct stat *st);
int fstat(int fd, struct stat *st);
int mkdir(const char *path, mode_t mode);

#endif

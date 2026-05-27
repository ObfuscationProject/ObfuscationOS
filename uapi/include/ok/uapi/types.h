#ifndef OK_UAPI_TYPES_H
#define OK_UAPI_TYPES_H

#include <stdint.h>

#define OK_NAME_MAX 255
#define OK_PATH_MAX 256

typedef int64_t ok_ssize_t;
typedef uint64_t ok_size_t;
typedef int64_t ok_off_t;
typedef uint64_t ok_ino_t;
typedef uint32_t ok_mode_t;

struct ok_timespec {
    int64_t tv_sec;
    int64_t tv_nsec;
};

struct ok_iovec {
    void *iov_base;
    ok_size_t iov_len;
};

struct ok_stat {
    ok_ino_t st_ino;
    ok_mode_t st_mode;
    uint32_t st_nlink;
    uint32_t st_uid;
    uint32_t st_gid;
    uint32_t st_rdev;
    ok_off_t st_size;
    uint32_t st_blksize;
    uint32_t st_blocks;
    struct ok_timespec st_atim;
    struct ok_timespec st_mtim;
    struct ok_timespec st_ctim;
};

struct ok_dirent {
    ok_ino_t d_ino;
    int64_t d_off;
    uint16_t d_reclen;
    uint8_t d_type;
    char d_name[OK_NAME_MAX + 1];
};

#define OK_DT_UNKNOWN 0
#define OK_DT_REG 1
#define OK_DT_DIR 2

#define OK_S_IFMT 0170000
#define OK_S_IFREG 0100000
#define OK_S_IFDIR 0040000

#define OK_S_IRUSR 0400
#define OK_S_IWUSR 0200
#define OK_S_IXUSR 0100
#define OK_S_IRGRP 0040
#define OK_S_IWGRP 0020
#define OK_S_IXGRP 0010
#define OK_S_IROTH 0004
#define OK_S_IWOTH 0002
#define OK_S_IXOTH 0001

#endif

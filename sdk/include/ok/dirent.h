#ifndef OK_DIRENT_H
#define OK_DIRENT_H

#include <ok/uapi/syscall.h>
#include <stddef.h>
#include <sys/types.h>

#define DT_UNKNOWN 0
#define DT_DIR 4
#define DT_REG 8

struct dirent {
    unsigned long d_ino;
    long d_off;
    unsigned short d_reclen;
    unsigned char d_type;
    char d_name[256];
};

ssize_t getdents64(int fd, void *buf, size_t count);

#endif

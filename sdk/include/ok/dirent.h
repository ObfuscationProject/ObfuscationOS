#ifndef OK_DIRENT_H
#define OK_DIRENT_H

#include <ok/uapi/types.h>
#include <stddef.h>
#include <sys/types.h>

ssize_t getdents(int fd, struct ok_dirent *dirents, size_t count);

#endif

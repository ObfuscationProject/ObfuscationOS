#ifndef _FCNTL_H
#define _FCNTL_H

#include <ok/uapi/syscall.h>

#define O_RDONLY OK_O_RDONLY
#define O_WRONLY OK_O_WRONLY
#define O_RDWR OK_O_RDWR
#define O_CREAT OK_O_CREAT
#define O_EXCL OK_O_EXCL
#define O_TRUNC OK_O_TRUNC
#define O_APPEND OK_O_APPEND
#define O_DIRECTORY OK_O_DIRECTORY

int open(const char *path, int flags, ...);

#endif

#ifndef _FCNTL_H
#define _FCNTL_H

#include <ok/uapi/syscall.h>

#ifndef OK_O_EXCL
#define OK_O_EXCL 0x0080U
#endif

#define O_RDONLY OK_O_RDONLY
#define O_WRONLY OK_O_WRONLY
#define O_RDWR OK_O_RDWR
#define O_CREAT OK_O_CREAT
#define O_EXCL OK_O_EXCL
#define O_TRUNC OK_O_TRUNC
#define O_APPEND OK_O_APPEND
#define O_NONBLOCK OK_O_NONBLOCK
#define O_CLOEXEC OK_O_CLOEXEC
#define F_DUPFD OK_F_DUPFD
#define F_GETFD OK_F_GETFD
#define F_SETFD OK_F_SETFD
#define F_GETFL OK_F_GETFL
#define F_SETFL OK_F_SETFL
#define F_ADD_SEALS OK_F_ADD_SEALS
#define F_GET_SEALS OK_F_GET_SEALS
#define F_SEAL_SEAL OK_F_SEAL_SEAL
#define F_SEAL_SHRINK OK_F_SEAL_SHRINK
#define F_SEAL_GROW OK_F_SEAL_GROW
#define F_SEAL_WRITE OK_F_SEAL_WRITE
#define FD_CLOEXEC OK_FD_CLOEXEC
#define O_DIRECTORY OK_O_DIRECTORY
#define O_NOFOLLOW OK_O_NOFOLLOW
#define AT_FDCWD OK_AT_FDCWD
#define AT_SYMLINK_NOFOLLOW OK_AT_SYMLINK_NOFOLLOW
#define AT_EMPTY_PATH OK_AT_EMPTY_PATH

int open(const char *path, int flags, ...);
int openat(int dirfd, const char *path, int flags, ...);
int fcntl(int fd, int command, ...);

#endif

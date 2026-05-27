#include <fcntl.h>
#include <ok/dirent.h>
#include <ok/syscall.h>
#include <ok/uapi/types.h>
#include <stdarg.h>
#include <stddef.h>
#include <sys/stat.h>
#include <unistd.h>

static void copy_stat(struct stat *dst, const struct ok_stat *src)
{
    dst->st_ino = src->st_ino;
    dst->st_mode = src->st_mode;
    dst->st_nlink = src->st_nlink;
    dst->st_uid = src->st_uid;
    dst->st_gid = src->st_gid;
    dst->st_rdev = src->st_rdev;
    dst->st_size = src->st_size;
    dst->st_blksize = src->st_blksize;
    dst->st_blocks = src->st_blocks;
    dst->st_atim = src->st_atim;
    dst->st_mtim = src->st_mtim;
    dst->st_ctim = src->st_ctim;
}

void _Exit(int status)
{
    (void)ok_syscall1(OK_SYS_EXIT, status);
    for (;;) {
    }
}

ssize_t read(int fd, void *buf, size_t count)
{
    return (ssize_t)ok_syscall_ret(ok_syscall3(OK_SYS_READ, fd, (long)buf, (long)count));
}

ssize_t write(int fd, const void *buf, size_t count)
{
    return (ssize_t)ok_syscall_ret(ok_syscall3(OK_SYS_WRITE, fd, (long)buf, (long)count));
}

int open(const char *path, int flags, ...)
{
    mode_t mode = 0;
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode = (mode_t)va_arg(ap, int);
        va_end(ap);
    }
    return (int)ok_syscall_ret(ok_syscall3(OK_SYS_OPEN, (long)path, flags, mode));
}

int close(int fd)
{
    return (int)ok_syscall_ret(ok_syscall1(OK_SYS_CLOSE, fd));
}

off_t lseek(int fd, off_t offset, int whence)
{
    return (off_t)ok_syscall_ret(ok_syscall3(OK_SYS_LSEEK, fd, offset, whence));
}

int stat(const char *path, struct stat *st)
{
    struct ok_stat kst;
    long result = ok_syscall_ret(ok_syscall2(OK_SYS_STAT, (long)path, (long)&kst));
    if (result < 0) {
        return -1;
    }
    copy_stat(st, &kst);
    return 0;
}

int fstat(int fd, struct stat *st)
{
    struct ok_stat kst;
    long result = ok_syscall_ret(ok_syscall2(OK_SYS_FSTAT, fd, (long)&kst));
    if (result < 0) {
        return -1;
    }
    copy_stat(st, &kst);
    return 0;
}

int mkdir(const char *path, mode_t mode)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_MKDIR, (long)path, mode));
}

int unlink(const char *path)
{
    return (int)ok_syscall_ret(ok_syscall1(OK_SYS_UNLINK, (long)path));
}

ssize_t getdents(int fd, struct ok_dirent *dirents, size_t count)
{
    return (ssize_t)ok_syscall_ret(ok_syscall3(OK_SYS_GETDENTS, fd, (long)dirents, (long)count));
}

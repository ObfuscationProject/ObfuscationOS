#include <fcntl.h>
#include <ok/dirent.h>
#include <ok/syscall.h>
#include <stdarg.h>
#include <stddef.h>
#include <sys/stat.h>
#include <unistd.h>

static void copy_stat(struct stat *dst, const struct ok_stat *src)
{
    dst->st_ino = 0;
    dst->st_mode = src->mode;
    dst->st_nlink = src->link_count;
    dst->st_uid = src->uid;
    dst->st_gid = src->gid;
    dst->st_rdev = 0;
    dst->st_size = (off_t)src->size;
    dst->st_blksize = src->block_size;
    dst->st_blocks = (unsigned int)src->blocks;
    dst->st_atim.seconds = 0;
    dst->st_atim.nanoseconds = 0;
    dst->st_mtim.seconds = 0;
    dst->st_mtim.nanoseconds = 0;
    dst->st_ctim.seconds = 0;
    dst->st_ctim.nanoseconds = 0;
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

pid_t getpid(void)
{
    return (pid_t)ok_syscall_ret(ok_syscall0(OK_SYS_GETPID));
}

uid_t getuid(void)
{
    return (uid_t)ok_syscall_ret(ok_syscall0(OK_SYS_GETUID));
}

uid_t geteuid(void)
{
    return (uid_t)ok_syscall_ret(ok_syscall0(OK_SYS_GETEUID));
}

gid_t getgid(void)
{
    return (gid_t)ok_syscall_ret(ok_syscall0(OK_SYS_GETGID));
}

gid_t getegid(void)
{
    return (gid_t)ok_syscall_ret(ok_syscall0(OK_SYS_GETEGID));
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

char *getcwd(char *buf, size_t size)
{
    long result = ok_syscall_ret(ok_syscall2(OK_SYS_GETCWD, (long)buf, (long)size));
    return result < 0 ? 0 : buf;
}

int chdir(const char *path)
{
    return (int)ok_syscall_ret(ok_syscall1(OK_SYS_CHDIR, (long)path));
}

ssize_t getdents64(int fd, void *buf, size_t count)
{
    return (ssize_t)ok_syscall_ret(ok_syscall3(OK_SYS_GETDENTS64, fd, (long)buf, (long)count));
}

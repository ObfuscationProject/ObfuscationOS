#include <fcntl.h>
#include <ok/dirent.h>
#include <ok/syscall.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <sys/stat.h>
#include <sys/uio.h>
#include <unistd.h>

static int copy_stat(struct stat *dst, const struct ok_stat *src)
{
    if (src->size > (uintptr_t)__LONG_MAX__ || src->blocks > (uint64_t)~0u)
        return (int)ok_syscall_ret(-OK_EOVERFLOW);
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
    return 0;
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
    return copy_stat(st, &kst);
}

int fstat(int fd, struct stat *st)
{
    struct ok_stat kst;
    long result = ok_syscall_ret(ok_syscall2(OK_SYS_FSTAT, fd, (long)&kst));
    if (result < 0) {
        return -1;
    }
    return copy_stat(st, &kst);
}

int mkdir(const char *path, mode_t mode)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_MKDIR, (long)path, mode));
}

int unlink(const char *path)
{
    return (int)ok_syscall_ret(ok_syscall1(OK_SYS_UNLINK, (long)path));
}

int rmdir(const char *path)
{
    return (int)ok_syscall_ret(ok_syscall1(OK_SYS_RMDIR, (long)path));
}

int rename(const char *oldpath, const char *newpath)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_RENAME, (long)oldpath, (long)newpath));
}

int renameat(int olddirfd, const char *oldpath, int newdirfd, const char *newpath)
{
    return (int)ok_syscall_ret(ok_syscall4(OK_SYS_RENAMEAT, olddirfd, (long)oldpath,
                                        newdirfd, (long)newpath));
}

int link(const char *oldpath, const char *newpath)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_LINK, (long)oldpath, (long)newpath));
}

int linkat(int olddirfd, const char *oldpath, int newdirfd, const char *newpath, int flags)
{
    return (int)ok_syscall_ret(ok_syscall5(OK_SYS_LINKAT, olddirfd, (long)oldpath,
                                        newdirfd, (long)newpath, flags));
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

pid_t fork(void)
{
    return (pid_t)ok_syscall_ret(ok_syscall0(OK_SYS_FORK));
}

int execve(const char *path, char *const argv[], char *const envp[])
{
    return (int)ok_syscall_ret(ok_syscall3(OK_SYS_EXECVE, (long)path, (long)argv, (long)envp));
}

pid_t waitpid(pid_t pid, int *status, int options)
{
    return (pid_t)ok_syscall_ret(ok_syscall4(OK_SYS_WAIT4, pid, (long)status, options, 0));
}

int pipe(int fds[2])
{
    return (int)ok_syscall_ret(ok_syscall1(OK_SYS_PIPE, (long)fds));
}

int dup2(int oldfd, int newfd)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_DUP2, oldfd, newfd));
}

ssize_t pread(int fd, void *buf, size_t count, off_t offset)
{ return (ssize_t)ok_syscall_ret(ok_syscall4(OK_SYS_PREAD64, fd, (long)buf, (long)count, offset)); }
ssize_t pwrite(int fd, const void *buf, size_t count, off_t offset)
{ return (ssize_t)ok_syscall_ret(ok_syscall4(OK_SYS_PWRITE64, fd, (long)buf, (long)count, offset)); }
ssize_t readv(int fd, const struct iovec *vectors, int count)
{ return (ssize_t)ok_syscall_ret(ok_syscall3(OK_SYS_READV, fd, (long)vectors, count)); }
ssize_t writev(int fd, const struct iovec *vectors, int count)
{ return (ssize_t)ok_syscall_ret(ok_syscall3(OK_SYS_WRITEV, fd, (long)vectors, count)); }
int fsync(int fd)
{ return (int)ok_syscall_ret(ok_syscall1(OK_SYS_FSYNC, fd)); }
int fdatasync(int fd)
{ return (int)ok_syscall_ret(ok_syscall1(OK_SYS_FDATASYNC, fd)); }
int ftruncate(int fd, off_t length)
{ return (int)ok_syscall_ret(ok_syscall2(OK_SYS_FTRUNCATE, fd, length)); }
int truncate(const char *path, off_t length)
{ return (int)ok_syscall_ret(ok_syscall2(OK_SYS_TRUNCATE, (long)path, length)); }

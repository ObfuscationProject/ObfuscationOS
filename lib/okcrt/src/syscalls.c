#include <fcntl.h>
#include <ok/dirent.h>
#include <ok/syscall.h>
#include <ok/socket.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <sys/random.h>
#include <sys/uio.h>
#include <sys/ioctl.h>
#include <unistd.h>
#include <time.h>
#include <poll.h>
#include <signal.h>

_Static_assert(sizeof(struct pollfd) == sizeof(struct ok_pollfd), "native poll layout");
_Static_assert(offsetof(struct pollfd, revents) == 6, "native poll result offset");
_Static_assert(sizeof(pid_t) == 4, "native terminal PID copy width");

int ioctl(int fd, unsigned long request, ...)
{
    long argument = 0;
    va_list arguments;
    va_start(arguments, request);
    /* The kernel decodes the low request word. Unknown requests have no
     * admitted argument shape, so do not read an optional argument for them. */
    switch ((uint32_t)request) {
    case TIOCSCTTY:
        argument = va_arg(arguments, int);
        break;
    case TIOCGPGRP:
    case TIOCSPGRP:
    case TIOCGSID:
        argument = (long)va_arg(arguments, void *);
        break;
    default:
        break;
    }
    va_end(arguments);
    return (int)ok_syscall_ret(ok_syscall3(OK_SYS_IOCTL, fd, (long)request, argument));
}

pid_t tcgetpgrp(int fd)
{
    pid_t group = 0;
    return ioctl(fd, TIOCGPGRP, (void *)&group) < 0 ? -1 : group;
}

int tcsetpgrp(int fd, pid_t group)
{
    return ioctl(fd, TIOCSPGRP, (void *)&group);
}

pid_t tcgetsid(int fd)
{
    pid_t sid = 0;
    return ioctl(fd, TIOCGSID, (void *)&sid) < 0 ? -1 : sid;
}

int poll(struct pollfd *fds, nfds_t count, int timeout)
{
    return (int)ok_syscall_ret(ok_syscall3(OK_SYS_POLL, (long)fds, count, timeout));
}

ssize_t getrandom(void *buffer, size_t size, unsigned int flags)
{
    return (ssize_t)ok_syscall_ret(ok_syscall3(OK_SYS_GETRANDOM, (long)buffer, (long)size, flags));
}

int pipe2(int fds[2], int flags)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_PIPE2, (long)fds, flags));
}

int dup(int fd)
{
    return (int)ok_syscall_ret(ok_syscall1(OK_SYS_DUP, fd));
}

int fcntl(int fd, int command, ...)
{
    int value = 0;
    if (command == F_DUPFD || command == F_SETFD || command == F_SETFL || command == F_ADD_SEALS) {
        va_list ap;
        va_start(ap, command);
        value = va_arg(ap, int);
        va_end(ap);
    }
    return (int)ok_syscall_ret(ok_syscall3(OK_SYS_FCNTL, fd, command, value));
}

_Static_assert(sizeof(struct timespec) == sizeof(struct ok_timespec), "native time64 size");
_Static_assert(offsetof(struct timespec, tv_nsec) == offsetof(struct ok_timespec, nanoseconds), "native time64 layout");

int clock_settime(clockid_t clock, const struct timespec *value)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_CLOCK_SETTIME, clock, (long)value));
}

int clock_gettime(clockid_t clock, struct timespec *value)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_CLOCK_GETTIME, clock, (long)value));
}

int clock_getres(clockid_t clock, struct timespec *value)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_CLOCK_GETRES, clock, (long)value));
}

int nanosleep(const struct timespec *request, struct timespec *remaining)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_NANOSLEEP, (long)request, (long)remaining));
}

int clock_nanosleep(clockid_t clock, int flags, const struct timespec *request, struct timespec *remaining)
{
    long result = ok_syscall4(OK_SYS_CLOCK_NANOSLEEP, clock, flags, (long)request, (long)remaining);
    return result < 0 ? (int)-result : 0;
}

static int copy_stat(struct stat *dst, const struct ok_stat_v2 *record)
{
    const struct ok_stat *src = &record->basic;
    if (src->size > (uintptr_t)__LONG_MAX__ || src->blocks > (uint64_t)~0u)
        return (int)ok_syscall_ret(-OK_EOVERFLOW);
    dst->st_ino = record->inode;
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

int openat(int dirfd, const char *path, int flags, ...)
{
    mode_t mode = 0644;
    if (flags & O_CREAT) {
        va_list ap;
        va_start(ap, flags);
        mode = (mode_t)va_arg(ap, int);
        va_end(ap);
    }
    return (int)ok_syscall_ret(ok_syscall4(OK_SYS_OPENAT, dirfd, (long)path, flags, mode));
}

int close(int fd)
{
    return (int)ok_syscall_ret(ok_syscall1(OK_SYS_CLOSE, fd));
}

pid_t getpid(void)
{
    return (pid_t)ok_syscall_ret(ok_syscall0(OK_SYS_GETPID));
}

pid_t getppid(void)
{
    return (pid_t)ok_syscall_ret(ok_syscall0(OK_SYS_GETPPID));
}

pid_t setsid(void)
{
    return (pid_t)ok_syscall_ret(ok_syscall0(OK_SYS_SETSID));
}

int setpgid(pid_t pid, pid_t pgid)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_SETPGID, pid, pgid));
}

pid_t getpgid(pid_t pid)
{
    return (pid_t)ok_syscall_ret(ok_syscall1(OK_SYS_GETPGID, pid));
}

pid_t getsid(pid_t pid)
{
    return (pid_t)ok_syscall_ret(ok_syscall1(OK_SYS_GETSID, pid));
}

pid_t getpgrp(void)
{
    return (pid_t)ok_syscall_ret(ok_syscall0(OK_SYS_GETPGRP));
}

int kill(pid_t pid, int signal)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_KILL, pid, signal));
}

/* Identity getters are infallible; 32-bit high IDs may overlap errno bits. */
uid_t getuid(void)
{
    return (uid_t)ok_syscall0(OK_SYS_GETUID);
}

uid_t geteuid(void)
{
    return (uid_t)ok_syscall0(OK_SYS_GETEUID);
}

gid_t getgid(void)
{
    return (gid_t)ok_syscall0(OK_SYS_GETGID);
}

gid_t getegid(void)
{
    return (gid_t)ok_syscall0(OK_SYS_GETEGID);
}

_Static_assert(sizeof(uid_t) == sizeof(uint32_t), "native UID width");
_Static_assert(sizeof(gid_t) == sizeof(uint32_t), "native GID width");
_Static_assert(OK_NATIVE_CREDENTIALS_VERSION == 1, "native credentials contract");

int setuid(uid_t uid)
{
    return (int)ok_syscall_ret(ok_syscall1(OK_SYS_SETUID, (long)uid));
}

int setgid(gid_t gid)
{
    return (int)ok_syscall_ret(ok_syscall1(OK_SYS_SETGID, (long)gid));
}

int setreuid(uid_t real, uid_t effective)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_SETREUID, (long)real, (long)effective));
}

int setregid(gid_t real, gid_t effective)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_SETREGID, (long)real, (long)effective));
}

int setresuid(uid_t real, uid_t effective, uid_t saved)
{
    return (int)ok_syscall_ret(ok_syscall3(OK_SYS_SETRESUID, (long)real, (long)effective, (long)saved));
}

int setresgid(gid_t real, gid_t effective, gid_t saved)
{
    return (int)ok_syscall_ret(ok_syscall3(OK_SYS_SETRESGID, (long)real, (long)effective, (long)saved));
}

int getresuid(uid_t *real, uid_t *effective, uid_t *saved)
{
    return (int)ok_syscall_ret(ok_syscall3(OK_SYS_GETRESUID, (long)real, (long)effective, (long)saved));
}

int getresgid(gid_t *real, gid_t *effective, gid_t *saved)
{
    return (int)ok_syscall_ret(ok_syscall3(OK_SYS_GETRESGID, (long)real, (long)effective, (long)saved));
}

off_t lseek(int fd, off_t offset, int whence)
{
    return (off_t)ok_syscall_ret(ok_syscall3(OK_SYS_LSEEK, fd, offset, whence));
}

int stat(const char *path, struct stat *st)
{
    return fstatat(OK_AT_FDCWD, path, st, 0);
}

int fstat(int fd, struct stat *st)
{
    struct ok_stat_v2 kst;
    long result = ok_syscall_ret(ok_syscall2(OK_SYS_FSTAT_V2, fd, (long)&kst));
    if (result < 0) {
        return -1;
    }
    return copy_stat(st, &kst);
}

int lstat(const char *path, struct stat *st)
{
    return fstatat(OK_AT_FDCWD, path, st, OK_AT_SYMLINK_NOFOLLOW);
}

int fstatat(int dirfd, const char *path, struct stat *st, int flags)
{
    struct ok_stat_v2 kst;
    long result = ok_syscall_ret(ok_syscall4(OK_SYS_NEWFSTATAT_V2, dirfd, (long)path, (long)&kst, flags));
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

int unlinkat(int dirfd, const char *path, int flags)
{
    return (int)ok_syscall_ret(ok_syscall3(OK_SYS_UNLINKAT, dirfd, (long)path, flags));
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

int symlink(const char *target, const char *path)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_SYMLINK, (long)target, (long)path));
}

int symlinkat(const char *target, int dirfd, const char *path)
{
    return (int)ok_syscall_ret(ok_syscall3(OK_SYS_SYMLINKAT, (long)target, dirfd, (long)path));
}

ssize_t readlink(const char *path, char *buffer, size_t size)
{
    return (ssize_t)ok_syscall_ret(ok_syscall3(OK_SYS_READLINK, (long)path, (long)buffer, (long)size));
}

ssize_t readlinkat(int dirfd, const char *path, char *buffer, size_t size)
{
    return (ssize_t)ok_syscall_ret(ok_syscall4(OK_SYS_READLINKAT, dirfd, (long)path, (long)buffer, (long)size));
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

int memfd_create(const char *name, unsigned int flags)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_MEMFD_CREATE, (long)name, flags));
}

void *mmap(void *address, size_t length, int protection, int flags, int fd, off_t offset)
{
    return (void *)ok_syscall_ret(ok_syscall6(OK_SYS_MMAP, (long)address, (long)length,
                                           protection, flags, fd, offset));
}

int mprotect(void *address, size_t length, int protection)
{
    return (int)ok_syscall_ret(ok_syscall3(OK_SYS_MPROTECT, (long)address, (long)length, protection));
}

int munmap(void *address, size_t length)
{
    return (int)ok_syscall_ret(ok_syscall2(OK_SYS_MUNMAP, (long)address, (long)length));
}
int ok_socketpair(int domain, int type, int protocol, int descriptors[2])
{ return (int)ok_syscall_ret(ok_syscall4(OK_SYS_SOCKETPAIR, domain, type, protocol, (long)descriptors)); }
ssize_t ok_sendmsg(int fd, const struct ok_msghdr *message, int flags)
{ return (ssize_t)ok_syscall_ret(ok_syscall3(OK_SYS_SENDMSG, fd, (long)message, flags)); }
ssize_t ok_recvmsg(int fd, struct ok_msghdr *message, int flags)
{ return (ssize_t)ok_syscall_ret(ok_syscall3(OK_SYS_RECVMSG, fd, (long)message, flags)); }

int ok_socket(int domain, int type, int protocol)
{ return (int)ok_syscall_ret(ok_syscall3(OK_SYS_SOCKET, domain, type, protocol)); }
int ok_bind(int fd, const struct ok_sockaddr_un *address, ok_socklen_t length)
{ return (int)ok_syscall_ret(ok_syscall3(OK_SYS_BIND, fd, (long)address, length)); }
int ok_listen(int fd, int backlog)
{ return (int)ok_syscall_ret(ok_syscall2(OK_SYS_LISTEN, fd, backlog)); }
int ok_connect(int fd, const struct ok_sockaddr_un *address, ok_socklen_t length)
{ return (int)ok_syscall_ret(ok_syscall3(OK_SYS_CONNECT, fd, (long)address, length)); }
int ok_accept4(int fd, struct ok_sockaddr_un *address, ok_socklen_t *length, int flags)
{ return (int)ok_syscall_ret(ok_syscall4(OK_SYS_ACCEPT4, fd, (long)address, (long)length, flags)); }
int ok_getsockopt(int fd, int level, int option, void *value, ok_socklen_t *length)
{ return (int)ok_syscall_ret(ok_syscall5(OK_SYS_GETSOCKOPT, fd, level, option, (long)value, (long)length)); }

/* Native metadata calls retain complete u32 scalars on every word size. */
_Static_assert(sizeof(mode_t) == sizeof(uint32_t), "native mode width");
_Static_assert(OK_NATIVE_METADATA_VERSION == 1, "native metadata contract");
int chmod(const char *path, mode_t mode)
{
    return (int)ok_syscall_ret(ok_syscall6(OK_SYS_CHMOD, (long)path, (long)mode, 0, 0, 0, 0));
}
int fchmod(int fd, mode_t mode)
{
    return (int)ok_syscall_ret(ok_syscall6(OK_SYS_FCHMOD, fd, (long)mode, 0, 0, 0, 0));
}
int fchmodat(int dirfd, const char *path, mode_t mode, int flags)
{
    return (int)ok_syscall_ret(ok_syscall6(OK_SYS_FCHMODAT, dirfd, (long)path, (long)mode, flags, 0, 0));
}
int chown(const char *path, uid_t uid, gid_t gid)
{
    return (int)ok_syscall_ret(ok_syscall6(OK_SYS_CHOWN, (long)path, (long)uid, (long)gid, 0, 0, 0));
}
int fchown(int fd, uid_t uid, gid_t gid)
{
    return (int)ok_syscall_ret(ok_syscall6(OK_SYS_FCHOWN, fd, (long)uid, (long)gid, 0, 0, 0));
}
int fchownat(int dirfd, const char *path, uid_t uid, gid_t gid, int flags)
{
    return (int)ok_syscall_ret(ok_syscall6(OK_SYS_FCHOWNAT, dirfd, (long)path, (long)uid, (long)gid, flags, 0));
}

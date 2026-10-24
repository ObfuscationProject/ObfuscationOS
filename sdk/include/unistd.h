#ifndef _UNISTD_H
#define _UNISTD_H

#include <stddef.h>
#include <sys/types.h>

#define STDIN_FILENO 0
#define STDOUT_FILENO 1
#define STDERR_FILENO 2

#define SEEK_SET 0
#define SEEK_CUR 1
#define SEEK_END 2

pid_t fork(void);
int execve(const char *path, char *const argv[], char *const envp[]);
int pipe(int fds[2]);
int dup(int fd);
int pipe2(int fds[2], int flags);
int dup2(int oldfd, int newfd);

ssize_t read(int fd, void *buf, size_t count);
ssize_t write(int fd, const void *buf, size_t count);
ssize_t pread(int fd, void *buf, size_t count, off_t offset);
ssize_t pwrite(int fd, const void *buf, size_t count, off_t offset);
int fsync(int fd);
int fdatasync(int fd);
int ftruncate(int fd, off_t length);
int truncate(const char *path, off_t length);
int close(int fd);
int chown(const char *path, uid_t uid, gid_t gid);
int fchown(int fd, uid_t uid, gid_t gid);
int fchownat(int dirfd, const char *path, uid_t uid, gid_t gid, int flags);
off_t lseek(int fd, off_t offset, int whence);
int unlink(const char *path);
int unlinkat(int dirfd, const char *path, int flags);
int rmdir(const char *path);
int link(const char *oldpath, const char *newpath);
int linkat(int olddirfd, const char *oldpath, int newdirfd, const char *newpath, int flags);
int symlink(const char *target, const char *path);
int symlinkat(const char *target, int dirfd, const char *path);
ssize_t readlink(const char *path, char *buffer, size_t size);
ssize_t readlinkat(int dirfd, const char *path, char *buffer, size_t size);
pid_t getpid(void);
pid_t getppid(void);
pid_t setsid(void);
int setpgid(pid_t pid, pid_t pgid);
pid_t getpgid(pid_t pid);
pid_t getsid(pid_t pid);
pid_t getpgrp(void);
pid_t tcgetpgrp(int fd);
int tcsetpgrp(int fd, pid_t group);
pid_t tcgetsid(int fd);
uid_t getuid(void);
uid_t geteuid(void);
gid_t getgid(void);
gid_t getegid(void);
int setuid(uid_t uid);
int setgid(gid_t gid);
int setreuid(uid_t real, uid_t effective);
int setregid(gid_t real, gid_t effective);
int setresuid(uid_t real, uid_t effective, uid_t saved);
int setresgid(gid_t real, gid_t effective, gid_t saved);
int getresuid(uid_t *real, uid_t *effective, uid_t *saved);
int getresgid(gid_t *real, gid_t *effective, gid_t *saved);
char *getcwd(char *buf, size_t size);
int chdir(const char *path);
void _Exit(int status) __attribute__((noreturn));

#endif

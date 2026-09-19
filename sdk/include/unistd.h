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
off_t lseek(int fd, off_t offset, int whence);
int unlink(const char *path);
pid_t getpid(void);
uid_t getuid(void);
uid_t geteuid(void);
gid_t getgid(void);
gid_t getegid(void);
char *getcwd(char *buf, size_t size);
int chdir(const char *path);
void _Exit(int status) __attribute__((noreturn));

#endif

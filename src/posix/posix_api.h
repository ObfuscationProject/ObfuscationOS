#ifndef POSIX_API_H
#define POSIX_API_H

#include <fcntl.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

// POSIX API兼容层
// 这里定义POSIX标准的函数接口

#ifdef __cplusplus
extern "C"
{
#endif

    // 文件操作
    int open(const char *pathname, int flags, ...);
    int close(int fd);
    ssize_t read(int fd, void *buf, size_t count);
    ssize_t write(int fd, const void *buf, size_t count);
    off_t lseek(int fd, off_t offset, int whence);

    // 进程操作
    pid_t fork(void);
    int execve(const char *filename, char *const argv[], char *const envp[]);
    void _exit(int status);
    pid_t getpid(void);
    pid_t getppid(void);
    int waitpid(pid_t pid, int *status, int options);

    // 内存管理
    void *mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset);
    int munmap(void *addr, size_t length);

    // 文件系统
    int mkdir(const char *pathname, mode_t mode);
    int rmdir(const char *pathname);
    int unlink(const char *pathname);
    int chmod(const char *pathname, mode_t mode);

    // 时间相关
    int gettimeofday(struct timeval *tv, struct timezone *tz);

    // 线程相关（如果支持）
    int pthread_create(void *thread, const void *attr, void *(*start_routine)(void *), void *arg);

#ifdef __cplusplus
}
#endif

#endif // POSIX_API_H
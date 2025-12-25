#include "../user/interface.hpp"
#include "posix_api.h"

// POSIX API实现
// 将POSIX函数调用映射到我们的系统调用接口

#ifdef __cplusplus
extern "C"
{
#endif

    int open(const char *pathname, int flags, ...)
    {
        // 忽略可变参数（mode），在实际实现中需要处理
        return user::SyscallInterface::open(pathname, flags);
    }

    int close(int fd)
    {
        return user::SyscallInterface::close(fd);
    }

    ssize_t read(int fd, void *buf, size_t count)
    {
        return user::SyscallInterface::read(fd, buf, count);
    }

    ssize_t write(int fd, const void *buf, size_t count)
    {
        return user::SyscallInterface::write(fd, buf, count);
    }

    off_t lseek(int fd, off_t offset, int whence)
    {
        // TODO: 实现lseek系统调用
        return -1;
    }

    pid_t fork(void)
    {
        return user::SyscallInterface::fork();
    }

    int execve(const char *filename, char *const argv[], char *const envp[])
    {
        return user::SyscallInterface::execve(filename, argv, envp);
    }

    void _exit(int status)
    {
        user::SyscallInterface::exit(status);
        // 理论上不会返回，但如果返回则死循环
        while (1)
            ;
    }

    pid_t getpid(void)
    {
        return user::SyscallInterface::getpid();
    }

    pid_t getppid(void)
    {
        return user::SyscallInterface::getppid();
    }

    int waitpid(pid_t pid, int *status, int options)
    {
        return user::SyscallInterface::waitpid(pid, status, options);
    }

    void *mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset)
    {
        return user::SyscallInterface::mmap(addr, length, prot, flags, fd, offset);
    }

    int munmap(void *addr, size_t length)
    {
        return user::SyscallInterface::munmap(addr, length);
    }

    int mkdir(const char *pathname, mode_t mode)
    {
        return user::SyscallInterface::mkdir(pathname, mode);
    }

    int rmdir(const char *pathname)
    {
        return user::SyscallInterface::rmdir(pathname);
    }

    int unlink(const char *pathname)
    {
        return user::SyscallInterface::unlink(pathname);
    }

    int chmod(const char *pathname, mode_t mode)
    {
        return user::SyscallInterface::chmod(pathname, mode);
    }

    int gettimeofday(struct timeval *tv, struct timezone *tz)
    {
        return user::SyscallInterface::gettimeofday(tv, tz);
    }

    // 临时实现一些标准库函数
    void *malloc(size_t size)
    {
        return user::SyscallInterface::malloc(size);
    }

    void free(void *ptr)
    {
        user::SyscallInterface::free(ptr);
    }

#ifdef __cplusplus
}
#endif
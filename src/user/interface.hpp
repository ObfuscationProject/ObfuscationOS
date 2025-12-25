#ifndef USER_INTERFACE_H
#define USER_INTERFACE_H

#include <stddef.h>
#include <stdint.h>

// 用户层接口定义
namespace user
{

// 系统调用接口
class SyscallInterface
{
  public:
    // POSIX兼容的系统调用
    static int read(int fd, void *buf, size_t count);
    static int write(int fd, const void *buf, size_t count);
    static int open(const char *pathname, int flags);
    static int close(int fd);
    static int fork();
    static int execve(const char *filename, char *const argv[], char *const envp[]);
    static int exit(int status);
    static int waitpid(int pid, int *status, int options);
    static int kill(int pid, int sig);
    static int getpid();
    static int getppid();

    // 内存管理
    static void *malloc(size_t size);
    static void free(void *ptr);
    static void *mmap(void *addr, size_t length, int prot, int flags, int fd, size_t offset);
    static int munmap(void *addr, size_t length);

    // 文件系统
    static int mkdir(const char *pathname, int mode);
    static int rmdir(const char *pathname);
    static int unlink(const char *pathname);
    static int chmod(const char *pathname, int mode);

    // 时间相关
    static int gettimeofday(void *tv, void *tz);
    static int sleep(unsigned int seconds);
    static int usleep(unsigned int usec);

  private:
    // 通用系统调用函数
    static uint64_t syscall(uint64_t num, uint64_t arg1, uint64_t arg2, uint64_t arg3);
};

} // namespace user

#endif // USER_INTERFACE_H
#include "../include/obflib.h"
#include "interface.hpp"

namespace user
{

int SyscallInterface::read(int fd, void *buf, size_t count)
{
    return (int)syscall(0, (uint64_t)fd, (uint64_t)buf, (uint64_t)count);
}

int SyscallInterface::write(int fd, const void *buf, size_t count)
{
    return (int)syscall(1, (uint64_t)fd, (uint64_t)buf, (uint64_t)count);
}

int SyscallInterface::open(const char *pathname, int flags)
{
    return (int)syscall(2, (uint64_t)pathname, (uint64_t)flags, 0);
}

int SyscallInterface::close(int fd)
{
    return (int)syscall(3, (uint64_t)fd, 0, 0);
}

int SyscallInterface::fork()
{
    return (int)syscall(57, 0, 0, 0);
}

int SyscallInterface::execve(const char *filename, char *const argv[], char *const envp[])
{
    return (int)syscall(59, (uint64_t)filename, (uint64_t)argv, (uint64_t)envp);
}

int SyscallInterface::exit(int status)
{
    return (int)syscall(60, (uint64_t)status, 0, 0);
}

int SyscallInterface::waitpid(int pid, int *status, int options)
{
    return (int)syscall(61, (uint64_t)pid, (uint64_t)status, (uint64_t)options);
}

int SyscallInterface::kill(int pid, int sig)
{
    return (int)syscall(62, (uint64_t)pid, (uint64_t)sig, 0);
}

int SyscallInterface::getpid()
{
    return (int)syscall(39, 0, 0, 0);
}

int SyscallInterface::getppid()
{
    return (int)syscall(110, 0, 0, 0);
}

void *SyscallInterface::malloc(size_t size)
{
    // TODO: 实现用户空间内存分配
    return nullptr;
}

void SyscallInterface::free(void *ptr)
{
    // TODO: 实现用户空间内存释放
}

void *SyscallInterface::mmap(void *addr, size_t length, int prot, int flags, int fd, size_t offset)
{
    return (void *)syscall(9, (uint64_t)addr, (uint64_t)length, (uint64_t)prot);
}

int SyscallInterface::munmap(void *addr, size_t length)
{
    return (int)syscall(11, (uint64_t)addr, (uint64_t)length, 0);
}

int SyscallInterface::mkdir(const char *pathname, int mode)
{
    return (int)syscall(83, (uint64_t)pathname, (uint64_t)mode, 0);
}

int SyscallInterface::rmdir(const char *pathname)
{
    return (int)syscall(84, (uint64_t)pathname, 0, 0);
}

int SyscallInterface::unlink(const char *pathname)
{
    return (int)syscall(87, (uint64_t)pathname, 0, 0);
}

int SyscallInterface::chmod(const char *pathname, int mode)
{
    return (int)syscall(90, (uint64_t)pathname, (uint64_t)mode, 0);
}

int SyscallInterface::gettimeofday(void *tv, void *tz)
{
    return (int)syscall(96, (uint64_t)tv, (uint64_t)tz, 0);
}

int SyscallInterface::sleep(unsigned int seconds)
{
    // 使用nanosleep系统调用
    // TODO: 实现sleep
    return 0;
}

int SyscallInterface::usleep(unsigned int usec)
{
    // TODO: 实现usleep
    return 0;
}

uint64_t SyscallInterface::syscall(uint64_t num, uint64_t arg1, uint64_t arg2, uint64_t arg3)
{
    uint64_t result;
    // 使用内联汇编进行系统调用
    __asm__ volatile("movq %1, %%rax\n\t" // 系统调用号
                     "movq %2, %%rdi\n\t" // 第一个参数
                     "movq %3, %%rsi\n\t" // 第二个参数
                     "movq %4, %%rdx\n\t" // 第三个参数
                     "syscall\n\t"        // 执行系统调用
                     "movq %%rax, %0"     // 保存返回值
                     : "=m"(result)
                     : "m"(num), "m"(arg1), "m"(arg2), "m"(arg3)
                     : "rax", "rdi", "rsi", "rdx");
    return result;
}

} // namespace user
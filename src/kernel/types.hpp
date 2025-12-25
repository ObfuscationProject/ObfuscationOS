#ifndef KERNEL_TYPES_H
#define KERNEL_TYPES_H

#include <stddef.h>
#include <stdint.h>

// 内核基础类型定义
namespace kernel
{

// 进程状态
enum class ProcessState
{
    READY,
    RUNNING,
    WAITING,
    TERMINATED
};

// 系统调用号
enum class SyscallNumber
{
    READ = 0,
    WRITE = 1,
    OPEN = 2,
    CLOSE = 3,
    // 更多系统调用...
};

// 内存管理相关
struct MemoryBlock
{
    void *address;
    size_t size;
    bool allocated;
};

// 进程控制块
struct ProcessControlBlock
{
    int pid;
    ProcessState state;
    void *stack_pointer;
    void *base_pointer;
    // 更多进程信息...
};

// 内核错误码
enum class KernelError
{
    SUCCESS = 0,
    OUT_OF_MEMORY,
    INVALID_ARGUMENT,
    NOT_IMPLEMENTED,
    PERMISSION_DENIED
};

} // namespace kernel

#endif // KERNEL_TYPES_H
#include <stddef.h>
#include <stdint.h>

// 实现C++运行时需要的函数

// 用于静态初始化的锁
extern "C" int __cxa_guard_acquire(int64_t *guard)
{
    // 检查是否已经初始化
    if (*guard)
    {
        return 0;
    }

    // 尝试获取锁（简单实现，实际应使用原子操作）
    *guard = 1;
    return 1;
}

extern "C" void __cxa_guard_release(int64_t *guard)
{
    // 释放锁
    *guard = 0xff;
}

extern "C" void __cxa_guard_abort(int64_t *guard)
{
    // 初始化失败，重置守卫
    *guard = 0;
}

// 用于析构函数注册
extern "C" int __cxa_atexit(void (*func)(void *), void *arg, void *dso_handle)
{
    // 在我们的系统中暂时不实现
    return 0;
}

// DSO句柄
extern "C" void *__dso_handle = 0;

// C++ new/delete操作符
void *operator new(size_t size)
{
    // 在我们的系统中暂时返回空指针
    return nullptr;
}

void *operator new[](size_t size)
{
    return nullptr;
}

void operator delete(void *ptr) noexcept
{
    // 空操作
}

void operator delete[](void *ptr) noexcept
{
    // 空操作
}

void operator delete(void *ptr, size_t size) noexcept
{
    // 空操作
}

void operator delete[](void *ptr, size_t size) noexcept
{
    // 空操作
}
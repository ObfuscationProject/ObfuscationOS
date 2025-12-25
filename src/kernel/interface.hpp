#ifndef KERNEL_INTERFACE_H
#define KERNEL_INTERFACE_H

#include "../hal/interface.hpp"
#include "types.hpp"
#include <stdint.h>

namespace kernel
{

class Kernel
{
  public:
    Kernel();
    ~Kernel();

    // 初始化内核
    bool initialize();

    // 启动内核
    void start();

    // 系统调用处理
    uint64_t syscall(uint64_t num, uint64_t arg1, uint64_t arg2, uint64_t arg3);

    // 内存管理
    void *allocate_memory(size_t size);
    void free_memory(void *ptr);
    void *map_memory(uint64_t phys_addr, size_t size);

    // 进程管理
    int create_process(void (*entry)());
    int get_current_process_id();
    void yield();

    // 设备管理
    bool register_device(const char *name, void *device_ops);
    void *get_device(const char *name);

    // 时间管理
    uint64_t get_uptime_ms();
    void sleep_ms(uint64_t ms);

  private:
    hal::HALInterface *hal_;
    uint64_t uptime_ms_;
    int current_process_id_;

    // 内部初始化函数
    bool init_memory_manager();
    bool init_process_manager();
    bool init_device_manager();
    bool init_scheduler();
};

// 获取内核实例
Kernel *get_kernel();

} // namespace kernel

#endif // KERNEL_INTERFACE_H
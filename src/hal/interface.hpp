#ifndef HAL_INTERFACE_H
#define HAL_INTERFACE_H

#include "types.hpp"
#include <stdint.h>

namespace hal
{

// HAL抽象接口
class HALInterface
{
  public:
    virtual ~HALInterface() = default;

    // 初始化HAL
    virtual bool initialize() = 0;

    // CPU相关操作
    virtual void halt() = 0;
    virtual void enable_interrupts() = 0;
    virtual void disable_interrupts() = 0;
    virtual uint64_t get_cpu_frequency() = 0;

    // 内存管理
    virtual void *physical_to_virtual(uint64_t phys_addr) = 0;
    virtual uint64_t virtual_to_physical(void *virt_addr) = 0;
    virtual bool map_memory(uint64_t phys_addr, uint64_t virt_addr, uint64_t size) = 0;

    // 中断管理
    virtual bool register_interrupt_handler(uint8_t irq, void (*handler)(InterruptFrame *)) = 0;
    virtual void enable_irq(uint8_t irq) = 0;
    virtual void disable_irq(uint8_t irq) = 0;

    // 定时器
    virtual bool setup_timer(uint64_t frequency_hz) = 0;

    // I/O操作
    virtual uint8_t inb(uint16_t port) = 0;
    virtual uint16_t inw(uint16_t port) = 0;
    virtual uint32_t inl(uint16_t port) = 0;
    virtual void outb(uint16_t port, uint8_t val) = 0;
    virtual void outw(uint16_t port, uint16_t val) = 0;
    virtual void outl(uint16_t port, uint32_t val) = 0;

    // 多核支持
    virtual uint32_t get_cpu_count() = 0;
    virtual uint32_t get_current_cpu() = 0;
    virtual bool start_cpu(uint32_t cpu_id, uint64_t entry_point) = 0;
};

// 获取当前架构的HAL实例
HALInterface *get_hal();

} // namespace hal

#endif // HAL_INTERFACE_H
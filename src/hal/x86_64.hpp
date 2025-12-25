#ifndef HAL_X86_64_H
#define HAL_X86_64_H

#include "interface.hpp"

namespace hal
{
namespace x86_64
{

class X86_64HAL : public HALInterface
{
  public:
    X86_64HAL();
    virtual ~X86_64HAL() override;

    // 初始化HAL
    virtual bool initialize() override;

    // CPU相关操作
    virtual void halt() override;
    virtual void enable_interrupts() override;
    virtual void disable_interrupts() override;
    virtual uint64_t get_cpu_frequency() override;

    // 内存管理
    virtual void *physical_to_virtual(uint64_t phys_addr) override;
    virtual uint64_t virtual_to_physical(void *virt_addr) override;
    virtual bool map_memory(uint64_t phys_addr, uint64_t virt_addr, uint64_t size) override;

    // 中断管理
    virtual bool register_interrupt_handler(uint8_t irq, void (*handler)(InterruptFrame *)) override;
    virtual void enable_irq(uint8_t irq) override;
    virtual void disable_irq(uint8_t irq) override;

    // 定时器
    virtual bool setup_timer(uint64_t frequency_hz) override;

    // I/O操作
    virtual uint8_t inb(uint16_t port) override;
    virtual uint16_t inw(uint16_t port) override;
    virtual uint32_t inl(uint16_t port) override;
    virtual void outb(uint16_t port, uint8_t val) override;
    virtual void outw(uint16_t port, uint16_t val) override;
    virtual void outl(uint16_t port, uint32_t val) override;

    // 多核支持
    virtual uint32_t get_cpu_count() override;
    virtual uint32_t get_current_cpu() override;
    virtual bool start_cpu(uint32_t cpu_id, uint64_t entry_point) override;

  private:
    bool setup_gdt();
    bool setup_idt();
    bool setup_pic();
    bool setup_apic();
    bool detect_cpu_features();
    bool setup_multicore();
};

} // namespace x86_64
} // namespace hal

#endif // HAL_X86_64_H
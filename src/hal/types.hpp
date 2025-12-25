#ifndef HAL_TYPES_H
#define HAL_TYPES_H

#include <stddef.h>
#include <stdint.h>

// HAL层基础类型定义
namespace hal
{

// CPU架构相关类型
enum class Architecture
{
    X86_64,
    ARM64,
    RISCV64
};

// 系统状态
enum class SystemState
{
    BOOTING,
    RUNNING,
    SHUTDOWN
};

// 中断相关类型
struct InterruptFrame
{
    uint64_t rip;
    uint64_t cs;
    uint64_t rflags;
    uint64_t rsp;
    uint64_t ss;
};

// 物理内存区域
struct MemoryRegion
{
    uint64_t base;
    uint64_t size;
    bool available;
};

// 设备描述符
struct DeviceDescriptor
{
    uint16_t vendor_id;
    uint16_t device_id;
    uint8_t class_code;
    uint8_t subclass;
    uint8_t prog_if;
    uint8_t revision_id;
};

} // namespace hal

#endif // HAL_TYPES_H
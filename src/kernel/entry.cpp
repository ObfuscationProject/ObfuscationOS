#include "entry.h"
#include "../hal/interface.hpp"
#include "../include/obflib.h"
#include "interface.hpp"

// 内核入口点
extern "C" void kernel_main(unsigned long multiboot_info, unsigned long magic)
{
    // 检查multiboot2魔数
    if (magic != 0x36d76289)
    {
        // 不是multiboot2引导，进入死循环
        while (true)
        {
            hal::get_hal()->halt();
        }
    }

    // 初始化内核
    kernel::Kernel *kernel = kernel::get_kernel();

    if (kernel->initialize())
    {
        // 启动内核
        kernel->start();
    }

    // 如果初始化失败，进入无限循环
    while (true)
    {
        hal::get_hal()->halt();
    }
}
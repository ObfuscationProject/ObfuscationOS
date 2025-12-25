#ifndef KERNEL_ENTRY_H
#define KERNEL_ENTRY_H

#include "multiboot2.h"

// 内核入口点声明
extern "C" void kernel_main(unsigned long multiboot_info, unsigned long magic);

#endif // KERNEL_ENTRY_H
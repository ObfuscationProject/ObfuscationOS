#ifndef MULTIBOOT2_HEADER_H
#define MULTIBOOT2_HEADER_H

#include <stdint.h>

// Multiboot2头结构
struct multiboot2_header
{
    uint32_t magic;
    uint32_t architecture;
    uint32_t header_length;
    uint32_t checksum;
    uint32_t entry_addr;
};

// Multiboot2信息结构
struct multiboot2_info
{
    uint32_t total_size;
    uint32_t reserved;
};

// Multiboot2标签类型
#define MULTIBOOT2_TAG_TYPE_END 0
#define MULTIBOOT2_TAG_TYPE_CMDLINE 1
#define MULTIBOOT2_TAG_TYPE_BOOT_LOADER_NAME 2
#define MULTIBOOT2_TAG_TYPE_MODULE 3
#define MULTIBOOT2_TAG_TYPE_BASIC_MEMINFO 4
#define MULTIBOOT2_TAG_TYPE_BOOTDEV 5
#define MULTIBOOT2_TAG_TYPE_MMAP 6
#define MULTIBOOT2_TAG_TYPE_FRAMEBUFFER 7

#endif // MULTIBOOT2_HEADER_H
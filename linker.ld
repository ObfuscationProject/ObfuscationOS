/* linker.ld - Multiboot2兼容的链接脚本 */
ENTRY(_start)

SECTIONS
{
    /* Multiboot2信息结构必须在前128KB内 */
    . = 1M;

    .multiboot_header : {
        /* Multiboot2头 */
        LONG(0xE85250D6)                    /* 魔数 */
        LONG(0)                             /* 架构: 保护模式i386 */
        LONG(24)                            /* 头长度 */
        LONG(0x100000000 - (0xE85250D6 + 0 + 24))  /* 校验和 */
        LONG(0)                             /* 结束标记类型 */
        LONG(0)                             /* 结束标记大小 */
    }

    /* 代码段 */
    .text : {
        *(.text)
    }

    /* 只读数据段 */
    .rodata : {
        *(.rodata)
    }

    /* 数据段 */
    .data : {
        *(.data)
    }

    /* BSS段 */
    .bss : {
        *(.bss)
    }

    /* 内核结束标记 */
    . = ALIGN(4K);
    kernel_end = .;
}
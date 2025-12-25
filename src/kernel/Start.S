# Start.S - Multiboot2兼容的内核启动代码
.section .multiboot_header
.align 8
multiboot2_header_start:
    .long 0xE85250D6                    # Multiboot2魔数
    .long 0                              # i386架构
    .long multiboot2_header_end - multiboot2_header_start  # 头长度
    .long (- (0xE85250D6 + 0 + (multiboot2_header_end - multiboot2_header_start)) ) & 0xFFFFFFFF  # 校验和
    .long _start                         # 入口地址
    .long 0                              # 保留字段
multiboot2_header_end:

.section .text
.global _start

_start:
    # 检查是否由Multiboot2引导器启动
    # multiboot2信息结构在%rbx中，魔数在%rax中
    # 这里我们简单地忽略multiboot2信息，直接设置栈并跳转到C代码

    # 设置栈
    mov $stack_top, %rsp

    # 保存multiboot2信息（如果需要的话）
    push %rbx  # 保存multiboot2信息指针
    push %rax  # 保存魔数

    # 调用内核主函数
    call kernel_main

    # 如果kernel_main返回（不应该），则进入无限循环
1:
    hlt
    jmp 1b

# 栈定义
.section .bss
.align 16
stack_bottom:
    .skip 8192  # 8KB 栈空间
stack_top:
ENTRY(_start)

SECTIONS
{
    _kernel_start = .;
    . = 0x00100000;

    .multiboot ALIGN(8) : { KEEP(*(.multiboot)) }

    .text ALIGN(0x1000) : { *(.text .text.*) }

    .rodata ALIGN(0x1000) : { *(.rodata .rodata.*) }

    .data ALIGN(0x1000) : { *(.data .data.*) }

    .bss ALIGN(0x1000) : { *(COMMON) *(.bss .bss.*) }

    _kernel_end = .;

    /DISCARD/ : { *(.eh_frame*) *(.comment) *(.note*) }
}

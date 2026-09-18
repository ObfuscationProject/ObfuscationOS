ENTRY(_start)
PHDRS
{
    text PT_LOAD FLAGS(5);
    rodata PT_LOAD FLAGS(4);
    data PT_LOAD FLAGS(6);
}
SECTIONS
{
    . = DEFINED(OK_USER_BASE) ? OK_USER_BASE : 0x40000000;
    .text : { *(.text .text.*) } :text
    . = ALIGN(4096);
    .rodata : { *(.rodata .rodata.*) } :rodata
    . = ALIGN(4096);
    .data : { *(.data .data.* .sdata .sdata.* .got .got.*) } :data
    .bss : { *(.bss .bss.* .sbss .sbss.* COMMON) } :data
    /DISCARD/ : { *(.eh_frame .eh_frame_hdr .comment .note.*) }
}

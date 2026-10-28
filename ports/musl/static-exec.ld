/* Static Linux-personality ET_EXEC layout for musl ports (tools/musl_cc.py).
   Same segments as tests/musl/bootstrap.ld; USER_BASE is supplied by the driver. */
ENTRY(_start)
PHDRS
{
    image PT_LOAD FILEHDR PHDRS FLAGS(5);
    data PT_LOAD FLAGS(6);
    tls PT_TLS FLAGS(4);
    stack PT_GNU_STACK FLAGS(6);
}
SECTIONS
{
    . = USER_BASE + SIZEOF_HEADERS;
    .text : { *(.text .text.*) KEEP(*(.init)) KEEP(*(.fini)) } :image
    .rodata : { *(.rodata .rodata.* .srodata .srodata.*) } :image
    .eh_frame : { *(.eh_frame .eh_frame_hdr) } :image
    . = ALIGN(4096);
    .tdata : { *(.tdata .tdata.*) } :data :tls
    .tbss (NOLOAD) : { *(.tbss .tbss.*) *(.tcommon) } :data :tls
    .data : { *(.data .data.* .sdata .sdata.*) } :data
    .init_array : {
        PROVIDE_HIDDEN(__init_array_start = .);
        KEEP(*(SORT_BY_INIT_PRIORITY(.init_array.*))) KEEP(*(.init_array))
        PROVIDE_HIDDEN(__init_array_end = .);
    } :data
    .fini_array : {
        PROVIDE_HIDDEN(__fini_array_start = .);
        KEEP(*(SORT_BY_INIT_PRIORITY(.fini_array.*))) KEEP(*(.fini_array))
        PROVIDE_HIDDEN(__fini_array_end = .);
    } :data
    . = ALIGN(16);
    _gp = . + 0x7ff0;
    .got : { *(.got .got.*) } :data
    .bss (NOLOAD) : { *(.bss .bss.* .sbss .sbss.*) *(COMMON) } :data
    /DISCARD/ : { *(.note.GNU-stack) *(.comment) }
}

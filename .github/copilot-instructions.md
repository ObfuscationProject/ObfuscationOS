# ObfuscationOS - AI Agent Instructions

## Project Overview
ObfuscationOS is an experimental x86_64 operating system kernel inspired by HarmonyOS, built from scratch with a focus on openness and independent development. This is a **bare-metal kernel** that runs directly on hardware without an underlying OS.

## Architecture & Key Components

### Boot Process & Memory Layout
- **Entry Point**: `_start` in `kernel/x86_64/boot.S` - GRUB2 loads the kernel at ~1MB
- **Boot Mode**: Starts in 32-bit protected mode, transitions to 64-bit long mode
- **Memory Map**: 
  - Identity-maps first 4GiB using 2MiB huge pages
  - AP trampoline at 0x7000, AP params at 0x8000
  - Kernel loaded at 0x00100000 (1MB)
- **Multiboot2**: Header in `.multiboot` section, passes info to `kernel_main(uint32_t magic, uintptr_t info)`

### Core Subsystems

#### 1. **Physical Memory Manager (PMM)** - `kernel/include/kern/mem/pmm.hpp`
- **Purpose**: Manages 4KiB physical frames using a bitmap
- **Key Files**: `kernel/x86_64/src/pmm.cpp`, `kernel/include/kern/mem/pmm.hpp`
- **Workflow**: 
  - Parses Multiboot2 memory map to find available RAM
  - Uses bitmap where each bit represents one 4KiB frame
  - `alloc_frame()` returns physical address, `free_frame()` marks as available
- **Convention**: Returns 0 on OOM, assumes contiguous frames for initial heap

#### 2. **Kernel Heap** - `kernel/include/kern/mem/heap.hpp`
- **Purpose**: Simple bump allocator using PMM frames
- **Key Files**: `kernel/x86_64/src/heap.cpp`
- **Workflow**: 
  - `init(initial_pages)` allocates contiguous frames from PMM
  - `kmalloc(bytes, align)` bumps pointer within heap region
  - **No free()** - this is a bump allocator
- **Convention**: Used for thread stacks and thread structures

#### 3. **Scheduler** - `kernel/include/kern/sched.hpp`
- **Purpose**: Cooperative round-robin scheduler with context switching
- **Key Files**: `kernel/x86_64/src/sched.cpp`, `kernel/x86_64/src/switch.S`
- **Architecture**:
  - **Thread Structure**: Contains saved CPU context (registers), stack, entry function
  - **Run Queue**: Single-linked list managed by `push_runq()`/`pop_runq()`
  - **Context Switch**: Assembly in `switch.S` saves/restores callee-saved regs + RSP/RIP
- **Workflow**:
  1. `create(fn)` allocates Thread + stack, sets up initial context
  2. `yield()` saves current thread, pops next from runq, calls `context_switch()`
  3. Thread entry trampoline calls user function, marks finished, yields again
- **Convention**: Cooperative (not preemptive) - threads must call `yield()`

#### 4. **SMP (Symmetric Multiprocessing)** - `kernel/include/kern/smp.hpp`
- **Purpose**: Starts Application Processors (APs) on multi-core systems
- **Key Files**: `kernel/x86_64/src/smp.cpp`, `kernel/x86_64/ap_trampoline.S`
- **Architecture**:
  - **AP Trampoline**: 16-bit → 32-bit → 64-bit code copied to 0x7000
  - **Boot Parameters**: Struct at 0x8000 contains PML4, entry point, stack, APIC ID
  - **APIC**: Uses Local APIC for IPIs (INIT + SIPI)
- **Workflow**:
  1. Parse ACPI MADT to find APIC IDs
  2. Copy trampoline blob to low memory
  3. Fill params struct with CR3 (PML4), entry point, stack
  4. Send INIT IPI, wait, send SIPI (twice), wait for AP online flag
- **Convention**: APs run `kern::smp::ap_entry()` which just halts (for now)

#### 5. **ACPI** - `kernel/include/kern/acpi.hpp`
- **Purpose**: Parse ACPI tables to find MADT (Multiple APIC Description Table)
- **Key Files**: `kernel/x86_64/src/acpi.cpp`
- **Workflow**:
  1. Find RSDP from Multiboot2 tags (type 14/15)
  2. Validate checksums, prefer XSDT (ACPI 2.0+) over RSDT
  3. Search for MADT signature in XSDT/RSDT entries
  4. Parse MADT to find Local APIC entries
- **Convention**: Checksum validation required, prefers XSDT

#### 6. **APIC** - `kernel/include/hal/apic.hpp`
- **Purpose**: Program Local APIC for IPIs and get LAPIC ID
- **Key Files**: `kernel/x86_64/src/apic.cpp`
- **Workflow**:
  1. Enable APIC via IA32_APIC_BASE MSR (bit 11)
  2. Map MMIO at physical address from MADT
  3. Enable SVR bit 8
  4. Send IPIs via ICR (0x300/0x310)
- **Convention**: Uses MMIO (not x2APIC), crude delays for IPI timing

#### 7. **Console** - `kernel/include/hal/console.hpp`
- **Purpose**: VGA text mode output for debugging
- **Key Files**: `kernel/x86_64/src/console_vga.cpp`
- **Architecture**: Direct writes to 0xB8000 (VGA buffer)
- **Convention**: Supports `\n`, `\r`, hex output for 32/64-bit values

## Build & Development Workflow

### Build System: XMake
```bash
# Build kernel only
xmake build kernel

# Build bootable ISO
xmake iso

# Run in QEMU
xmake qemu
```

### Critical Build Commands (from xmake.lua)
- **Compiler**: C++23 with freestanding flags
- **Key flags**: `-ffreestanding`, `-fno-exceptions`, `-fno-rtti`, `-mno-red-zone`, `-mcmodel=kernel`
- **Linker**: Custom `linker.ld` at 0x00100000, max-page-size=4KiB
- **Output**: `build/linux/x86_64/release/kernel.elf` → ISO with GRUB2

### Debugging with QEMU
```bash
# Run with debug output to stdio and log to qemu.log
qemu-system-x86_64 -m 256M -smp 4 -cdrom build/ObfuscationOS.iso \
  -no-reboot -no-shutdown -d int,cpu_reset -D qemu.log \
  -debugcon stdio -global isa-debugcon.iobase=0xe9
```

**Debug Port**: 0xE9 (isa-debugcon) - kernel writes debug chars here
**QEMU Log**: Captures interrupts, CPU resets for low-level debugging

### Testing Approach
- **No unit tests** - this is bare metal
- **Debug output**: Use `hal::console::write()` and port 0xE9
- **QEMU**: Use `-d int,cpu_reset` to trace interrupts
- **AP boot**: Watch for 'A', 'B', '1', '2', '3', '4', 'C' chars on debug port

## Project-Specific Conventions

### 1. **Memory Management**
- **Physical**: Bitmap-based PMM, 4KiB frames
- **Virtual**: Identity-mapped first 4GiB (initial), no VMM yet
- **Heap**: Bump allocator, no free, used for threads only
- **Stacks**: 16KiB per thread, allocated from heap

### 2. **Threading Model**
- **Cooperative**: Threads must call `yield()` explicitly
- **No preemption**: No timer interrupts yet
- **Single run queue**: Simple linked list, no priorities
- **Thread-local**: `g_current` tracks running thread

### 3. **SMP Boot Protocol**
- **Sequential**: APs started one at a time (safe for temp stacks)
- **Fixed addresses**: 0x7000 (trampoline), 0x8000 (params)
- **Stack pool**: 8 static stacks for APs (16KiB each)
- **Simple sync**: `g_ap_online` counter, no locks yet

### 4. **Error Handling**
- **No exceptions**: `-fno-exceptions` flag
- **Return codes**: 0/nullptr for failures
- **Halt loops**: `for(;;) asm volatile("hlt")` for fatal errors
- **Console messages**: Always print before halting

### 5. **Assembly Conventions**
- **Intel syntax**: `.intel_syntax noprefix`
- **C++ interop**: `extern "C"` for assembly functions
- **Section discipline**: `.text`, `.bss`, `.ap_trampoline`
- **Stack alignment**: 16-byte alignment enforced

### 6. **Data Structure Packing**
- **ACPI**: `#pragma pack(push, 1)` for all tables
- **Context**: Fixed layout in `struct Context` (callee-saved + rsp + rip)
- **AP params**: Fixed memory layout at 0x8000

## Integration Points & Dependencies

### External Dependencies
- **GRUB2**: For ISO creation and booting
- **QEMU**: For emulation (x86_64, 4 cores, 256MB RAM)
- **ACPI**: Hardware tables from firmware
- **Multiboot2**: Boot protocol with memory map and ACPI info

### Cross-Component Communication
- **Boot → Kernel**: Multiboot2 info pointer passed via `rsi` in long mode
- **PMM → Heap**: Heap allocates frames via `pmm::alloc_frame()`
- **Scheduler → Heap**: Threads allocate stacks via `heap::kmalloc()`
- **SMP → ACPI**: Parses MADT to find APIC IDs
- **SMP → APIC**: Sends IPIs to start APs
- **AP trampoline → Kernel**: APs jump to `kern::smp::ap_entry()`

### Hardware Interfaces
- **VGA**: Direct memory-mapped I/O at 0xB8000
- **APIC**: MMIO at LAPIC base from MADT, MSR at 0x1B
- **A20 Gate**: Port 0x92 for enabling A20 line
- **Debug Port**: 0xE9 for QEMU debug output

## Key Files to Reference

### Core Architecture
- `kernel/x86_64/boot.S` - Boot entry, paging setup, long mode transition
- `kernel/x86_64/src/kmain.cpp` - Kernel entry point, subsystem initialization
- `kernel/x86_64/linker.ld` - Memory layout and section placement

### Memory Management
- `kernel/include/kern/mem/pmm.hpp` - PMM interface
- `kernel/x86_64/src/pmm.cpp` - Bitmap implementation
- `kernel/include/kern/mem/heap.hpp` - Heap interface
- `kernel/x86_64/src/heap.cpp` - Bump allocator

### Scheduling & SMP
- `kernel/include/kern/sched.hpp` - Scheduler interface
- `kernel/x86_64/src/sched.cpp` - Round-robin implementation
- `kernel/x86_64/src/switch.S` - Context switch assembly
- `kernel/include/kern/smp.hpp` - SMP interface
- `kernel/x86_64/src/smp.cpp` - AP startup logic
- `kernel/x86_64/ap_trampoline.S` - AP boot blob

### Hardware & ACPI
- `kernel/include/kern/acpi.hpp` - ACPI table structures
- `kernel/x86_64/src/acpi.cpp` - RSDP/XSDT/MADT parsing
- `kernel/include/hal/apic.hpp` - APIC interface
- `kernel/x86_64/src/apic.cpp` - IPI and LAPIC management
- `kernel/include/hal/console.hpp` - Console interface
- `kernel/x86_64/src/console_vga.cpp` - VGA text mode

### Boot Protocol
- `kernel/include/kern/mb2.hpp` - Multiboot2 structures
- `kernel/x86_64/src/mb2.cpp` - Tag parsing utilities

## Common Pitfalls & Solutions

### 1. **AP Won't Start**
- **Check**: Trampoline copied correctly? Params at 0x8000 valid?
- **Debug**: Watch for 'A', 'B', '1', '2', '3', '4', 'C' on port 0xE9
- **Verify**: CR3 loaded, GDT patched, stack set, entry point correct

### 2. **Scheduler Crashes**
- **Check**: Stack alignment (16-byte), thread entry trampoline setup
- **Debug**: Print thread creation success, runq state
- **Verify**: Context switch saves/restores all callee-saved regs

### 3. **Memory Corruption**
- **Check**: PMM bitmap bounds, heap alignment, stack overflow
- **Debug**: Print frame counts, heap start/end
- **Verify**: Identity map covers all needed addresses

### 4. **ACPI Not Found**
- **Check**: Multiboot2 tags present? Checksums valid?
- **Debug**: Print RSDP/XSDT/MADT physical addresses
- **Verify**: XSDT entries are 64-bit, RSDT entries are 32-bit

## Development Guidelines

### Adding New Features
1. **Memory**: Always check PMM/heap allocation failures
2. **Threads**: Ensure stack size sufficient (default 16KiB)
3. **SMP**: Start with single AP, verify before more
4. **Hardware**: Use `volatile` for MMIO, `asm volatile` for I/O
5. **Debug**: Use `hal::console::write()` and port 0xE9 extensively

### Code Style
- **Namespaces**: `kern::`, `hal::`, `kern::mem::`, `kern::sched::`
- **Error handling**: Return 0/nullptr, halt loops for fatal
- **Assembly**: Intel syntax, explicit sections
- **Types**: Use `std::uint{32,64}_t`, `std::size_t` for sizes
- **No C++ exceptions/RTTI**: Freestanding kernel requirements

### Testing New Code
- **Compile**: `xmake build kernel -vD` for verbose output
- **Boot**: `xmake iso` then `xmake qemu`
- **Debug**: Add console prints, watch QEMU debugcon
- **SMP**: Use `-smp N` in QEMU to test multi-core

This project is a **bare-metal kernel** - no standard library, no OS services, direct hardware access. Always think about physical memory, hardware registers, and CPU state when making changes.
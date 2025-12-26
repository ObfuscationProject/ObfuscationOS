#include "hal/console.hpp"
#include "kern/mem/heap.hpp"
#include "kern/mem/pmm.hpp"
#include "kern/sched.hpp"
#include "kern/smp.hpp"
#include <cstdint>

extern "C" void kernel_main(std::uint32_t mb_magic, std::uintptr_t mb_info) noexcept
{
    (void)mb_magic;

    hal::console::clear();
    hal::console::write("Boot OK (long mode)\n");

    hal::console::write("-> pmm::init\n");
    kern::mem::pmm::init(mb_info);
    hal::console::write("-> pmm::init OK\n");

    hal::console::write("-> heap::init\n");
    kern::mem::heap::init(128);
    hal::console::write("-> heap::init OK\n");

    hal::console::write("-> sched::init\n");
    kern::sched::init();
    hal::console::write("-> sched::init OK\n");

    hal::console::write("-> smp::init\n");
    kern::smp::init(mb_info);
    hal::console::write("-> smp::init OK\n");

    hal::console::write("DONE\n");
    for (;;)
        asm volatile("hlt");
}

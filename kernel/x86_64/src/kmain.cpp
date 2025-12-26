#include "hal/console.hpp"
#include "kern/mb2.hpp"
#include "kern/mem/heap.hpp"
#include "kern/mem/pmm.hpp"
#include "kern/sched.hpp"
#include "kern/smp.hpp"

static void worker1() noexcept
{
    for (;;)
    {
        hal::console::write("[T1] hello\n");
        kern::sched::yield();
    }
}
static void worker2() noexcept
{
    for (;;)
    {
        hal::console::write("[T2] world\n");
        kern::sched::yield();
    }
}

extern "C" void kernel_main(std::uint32_t mb_magic, std::uintptr_t mb_info) noexcept
{
    (void)mb_magic;

    hal::console::clear();
    hal::console::write("Boot OK (long mode)\n");

    kern::mem::pmm::init(mb_info);
    kern::mem::heap::init(128);

    kern::sched::init();

    kern::smp::init(mb_info);

    kern::sched::create(worker1);
    kern::sched::create(worker2);

    hal::console::write("Starting scheduler...\n");
    kern::sched::yield();

    for (;;)
        asm volatile("hlt");
}

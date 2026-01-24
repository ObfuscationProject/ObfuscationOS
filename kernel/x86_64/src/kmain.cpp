#include "hal/apic.hpp"
#include "hal/console.hpp"
#include "kern/interrupts.hpp"
#include "kern/mem/heap.hpp"
#include "kern/mem/pmm.hpp"
#include "kern/sched.hpp"
#include "kern/smp.hpp"
#include <cstdint>

static void worker1() noexcept
{
    hal::console::write("[T1] cpu=");
    hal::console::write_hex<std::uint32_t>(hal::apic::lapic_id());
    hal::console::write(" hello\n");
    kern::sched::yield();
}
static void worker2() noexcept
{
    hal::console::write("[T2] cpu=");
    hal::console::write_hex<std::uint32_t>(hal::apic::lapic_id());
    hal::console::write(" world\n");
    kern::sched::yield();
}
static void worker_heap() noexcept
{
    auto *p = kern::mem::heap::kmalloc(64);
    if (p)
        kern::mem::heap::kfree(p);
    hal::console::write("[TH] cpu=");
    hal::console::write_hex<std::uint32_t>(hal::apic::lapic_id());
    hal::console::write(" heap ok\n");
    kern::sched::yield();
}

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

    hal::console::write("-> interrupts::init\n");
    kern::interrupts::init();
    hal::console::write("-> interrupts::init OK\n");

    // Heap free test (single-threaded)
    auto *test = kern::mem::heap::kmalloc(32);
    if (test)
    {
        kern::mem::heap::kfree(test);
        hal::console::write("heap: kfree OK\n");
    }
    else
    {
        hal::console::write("heap: kfree FAILED\n");
    }

    auto *t1 = kern::sched::create(worker1);
    auto *t2 = kern::sched::create(worker2);
    auto *t3 = kern::sched::create(worker_heap);
    if (!t1 || !t2 || !t3)
    {
        hal::console::write("ERROR: thread create failed (heap/pmem)\n");
        for (;;)
            asm volatile("hlt");
    }

    kern::interrupts::enable();
    hal::console::write("Starting scheduler...\n");
    kern::sched::yield();

    hal::console::write("DONE\n");
    for (;;)
        asm volatile("hlt");
}

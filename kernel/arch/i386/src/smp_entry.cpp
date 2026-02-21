#include "hal/apic.hpp"
#include "hal/console.hpp"
#include "kern/interrupts.hpp"
#include "kern/sched.hpp"
#include "kern/smp.hpp"

namespace kern::smp
{

extern "C" void ap_entry(std::uint32_t apic_id) noexcept
{
    // Basic proof: AP is alive.
    hal::console::write("AP online, apic id=");
    hal::console::write_hex<std::uint32_t>(apic_id);
    hal::console::write("\n");

    hal::apic::enable_local();
    kern::interrupts::init();
    kern::sched::init_cpu();
    kern::interrupts::enable();
    kern::sched::run();
}

} // namespace kern::smp

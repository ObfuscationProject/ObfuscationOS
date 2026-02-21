// smp.cpp
#include "hal/smp.hpp"
#include "hal/acpi.hpp"
#include "hal/apic.hpp"
#include "hal/console.hpp"
#include <cstdint>

namespace hal::smp
{

void init(std::uintptr_t mb2_info, const InitHooks &hooks) noexcept
{
    auto root = hal::acpi::find_root_from_mb2(mb2_info);
    auto *madt = hal::acpi::find_madt(root);

    if (!madt)
    {
        hal::console::write("SMP: MADT not found, staying single-core.\n");
        // Fallback: try default LAPIC base so the timer can still work.
        hal::apic::init(0xFEE00000);
        if (hooks.apic_ready)
            hooks.apic_ready();
        if (hooks.register_cpu)
            hooks.register_cpu(hal::apic::lapic_id());
        return;
    }

    hal::apic::init(madt->lapic_addr);
    if (hooks.apic_ready)
        hooks.apic_ready();
    if (hooks.register_cpu)
        hooks.register_cpu(hal::apic::lapic_id());

    hal::console::write("SMP: i386 build uses single-core for now.\n");
}

} // namespace hal::smp

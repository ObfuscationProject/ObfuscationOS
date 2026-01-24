#pragma once
#include <cstdint>

namespace hal::smp
{

using ApEntry = void (*)(std::uint32_t apic_id) noexcept;
using ApicReadyHook = void (*)() noexcept;
using RegisterCpuHook = void (*)(std::uint32_t apic_id) noexcept;

struct InitHooks
{
    ApEntry ap_entry{nullptr};
    ApicReadyHook apic_ready{nullptr};
    RegisterCpuHook register_cpu{nullptr};
};

void init(std::uintptr_t mb2_info, const InitHooks &hooks) noexcept;

} // namespace hal::smp

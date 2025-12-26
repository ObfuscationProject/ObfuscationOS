// smp.hpp
#pragma once
#include <cstddef>
#include <cstdint>

namespace kern::smp
{
void init(std::uintptr_t mb2_info) noexcept;
extern "C" void ap_entry(std::uint32_t apic_id) noexcept;
} // namespace kern::smp

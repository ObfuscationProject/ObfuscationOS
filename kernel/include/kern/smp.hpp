// smp.hpp
#pragma once
#include <cstddef>
#include <cstdint>

namespace kern::smp
{
extern "C" void ap_entry(std::uint32_t apic_id) noexcept;
} // namespace kern::smp

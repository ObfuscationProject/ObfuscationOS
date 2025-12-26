#pragma once
#include <cstddef>
#include <cstdint>

namespace hal::apic
{

void init(std::uintptr_t lapic_phys) noexcept;

std::uint32_t lapic_id() noexcept;

void send_init_ipi(std::uint32_t apic_id) noexcept;
void send_startup_ipi(std::uint32_t apic_id, std::uint8_t vector) noexcept;

} // namespace hal::apic

#pragma once
#include <cstdint>

namespace hal::apic
{

void init(std::uintptr_t lapic_phys) noexcept;
void enable_local() noexcept;

std::uint32_t lapic_id() noexcept;

void eoi() noexcept;
void timer_init(std::uint8_t vector, std::uint32_t initial_count, std::uint8_t divide, bool periodic) noexcept;

void send_init_ipi(std::uint32_t apic_id) noexcept;
void send_startup_ipi(std::uint32_t apic_id, std::uint8_t vector) noexcept;

} // namespace hal::apic

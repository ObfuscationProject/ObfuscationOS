#include "hal/apic.hpp"

namespace hal::apic
{

static volatile std::uint32_t *g_lapic = nullptr;

static inline std::uint32_t rd(std::size_t reg)
{
    return g_lapic[reg / 4];
}
static inline void wr(std::size_t reg, std::uint32_t v)
{
    g_lapic[reg / 4] = v;
    (void)g_lapic[reg / 4]; // read-back to flush
}

static void udelay()
{
    for (volatile int i = 0; i < 200000; ++i)
    {
        asm volatile("pause");
    }
}

void init(std::uintptr_t lapic_phys) noexcept
{
    g_lapic = reinterpret_cast<volatile std::uint32_t *>(lapic_phys);

    // Spurious Interrupt Vector Register (0xF0): set enable bit (8).
    wr(0xF0, rd(0xF0) | 0x100);
}

std::uint32_t lapic_id() noexcept
{
    // LAPIC ID register 0x20, ID is in bits 24..31 for xAPIC
    return rd(0x20) >> 24;
}

void send_init_ipi(std::uint32_t apic_id) noexcept
{
    wr(0x310, apic_id << 24);
    wr(0x300, 0x00004500);
    udelay();
}

void send_startup_ipi(std::uint32_t apic_id, std::uint8_t vector) noexcept
{
    wr(0x310, apic_id << 24);
    wr(0x300, 0x00004600 | vector);
    udelay();
}

} // namespace hal::apic

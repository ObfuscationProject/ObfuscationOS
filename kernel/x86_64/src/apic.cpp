#include "hal/apic.hpp"
#include <cstddef>
#include <cstdint>

namespace hal::apic
{

static volatile std::uint32_t *g_lapic = nullptr;

static inline std::uint64_t rdmsr(std::uint32_t msr) noexcept
{
    std::uint32_t lo, hi;
    asm volatile("rdmsr" : "=a"(lo), "=d"(hi) : "c"(msr));
    return (std::uint64_t(hi) << 32) | lo;
}

static inline void wrmsr(std::uint32_t msr, std::uint64_t v) noexcept
{
    std::uint32_t lo = std::uint32_t(v);
    std::uint32_t hi = std::uint32_t(v >> 32);
    asm volatile("wrmsr" ::"c"(msr), "a"(lo), "d"(hi));
}

static void enable_apic_msr(std::uintptr_t lapic_phys) noexcept
{
    constexpr std::uint32_t IA32_APIC_BASE = 0x1B;

    auto v = rdmsr(IA32_APIC_BASE);

    // Bit 11: APIC Global Enable (must be 1 to use local APIC)
    v |= (1ull << 11);

    // Bit 10: x2APIC enable. We are using xAPIC MMIO, so keep it 0.
    v &= ~(1ull << 10);

    // Program base address bits [35:12] if you want to trust MADT.
    // Keep low 12 bits (flags), replace base.
    v = (v & 0xFFFu) | (std::uint64_t(lapic_phys) & 0xFFFFF000ull);

    wrmsr(IA32_APIC_BASE, v);
}

static inline std::uint32_t rd(std::size_t reg) noexcept
{
    return g_lapic[reg / 4];
}

static inline void wr(std::size_t reg, std::uint32_t v) noexcept
{
    g_lapic[reg / 4] = v;
    (void)g_lapic[reg / 4]; // flush
}

static inline void pause_loop(std::uint32_t iters) noexcept
{
    for (std::uint32_t i = 0; i < iters; ++i)
        asm volatile("pause");
}

static bool wait_delivery(std::uint32_t iters = 2000000) noexcept
{
    // ICR low bit 12 = Delivery Status (1=send pending) :contentReference[oaicite:3]{index=3}
    while (iters--)
    {
        if ((rd(0x300) & (1u << 12)) == 0)
            return true;
        asm volatile("pause");
    }
    return false;
}

void init(std::uintptr_t lapic_phys) noexcept
{
    enable_apic_msr(lapic_phys);
    g_lapic = reinterpret_cast<volatile std::uint32_t *>(lapic_phys);

    // SVR (0xF0) bit8 = enable local APIC
    wr(0xF0, rd(0xF0) | 0x100);
}

std::uint32_t lapic_id() noexcept
{
    return rd(0x20) >> 24;
}

void send_init_ipi(std::uint32_t apic_id) noexcept
{
    wr(0x310, apic_id << 24);
    wr(0x300, 0x00004500); // INIT :contentReference[oaicite:4]{index=4}
    wait_delivery();
    // crude delay ~10ms-ish (no timer yet): make it a bit longer than before
    pause_loop(5000000);
}

void send_startup_ipi(std::uint32_t apic_id, std::uint8_t vector) noexcept
{
    wr(0x310, apic_id << 24);
    wr(0x300, 0x00004600 | vector); // SIPI :contentReference[oaicite:5]{index=5}
    wait_delivery();
    // spec wants ~200us between SIPIs; this is crude but OK for now
    pause_loop(200000);
}

} // namespace hal::apic

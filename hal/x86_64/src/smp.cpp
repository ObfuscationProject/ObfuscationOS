// smp.cpp
#include "hal/smp.hpp"
#include "hal/acpi.hpp"
#include "hal/apic.hpp"
#include "hal/console.hpp"
#include <atomic>
#include <cstddef>
#include <cstdint>

extern "C"
{
    void ap_trampoline_begin();
    void ap_trampoline_end();
}

namespace
{

// AP params at 0x8000 (must match trampoline)
struct ApBootParams
{
    std::uint64_t pml4_phys;
    std::uint64_t entry;
    std::uint64_t stack_top;
    std::uint32_t apic_id;
    std::uint32_t reserved;
};

constexpr std::uintptr_t kTrampolinePhys = 0x7000;
constexpr std::uintptr_t kParamsPhys = 0x8000;

static std::atomic_uint g_ap_online = 0;
static hal::smp::InitHooks g_hooks = {};

static void mem_copy(std::uintptr_t dst, std::uintptr_t src, std::size_t n)
{
    auto *d = reinterpret_cast<std::uint8_t *>(dst);
    auto *s = reinterpret_cast<const std::uint8_t *>(src);
    for (std::size_t i = 0; i < n; ++i)
        d[i] = s[i];
}

static void udelay()
{
    for (int i = 0; i < 200000; ++i)
        asm volatile("pause" ::: "memory");
}

static std::uintptr_t read_cr3()
{
    std::uintptr_t v;
    asm volatile("mov %%cr3, %0" : "=r"(v));
    return v;
}

} // namespace

extern "C" void hal_smp_ap_entry(std::uint32_t apic_id) noexcept
{
    // Basic proof: AP is alive.
    hal::console::write("AP online, apic_id=");
    hal::console::write_hex<std::uint32_t>(apic_id);
    hal::console::write("\n");

    g_ap_online.fetch_add(1, std::memory_order_relaxed);
    hal::apic::enable_local();

    if (g_hooks.ap_entry)
        g_hooks.ap_entry(apic_id);

    for (;;)
        asm volatile("hlt");
}

namespace hal::smp
{

void init(std::uintptr_t mb2_info, const InitHooks &hooks) noexcept
{
    g_hooks = hooks;
    g_ap_online.store(0, std::memory_order_relaxed);

    auto root = hal::acpi::find_root_from_mb2(mb2_info);
    auto *madt = hal::acpi::find_madt(root);

    if (!madt)
    {
        hal::console::write("SMP: MADT not found, staying single-core.\n");
        // Fallback: try default LAPIC base so the timer can still work.
        hal::apic::init(0xFEE00000);
        if (g_hooks.apic_ready)
            g_hooks.apic_ready();
        if (g_hooks.register_cpu)
            g_hooks.register_cpu(hal::apic::lapic_id());
        return;
    }

    hal::apic::init(madt->lapic_addr);
    if (g_hooks.apic_ready)
        g_hooks.apic_ready();
    auto bsp_id = hal::apic::lapic_id();
    if (g_hooks.register_cpu)
        g_hooks.register_cpu(bsp_id);

    if (!g_hooks.ap_entry)
    {
        hal::console::write("SMP: no AP entry, staying single-core.\n");
        return;
    }

    // Copy trampoline blob to 0x7000
    std::uintptr_t src = reinterpret_cast<std::uintptr_t>(ap_trampoline_begin);
    std::uintptr_t end = reinterpret_cast<std::uintptr_t>(ap_trampoline_end);
    mem_copy(kTrampolinePhys, src, static_cast<std::size_t>(end - src));

    auto *params = reinterpret_cast<ApBootParams *>(kParamsPhys);
    params->pml4_phys = read_cr3();
    params->entry = reinterpret_cast<std::uint64_t>(&hal_smp_ap_entry);

    // Enumerate Local APIC entries in MADT
    std::uintptr_t p = reinterpret_cast<std::uintptr_t>(madt) + sizeof(hal::acpi::Madt);
    std::uintptr_t e = reinterpret_cast<std::uintptr_t>(madt) + madt->hdr.length;

    std::uint32_t started = 0;

    while (p + sizeof(hal::acpi::MadtEntryHdr) <= e)
    {
        auto *h = reinterpret_cast<const hal::acpi::MadtEntryHdr *>(p);
        if (h->length < sizeof(hal::acpi::MadtEntryHdr))
            break;

        if (h->type == 0 && h->length >= sizeof(hal::acpi::MadtLocalApic))
        {
            auto *la = reinterpret_cast<const hal::acpi::MadtLocalApic *>(p);
            if ((la->flags & 1u) && la->apic_id != bsp_id)
            {
                // Start AP sequentially (safe temp stack usage)
                static std::uint8_t ap_stack_pool[8][16 * 1024] = {};
                if (started < 8)
                {
                    params->stack_top =
                        reinterpret_cast<std::uint64_t>(&ap_stack_pool[started][sizeof(ap_stack_pool[0])]);
                    params->apic_id = la->apic_id;

                    hal::apic::send_init_ipi(la->apic_id);
                    udelay();

                    std::uint8_t vec = static_cast<std::uint8_t>(kTrampolinePhys >> 12);
                    hal::apic::send_startup_ipi(la->apic_id, vec);
                    udelay();
                    hal::apic::send_startup_ipi(la->apic_id, vec);

                    // Wait for AP online flag (simple, with timeout later)
                    for (int spin = 0; spin < 2000000; ++spin)
                    {
                        if (g_ap_online.load(std::memory_order_relaxed) == started + 1)
                            break;
                        asm volatile("pause" ::: "memory");
                    }

                    if (g_hooks.register_cpu)
                        g_hooks.register_cpu(la->apic_id);
                    ++started;
                }
            }
        }
        p += h->length;
    }

    hal::console::write("SMP: started APs.\n");
}

} // namespace hal::smp

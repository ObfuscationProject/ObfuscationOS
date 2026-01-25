#include "kern/arch/interrupts.hpp"
#include "hal/apic.hpp"
#include "hal/console.hpp"
#include "kern/sched.hpp"
#include <atomic>

namespace kern::interrupts
{

struct IdtEntry
{
    std::uint16_t off_low;
    std::uint16_t sel;
    std::uint8_t ist;
    std::uint8_t flags;
    std::uint16_t off_mid;
    std::uint32_t off_high;
    std::uint32_t zero;
} __attribute__((packed));

struct IdtPtr
{
    std::uint16_t limit;
    std::uint64_t base;
} __attribute__((packed));

static IdtEntry g_idt[256] = {};
static Handler g_handlers[256] = {};
static std::atomic_flag g_idt_lock = ATOMIC_FLAG_INIT;
static std::atomic_bool g_idt_built = false;

extern "C" void (*isr_stub_table[256])() noexcept;

static void timer_handler(Frame *frame) noexcept;
static void spurious_handler(Frame *frame) noexcept;

static inline void outb(std::uint16_t port, std::uint8_t v) noexcept
{
    asm volatile("outb %0, %1" ::"a"(v), "Nd"(port));
}

static void disable_legacy_pic() noexcept
{
    // Mask all IRQs on both PICs.
    outb(0x21, 0xFF);
    outb(0xA1, 0xFF);
}

static void set_gate(std::uint8_t vec, void (*isr)() noexcept) noexcept
{
    constexpr std::uint16_t kCodeSel = 0x08;
    constexpr std::uint8_t kFlags = 0x8E; // present, DPL0, interrupt gate

    auto addr = reinterpret_cast<std::uint64_t>(isr);
    g_idt[vec].off_low = static_cast<std::uint16_t>(addr & 0xFFFFu);
    g_idt[vec].sel = kCodeSel;
    g_idt[vec].ist = 0;
    g_idt[vec].flags = kFlags;
    g_idt[vec].off_mid = static_cast<std::uint16_t>((addr >> 16) & 0xFFFFu);
    g_idt[vec].off_high = static_cast<std::uint32_t>((addr >> 32) & 0xFFFFFFFFu);
    g_idt[vec].zero = 0;
}

static void load_idt() noexcept
{
    IdtPtr idtr{static_cast<std::uint16_t>(sizeof(g_idt) - 1), reinterpret_cast<std::uint64_t>(&g_idt[0])};
    asm volatile("lidt %0" : : "m"(idtr));
}

static void build_idt_once() noexcept
{
    if (g_idt_built.load(std::memory_order_acquire))
        return;

    while (g_idt_lock.test_and_set(std::memory_order_acquire))
        asm volatile("pause");

    if (!g_idt_built.load(std::memory_order_relaxed))
    {
        disable_legacy_pic();

        for (std::size_t i = 0; i < 256; ++i)
            set_gate(static_cast<std::uint8_t>(i), isr_stub_table[i]);

        register_handler(kTimerVector, timer_handler);
        register_handler(kSpuriousVector, spurious_handler);

        g_idt_built.store(true, std::memory_order_release);
    }

    g_idt_lock.clear(std::memory_order_release);
}

void register_handler(std::uint8_t vector, Handler handler) noexcept
{
    g_handlers[vector] = handler;
}

static void timer_handler(Frame *frame) noexcept
{
    hal::apic::eoi();
    kern::sched::yield_from_irq(frame);
}

static void spurious_handler(Frame *frame) noexcept
{
    (void)frame;
    hal::apic::eoi();
}

extern "C" __attribute__((force_align_arg_pointer)) void isr_dispatch(Frame *frame) noexcept
{
    if (!frame)
        return;

    auto handler = g_handlers[static_cast<std::uint8_t>(frame->vector)];
    if (handler)
    {
        handler(frame);
        return;
    }

    // Unhandled vector: halt on exceptions, EOI on external IRQs.
    if (frame->vector < 0x20)
    {
        hal::console::write("Unhandled exception, vector=");
        hal::console::write_hex<std::uint32_t>(static_cast<std::uint32_t>(frame->vector));
        hal::console::write(" error=");
        hal::console::write_hex<std::uint32_t>(static_cast<std::uint32_t>(frame->error));
        hal::console::write("\\n");
        for (;;)
            asm volatile("hlt");
    }
    hal::apic::eoi();
}

void init() noexcept
{
    build_idt_once();
    load_idt();

    // Configure LAPIC timer for periodic interrupts.
    hal::apic::timer_init(kTimerVector, 1000000, 0x3, true); // divide=16, count≈tunable
}

void enable() noexcept
{
    asm volatile("sti");
}

void disable() noexcept
{
    asm volatile("cli");
}

std::uint64_t save() noexcept
{
    std::uint64_t flags = 0;
    asm volatile("pushfq; pop %0" : "=r"(flags));
    return flags;
}

void restore(std::uint64_t flags) noexcept
{
    asm volatile("push %0; popfq" : : "r"(flags) : "memory", "cc");
}

} // namespace kern::interrupts

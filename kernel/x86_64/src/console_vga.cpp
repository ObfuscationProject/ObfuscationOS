#include "hal/console.hpp"
#include <atomic>
#include <cstddef>
#include <cstdint>

namespace
{

constexpr std::size_t kVgaWidth = 80;
constexpr std::size_t kVgaHeight = 25;

volatile std::uint16_t *const kVgaBuffer = reinterpret_cast<volatile std::uint16_t *>(0xB8000);

std::size_t g_row = 0;
std::size_t g_col = 0;
std::atomic_flag g_console_lock = ATOMIC_FLAG_INIT;

// Light gray on black.
constexpr std::uint8_t kAttr = 0x07;

constexpr std::uint16_t make_cell(char c, std::uint8_t attr)
{
    return (static_cast<std::uint16_t>(attr) << 8) | static_cast<std::uint8_t>(c);
}

void scroll_if_needed() noexcept
{
    if (g_row < kVgaHeight)
        return;

    // Scroll up by 1 row.
    for (std::size_t r = 1; r < kVgaHeight; ++r)
    {
        for (std::size_t c = 0; c < kVgaWidth; ++c)
        {
            kVgaBuffer[(r - 1) * kVgaWidth + c] = kVgaBuffer[r * kVgaWidth + c];
        }
    }

    // Clear last row.
    for (std::size_t c = 0; c < kVgaWidth; ++c)
    {
        kVgaBuffer[(kVgaHeight - 1) * kVgaWidth + c] = make_cell(' ', kAttr);
    }

    g_row = kVgaHeight - 1;
    g_col = 0;
}

void put_char(char ch) noexcept
{
    if (ch == '\n')
    {
        g_col = 0;
        ++g_row;
        scroll_if_needed();
        return;
    }
    if (ch == '\r')
    {
        g_col = 0;
        return;
    }

    kVgaBuffer[g_row * kVgaWidth + g_col] = make_cell(ch, kAttr);
    ++g_col;
    if (g_col >= kVgaWidth)
    {
        g_col = 0;
        ++g_row;
        scroll_if_needed();
    }
}

static inline std::uint64_t irq_save() noexcept
{
    std::uint64_t flags = 0;
    asm volatile("pushfq; pop %0; cli" : "=r"(flags) :: "memory");
    return flags;
}

static inline void irq_restore(std::uint64_t flags) noexcept
{
    asm volatile("push %0; popfq" : : "r"(flags) : "memory", "cc");
}

static inline void lock() noexcept
{
    while (g_console_lock.test_and_set(std::memory_order_acquire))
        asm volatile("pause");
}

static inline void unlock() noexcept
{
    g_console_lock.clear(std::memory_order_release);
}

} // namespace

namespace hal::console
{

void clear() noexcept
{
    auto flags = irq_save();
    lock();
    for (std::size_t r = 0; r < kVgaHeight; ++r)
    {
        for (std::size_t c = 0; c < kVgaWidth; ++c)
        {
            kVgaBuffer[r * kVgaWidth + c] = make_cell(' ', kAttr);
        }
    }
    g_row = 0;
    g_col = 0;
    unlock();
    irq_restore(flags);
}

void write(const char *s) noexcept
{
    if (!s)
        return;
    auto flags = irq_save();
    lock();
    while (*s)
    {
        put_char(*s++);
    }
    unlock();
    irq_restore(flags);
}

void write(const char *s, std::size_t n) noexcept
{
    if (!s)
        return;
    auto flags = irq_save();
    lock();
    for (std::size_t i = 0; i < n; ++i)
    {
        put_char(s[i]);
    }
    unlock();
    irq_restore(flags);
}

template <> void write_hex<std::uint64_t>(std::uint64_t v) noexcept
{
    auto flags = irq_save();
    lock();
    const char *hex = "0123456789ABCDEF";
    for (int i = 15; i >= 0; --i)
    {
        char c = hex[(v >> (i * 4)) & 0xF];
        put_char(c);
    }
    unlock();
    irq_restore(flags);
}

template <> void write_hex<std::uint32_t>(std::uint32_t v) noexcept
{
    auto flags = irq_save();
    lock();
    const char *hex = "0123456789ABCDEF";
    for (int i = 7; i >= 0; --i)
    {
        char c = hex[(v >> (i * 4)) & 0xF];
        put_char(c);
    }
    unlock();
    irq_restore(flags);
}

} // namespace hal::console

#include "hal/console.hpp"
#include <cstddef>
#include <cstdint>

namespace
{

constexpr std::size_t kVgaWidth = 80;
constexpr std::size_t kVgaHeight = 25;

volatile std::uint16_t *const kVgaBuffer = reinterpret_cast<volatile std::uint16_t *>(0xB8000);

std::size_t g_row = 0;
std::size_t g_col = 0;

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

} // namespace

namespace hal::console
{

void clear() noexcept
{
    for (std::size_t r = 0; r < kVgaHeight; ++r)
    {
        for (std::size_t c = 0; c < kVgaWidth; ++c)
        {
            kVgaBuffer[r * kVgaWidth + c] = make_cell(' ', kAttr);
        }
    }
    g_row = 0;
    g_col = 0;
}

void write(const char *s) noexcept
{
    if (!s)
        return;
    while (*s)
    {
        put_char(*s++);
    }
}

void write(const char *s, std::size_t n) noexcept
{
    if (!s)
        return;
    for (std::size_t i = 0; i < n; ++i)
    {
        put_char(s[i]);
    }
}

} // namespace hal::console

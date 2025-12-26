#pragma once
#include <cstddef>
#include <cstdint>

namespace hal::console
{

// Clears the screen and resets cursor.
void clear() noexcept;

// Writes a null-terminated string to the console.
void write(const char *s) noexcept;

// Writes a buffer with explicit length.
void write(const char *s, std::size_t n) noexcept;

template <typename dtype> void write_hex(dtype) noexcept
{
    static_assert(sizeof(dtype) == 0, "dtype is not implement");
}
template <> void write_hex<std::uint64_t>(std::uint64_t v) noexcept;
template <> void write_hex<std::uint32_t>(std::uint32_t v) noexcept;

} // namespace hal::console

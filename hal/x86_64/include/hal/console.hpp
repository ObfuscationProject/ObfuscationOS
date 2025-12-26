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

void write_hex_u64(std::uint64_t v) noexcept;

} // namespace hal::console

#pragma once
#include <cstdint>

namespace kern::interrupts
{

struct Frame;
using Handler = void (*)(Frame *) noexcept;

void init() noexcept;
void register_handler(std::uint8_t vector, Handler handler) noexcept;

void enable() noexcept;
void disable() noexcept;
std::uint64_t save() noexcept;
void restore(std::uint64_t flags) noexcept;

} // namespace kern::interrupts

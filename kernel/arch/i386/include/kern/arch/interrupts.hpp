#pragma once
#include <cstdint>
#include "kern/interrupts.hpp"

namespace kern::interrupts
{

constexpr std::uint8_t kTimerVector = 0x20;
constexpr std::uint8_t kSpuriousVector = 0xFF;

struct Frame
{
    std::uint32_t edi;
    std::uint32_t esi;
    std::uint32_t ebp;
    std::uint32_t ebx;
    std::uint32_t edx;
    std::uint32_t ecx;
    std::uint32_t eax;

    std::uint32_t vector;
    std::uint32_t error;

    std::uint32_t eip;
    std::uint32_t cs;
    std::uint32_t eflags;
    std::uint32_t esp;
    std::uint32_t ss;
};

} // namespace kern::interrupts

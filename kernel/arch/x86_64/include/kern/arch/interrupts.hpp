#pragma once
#include <cstdint>
#include "kern/interrupts.hpp"

namespace kern::interrupts
{

constexpr std::uint8_t kTimerVector = 0x20;
constexpr std::uint8_t kSpuriousVector = 0xFF;

struct Frame
{
    std::uint64_t r15;
    std::uint64_t r14;
    std::uint64_t r13;
    std::uint64_t r12;
    std::uint64_t r11;
    std::uint64_t r10;
    std::uint64_t r9;
    std::uint64_t r8;

    std::uint64_t rdi;
    std::uint64_t rsi;
    std::uint64_t rbp;
    std::uint64_t rbx;
    std::uint64_t rdx;
    std::uint64_t rcx;
    std::uint64_t rax;

    std::uint64_t vector;
    std::uint64_t error;

    std::uint64_t rip;
    std::uint64_t cs;
    std::uint64_t rflags;
    std::uint64_t rsp;
    std::uint64_t ss;
};

} // namespace kern::interrupts

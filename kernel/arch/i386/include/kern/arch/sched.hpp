#pragma once
#include <cstddef>
#include <cstdint>
#include "kern/sched.hpp"

namespace kern::sched
{

struct Context
{
    std::uint32_t ebx, ebp, esi, edi;
    std::uint32_t esp;
    std::uint32_t eip;
};

struct Thread
{
    Context ctx{};
    Thread *next{nullptr};
    Thread *all_next{nullptr};
    ThreadFn entry{nullptr};
    bool finished{false};
    std::uint8_t *stack{nullptr};
    std::size_t stack_size{0};
};

extern "C" void context_switch(Context *oldc, Context *newc) noexcept;

} // namespace kern::sched

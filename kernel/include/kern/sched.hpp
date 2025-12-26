#pragma once
#include <cstddef>
#include <cstdint>

namespace kern::sched
{

using ThreadFn = void (*)() noexcept;

struct Context
{
    std::uint64_t rbx, rbp, r12, r13, r14, r15;
    std::uint64_t rsp;
    std::uint64_t rip;
};

struct Thread
{
    Context ctx{};
    Thread *next{nullptr};
    ThreadFn entry{nullptr};
    bool finished{false};
    std::uint8_t *stack{nullptr};
    std::size_t stack_size{0};
};

extern "C" void context_switch(Context *oldc, Context *newc) noexcept;

void init() noexcept;
Thread *create(ThreadFn fn, std::size_t stack_size = 16 * 1024) noexcept;
void yield() noexcept;

} // namespace kern::sched

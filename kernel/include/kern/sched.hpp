#pragma once
#include <cstddef>
#include <cstdint>
#include "kern/interrupts.hpp"

namespace kern::sched
{

using ThreadFn = void (*)() noexcept;

struct Thread;

void init() noexcept;
void init_cpu() noexcept;
void apic_ready() noexcept;
void register_cpu(std::uint32_t apic_id) noexcept;
Thread *create(ThreadFn fn, std::size_t stack_size = 16 * 1024) noexcept;
void yield() noexcept;
void yield_from_irq(kern::interrupts::Frame *frame) noexcept;
void run() noexcept;

} // namespace kern::sched

#include "kern/sched.hpp"
#include "hal/console.hpp"
#include "kern/interrupts.hpp"
#include "kern/mem/heap.hpp"
#include <cstdint>

namespace kern::sched
{

static Thread *g_runq = nullptr;
static Thread *g_current = nullptr;

extern "C" void thread_entry_trampoline() noexcept;
extern "C" void irq_return_trampoline() noexcept;

static Thread *pop_runq() noexcept
{
    if (!g_runq)
        return nullptr;
    Thread *t = g_runq;
    g_runq = g_runq->next;
    t->next = nullptr;
    return t;
}

static void push_runq(Thread *t) noexcept
{
    t->next = nullptr;
    if (!g_runq)
    {
        g_runq = t;
        return;
    }
    Thread *p = g_runq;
    while (p->next)
        p = p->next;
    p->next = t;
}

extern "C" void thread_entry_trampoline() noexcept
{
    if (!g_current || !g_current->entry)
    {
        for (;;)
            asm volatile("hlt");
    }
    kern::interrupts::enable();
    g_current->entry();
    g_current->finished = true;
    yield();
    for (;;)
        asm volatile("hlt");
}

void init() noexcept
{
    // Create a dummy "current" thread for BSP context.
    static Thread bootstrap{};
    g_current = &bootstrap;
}

Thread *create(ThreadFn fn, std::size_t stack_size) noexcept
{
    auto *t = reinterpret_cast<Thread *>(kern::mem::heap::kmalloc(sizeof(Thread), alignof(Thread)));
    if (!t)
        return nullptr;

    auto *stack = reinterpret_cast<std::uint8_t *>(kern::mem::heap::kmalloc(stack_size, 16));
    if (!stack)
        return nullptr;

    *t = {};
    t->entry = fn;
    t->stack = stack;
    t->stack_size = stack_size;

    std::uintptr_t sp = reinterpret_cast<std::uintptr_t>(stack + stack_size);
    sp &= ~std::uintptr_t(0xF);

    // We jump into a normal C++ function (not call), so emulate a call frame:
    // place a fake return address and make RSP % 16 == 8 on function entry.
    sp -= 8;
    *reinterpret_cast<std::uint64_t *>(sp) = 0;

    t->ctx.rsp = sp;
    t->ctx.rip = reinterpret_cast<std::uint64_t>(&thread_entry_trampoline);

    push_runq(t);
    return t;
}

void yield() noexcept
{
    kern::interrupts::disable();
    Thread *prev = g_current;

    // Put current back if it is a real thread and not finished.
    if (prev && prev->entry && !prev->finished)
    {
        push_runq(prev);
    }

    Thread *next = pop_runq();
    if (!next)
    {
        hal::console::write("No runnable threads; halting.\n");
        for (;;)
            asm volatile("hlt");
    }

    g_current = next;
    context_switch(&prev->ctx, &next->ctx);
}

void yield_from_irq(kern::interrupts::Frame *frame) noexcept
{
    Thread *prev = g_current;

    if (!prev || !prev->entry || prev->finished)
        return;

    if (!g_runq)
        return;

    prev->ctx.rsp = reinterpret_cast<std::uint64_t>(frame);
    prev->ctx.rip = reinterpret_cast<std::uint64_t>(&irq_return_trampoline);

    push_runq(prev);
    Thread *next = pop_runq();
    if (!next)
        return;

    g_current = next;
    Context tmp{};
    context_switch(&tmp, &next->ctx);
}

} // namespace kern::sched

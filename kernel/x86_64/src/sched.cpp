#include "kern/sched.hpp"
#include "hal/apic.hpp"
#include "hal/console.hpp"
#include "kern/interrupts.hpp"
#include "kern/mem/heap.hpp"
#include <atomic>
#include <cstdint>

namespace kern::sched
{

constexpr std::size_t kMaxCpus = 256;

static Thread *g_runq = nullptr;
static Thread *g_current[kMaxCpus] = {};
static Thread g_bootstrap[kMaxCpus] = {};
static std::atomic_flag g_runq_lock = ATOMIC_FLAG_INIT;
static bool g_apic_ready = false;

extern "C" void thread_entry_trampoline() noexcept;
extern "C" void irq_return_trampoline() noexcept;

static inline void runq_lock() noexcept
{
    while (g_runq_lock.test_and_set(std::memory_order_acquire))
        asm volatile("pause");
}

static inline void runq_unlock() noexcept
{
    g_runq_lock.clear(std::memory_order_release);
}

static inline std::size_t cpu_index() noexcept
{
    if (!g_apic_ready)
        return 0;
    return static_cast<std::size_t>(hal::apic::lapic_id());
}

static Thread *pop_runq_locked() noexcept
{
    if (!g_runq)
        return nullptr;
    Thread *t = g_runq;
    g_runq = g_runq->next;
    t->next = nullptr;
    return t;
}

static void push_runq_locked(Thread *t) noexcept
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

static Thread *pop_runq() noexcept
{
    runq_lock();
    Thread *t = pop_runq_locked();
    runq_unlock();
    return t;
}

static void push_runq(Thread *t) noexcept
{
    runq_lock();
    push_runq_locked(t);
    runq_unlock();
}

extern "C" void thread_entry_trampoline() noexcept
{
    auto *cur = g_current[cpu_index()];
    if (!cur || !cur->entry)
    {
        for (;;)
            asm volatile("hlt");
    }
    kern::interrupts::enable();
    cur->entry();
    cur->finished = true;
    yield();
    for (;;)
        asm volatile("hlt");
}

void init() noexcept
{
    // Create a dummy "current" thread for BSP context.
    g_current[0] = &g_bootstrap[0];
}

void init_cpu() noexcept
{
    g_current[cpu_index()] = &g_bootstrap[cpu_index()];
}

void apic_ready() noexcept
{
    g_apic_ready = true;
    std::size_t id = cpu_index();
    if (!g_current[id])
        g_current[id] = g_current[0];
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
    Thread *prev = g_current[cpu_index()];

    // Put current back if it is a real thread and not finished.
    if (prev && prev->entry && !prev->finished)
    {
        runq_lock();
        push_runq_locked(prev);
        runq_unlock();
    }

    Thread *next = pop_runq();
    while (!next)
    {
        kern::interrupts::enable();
        asm volatile("hlt");
        kern::interrupts::disable();
        next = pop_runq();
    }

    g_current[cpu_index()] = next;
    context_switch(&prev->ctx, &next->ctx);
}

void yield_from_irq(kern::interrupts::Frame *frame) noexcept
{
    Thread *prev = g_current[cpu_index()];

    if (!prev || !prev->entry || prev->finished)
        return;

    prev->ctx.rsp = reinterpret_cast<std::uint64_t>(frame);
    prev->ctx.rip = reinterpret_cast<std::uint64_t>(&irq_return_trampoline);

    runq_lock();
    push_runq_locked(prev);
    Thread *next = pop_runq_locked();
    runq_unlock();
    if (!next)
        return;

    g_current[cpu_index()] = next;
    Context tmp{};
    context_switch(&tmp, &next->ctx);
}

void run() noexcept
{
    for (;;)
        yield();
}

} // namespace kern::sched

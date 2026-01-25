#include "kern/arch/sched.hpp"
#include "hal/apic.hpp"
#include "kern/interrupts.hpp"
#include "kern/mem/heap.hpp"
#include <atomic>
#include <cstdint>

namespace kern::sched
{

constexpr std::size_t kMaxCpus = 256;

static Thread *g_runq[kMaxCpus] = {};
static std::atomic_flag g_runq_lock[kMaxCpus];

static Thread *g_current[kMaxCpus] = {};
static Thread g_bootstrap[kMaxCpus] = {};

static Thread *g_all_threads = nullptr;
static std::atomic_flag g_all_lock = ATOMIC_FLAG_INIT;

static std::uint32_t g_cpu_list[kMaxCpus] = {};
static std::atomic_flag g_cpu_lock = ATOMIC_FLAG_INIT;
static std::atomic_uint g_cpu_count = 0;
static std::atomic_uint g_rr_counter = 0;
static std::atomic_bool g_apic_ready = false;

extern "C" void thread_entry_trampoline() noexcept;
extern "C" void irq_return_trampoline() noexcept;

static inline void runq_lock(std::size_t cpu) noexcept
{
    while (g_runq_lock[cpu].test_and_set(std::memory_order_acquire))
        asm volatile("pause");
}

static inline void runq_unlock(std::size_t cpu) noexcept
{
    g_runq_lock[cpu].clear(std::memory_order_release);
}

static inline void all_lock() noexcept
{
    while (g_all_lock.test_and_set(std::memory_order_acquire))
        asm volatile("pause");
}

static inline void all_unlock() noexcept
{
    g_all_lock.clear(std::memory_order_release);
}

static inline void cpu_list_lock() noexcept
{
    while (g_cpu_lock.test_and_set(std::memory_order_acquire))
        asm volatile("pause");
}

static inline void cpu_list_unlock() noexcept
{
    g_cpu_lock.clear(std::memory_order_release);
}

static inline std::size_t cpu_index() noexcept
{
    if (!g_apic_ready.load(std::memory_order_acquire))
        return 0;
    auto id = static_cast<std::size_t>(hal::apic::lapic_id());
    if (id >= kMaxCpus)
        return 0;
    return id;
}

static Thread *pop_runq_locked(std::size_t cpu) noexcept
{
    Thread *head = g_runq[cpu];
    if (!head)
        return nullptr;
    g_runq[cpu] = head->next;
    head->next = nullptr;
    return head;
}

static void push_runq_locked(std::size_t cpu, Thread *t) noexcept
{
    t->next = nullptr;
    if (!g_runq[cpu])
    {
        g_runq[cpu] = t;
        return;
    }
    Thread *p = g_runq[cpu];
    while (p->next)
        p = p->next;
    p->next = t;
}

static Thread *pop_runq(std::size_t cpu) noexcept
{
    runq_lock(cpu);
    Thread *t = pop_runq_locked(cpu);
    runq_unlock(cpu);
    return t;
}

static void push_runq(std::size_t cpu, Thread *t) noexcept
{
    runq_lock(cpu);
    push_runq_locked(cpu, t);
    runq_unlock(cpu);
}

static void add_all_threads(Thread *t) noexcept
{
    all_lock();
    t->all_next = g_all_threads;
    g_all_threads = t;
    all_unlock();
}

static std::size_t pick_target_cpu() noexcept
{
    std::size_t count = g_cpu_count.load(std::memory_order_relaxed);
    if (count == 0)
        return cpu_index();
    if (count > kMaxCpus)
        count = kMaxCpus;

    cpu_list_lock();
    std::size_t idx = static_cast<std::size_t>(g_rr_counter.fetch_add(1, std::memory_order_relaxed)) % count;
    std::size_t apic_id = static_cast<std::size_t>(g_cpu_list[idx]);
    cpu_list_unlock();
    return apic_id;
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
    for (std::size_t i = 0; i < kMaxCpus; ++i)
        g_runq_lock[i].clear(std::memory_order_release);

    g_current[0] = &g_bootstrap[0];
    g_all_threads = nullptr;
    g_all_lock.clear(std::memory_order_release);
    g_rr_counter.store(0, std::memory_order_relaxed);
    g_cpu_count.store(0, std::memory_order_relaxed);
    g_cpu_lock.clear(std::memory_order_release);
    g_apic_ready.store(false, std::memory_order_release);
}

void init_cpu() noexcept
{
    g_current[cpu_index()] = &g_bootstrap[cpu_index()];
}

void apic_ready() noexcept
{
    g_apic_ready.store(true, std::memory_order_release);
    std::size_t id = cpu_index();
    if (!g_current[id])
        g_current[id] = g_current[0];
}

void register_cpu(std::uint32_t apic_id) noexcept
{
    if (apic_id >= kMaxCpus)
        return;

    cpu_list_lock();
    std::size_t count = g_cpu_count.load(std::memory_order_relaxed);
    for (std::size_t i = 0; i < count; ++i)
    {
        if (g_cpu_list[i] == apic_id)
        {
            cpu_list_unlock();
            return;
        }
    }
    if (count >= kMaxCpus)
    {
        cpu_list_unlock();
        return;
    }

    g_cpu_list[count] = apic_id;
    g_cpu_count.store(static_cast<unsigned>(count + 1), std::memory_order_relaxed);
    cpu_list_unlock();
}

Thread *create(ThreadFn fn, std::size_t stack_size) noexcept
{
    auto *t = reinterpret_cast<Thread *>(kern::mem::heap::kmalloc(sizeof(Thread), alignof(Thread)));
    if (!t)
        return nullptr;

    auto *stack = reinterpret_cast<std::uint8_t *>(kern::mem::heap::kmalloc(stack_size, 16));
    if (!stack)
    {
        kern::mem::heap::kfree(t);
        return nullptr;
    }

    *t = {};
    t->entry = fn;
    t->stack = stack;
    t->stack_size = stack_size;

    std::uintptr_t sp = reinterpret_cast<std::uintptr_t>(stack + stack_size);
    sp &= ~std::uintptr_t(0xF);

    // We jump into a normal C++ function (not call), so emulate a call frame:
    // place a fake return address and make ESP % 16 == 12 on function entry.
    sp -= 4;
    *reinterpret_cast<std::uint32_t *>(sp) = 0;

    t->ctx.esp = static_cast<std::uint32_t>(sp);
    t->ctx.eip = static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(&thread_entry_trampoline));

    add_all_threads(t);
    push_runq(pick_target_cpu(), t);
    return t;
}

void yield() noexcept
{
    kern::interrupts::disable();
    std::size_t cpu = cpu_index();
    Thread *prev = g_current[cpu];

    // Put current back if it is a real thread and not finished.
    if (prev && prev->entry && !prev->finished)
        push_runq(cpu, prev);

    Thread *next = pop_runq(cpu);
    while (!next)
    {
        kern::interrupts::enable();
        asm volatile("hlt");
        kern::interrupts::disable();
        next = pop_runq(cpu);
    }

    g_current[cpu] = next;
    context_switch(&prev->ctx, &next->ctx);
}

void yield_from_irq(kern::interrupts::Frame *frame) noexcept
{
    std::size_t cpu = cpu_index();
    Thread *prev = g_current[cpu];

    if (!prev || !prev->entry || prev->finished)
        return;

    prev->ctx.esp = static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(frame));
    prev->ctx.eip = static_cast<std::uint32_t>(reinterpret_cast<std::uintptr_t>(&irq_return_trampoline));

    runq_lock(cpu);
    push_runq_locked(cpu, prev);
    Thread *next = pop_runq_locked(cpu);
    runq_unlock(cpu);
    if (!next)
        return;

    g_current[cpu] = next;
    Context tmp{};
    context_switch(&tmp, &next->ctx);
}

void run() noexcept
{
    for (;;)
        yield();
}

} // namespace kern::sched

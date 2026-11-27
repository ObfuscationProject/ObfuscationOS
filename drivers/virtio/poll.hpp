#pragma once
#include "ok/core/types.hpp"
#include "ok/interrupt/platform.hpp"
#include "ok/smp/kernel_section.hpp"
#include <atomic>
#include <concepts>

namespace os::drivers::detail
{
// Polled completion is an explicit build choice (the virtio_polling option).
// Otherwise a driver polls only before the kernel's interrupt service starts
// or when its line cannot be bound, and the kernel counts every polled wait
// (OK_IRQ_COMPLETIONS).
#ifdef OS_VIRTIO_POLLING
inline constexpr bool polling_selected = true;
#else
inline constexpr bool polling_selected = false;
#endif
// Serialized boot-CPU polling. Completion wins a deadline tie; a clock error
// is explicit. Iteration count and CPU speed are not elapsed-time measures.
// Inside a kernel section (interrupts masked, no kernel lock) every pass
// serves this CPU's pending top halves, so a kernel-lock holder waiting for a
// line routed here is not stalled behind the poll; elsewhere it is a no-op.
template <typename Ready, typename Clock>
    requires requires(Ready ready, Clock clock) {
        { ready() } -> std::same_as<bool>;
        { clock() } -> std::same_as<ok::Result<ok::u64>>;
    }
ok::Status poll_until(Ready ready, Clock clock, ok::u64 start, ok::u64 timeout)
{
    for (;;)
    {
        if (ready())
            return ok::Status::success();
        ok::smp::serve_while_polling();
        auto now = clock();
        if (!now)
            return now.status();
        if (now.value() < start)
            return ok::Status::fault("Virtio block monotonic clock regressed");
        if (now.value() - start >= timeout)
            return ready() ? ok::Status::success() : ok::Status::fault("Virtio block completion timed out");
    }
}
// Interrupt-driven completion: ready() is checked once, then again only after
// signalled() reports that the device's own line fired; other wakes (the tick,
// other lines) only advance the deadline. wait() sleeps until an interrupt has
// been taken and its bottom halves have run, and returns false when the
// platform cannot sleep: the rest of the deadline is then polled.
//
// SMP: outside a kernel section the caller holds the kernel lock across the
// whole wait, on any CPU. The device's line may be routed to another CPU,
// whose top half ends this CPU's wait with an IPI; the bottom halves then run
// here, under the lock. Inside a section (an ext4 regular-file call) wait()
// refuses, and the rest of the deadline is polled without the kernel lock.
template <typename Ready, typename Signalled, typename Clock, typename Wait>
    requires requires(Ready ready, Signalled signalled, Clock clock, Wait wait) {
        { ready() } -> std::same_as<bool>;
        { signalled() } -> std::same_as<bool>;
        { clock() } -> std::same_as<ok::Result<ok::u64>>;
        { wait() } -> std::same_as<bool>;
    }
ok::Status wait_until(Ready ready, Signalled signalled, Clock clock, ok::u64 start, ok::u64 timeout, Wait wait)
{
    for (bool check = true;; check = signalled())
    {
        if (check && ready())
            return ok::Status::success();
        auto now = clock();
        if (!now)
            return now.status();
        if (now.value() < start)
            return ok::Status::fault("Virtio block monotonic clock regressed");
        if (now.value() - start >= timeout)
            return ready() ? ok::Status::success() : ok::Status::fault("Virtio block completion timed out");
        if (!wait())
            return poll_until(ready, clock, start, timeout);
    }
}
// A bottom half's "the device's line fired" flag for a waiter. A bottom half
// may run on another CPU than its waiter (kernel spec 4.13): on the profiles
// that start secondary CPUs take() is one word exchange, so a raise() between
// a load and a clearing store cannot be lost. Every profile has a word
// exchange, not every one a byte exchange; the one-CPU profiles keep a load
// and a store.
#if defined(__x86_64__) || defined(__aarch64__) || (defined(__riscv) && __riscv_xlen == 64)
inline constexpr bool device_signal_exchange = true;
#else
inline constexpr bool device_signal_exchange = false;
#endif
class DeviceSignal final
{
  public:
    void raise() noexcept
    {
        raised_.store(1, std::memory_order_release);
    }
    // Whether the line fired since the last take(); clears it.
    [[nodiscard]] bool take() noexcept
    {
        if constexpr (device_signal_exchange)
            return raised_.exchange(0, std::memory_order_acq_rel) != 0;
        if (!raised_.load(std::memory_order_acquire))
            return false;
        raised_.store(0, std::memory_order_relaxed);
        return true;
    }

  private:
    std::atomic<ok::u32> raised_{0};
};

// The kernel's interrupt wait followed by the bottom halves it made pending.
// On a secondary CPU it halts until its own line, an IPI or its local tick;
// only an x86_64 boot left on the 8259 pair returns false there (polling).
inline bool wait_for_device_interrupt()
{
    if (!ok::interrupt::wait_for_interrupt())
        return false;
    static_cast<void>(ok::interrupt::drain_platform_irqs());
    return true;
}
// The same for a driver waiting on its own bound line: top halves of other
// lines on other CPUs do not end the halt (the kernel's waiting_line).
inline bool wait_for_device_line(ok::interrupt::IrqLine line)
{
    if (!ok::interrupt::wait_for_line(line))
        return false;
    static_cast<void>(ok::interrupt::drain_platform_irqs());
    return true;
}
} // namespace os::drivers::detail

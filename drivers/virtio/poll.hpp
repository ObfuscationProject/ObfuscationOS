#pragma once
#include "ok/core/types.hpp"
#include "ok/interrupt/platform.hpp"
#include <concepts>

namespace os::drivers::detail
{
// Serialized boot-CPU polling. Completion wins a deadline tie; a clock error
// is explicit. Iteration count and CPU speed are not elapsed-time measures.
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
// The kernel's idle wait followed by the bottom halves it made pending.
inline bool wait_for_device_interrupt()
{
    if (!ok::interrupt::wait_for_interrupt())
        return false;
    static_cast<void>(ok::interrupt::drain_platform_irqs());
    return true;
}
} // namespace os::drivers::detail

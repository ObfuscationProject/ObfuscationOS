#pragma once
#include "ok/core/types.hpp"
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
// Interrupt-driven completion: between readiness checks it calls wait(),
// which sleeps until an interrupt (the device's line or the tick) has been
// taken and its bottom halves have run. wait() returns false when the platform
// cannot sleep, and the rest of the deadline is polled as before.
template <typename Ready, typename Clock, typename Wait>
    requires requires(Ready ready, Clock clock, Wait wait) {
        { ready() } -> std::same_as<bool>;
        { clock() } -> std::same_as<ok::Result<ok::u64>>;
        { wait() } -> std::same_as<bool>;
    }
ok::Status wait_until(Ready ready, Clock clock, ok::u64 start, ok::u64 timeout, Wait wait)
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
        if (!wait())
            return poll_until(ready, clock, start, timeout);
    }
}
} // namespace os::drivers::detail

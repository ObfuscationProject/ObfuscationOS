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
} // namespace os::drivers::detail

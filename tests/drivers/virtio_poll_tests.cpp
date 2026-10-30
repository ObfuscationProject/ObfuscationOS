#include "drivers/virtio/poll.hpp"
#include <cassert>
#include <cstdio>
using namespace ok;
int main()
{
    u64 count = 0;
    auto healthy = [&]() -> Result<u64> { return ++count; };
    assert(os::drivers::detail::poll_until([] { return true; }, healthy, 0, 10));
    assert(count == 0);
    assert(os::drivers::detail::poll_until([&] { return count == 5; }, healthy, 0, 10));
    count = 0;
    auto failure = os::drivers::detail::poll_until([] { return false; }, healthy, 0, 10);
    assert(!failure && count == 10);
    count = 0;
    assert(os::drivers::detail::poll_until([&] { return count == 10; }, healthy, 0, 10));
    auto bad = []() -> Result<u64> { return Status::io_error("clock failed"); };
    assert(os::drivers::detail::poll_until([] { return false; }, bad, 0, 10).code() == StatusCode::io_error);
    auto regressed = []() -> Result<u64> { return 8; };
    assert(!os::drivers::detail::poll_until([] { return false; }, regressed, 9, 10));
    count = ~u64{0} - 4;
    const u64 start = count;
    assert(!os::drivers::detail::poll_until([] { return false; }, healthy, start, 3));
    assert(count == start + 3);
    count = 0;
    auto slow = [&]() -> Result<u64> {
        ++count;
        return count / 1000;
    };
    assert(os::drivers::detail::poll_until([&] { return count == 5000; }, slow, 0, 10));
    // wait_until: readiness wins before any wait; afterwards the device is
    // checked only when its own line signalled; a waiter that cannot sleep
    // falls back to polling the same deadline.
    using os::drivers::detail::wait_until;
    count = 0;
    u64 waits = 0, checks = 0;
    auto sleeper = [&] { ++waits; return true; };
    auto always = [] { return true; };
    auto never = [] { return false; };
    assert(wait_until([] { return true; }, always, healthy, 0, 10, sleeper) && waits == 0);
    assert(wait_until([&] { return waits == 3; }, always, healthy, 0, 10, sleeper) && waits == 3);
    // The device completed after two wakes but signalled on the fourth: the
    // tick wakes in between never touch it.
    waits = 0;
    count = 0;
    assert(wait_until([&] { ++checks; return waits >= 2; }, [&] { return waits == 4; }, healthy, 0, 10, sleeper));
    assert(waits == 4 && checks == 2);
    waits = 0;
    count = 0;
    assert(!wait_until([] { return false; }, always, healthy, 0, 10, sleeper) && waits == 9);
    // Never signalled: the first check and the deadline's final one only.
    waits = 0;
    count = 0;
    checks = 0;
    assert(!wait_until([&] { ++checks; return false; }, never, healthy, 0, 10, sleeper) && waits == 9 && checks == 2);
    count = 0;
    auto awake = [] { return false; };
    assert(wait_until([&] { return count == 6; }, always, healthy, 0, 10, awake));
    assert(wait_until([] { return false; }, always, bad, 0, 10, sleeper).code() == StatusCode::io_error);
    puts("VIRTIO_POLL_PASS scope=model elapsed=pass deadline_tie=pass clock_error=pass overflow=pass interrupt_wait=pass signalled_wait=pass");
}

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
    puts("VIRTIO_POLL_PASS scope=model elapsed=pass deadline_tie=pass clock_error=pass overflow=pass");
}

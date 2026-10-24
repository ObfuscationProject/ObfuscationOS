#include "drivers/virtio/net.hpp"
#include <ok/arch/clock.hpp>
#include <cstdio>
#include <cstdlib>
#include <type_traits>

namespace
{
ok::usize checks{}, clock_calls{};
void check(bool passed)
{
    ++checks;
    if (!passed) { std::fprintf(stderr, "NET_INACTIVE_FAIL check=%zu\n", checks); std::abort(); }
}
}
namespace ok::arch
{
Result<u64> monotonic_nanoseconds()
{
    ++clock_calls;
    return Status::not_initialized("hosted inactive-device test has no device clock");
}
}
int main()
{
    static_assert(!std::is_default_constructible_v<os::drivers::VirtioNetDevice>);
    static_assert(!std::is_copy_constructible_v<os::drivers::VirtioNetDevice>);
    static_assert(!std::is_move_constructible_v<os::drivers::VirtioNetDevice>);
    auto &device = os::drivers::virtio_net_device();
    std::array<std::byte, 1514> frame{};
    check(&device == &os::drivers::virtio_net_device());
    for (ok::usize turn = 0; turn < 8; ++turn)
    {
        check(!device.active() && device.transmit_credit() == 0);
        check(device.try_transmit(frame).code() == ok::StatusCode::not_initialized);
        check(device.transmit(frame).code() == ok::StatusCode::not_initialized);
        check(device.poll_transmit().status().code() == ok::StatusCode::not_initialized);
        check(device.poll_transmit(1).status().code() == ok::StatusCode::not_initialized);
        check(device.poll_transmit(0).status().code() == ok::StatusCode::invalid_argument);
        check(device.poll_transmit(9).status().code() == ok::StatusCode::invalid_argument);
        check(device.receive(frame).status().code() == ok::StatusCode::not_initialized);
        check(device.poll_receive().status().code() == ok::StatusCode::not_initialized);
        check(device.poll_receive(1).status().code() == ok::StatusCode::not_initialized);
        check(device.poll_receive(0).status().code() == ok::StatusCode::invalid_argument);
        check(device.poll_receive(9).status().code() == ok::StatusCode::invalid_argument);
        check(device.receive_pending() == 0 && device.receive_credit() == 0);
        check(device.stop().code() == ok::StatusCode::not_initialized);
        check(!device.active() && device.transmit_credit() == 0 && !clock_calls);
    }
    std::printf("NET_INACTIVE_PASS scope=hosted-inactive-production checks=%zu clock_calls=%zu\n", checks, clock_calls);
}

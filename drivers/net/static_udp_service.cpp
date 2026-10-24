#include "static_udp.hpp"

namespace os::drivers::net
{
ok::Status StaticUdpService::start()
{
    if (active_) return ok::Status::already_exists("static UDP service is active");
    if (auto status = device_.start(); !status) return status;
    endpoint_.local_mac(device_.mac());
    active_ = true;
    return ok::Status::success();
}
ok::Status StaticUdpService::stop()
{
    if (!active_) return ok::Status::not_initialized("static UDP service is inactive");
    active_ = false;
    return device_.stop();
}
ok::Result<PollKind> StaticUdpService::poll_once()
{
    if (!active_) return ok::Status::not_initialized("static UDP service is inactive");
    const auto received = device_.receive(incoming_);
    if (!received)
    {
        if (received.status().code() == ok::StatusCode::not_found) return PollKind::idle;
        return received.status();
    }
    const auto response = endpoint_.respond({incoming_.data(), received.value()}, outgoing_);
    if (!response) return response.status();
    if (response.value().kind == ResponseKind::dropped) return PollKind::dropped;
    if (auto status = device_.transmit({outgoing_.data(), response.value().length}); !status)
        return status;
    return response.value().kind == ResponseKind::arp ? PollKind::arp_replied : PollKind::udp_replied;
}
}

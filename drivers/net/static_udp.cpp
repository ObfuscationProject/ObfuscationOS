#include "static_udp.hpp"

namespace os::drivers::net
{
namespace
{
using namespace ok;
namespace wire = ok::net::wire;

bool overlap(wire::Bytes input, std::span<std::byte> output)
{
    if (input.empty() || output.empty()) return false;
    const uptr in = reinterpret_cast<uptr>(input.data());
    const uptr out = reinterpret_cast<uptr>(output.data());
    return in >= out ? in - out < output.size() : out - in < input.size();
}
bool broadcast(Mac address)
{
    for (auto value : address) if (value != 0xff) return false;
    return true;
}
bool zero(Mac address)
{
    for (auto value : address) if (value) return false;
    return true;
}
void put_mac(std::span<std::byte> output, usize offset, Mac address)
{
    for (usize i = 0; i < address.size(); ++i) output[offset + i] = std::byte{address[i]};
}
void put_ip(std::span<std::byte> output, usize offset, Ipv4 address)
{
    for (usize i = 0; i < address.size(); ++i) output[offset + i] = std::byte{address[i]};
}
}

ok::Result<Response> StaticUdpEndpoint::respond(ok::net::wire::Bytes input,
                                                 std::span<std::byte> output)
{
    if (overlap(input, output)) return ok::Status::invalid_argument("network input aliases output");
    const auto ethernet = wire::ethernet(input);
    if (!ethernet) return Response{};
    if (ethernet.value().source != config_.peer_mac) return Response{};
    if (ethernet.value().type == 0x0806)
    {
        if (ethernet.value().destination != local_mac_ && !broadcast(ethernet.value().destination))
            return Response{};
        const auto request = wire::arp(ethernet.value().payload);
        if (!request || request.value().operation != 1 ||
            request.value().sender_mac != config_.peer_mac ||
            request.value().sender_ip != config_.peer_ip ||
            request.value().target_ip != config_.local_ip ||
            (!zero(request.value().target_mac) && request.value().target_mac != local_mac_))
            return Response{};
        if (output.size() < 60) return ok::Status::overflow("ARP output capacity is below Ethernet minimum");
        for (ok::usize i = 0; i < 60; ++i) output[i] = std::byte{};
        put_mac(output, 0, config_.peer_mac); put_mac(output, 6, local_mac_);
        wire::be16(output, 12, 0x0806);
        wire::be16(output, 14, 1); wire::be16(output, 16, 0x0800);
        output[18] = std::byte{6}; output[19] = std::byte{4}; wire::be16(output, 20, 2);
        put_mac(output, 22, local_mac_); put_ip(output, 28, config_.local_ip);
        put_mac(output, 32, config_.peer_mac); put_ip(output, 38, config_.peer_ip);
        return Response{ResponseKind::arp, 60};
    }
    if (ethernet.value().type != 0x0800 || ethernet.value().destination != local_mac_)
        return Response{};
    const auto ip = wire::ipv4(ethernet.value().payload);
    if (!ip || ip.value().source != config_.peer_ip ||
        ip.value().destination != config_.local_ip || !ip.value().ttl)
        return Response{};
    const auto request = wire::udp(ip.value());
    if (!request || !request.value().checksum_present ||
        request.value().source_port != config_.peer_port ||
        request.value().destination_port != config_.local_port ||
        request.value().payload.size() > request_capacity ||
        wire::be16(ip.value().payload, 4) != ip.value().payload.size())
        return Response{};
    const ok::usize payload_size = 3 + request.value().payload.size();
    const ok::usize packet_size = 28 + payload_size;
    const ok::usize frame_size = 14 + packet_size > 60 ? 14 + packet_size : 60;
    if (output.size() < frame_size) return ok::Status::overflow("UDP output capacity is below reply size");
    reply_payload_[0] = std::byte{'O'}; reply_payload_[1] = std::byte{'K'};
    reply_payload_[2] = std::byte{':'};
    for (ok::usize i = 0; i < request.value().payload.size(); ++i)
        reply_payload_[3 + i] = request.value().payload[i];
    const auto built = wire::build_udp(output.subspan(14, packet_size), config_.local_ip,
        config_.peer_ip, config_.local_port, config_.peer_port, next_identifier_, 64,
        {reply_payload_.data(), payload_size});
    if (!built) return built.status();
    ++next_identifier_;
    put_mac(output, 0, config_.peer_mac); put_mac(output, 6, local_mac_);
    wire::be16(output, 12, 0x0800);
    for (ok::usize i = 14 + packet_size; i < frame_size; ++i) output[i] = std::byte{};
    return Response{ResponseKind::udp, frame_size};
}

}

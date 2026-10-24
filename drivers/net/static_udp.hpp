#pragma once

#include "drivers/virtio/net.hpp"
#include <ok/net/wire.hpp>
#include <array>
#include <span>

namespace os::drivers::net
{
using Mac = ok::net::wire::Mac;
using Ipv4 = ok::net::wire::Ipv4;

struct StaticUdpConfig
{
    Ipv4 local_ip{}, peer_ip{};
    Mac peer_mac{};
    ok::u16 local_port{}, peer_port{};
};

enum class ResponseKind : ok::u8 { dropped, arp, udp };
struct Response
{
    ResponseKind kind{ResponseKind::dropped};
    ok::usize length{};
};

// A fixed peer and a single UDP service. This packet model never learns ARP
// state, allocates memory or accesses a NIC; callers retain borrowed frames.
class StaticUdpEndpoint final
{
  public:
    static constexpr ok::usize ethernet_capacity = 1514;
    static constexpr ok::usize request_capacity = 1469;
    StaticUdpEndpoint(StaticUdpConfig config, Mac local_mac) : config_(config), local_mac_(local_mac) {}
    void local_mac(Mac value) { local_mac_ = value; }
    ok::Result<Response> respond(ok::net::wire::Bytes input, std::span<std::byte> output);
  private:
    StaticUdpConfig config_{};
    Mac local_mac_{};
    ok::u16 next_identifier_{0x9000};
    std::array<std::byte, 1472> reply_payload_{};
};

enum class PollKind : ok::u8 { idle, dropped, arp_replied, udp_replied };

// Serialized boot-CPU polling over the existing native Virtio NIC boundary.
class StaticUdpService final
{
  public:
    StaticUdpService(VirtioNetDevice &device, StaticUdpConfig config)
        : device_(device), endpoint_(config, {}) {}
    ok::Status start();
    ok::Status stop();
    ok::Result<PollKind> poll_once();
  private:
    VirtioNetDevice &device_;
    StaticUdpEndpoint endpoint_;
    bool active_{};
    std::array<std::byte, StaticUdpEndpoint::ethernet_capacity> incoming_{}, outgoing_{};
};
}

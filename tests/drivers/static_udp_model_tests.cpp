#include "drivers/net/static_udp.hpp"
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

using namespace ok;
namespace static_net = os::drivers::net;
namespace
{
usize checks{};
#define CHECK(value) do { ++checks; if (!(value)) { \
    std::fprintf(stderr, "STATIC_UDP_MODEL_FAIL line=%d check=%zu: %s\n", __LINE__, checks, #value); \
    std::abort(); } } while (false)

std::vector<std::byte> hex(const char *text)
{
    auto digit = [](char value) -> u8 {
        if (value >= '0' && value <= '9') return static_cast<u8>(value - '0');
        if (value >= 'a' && value <= 'f') return static_cast<u8>(value - 'a' + 10);
        std::abort();
    };
    std::vector<std::byte> out;
    for (usize i = 0; text[i]; i += 2)
    {
        CHECK(text[i + 1]);
        out.push_back(std::byte{static_cast<u8>(digit(text[i]) * 16 + digit(text[i + 1]))});
    }
    return out;
}
u16 get16(const std::vector<std::byte> &bytes, usize at)
{
    return static_cast<u16>((std::to_integer<u8>(bytes[at]) << 8) | std::to_integer<u8>(bytes[at + 1]));
}
void put16(std::vector<std::byte> &bytes, usize at, u16 value)
{
    bytes[at] = std::byte{static_cast<u8>(value >> 8)};
    bytes[at + 1] = std::byte{static_cast<u8>(value)};
}
u16 checksum(const std::vector<std::byte> &bytes)
{
    std::uint64_t value = 0;
    for (usize i = 0; i < bytes.size(); i += 2)
    {
        value += std::to_integer<u8>(bytes[i]) << 8;
        if (i + 1 < bytes.size()) value += std::to_integer<u8>(bytes[i + 1]);
    }
    while (value >> 16) value = (value & 0xffffu) + (value >> 16);
    return static_cast<u16>(~value);
}
void ip_checksum(std::vector<std::byte> &frame)
{
    put16(frame, 24, 0);
    std::vector<std::byte> header(frame.begin() + 14, frame.begin() + 34);
    put16(frame, 24, checksum(header));
}
void udp_checksum(std::vector<std::byte> &frame)
{
    const auto size = get16(frame, 38);
    put16(frame, 40, 0);
    std::vector<std::byte> pseudo;
    pseudo.insert(pseudo.end(), frame.begin() + 26, frame.begin() + 34);
    pseudo.push_back(std::byte{}); pseudo.push_back(std::byte{17});
    pseudo.push_back(std::byte{static_cast<u8>(size >> 8)});
    pseudo.push_back(std::byte{static_cast<u8>(size)});
    pseudo.insert(pseudo.end(), frame.begin() + 34, frame.begin() + 34 + size);
    const auto value = checksum(pseudo);
    put16(frame, 40, value ? value : 0xffff);
}

std::vector<std::byte> make_request(std::vector<std::byte> payload)
{
    const auto prefix = hex("02112233445502aabbccddee0800450000001234400040110000c0000201c0000202"
                            "3039d43100000000");
    auto frame = prefix;
    frame.insert(frame.end(), payload.begin(), payload.end());
    put16(frame, 16, static_cast<u16>(28 + payload.size()));
    put16(frame, 38, static_cast<u16>(8 + payload.size()));
    ip_checksum(frame); udp_checksum(frame);
    while (frame.size() < 60) frame.push_back(std::byte{});
    return frame;
}

void run()
{
    const static_net::StaticUdpConfig config{{192, 0, 2, 2}, {192, 0, 2, 1},
                                       {2, 0xaa, 0xbb, 0xcc, 0xdd, 0xee}, 54321, 12345};
    const static_net::Mac local_mac{2, 0x11, 0x22, 0x33, 0x44, 0x55};
    static_net::StaticUdpEndpoint endpoint(config, local_mac);
    const auto arp_request = hex("ffffffffffff02aabbccddee0806000108000604000102aabbccddeec0000201"
                                 "000000000000c0000202000000000000000000000000000000000000");
    const auto arp_reply = hex("02aabbccddee02112233445508060001080006040002021122334455c0000202"
                               "02aabbccddeec0000201000000000000000000000000000000000000");
    const auto request = hex("02112233445502aabbccddee08004500002e123440004011a487c0000201c0000202"
                             "3039d431001adb784f62667573636174696f6e4f5300756470ff");
    const auto reply = hex("02aabbccddee02112233445508004500003190004000401126b8c0000202c0000201"
                           "d4313039001d1b5e4f4b3a4f62667573636174696f6e4f5300756470ff");
    CHECK(arp_request.size() == 60 && arp_reply.size() == 60);
    CHECK(request.size() == 60 && reply.size() == 63);
    CHECK(make_request(hex("4f62667573636174696f6e4f5300756470ff")) == request);
    std::array<std::byte, 1514> output{};
    output.fill(std::byte{0xa5});
    auto result = endpoint.respond(arp_request, output);
    CHECK(result && result.value().kind == static_net::ResponseKind::arp && result.value().length == 60);
    CHECK(std::memcmp(output.data(), arp_reply.data(), 60) == 0);
    CHECK(output[60] == std::byte{0xa5});
    output.fill(std::byte{0xa5});
    result = endpoint.respond(request, output);
    CHECK(result && result.value().kind == static_net::ResponseKind::udp && result.value().length == reply.size());
    CHECK(std::memcmp(output.data(), reply.data(), reply.size()) == 0);
    CHECK(output[reply.size()] == std::byte{0xa5});

    auto drop = [&](const std::vector<std::byte> &frame) {
        output.fill(std::byte{0xa5});
        const auto response = endpoint.respond(frame, output);
        CHECK(response && response.value().kind == static_net::ResponseKind::dropped && response.value().length == 0);
        for (auto value : output) CHECK(value == std::byte{0xa5});
    };
    for (usize n = 0; n < 14; ++n) drop({request.begin(), request.begin() + n});
    for (usize n = 0; n < 28; ++n) drop({arp_request.begin(), arp_request.begin() + 14 + n});
    for (usize n = 0; n < 20; ++n) drop({request.begin(), request.begin() + 14 + n});
    auto bad = request; bad[0] = std::byte{0}; drop(bad);
    bad = request; bad[6] = std::byte{0}; drop(bad);
    bad = request; bad[12] = std::byte{0x81}; bad[13] = std::byte{0x00}; drop(bad);
    bad = arp_request; bad[22] = std::byte{0}; drop(bad);
    bad = arp_request; bad[31] = std::byte{3}; drop(bad);
    bad = arp_request; put16(bad, 20, 2); drop(bad);
    bad = request; bad[24] ^= std::byte{1}; drop(bad); // IP checksum.
    bad = request; bad[50] ^= std::byte{1}; drop(bad); // UDP payload checksum.
    bad = request; bad[26] ^= std::byte{1}; ip_checksum(bad); drop(bad); // Pseudo-header source.
    bad = request; bad[30] ^= std::byte{1}; ip_checksum(bad); udp_checksum(bad); drop(bad); // Foreign IP.
    bad = request; put16(bad, 36, 54320); udp_checksum(bad); drop(bad); // Foreign UDP port.
    bad = request; put16(bad, 38, 27); drop(bad); // UDP length exceeds IP payload.
    bad = request; put16(bad, 16, 200); ip_checksum(bad); drop(bad); // Forged IP length.
    bad = request; put16(bad, 20, 0x2000); ip_checksum(bad); drop(bad); // Fragment.
    bad = request; put16(bad, 20, 0x8000); ip_checksum(bad); drop(bad); // Reserved bit.
    bad = request; put16(bad, 40, 0); drop(bad); // Policy rejects omitted UDP checksum.
    bad = request; bad[22] = std::byte{0}; ip_checksum(bad); drop(bad); // Zero TTL.
    std::vector<std::byte> oversized(1470, std::byte{0x55});
    drop(make_request(oversized));

    output.fill(std::byte{0xa5});
    const auto unchanged = output;
    result = endpoint.respond(request, {output.data(), 62});
    CHECK(!result && result.status().code() == StatusCode::overflow && output == unchanged);
    auto alias = request;
    const auto before = alias;
    result = endpoint.respond(alias, alias);
    CHECK(!result && result.status().code() == StatusCode::invalid_argument && alias == before);

    // A second request increments only the reply identifier, not ARP or drops.
    output.fill(std::byte{});
    result = endpoint.respond(request, output);
    CHECK(result && result.value().kind == static_net::ResponseKind::udp && get16(
        std::vector<std::byte>(output.begin(), output.begin() + result.value().length), 18) == 0x9001);
    std::printf("STATIC_UDP_MODEL_PASS checks=%zu request=arp+udp drops=hostile alias=atomic\n", checks);
}
}
int main() { run(); }

#include "drivers/virtio/net_receive.hpp"
#include <cstdio>
#include <cstdlib>
#include <type_traits>

using namespace ok;
using namespace os::drivers::net_detail;
namespace
{
usize checks{};
void check(bool passed)
{
    ++checks;
    if (!passed) { std::fprintf(stderr, "NET_RX_QUEUE_FAIL check=%zu\n", checks); std::abort(); }
}
std::byte value(usize round, u16 descriptor, usize offset)
{
    return std::byte{static_cast<u8>((round * 17) ^ (descriptor * 31) ^ offset)};
}
}

int main()
{
    static_assert(!std::is_copy_constructible_v<ReceivedPackets>);
    static_assert(!std::is_move_constructible_v<ReceivedPackets>);
    ReceivedPackets packets;
    Ownership ownership;
    std::array<std::byte, receive_frame_capacity> input{}, output{};
    check(packets.copy_front(output).status().code() == StatusCode::not_found);
    check(packets.release_front().status().code() == StatusCode::not_found);
    check(!packets.front_descriptor() && !packets.front_size());
    check(packets.count() == 0 && packets.credit() == queue_size);
    check(packets.push(8, std::span{input}.first(14)).code() == StatusCode::invalid_argument);
    check(packets.push(0, std::span{input}.first(13)).code() == StatusCode::invalid_argument);
    check(packets.count() == 0 && packets.credit() == queue_size);
    for (u16 id = 0; id < queue_size; ++id)
        check(ownership.publish(id, 1526).ok());
    const std::array<u16, queue_size> order{6, 0, 7, 3, 2, 1, 4, 5};
    // Every index derives from ordinary publication/completion methods. No
    // device ring or private counters are rewritten, including through u16 wrap.
    for (usize round = 0; round < 8250; ++round)
    {
        const u16 device_index = ownership.published();
        for (usize position = 0; position < order.size(); ++position)
        {
            const u16 id = order[position];
            const usize size = 14 + (round + id) % (receive_frame_capacity - 13);
            for (usize i = 0; i < size; ++i) input[i] = value(round, id, i);
            check(ownership.validate(device_index, id, static_cast<u32>(12 + size)).ok());
            check(packets.push(id, std::span{input}.first(size)).ok());
            check(ownership.complete(device_index, id, static_cast<u32>(12 + size)).ok());
            input.fill(std::byte{0xa5});
            check(packets.holds(id) && !ownership.owns(id));
            check(packets.push(id, std::span{input}.first(size)).code() == StatusCode::invalid_argument);
            check(packets.count() == position + 1 && ownership.count() == queue_size - position - 1);
        }
        check(packets.count() == queue_size && packets.credit() == 0 && ownership.count() == 0);
        for (usize position = 0; position < order.size(); ++position)
        {
            const u16 id = order[position];
            const usize size = 14 + (round + id) % (receive_frame_capacity - 13);
            check(packets.front_descriptor().value() == id && packets.front_size().value() == size);
            output.fill(std::byte{0x5a});
            check(packets.copy_front(std::span{output}.first(size - 1)).status().code() == StatusCode::overflow);
            check(packets.count() == queue_size - position && packets.holds(id));
            for (auto byte : output) check(byte == std::byte{0x5a});
            auto copied = packets.copy_front(output);
            check(copied.ok() && copied.value() == size);
            for (usize i = 0; i < size; ++i) check(output[i] == value(round, id, i));
            for (usize i = size; i < output.size(); ++i) check(output[i] == std::byte{0x5a});
            const auto released = packets.release_front();
            check(released.ok() && released.value() == id && !packets.holds(id));
            check(ownership.publish(id, 1526).ok());
            check(packets.count() == queue_size - position - 1 && ownership.count() == position + 1);
            output.fill(std::byte{});
        }
        check(packets.count() == 0 && ownership.count() == queue_size);
    }
    // An acknowledged reset may discard held copied packets through the ordinary
    // FIFO reset API. The production reset boundary has separate device evidence.
    check(packets.push(0, std::span{input}.first(14)).ok());
    packets.reset();
    check(packets.count() == 0 && packets.credit() == queue_size && !packets.holds(0));
    check(packets.copy_front(output).status().code() == StatusCode::not_found);
    std::printf("NET_RX_QUEUE_PASS scope=hosted-model checks=%zu copied=pass retry=pass identity=pass full=pass wrap16=pass reset-api=pass\n", checks);
}

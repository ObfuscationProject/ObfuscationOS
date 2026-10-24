#pragma once

#include "net_queue.hpp"
#include <span>

namespace os::drivers::net_detail
{
inline constexpr usize receive_frame_capacity = 1514;

// CPU-owned copied packets. No DMA or caller-owned pointers escape this FIFO.
// Each queued packet holds one descriptor until the ordinary receive releases it.
class ReceivedPackets final
{
  public:
    ReceivedPackets() = default;
    ReceivedPackets(const ReceivedPackets &) = delete;
    ReceivedPackets &operator=(const ReceivedPackets &) = delete;
    ReceivedPackets(ReceivedPackets &&) = delete;
    ReceivedPackets &operator=(ReceivedPackets &&) = delete;

    Status push(u16 descriptor, std::span<const std::byte> frame)
    {
        if (descriptor >= queue_size || held_[descriptor] || frame.size() < 14 ||
            frame.size() > receive_frame_capacity)
            return Status::invalid_argument("Virtio net copied RX identity or frame size is invalid");
        if (count_ == queue_size)
            return Status::would_block("Virtio net copied RX queue is full");
        auto &packet = packets_[(head_ + count_) % queue_size];
        for (usize i = 0; i < frame.size(); ++i)
            packet.bytes[i] = frame[i];
        packet.descriptor = descriptor;
        packet.size = static_cast<u16>(frame.size());
        held_[descriptor] = true;
        ++count_;
        return {};
    }
    [[nodiscard]] Result<u16> front_descriptor() const
    {
        if (!count_) return Status::not_found("Virtio net copied RX queue is empty");
        return packets_[head_].descriptor;
    }
    [[nodiscard]] Result<usize> front_size() const
    {
        if (!count_) return Status::not_found("Virtio net copied RX queue is empty");
        return packets_[head_].size;
    }
    Result<usize> copy_front(std::span<std::byte> frame) const
    {
        if (!count_) return Status::not_found("Virtio net copied RX queue is empty");
        const auto &packet = packets_[head_];
        if (frame.size() < packet.size)
            return Status::overflow("Virtio net receive buffer is too small");
        for (usize i = 0; i < packet.size; ++i)
            frame[i] = packet.bytes[i];
        return packet.size;
    }
    Result<u16> release_front()
    {
        if (!count_) return Status::not_found("Virtio net copied RX queue is empty");
        const u16 descriptor = packets_[head_].descriptor;
        held_[descriptor] = false;
        head_ = static_cast<u16>((head_ + 1) % queue_size);
        --count_;
        return descriptor;
    }
    // Called by production only after acknowledged device reset. Private bytes
    // need no large stack temporary; count/identity make old copies inaccessible.
    void reset()
    {
        head_ = count_ = 0;
        held_.fill(false);
    }
    [[nodiscard]] usize count() const { return count_; }
    [[nodiscard]] usize credit() const { return queue_size - count_; }
    [[nodiscard]] bool holds(u16 descriptor) const
    {
        return descriptor < queue_size && held_[descriptor];
    }
  private:
    struct Packet
    {
        std::array<std::byte, receive_frame_capacity> bytes{};
        u16 descriptor{}, size{};
    };
    std::array<Packet, queue_size> packets_{};
    std::array<bool, queue_size> held_{};
    u16 head_{}, count_{};
};
}

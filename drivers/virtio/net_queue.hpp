#pragma once

#include <ok/core/types.hpp>
#include <array>
#include <cstddef>

namespace os::drivers::net_detail
{
using namespace ok;
inline constexpr usize queue_size = 8;

template <typename T> constexpr T little(T value)
{
#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    if constexpr (sizeof(T) == 2) return __builtin_bswap16(value);
    if constexpr (sizeof(T) == 4) return __builtin_bswap32(value);
    if constexpr (sizeof(T) == 8) return __builtin_bswap64(value);
#endif
    return value;
}

struct Descriptor { u64 address; u32 length; u16 flags; u16 next; };
struct Available { u16 flags; u16 index; u16 ring[queue_size]; u16 used_event; };
struct UsedElement { u32 id; u32 length; };
struct Used { u16 flags; u16 index; UsedElement ring[queue_size]; u16 available_event; };
struct alignas(4096) Ring
{
    Descriptor descriptors[queue_size]{};
    Available available{};
    alignas(4096) Used used{};
};
static_assert(sizeof(Descriptor) == 16 && sizeof(UsedElement) == 8);
static_assert(offsetof(Ring, used) == 4096);

// CPU-only ownership ledger, deliberately separate from device-writable memory.
// The caller samples the used index/element with DMA acquire ordering. A rejected
// completion changes no ledger state; the caller must retire that device queue.
class Ownership final
{
  public:
    // Admission scans CPU-owned state only. A hole can differ from published%8
    // because devices may complete descriptors out of order.
    Result<u16> free_descriptor() const
    {
        for (usize offset = 0; offset < queue_size; ++offset)
        {
            const auto id = static_cast<u16>((published_ + offset) % queue_size);
            if (!active_[id]) return id;
        }
        return Status::would_block("Virtio net transmit queue is full");
    }
    Status publish(u16 id, u32 capacity)
    {
        if (id >= queue_size || active_[id] || count_ == queue_size)
            return Status::invalid_argument("Virtio net descriptor is already owned or invalid");
        active_[id] = true;
        capacity_[id] = capacity;
        ++count_;
        ++published_;
        return Status::success();
    }
    Status validate(u16 device_index, u32 id, u32 length) const
    {
        const auto pending = static_cast<u16>(device_index - consumed_);
        if (!pending) return Status::not_found("Virtio net queue has no completion");
        if (pending > count_ || id >= queue_size || !active_[id] || length > capacity_[id])
            return Status::fault("Virtio net completion violates descriptor ownership");
        return Status::success();
    }
    Result<u16> complete(u16 device_index, u32 id, u32 length)
    {
        if (auto status = validate(device_index, id, length); !status) return status;
        active_[id] = false;
        --count_;
        ++consumed_;
        return static_cast<u16>(id);
    }
    Result<u16> complete_transmit(u16 device_index, u32 id, u32 length)
    {
        // TX descriptors are device-readable only. Check before releasing DMA
        // ownership so an invalid length cannot make its slot available again.
        if (length) return Status::fault("Virtio net TX used length is not zero");
        return complete(device_index, id, length);
    }
    [[nodiscard]] bool owns(u16 id) const { return id < queue_size && active_[id]; }
    [[nodiscard]] u16 published() const { return published_; }
    [[nodiscard]] u16 consumed() const { return consumed_; }
    [[nodiscard]] u16 count() const { return count_; }
  private:
    std::array<bool, queue_size> active_{};
    std::array<u32, queue_size> capacity_{};
    u16 published_{}, consumed_{}, count_{};
};
}

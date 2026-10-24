#pragma once

#include <ok/core/types.hpp>
#include <array>
#include <span>

namespace os::drivers
{
class VirtioNetDevice;
VirtioNetDevice &virtio_net_device();
// Serialized boot-CPU polling over modern Virtio MMIO or PCI, coherent QEMU
// RAM, Ethernet MTU 1500, no offloads or interrupt claim.
class VirtioNetDevice final
{
  public:
    VirtioNetDevice(const VirtioNetDevice &) = delete;
    VirtioNetDevice &operator=(const VirtioNetDevice &) = delete;
    ok::Status start();
    ok::Status stop();
    ok::Status transmit(std::span<const std::byte> frame);
    // Immediate copied submission, without clock sampling or a completion wait.
    // would_block leaves all published descriptors and frame buffers intact.
    ok::Status try_transmit(std::span<const std::byte> frame);
    // Retire at most budget completions (1..8). Consumption does not imply peer
    // delivery. A fault retires the link and retains DMA storage until reset.
    ok::Result<ok::usize> poll_transmit(ok::usize budget = 8);
    // Serialized CPU-ledger snapshot; no device I/O or credit reservation.
    [[nodiscard]] ok::usize transmit_credit() const;
    // Adopt at most budget (1..8) actual RX completions into copied driver-owned
    // packets. Their descriptors stay held until receive copies and releases.
    // would_block leaves a full copied queue and device buffers intact.
    ok::Result<ok::usize> poll_receive(ok::usize budget = 8);
    [[nodiscard]] ok::usize receive_pending() const;
    // CPU-ledger count of posted descriptors, including unobserved completions.
    // This is a snapshot, not a device observation or a reservation.
    [[nodiscard]] ok::usize receive_credit() const;
    // Nonblocking receive. not_found means no packet; overflow leaves the packet
    // owned by the driver so a caller can retry with a larger buffer. Success
    // releases and reposts that descriptor after copying, with no escaped lease.
    ok::Result<ok::usize> receive(std::span<std::byte> frame);
    [[nodiscard]] std::array<ok::u8, 6> mac() const { return mac_; }
    [[nodiscard]] bool active() const { return active_; }
    [[nodiscard]] ok::Status shutdown_preflight_unused() const;
  private:
    friend VirtioNetDevice &virtio_net_device();
    // Only the boot-lifetime instance can exist. Device DMA and a quarantined
    // reset must never retain a pointer to a destroyed caller-owned object.
    VirtioNetDevice() = default;
    ~VirtioNetDevice() = default;
    ok::Result<ok::u16> submit_transmit(std::span<const std::byte> frame);
    std::array<ok::u8, 6> mac_{};
    bool active_{}, retired_{};
};
}

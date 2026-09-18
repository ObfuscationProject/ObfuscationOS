#pragma once

#include <ok/driver/abi.hpp>

namespace obos::linux_compat
{

using namespace ok;
using namespace ok::driver;

// Behavioral prototype only: these adapters do not access hardware or expose Linux C headers.

struct pci_device_id
{
    u32 vendor{0};
    u32 device{0};
};

struct pci_driver
{
    std::string_view name{};
    std::span<const pci_device_id> ids{};
    Status (*probe)(OkDevice &device, const pci_device_id &id){nullptr};
    Status (*remove)(OkDevice &device){nullptr};
};

class LinuxPciShim final
{
  public:
    Status register_driver(pci_driver &driver);
    Status bind(OkDevice &device);
    Status remove(OkDevice &device);
    [[nodiscard]] OkMmioRegion *ioremap(uptr, usize);
    Status iounmap(OkMmioRegion *region);
    [[nodiscard]] void *kmalloc(usize size);
    Status kfree(void *pointer);
    Result<OkDmaMapping> dma_map_single(OkDmaBuffer &buffer, usize size, OkDmaDirection direction);
    Status dma_unmap_single(OkDmaMapping &mapping);
    Status schedule_work();
    Result<usize> flush_work();
    Status request_irq(OkIrqHandle &handle, u32 vector);
    Status free_irq(OkIrqHandle &handle);
    [[nodiscard]] usize probe_count() const
    {
        return probe_count_;
    }
    [[nodiscard]] usize remove_count() const
    {
        return remove_count_;
    }

  private:
    pci_driver *driver_{nullptr};
    OkMmioRegion mmio_{};
    std::array<std::byte, 256> heap_{};
    bool heap_used_{false};
    OkDmaMapper dma_{};
    OkWorkQueue workqueue_{};
    usize probe_count_{0};
    usize remove_count_{0};
};

} // namespace obos::linux_compat

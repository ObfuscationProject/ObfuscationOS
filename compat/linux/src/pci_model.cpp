#include "obos/linux/pci_model.hpp"

namespace obos::linux_compat
{

Status LinuxPciShim::register_driver(pci_driver &driver)
{
    if (driver.probe == nullptr || driver.remove == nullptr)
    {
        return Status::invalid_argument("Linux PCI shim driver callbacks are incomplete");
    }
    driver_ = &driver;
    return Status::success();
}

Status LinuxPciShim::bind(OkDevice &device)
{
    if (driver_ == nullptr)
    {
        return Status::not_initialized("Linux PCI shim has no registered driver");
    }
    for (const auto &id : driver_->ids)
    {
        if ((id.vendor == 0xffff'ffffu || id.vendor == device.id.vendor) &&
            (id.device == 0xffff'ffffu || id.device == device.id.device))
        {
            if (auto status = driver_->probe(device, id); !status.ok())
            {
                return status;
            }
            device.attached = true;
            ++probe_count_;
            return Status::success();
        }
    }
    return Status::not_found("Linux PCI shim driver did not match device");
}

Status LinuxPciShim::remove(OkDevice &device)
{
    if (driver_ == nullptr)
    {
        return Status::not_initialized("Linux PCI shim has no registered driver");
    }
    if (auto status = driver_->remove(device); !status.ok())
    {
        return status;
    }
    device.attached = false;
    ++remove_count_;
    return Status::success();
}

OkMmioRegion *LinuxPciShim::ioremap(uptr, usize)
{
    mmio_.mapped = true;
    return &mmio_;
}

Status LinuxPciShim::iounmap(OkMmioRegion *region)
{
    if (region == nullptr || region != &mmio_)
    {
        return Status::invalid_argument("invalid MMIO unmap");
    }
    region->mapped = false;
    return Status::success();
}

void *LinuxPciShim::kmalloc(usize size)
{
    if (heap_used_ || size > heap_.size())
    {
        return nullptr;
    }
    heap_used_ = true;
    return heap_.data();
}

Status LinuxPciShim::kfree(void *pointer)
{
    if (pointer != heap_.data() || !heap_used_)
    {
        return Status::invalid_argument("invalid shim allocation free");
    }
    heap_used_ = false;
    return Status::success();
}

Result<OkDmaMapping> LinuxPciShim::dma_map_single(OkDmaBuffer &buffer, usize size, OkDmaDirection direction)
{
    return dma_.map(buffer, size, direction);
}

Status LinuxPciShim::dma_unmap_single(OkDmaMapping &mapping)
{
    return dma_.unmap(mapping);
}

Status LinuxPciShim::schedule_work()
{
    return workqueue_.enqueue();
}

Result<usize> LinuxPciShim::flush_work()
{
    return workqueue_.drain();
}

Status LinuxPciShim::request_irq(OkIrqHandle &handle, u32 vector)
{
    if (handle.registered)
    {
        return Status::already_exists("IRQ already registered");
    }
    handle = OkIrqHandle{.vector = vector, .registered = true};
    return Status::success();
}

Status LinuxPciShim::free_irq(OkIrqHandle &handle)
{
    if (!handle.registered)
    {
        return Status::invalid_argument("IRQ is not registered");
    }
    handle.registered = false;
    return Status::success();
}

} // namespace obos::linux_compat

#include "obos/linux/pci_model.hpp"

#include <cstdio>

using namespace ok;

namespace
{
Status test_linux_driver_shim()
{
    obos::linux_compat::LinuxPciShim shim;
    driver::OkDevice device{
        .bus = driver::OkBusType::pci,
        .id = driver::OkDeviceId{.vendor = 0x1af4, .device = 0x1000, .class_code = 0x02},
    };
    if (shim.bind(device).code() != StatusCode::not_initialized)
    {
        return Status::fault("Linux driver shim accepted bind before driver registration");
    }

    obos::linux_compat::pci_driver incomplete{};
    if (shim.register_driver(incomplete).code() != StatusCode::invalid_argument)
    {
        return Status::fault("Linux driver shim accepted incomplete callbacks");
    }

    static const std::array ids{obos::linux_compat::pci_device_id{.vendor = 0x1af4, .device = 0x1000}};
    struct LinuxShimState
    {
        bool probed{false};
        bool removed{false};
    };
    static LinuxShimState shim_state{};
    shim_state = {};
    obos::linux_compat::pci_driver linux_driver{
        .name = "linux-fake-pci",
        .ids = ids,
        .probe =
            [](driver::OkDevice &, const obos::linux_compat::pci_device_id &) {
                shim_state.probed = true;
                return Status::success();
            },
        .remove =
            [](driver::OkDevice &) {
                shim_state.removed = true;
                return Status::success();
            },
    };
    if (auto status = shim.register_driver(linux_driver); !status.ok())
    {
        return status;
    }
    driver::OkDevice missing{
        .bus = driver::OkBusType::pci,
        .id = driver::OkDeviceId{.vendor = 0x1234, .device = 0x5678, .class_code = 0x02},
    };
    if (shim.bind(missing).code() != StatusCode::not_found)
    {
        return Status::fault("Linux driver shim matched the wrong PCI ID");
    }
    if (auto status = shim.bind(device); !status.ok())
    {
        return status;
    }
    if (!device.attached || shim.probe_count() != 1)
    {
        return Status::fault("Linux driver shim probe accounting failed");
    }

    auto *mmio = shim.ioremap(0x1000, 64);
    if (mmio == nullptr || !mmio->writel(0, 0xfeed).ok() || mmio->readl(0) != 0xfeed || !shim.iounmap(mmio).ok() ||
        mmio->writel(0, 0).code() != StatusCode::not_initialized)
    {
        return Status::fault("Linux driver shim MMIO validation failed");
    }
    if (shim.iounmap(nullptr).code() != StatusCode::invalid_argument)
    {
        return Status::fault("Linux driver shim accepted invalid MMIO unmap");
    }

    auto *allocation = shim.kmalloc(16);
    if (allocation == nullptr || shim.kmalloc(16) != nullptr || !shim.kfree(allocation).ok() ||
        shim.kfree(allocation).code() != StatusCode::invalid_argument)
    {
        return Status::fault("Linux driver shim allocation validation failed");
    }

    driver::OkDmaBuffer dma_buffer{};
    dma_buffer.size = 128;
    auto dma_mapping = shim.dma_map_single(dma_buffer, 64, driver::OkDmaDirection::bidirectional);
    if (!dma_mapping || !dma_mapping.value().mapped || dma_mapping.value().size != 64)
    {
        return Status::fault("Linux driver shim DMA map validation failed");
    }
    auto active_mapping = dma_mapping.value();
    if (!shim.dma_unmap_single(active_mapping).ok() || active_mapping.mapped ||
        shim.dma_unmap_single(active_mapping).code() != StatusCode::invalid_argument)
    {
        return Status::fault("Linux driver shim DMA unmap validation failed");
    }

    if (!shim.schedule_work().ok() || !shim.schedule_work().ok())
    {
        return Status::fault("Linux driver shim work scheduling failed");
    }
    auto flushed = shim.flush_work();
    if (!flushed || flushed.value() != 2)
    {
        return Status::fault("Linux driver shim workqueue flush validation failed");
    }

    driver::OkSpinLock spinlock;
    if (!spinlock.try_lock())
    {
        return Status::fault("Linux driver shim spinlock validation failed");
    }
    spinlock.unlock();

    driver::OkIrqHandle irq{};
    if (!shim.request_irq(irq, 44).ok() || irq.vector != 44 ||
        shim.request_irq(irq, 45).code() != StatusCode::already_exists || !shim.free_irq(irq).ok() ||
        shim.free_irq(irq).code() != StatusCode::invalid_argument)
    {
        return Status::fault("Linux driver shim IRQ validation failed");
    }

    if (auto status = shim.remove(device); !status.ok())
    {
        return status;
    }
    if (!shim_state.probed || !shim_state.removed || device.attached || shim.remove_count() != 1)
    {
        return Status::fault("Linux driver shim probe/remove validation failed");
    }

    return Status::success();
}

} // namespace

int main()
{
    const auto status = test_linux_driver_shim();
    if (!status.ok())
    {
        std::fprintf(stderr, "%.*s\n", static_cast<int>(status.message().size()), status.message().data());
        return 1;
    }
    std::puts("OS_LINUX_PCI_MODEL_PASS");
    return 0;
}

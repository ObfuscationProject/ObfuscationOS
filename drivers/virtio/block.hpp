#pragma once

#include <ok/driver/driver.hpp>

namespace os::drivers
{

// Discover and initialize one QEMU Virtio disk without changing disk contents.
// The returned device has static lifetime. A missing transport returns not_found.
// The original attempt is one-shot; failed queue ownership is never reconstructed.
ok::Result<ok::driver::BlockDevice *> probe_virtio_block();

// Read-only singleton/FLUSH/idle admission for the exact published transport.
// This neither stops producers nor releases the device's static DMA storage.
ok::Status preflight_virtio_block_shutdown(const ok::driver::BlockDevice &device);

// Called only after the original mounted provider has sealed clean. Closes
// request admission and checks reset acknowledgment; queue storage stays static.
ok::Status stop_virtio_block_shutdown(const ok::driver::BlockDevice &device);

} // namespace os::drivers

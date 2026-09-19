#pragma once

#include <ok/driver/driver.hpp>

namespace os::drivers
{

// Discover and initialize one QEMU Virtio disk without changing disk contents.
// The returned device has static lifetime. A missing transport returns not_found.
ok::Result<ok::driver::BlockDevice *> probe_virtio_block();

} // namespace os::drivers

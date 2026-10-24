#pragma once

#include <ok/driver/entropy.hpp>

namespace os::drivers
{

// Static-lifetime x86-64 modern Virtio RNG PCI source. Other profiles report
// not_found until their transports are independently qualified. The original
// probe result is retained; failed static queue owners are never reconstructed.
ok::Result<ok::driver::EntropySource *> probe_virtio_rng();

// Serialized shutdown of the exact published polling source. Admission reads
// queue/transport ownership; stop resets once and retains static DMA storage.
ok::Status preflight_virtio_rng_shutdown(const ok::driver::EntropySource *source);
ok::Status stop_virtio_rng_shutdown(const ok::driver::EntropySource *source);

} // namespace os::drivers

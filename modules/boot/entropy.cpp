#include "../../drivers/virtio/rng.hpp"
#include <ok/posix/posix.hpp>

extern "C" void ok_platform_console_write_char(char);

namespace
{
void report(const char *text)
{
    while (*text) ok_platform_console_write_char(*text++);
}
#if defined(__aarch64__) || defined(__arm__) || defined(__riscv)
constexpr auto ready = "OK_ENTROPY source=virtio-rng-mmio state=ready\n";
constexpr auto failed = "OK_ENTROPY source=virtio-rng-mmio state=failed\n";
#else
constexpr auto ready = "OK_ENTROPY source=virtio-rng-pci state=ready\n";
constexpr auto failed = "OK_ENTROPY source=virtio-rng-pci state=failed\n";
#endif
}

extern "C" ok::Status ok_boot_entropy(ok::posix::PosixService &posix)
{
    auto source = os::drivers::probe_virtio_rng();
    if (!source)
    {
        if (source.status().code() == ok::StatusCode::not_found)
        {
            report("OK_ENTROPY source=none state=unavailable\n");
            return ok::Status::success();
        }
        report(failed);
        return source.status();
    }
    posix.set_entropy_source(source.value());
    report(ready);
    return ok::Status::success();
}

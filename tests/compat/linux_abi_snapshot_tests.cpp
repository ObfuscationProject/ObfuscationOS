#include "obos/linux/abi_snapshot.hpp"

#include <cstdio>

using namespace ok;
using namespace obos::linux_compat;

namespace
{
Status test_linux_abi_snapshot()
{
    LinuxAbiSnapshot snapshot;
    if (auto status = snapshot.begin("mainline-tracking", true); !status.ok())
    {
        return status;
    }
    if (auto status = snapshot.record_required_symbol("pci_register_driver"); !status.ok())
    {
        return status;
    }
    if (auto status = snapshot.record_required_symbol("dma_map_single"); !status.ok())
    {
        return status;
    }
    if (auto status = snapshot.record_implemented_symbol("pci_register_driver"); !status.ok())
    {
        return status;
    }
    if (auto status = snapshot.record_layout("struct pci_driver", 64, 8); !status.ok())
    {
        return status;
    }
    if (!snapshot.tracks_mainline() || snapshot.required_symbol_count() != 2 ||
        snapshot.implemented_symbol_count() != 1 || snapshot.layout_count() != 1 || snapshot.coverage_x100() != 5000)
    {
        return Status::fault("Linux mainline ABI snapshot validation failed");
    }

    if (snapshot.baseline() != "mainline-tracking" ||
        snapshot.record_required_symbol("pci_register_driver").code() != StatusCode::already_exists ||
        snapshot.record_implemented_symbol("pci_register_driver").code() != StatusCode::already_exists ||
        snapshot.record_layout("struct pci_driver", 128, 9).code() != StatusCode::already_exists)
    {
        return Status::fault("Linux ABI snapshot did not preserve its baseline or reject duplicates");
    }
    if (auto status = snapshot.begin("selected-lts", false); !status.ok())
    {
        return status;
    }
    if (snapshot.baseline() != "selected-lts" || snapshot.tracks_mainline() || snapshot.required_symbol_count() != 0 ||
        snapshot.implemented_symbol_count() != 0 || snapshot.layout_count() != 0 || snapshot.coverage_x100() != 10000)
    {
        return Status::fault("Linux ABI snapshot did not reset for a new baseline");
    }
    return Status::success();
}
} // namespace

int main()
{
    const auto status = test_linux_abi_snapshot();
    if (!status.ok())
    {
        std::fprintf(stderr, "%.*s\n", static_cast<int>(status.message().size()), status.message().data());
        return 1;
    }
    std::puts("OS_LINUX_ABI_SNAPSHOT_MODEL_PASS");
    return 0;
}

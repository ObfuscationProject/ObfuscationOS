#include "obos/linux/abi_snapshot.hpp"

namespace obos::linux_compat
{
namespace
{
Status append_tracked_symbol(StaticVector<ModuleSymbol, max_module_symbols> &symbols, std::string_view name,
                             ModuleSymbolBinding binding, uptr address = 0)
{
    if (name.empty())
    {
        return Status::invalid_argument("module symbol name is empty");
    }
    ModuleSymbol symbol{.address = address, .binding = binding, .resolved = address != 0};
    if (auto status = symbol.name.assign(name); !status.ok())
    {
        return status;
    }
    return symbols.push_back(symbol);
}

} // namespace

Status LinuxAbiSnapshot::begin(std::string_view baseline, bool tracks_mainline)
{
    if (auto status = baseline_.assign(baseline); !status.ok())
    {
        return status;
    }
    tracks_mainline_ = tracks_mainline;
    required_symbols_.clear();
    implemented_symbols_.clear();
    layouts_.clear();
    return Status::success();
}

Status LinuxAbiSnapshot::record_required_symbol(std::string_view name)
{
    if (contains(std::span<const ModuleSymbol>{required_symbols_.begin(), required_symbols_.size()}, name))
    {
        return Status::already_exists("required Linux ABI symbol already recorded");
    }
    return append_tracked_symbol(required_symbols_, name, ModuleSymbolBinding::imported);
}

Status LinuxAbiSnapshot::record_implemented_symbol(std::string_view name)
{
    if (contains(std::span<const ModuleSymbol>{implemented_symbols_.begin(), implemented_symbols_.size()}, name))
    {
        return Status::already_exists("implemented Linux ABI symbol already recorded");
    }
    return append_tracked_symbol(implemented_symbols_, name, ModuleSymbolBinding::exported, 1);
}

Status LinuxAbiSnapshot::record_layout(std::string_view name, u32 size, u32 field_count)
{
    for (const auto &layout : layouts_)
    {
        if (layout.name.view() == name)
        {
            return Status::already_exists("Linux ABI layout already recorded");
        }
    }
    LinuxStructLayout layout{.size = size, .field_count = field_count};
    if (auto status = layout.name.assign(name); !status.ok())
    {
        return status;
    }
    return layouts_.push_back(layout);
}

bool LinuxAbiSnapshot::contains(std::span<const ModuleSymbol> symbols, std::string_view name) const
{
    for (const auto &symbol : symbols)
    {
        if (symbol.name.view() == name)
        {
            return true;
        }
    }
    return false;
}

u32 LinuxAbiSnapshot::coverage_x100() const
{
    if (required_symbols_.empty())
    {
        return 10000;
    }
    usize covered = 0;
    for (const auto &symbol : required_symbols_)
    {
        if (contains(std::span<const ModuleSymbol>{implemented_symbols_.begin(), implemented_symbols_.size()},
                     symbol.name.view()))
        {
            ++covered;
        }
    }
    return static_cast<u32>((covered * 10000u) / required_symbols_.size());
}

} // namespace obos::linux_compat

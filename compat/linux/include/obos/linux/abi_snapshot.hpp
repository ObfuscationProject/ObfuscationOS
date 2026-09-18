#pragma once

#include <ok/core/module.hpp>

namespace obos::linux_compat
{
using namespace ok;

// OS-owned tracking of explicitly recorded Linux driver requirements.
// Coverage measures this recorded set, not compatibility with a Linux release.
inline constexpr usize max_linux_abi_layouts = 32;

struct LinuxStructLayout
{
    FixedString<max_module_name> name{};
    u32 size{0};
    u32 field_count{0};
};

class LinuxAbiSnapshot final
{
  public:
    Status begin(std::string_view baseline, bool tracks_mainline);
    Status record_required_symbol(std::string_view name);
    Status record_implemented_symbol(std::string_view name);
    Status record_layout(std::string_view name, u32 size, u32 field_count);
    [[nodiscard]] std::string_view baseline() const
    {
        return baseline_.view();
    }
    [[nodiscard]] bool tracks_mainline() const
    {
        return tracks_mainline_;
    }
    [[nodiscard]] usize required_symbol_count() const
    {
        return required_symbols_.size();
    }
    [[nodiscard]] usize implemented_symbol_count() const
    {
        return implemented_symbols_.size();
    }
    [[nodiscard]] usize layout_count() const
    {
        return layouts_.size();
    }
    [[nodiscard]] u32 coverage_x100() const;

  private:
    [[nodiscard]] bool contains(std::span<const ModuleSymbol> symbols, std::string_view name) const;

    FixedString<max_module_text> baseline_{};
    bool tracks_mainline_{false};
    StaticVector<ModuleSymbol, max_module_symbols> required_symbols_{};
    StaticVector<ModuleSymbol, max_module_symbols> implemented_symbols_{};
    StaticVector<LinuxStructLayout, max_linux_abi_layouts> layouts_{};
};

} // namespace obos::linux_compat

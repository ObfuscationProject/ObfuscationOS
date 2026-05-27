#include <ok/core/module.hpp>
#include <ok/gui/desktop.hpp>

namespace obfuscationos::modules
{

// OS-side C++ OOP module source for the base GUI package. The current kernel
// loader consumes system-gui.okmod metadata and binds it to the compatible
// desktop-module ABI; once native relocation lands, this source is the module
// implementation that should be compiled into the loadable image.
class SystemGuiModule final
{
  public:
    static constexpr const char *name = "system-gui";
    static constexpr const char *service = "gui.system-desktop";
    static constexpr const char *title = "ObfuscationOS Login";
    static constexpr const char *brand = "ObfuscationOS";
};

} // namespace obfuscationos::modules

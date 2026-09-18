#pragma once
#include "external_module.hpp"
#include "ok/core/kernel.hpp"

namespace obfuscationos::modules
{
using namespace ok;
class SystemGuiRuntime final : public KernelExtension
{
  public:
    Status self_test(Kernel &kernel) override;
    Status start(Kernel &kernel) override;
    Result<fs::FileBuffer> read_package(Kernel &kernel, std::string_view path) override;
    Status load_package(Kernel &kernel, std::string_view path, const ModuleImageInfo &image) override;
    Result<bool> pointer_click(Kernel &kernel, i32 x, i32 y) override;
    Result<bool> key(Kernel &kernel, int value) override;
    Status surface_action(Kernel &kernel, gui::SurfaceId surface, ExtensionSurfaceAction action) override;
    Status process_exited(Kernel &kernel, sched::ProcessId pid) override;
    Status refresh(Kernel &kernel, bool focus) override;
    ExternalGuiDesktopModule *loaded_gui_desktop_module()
    {
        return external_gui_desktop_module_.configured() ? &external_gui_desktop_module_ : nullptr;
    }

  private:
    Status start_selected_system_gui_session(ExternalGuiDesktopModule &desktop);
    Status handle_system_gui_dock_launcher(ExternalGuiDockApp app);
    Status focus_system_gui_app(ExternalGuiDockApp app);
    Result<usize> read_user_program_file(std::string_view path);
    Status load_external_gui_desktop_module(std::string_view path, const ModuleImageInfo &image);
    Status launch_system_gui_app(ExternalGuiDockApp app);
    Status launch_system_gui_app_session();
    Result<usize> find_system_gui_app_by_surface(gui::SurfaceId surface) const;
    Result<usize> find_system_gui_app_by_process(sched::ProcessId pid) const;
    Status close_system_gui_app_at(usize index, bool kill_process);
    Status refresh_external_gui_modules(bool focus_desktop);
    Kernel *kernel_{nullptr};
    arch::ArchOperations *arch_ptr_{nullptr};
    ExternalGuiDesktopModule external_gui_desktop_module_{};
    std::array<ExternalGuiAppModule, max_external_gui_apps> external_gui_app_modules_{};
    std::array<std::byte, fs::simplefs_max_file_data> user_program_image_{};
    bool self_test_passed_{false};
    bool boot_announced_{false};
};
KernelExtension *system_gui_extension();
Status run_system_gui_integration_tests(Kernel &kernel);
} // namespace obfuscationos::modules

#pragma once

#include "ok/core/module.hpp"
#include "ok/gui/desktop.hpp"
#include "ok/sched/scheduler.hpp"
#include "ok/smp/smp.hpp"

#include "ok/fs/vfs.hpp"
#include "ok/posix/posix.hpp"
#include <array>
#include "files_actions.hpp"
#include "notes_handoff.hpp"

namespace ok
{

inline constexpr usize max_loaded_module_path = 96;
inline constexpr usize max_loaded_gui_text = 64;
inline constexpr usize max_external_gui_apps = 8;

enum class ExternalGuiDesktopState : u8
{
    unloaded,
    stopped,
    greeter,
    desktop,
};

enum class ExternalGuiAppState : u8
{
    unloaded,
    stopped,
    running,
};

enum class ExternalGuiLoginUser : u8
{
    root,
    user,
};

enum class ExternalGuiDockApp : u8
{
    none,
    shell,
    settings,
    tasks,
    about,
    notes,
    files,
};

class ExternalGuiDesktopModule final : public KernelModule, public KernelService
{
  public:
    void bind_metrics(const sched::Scheduler &scheduler, const smp::CpuTopology &topology)
    {
        scheduler_ = &scheduler;
        topology_ = &topology;
    }

    Status configure_from_image(std::string_view path, const ModuleImageInfo &image);

    [[nodiscard]] ModuleManifest manifest() const override;
    [[nodiscard]] std::string_view service_id() const override
    {
        return service_id_.view();
    }
    [[nodiscard]] void *service(std::string_view service_id) override;
    Status start(ServiceRegistry &services) override;
    Status stop() override;
    Status shutdown() override;
    [[nodiscard]] Status shutdown_preflight() const override;
    Status refresh();
    Status handle_key(int key);
    Status handle_pointer_click(i32 x, i32 y);
    Status login_default_user();
    [[nodiscard]] Result<ExternalGuiDockApp> dock_launcher_at(i32 x, i32 y) const;
    [[nodiscard]] std::string_view selected_login_user_name() const;

    [[nodiscard]] bool configured() const
    {
        return configured_;
    }
    [[nodiscard]] ExternalGuiDesktopState desktop_state() const
    {
        return desktop_state_;
    }
    [[nodiscard]] std::string_view module_name() const
    {
        return name_.view();
    }
    [[nodiscard]] std::string_view load_path() const
    {
        return load_path_.view();
    }
    [[nodiscard]] gui::SurfaceId dashboard_surface() const
    {
        return dashboard_surface_;
    }
    [[nodiscard]] usize render_count() const
    {
        return render_count_;
    }

  private:
    Status open_shell_surface(std::string_view title, gui::GuiShellMode mode);
    Status render_greeter();
    Status render_desktop_shell();
    Status assign_parameter(std::string_view name, std::string_view value);

    bool configured_{false};
    FixedString<max_module_name> name_{};
    FixedString<max_module_name> version_{};
    FixedString<max_module_name> service_id_{};
    FixedString<max_loaded_module_path> load_path_{};
    FixedString<max_loaded_gui_text> brand_{"ObfuscationOS"};
    FixedString<max_loaded_gui_text> title_{"ObfuscationOS Login"};
    FixedString<max_loaded_gui_text> subtitle_{"default user root"};
    std::array<ModuleDependency, 1> dependencies_{{ModuleDependency{.name = gui::gui_module_name, .required = true}}};
    std::array<std::string_view, 2> required_services_{{gui::gui_service_id, gui::gui_desktop_service_id}};
    std::array<std::string_view, 1> exported_services_{};
    gui::GuiCompositor *compositor_{nullptr};
    gui::GuiDesktopService *desktop_{nullptr};
    const sched::Scheduler *scheduler_{nullptr};
    const smp::CpuTopology *topology_{nullptr};
    ExternalGuiDesktopState desktop_state_{ExternalGuiDesktopState::unloaded};
    gui::SurfaceId dashboard_surface_{0};
    usize render_count_{0};
    ExternalGuiLoginUser selected_login_user_{ExternalGuiLoginUser::root};
    bool login_dropdown_open_{false};
};

class ExternalGuiAppModule final : public KernelModule, public KernelService
{
  public:
    void bind_metrics(const sched::Scheduler &scheduler, const smp::CpuTopology &topology)
    {
        scheduler_ = &scheduler;
        topology_ = &topology;
    }

    void bind_environment(fs::VirtualFileSystem &vfs, posix::PosixService &posix)
    {
        vfs_ = &vfs;
        posix_ = &posix;
    }
    Status handle_key(int key);
    Status handle_pointer(i32 x, i32 y);
    void set_accent(u32 color)
    {
        accent_ = color;
    }
    [[nodiscard]] u32 accent() const
    {
        return accent_;
    }
    [[nodiscard]] std::string_view document() const
    {
        return document_.view();
    }
    [[nodiscard]] std::string_view directory() const
    {
        return directory_.view();
    }
    [[nodiscard]] bool unsaved_changes() const { return document_dirty_; }
    [[nodiscard]] bool notes_save_blocked() const { return notes_load_failed_; }
    [[nodiscard]] std::string_view notes_document_path() const { return notes_has_target_ ? notes_target_.path.view() : std::string_view{}; }
    [[nodiscard]] std::string_view app_status() const { return status_line_.view(); }
    [[nodiscard]] bool has_notes_request() const { return notes_request_pending_; }
    [[nodiscard]] const obfuscationos::desktop::NotesTarget &notes_request() const { return notes_request_; }
    Status open_notes_target(const obfuscationos::desktop::NotesTarget &target);
    Status finish_notes_request(Status result, bool render = true);
    Status configure_from_image(std::string_view path, const ModuleImageInfo &image);
    Status configure_from_elf(std::string_view app_id, std::string_view path, std::string_view title,
                              std::string_view subtitle, std::string_view body, std::string_view command,
                              std::string_view line1, std::string_view line2, std::string_view line3, gui::Rect bounds,
                              std::string_view accent, sched::ProcessId process_id);

    [[nodiscard]] ModuleManifest manifest() const override;
    [[nodiscard]] std::string_view service_id() const override
    {
        return service_id_.view();
    }
    [[nodiscard]] void *service(std::string_view service_id) override;
    Status start(ServiceRegistry &services) override;
    Status start(gui::GuiCompositor &compositor, gui::GuiDesktopService &desktop);
    Status stop() override;
    Status shutdown() override;
    [[nodiscard]] Status shutdown_preflight() const override;
    Status refresh();
    void reset();

    [[nodiscard]] bool configured() const
    {
        return configured_;
    }
    [[nodiscard]] ExternalGuiAppState app_state() const
    {
        return app_state_;
    }
    [[nodiscard]] std::string_view module_name() const
    {
        return name_.view();
    }
    [[nodiscard]] std::string_view app_id() const
    {
        return service_id_.view();
    }
    [[nodiscard]] std::string_view load_path() const
    {
        return load_path_.view();
    }
    [[nodiscard]] sched::ProcessId process_id() const
    {
        return process_id_;
    }
    [[nodiscard]] gui::SurfaceId surface() const
    {
        return surface_;
    }
    [[nodiscard]] usize render_count() const
    {
        return render_count_;
    }

  private:
    Status open_window();
    Status render_window();
    Status assign_parameter(std::string_view name, std::string_view value);

    Status execute_command();
    Status load_notes();
    Status save_notes();
    Status open_file_entry(usize index);
    Status begin_file_action(obfuscationos::desktop::FilesAction action);
    Status commit_file_action();
    fs::VirtualFileSystem *vfs_{nullptr};
    posix::PosixService *posix_{nullptr};
    FixedString<1024> document_{"A little space for your ideas.\n\nType to edit. Ctrl+S to save."};
    FixedString<192> input_{};
    FixedString<1024> output_{"ObfuscationOS terminal\nType help to see available commands."};
    FixedString<96> directory_{"/"};
    FixedString<96> status_line_{"Ready"};
    usize selected_entry_{0};
    bool document_dirty_{false};
    bool notes_load_failed_{false};
    bool notes_has_target_{false};
    bool notes_publication_uncertain_{false};
    bool notes_retained_after_render_failure_{false};
    obfuscationos::desktop::NotesTarget notes_target_{};
    bool notes_request_pending_{false};
    obfuscationos::desktop::NotesTarget notes_request_{};
    bool file_listing_captured_{false};
    fs::DirectoryListing file_display_listing_{};
    FixedString<96> file_display_directory_{};
    posix::FileStatus file_display_parent_{};
    bool file_preview_{false};
    obfuscationos::desktop::FilesAction file_action_{obfuscationos::desktop::FilesAction::none};
    FixedString<64> file_action_source_{};
    FixedString<96> file_action_directory_{};
    posix::FileStatus file_action_selection_{};
    posix::FileStatus file_action_parent_{};
    bool configured_{false};
    FixedString<max_module_name> name_{};
    FixedString<max_module_name> version_{};
    FixedString<max_module_name> service_id_{};
    FixedString<max_loaded_module_path> load_path_{};
    FixedString<max_loaded_gui_text> title_{"System App"};
    FixedString<max_loaded_gui_text> subtitle_{"C++ OOP GUI module"};
    FixedString<max_loaded_gui_text> body_{"Loaded from /boot/modules"};
    FixedString<max_loaded_gui_text> command_{};
    FixedString<max_loaded_gui_text> line1_{};
    FixedString<max_loaded_gui_text> line2_{};
    FixedString<max_loaded_gui_text> line3_{};
    std::array<ModuleDependency, 1> dependencies_{{ModuleDependency{.name = gui::gui_module_name, .required = true}}};
    std::array<std::string_view, 3> required_services_{{gui::gui_service_id, gui::gui_desktop_service_id, {}}};
    usize required_service_count_{2};
    std::array<std::string_view, 1> exported_services_{};
    gui::GuiCompositor *compositor_{nullptr};
    gui::GuiDesktopService *desktop_{nullptr};
    const sched::Scheduler *scheduler_{nullptr};
    const smp::CpuTopology *topology_{nullptr};
    ExternalGuiAppState app_state_{ExternalGuiAppState::unloaded};
    gui::SurfaceId surface_{0};
    gui::Rect bounds_{.x = 72, .y = 64, .width = 276, .height = 112};
    u32 accent_{0xffffcc66u};
    sched::ProcessId process_id_{0};
    usize render_count_{0};
};

} // namespace ok

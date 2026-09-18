#include "ok/core/entry.hpp"
#include "system_gui_runtime.hpp"

namespace obfuscationos::modules
{
namespace
{
bool file_contains(const fs::FileBuffer &file, std::string_view needle)
{
    if (needle.empty())
    {
        return true;
    }
    if (needle.size() > file.size)
    {
        return false;
    }
    for (usize i = 0; i + needle.size() <= file.size; ++i)
    {
        bool match = true;
        for (usize j = 0; j < needle.size(); ++j)
        {
            if (std::to_integer<char>(file.data[i + j]) != needle[j])
            {
                match = false;
                break;
            }
        }
        if (match)
        {
            return true;
        }
    }
    return false;
}

std::span<const std::byte> bytes_for(std::string_view text)
{
    return {reinterpret_cast<const std::byte *>(text.data()), text.size()};
}

Result<gui::SurfaceInfo> find_surface_by_title(Kernel &kernel, std::string_view title)
{
    for (gui::SurfaceId id = 1; id < 64; ++id)
    {
        auto info = kernel.gui().compositor().surface_info(id);
        if (!info)
        {
            continue;
        }
        if (info.value().title == title)
        {
            return info.value();
        }
    }
    return Status::not_found("surface title was not found");
}

usize process_count_named(const sched::Scheduler &scheduler, std::string_view name)
{
    usize count = 0;
    for (const auto &process : scheduler.processes())
    {
        if (process.name() == name)
        {
            ++count;
        }
    }
    return count;
}

Result<sched::ProcessId> first_process_named(const sched::Scheduler &scheduler, std::string_view name)
{
    for (const auto &process : scheduler.processes())
    {
        if (process.name() == name)
        {
            return process.pid();
        }
    }
    return Status::not_found("process name was not found");
}

void write_le16(std::span<std::byte> out, usize offset, u16 value)
{
    out[offset] = static_cast<std::byte>(value & 0xffu);
    out[offset + 1] = static_cast<std::byte>((value >> 8) & 0xffu);
}

void write_le32(std::span<std::byte> out, usize offset, u32 value)
{
    write_le16(out, offset, static_cast<u16>(value & 0xffffu));
    write_le16(out, offset + 2, static_cast<u16>((value >> 16) & 0xffffu));
}

void write_le64(std::span<std::byte> out, usize offset, u64 value)
{
    write_le32(out, offset, static_cast<u32>(value & 0xffff'ffffu));
    write_le32(out, offset + 4, static_cast<u32>((value >> 32) & 0xffff'ffffu));
}

u16 elf_machine_for(arch::Architecture architecture)
{
    switch (architecture)
    {
    case arch::Architecture::i386:
        return 0x03;
    case arch::Architecture::aarch64:
        return 0xb7;
    case arch::Architecture::arm32:
        return 0x28;
    case arch::Architecture::rv64:
    case arch::Architecture::rv32:
        return 0xf3;
    case arch::Architecture::mips:
    case arch::Architecture::mips64:
        return 0x08;
    case arch::Architecture::ppc:
        return 0x14;
    case arch::Architecture::loongarch64:
        return 0x102;
    case arch::Architecture::x86_64:
        return 0x3e;
    }
    return 0x3e;
}

template <usize ImageSize = 128> std::array<std::byte, ImageSize> make_test_elf(arch::Architecture architecture)
{
    static_assert(ImageSize >= 128);
    std::array<std::byte, ImageSize> image{};
    auto bytes = std::span<std::byte>(image.data(), image.size());
    bytes[0] = std::byte{0x7f};
    bytes[1] = std::byte{'E'};
    bytes[2] = std::byte{'L'};
    bytes[3] = std::byte{'F'};
    bytes[4] = std::byte{2};
    bytes[5] = std::byte{1};
    bytes[6] = std::byte{1};
    write_le32(bytes, 20, 1);
    write_le16(bytes, 52, 64);
    write_le16(bytes, 16, 2);
    write_le16(bytes, 18, elf_machine_for(architecture));
    write_le64(bytes, 24, 0x400000);
    write_le64(bytes, 32, 64);
    write_le16(bytes, 54, 56);
    write_le16(bytes, 56, 1);
    write_le32(bytes, 64, 1);
    write_le32(bytes, 68, 0x5);
    write_le64(bytes, 72, 120);
    write_le64(bytes, 80, 0x400000);
    write_le64(bytes, 88, 0x400000);
    write_le64(bytes, 96, 4);
    write_le64(bytes, 104, 0x2000);
    write_le64(bytes, 112, 1);
    bytes[120] = std::byte{0xc3};
    return image;
}

constexpr std::string_view os_system_gui_module_path{"/boot/modules/system-gui.okmod"};
constexpr std::string_view os_system_gui_module_text{"OKMOD\n"
                                                     "name=system-gui\n"
                                                     "version=1\n"
                                                     "vermagic=okernel-cxx-oop\n"
                                                     "require=gui.compositor\n"
                                                     "require=gui.desktop\n"
                                                     "export=gui.system-desktop\n"
                                                     "param=entry:oop\n"
                                                     "param=class:desktop\n"
                                                     "param=brand:ObfuscationOS\n"
                                                     "param=title:ObfuscationOS Login\n"
                                                     "param=subtitle:choose root or user\n"
                                                     "signature=system-gui-dev\n"};

Status ensure_test_directory(Kernel &kernel, std::string_view path)
{
    auto stat = kernel.vfs().stat(path);
    if (stat)
    {
        return stat.value().type == fs::NodeType::directory ? Status::success()
                                                            : Status::invalid_argument("test path is not a directory");
    }
    if (stat.status().code() != StatusCode::not_found)
    {
        return stat.status();
    }
    return kernel.vfs().create(path, fs::NodeType::directory);
}

Status stage_os_system_gui_module(Kernel &kernel)
{
    if (auto status = ensure_test_directory(kernel, "/boot"); !status.ok())
    {
        return status;
    }
    if (auto status = ensure_test_directory(kernel, "/boot/modules"); !status.ok())
    {
        return status;
    }
    auto stat = kernel.vfs().stat(os_system_gui_module_path);
    if (!stat)
    {
        if (stat.status().code() != StatusCode::not_found)
        {
            return stat.status();
        }
        if (auto status = kernel.vfs().create(os_system_gui_module_path, fs::NodeType::regular); !status.ok())
        {
            return status;
        }
    }
    return kernel.vfs().write_file(os_system_gui_module_path, bytes_for(os_system_gui_module_text));
}

Status stage_system_gui_user_apps(Kernel &kernel)
{
    const auto elf = make_test_elf<8192>(kernel.arch().architecture());
    constexpr std::string_view paths[] = {"/oksh", "/settings", "/tasks", "/notes", "/about", "/ls"};
    for (const auto path : paths)
    {
        auto stat = kernel.simplefs().stat(path);
        if (!stat)
        {
            if (stat.status().code() != StatusCode::not_found)
            {
                return stat.status();
            }
            if (auto status = kernel.simplefs().create(path, fs::NodeType::regular); !status.ok())
            {
                return status;
            }
        }
        if (auto status = kernel.simplefs().write_file(path, std::span<const std::byte>{elf.data(), elf.size()});
            !status.ok())
        {
            return status;
        }
    }
    return Status::success();
}

Status test_system_gui_module_loads_after_boot(Kernel &kernel)
{
    if (kernel.kernel_modules().find("system-gui") != nullptr ||
        kernel.kernel_modules().services().contains("gui.system-desktop"))
    {
        return Status::fault("system GUI module was loaded before the OS loader ran");
    }
    if (auto status = stage_os_system_gui_module(kernel); !status.ok())
    {
        return status;
    }

    syscall::Request request{.number = syscall::Number::load_module};
    request.args[0] = reinterpret_cast<u64>(os_system_gui_module_path.data());
    auto response = kernel.syscalls().dispatch(request);
    auto *registered = kernel.kernel_modules().find("system-gui");
    auto module_file = kernel.vfs().read_file(os_system_gui_module_path);
    if (!response.status.ok() || response.value != 0 || !module_file || registered == nullptr ||
        registered->manifest().built_in || registered->state() != ModuleState::started ||
        !kernel.kernel_modules().services().contains("gui.system-desktop"))
    {
        return Status::fault("system GUI module was not loaded by the OS module loader syscall");
    }
    if (!file_contains(module_file.value(), "name=system-gui") ||
        !file_contains(module_file.value(), "require=gui.compositor") ||
        !file_contains(module_file.value(), "require=gui.desktop") ||
        !file_contains(module_file.value(), "export=gui.system-desktop") ||
        !file_contains(module_file.value(), "param=entry:oop") ||
        !file_contains(module_file.value(), "param=class:desktop"))
    {
        return Status::fault("system desktop OKMOD package metadata is incomplete");
    }

    auto *desktop = static_cast<SystemGuiRuntime *>(kernel.extension())->loaded_gui_desktop_module();
    auto info = find_surface_by_title(kernel, "ObfuscationOS Login");
    if (desktop == nullptr || desktop->desktop_state() != ExternalGuiDesktopState::greeter ||
        kernel.gui().compositor().shell_mode() != gui::GuiShellMode::system_greeter || !info ||
        info.value().title != "ObfuscationOS Login" || info.value().app != gui::TaskbarApp::none ||
        info.value().chrome != gui::SurfaceChrome::plain || info.value().bounds.width != driver::framebuffer_width ||
        info.value().bounds.height != driver::framebuffer_height ||
        kernel.gui().compositor().last_present_checksum() == 0)
    {
        return Status::fault("system GUI did not stop at the pre-desktop root greeter");
    }

    const auto taskbar_y = static_cast<i32>(driver::framebuffer_height - gui::taskbar_height + 6);
    auto launcher = kernel.gui().compositor().taskbar_launcher_at(gui::task_monitor_launcher_x + 4, taskbar_y);
    if (launcher || launcher.status().code() != StatusCode::not_found)
    {
        return Status::fault("kernel taskbar was visible before system GUI login");
    }
    if (find_surface_by_title(kernel, "Tiny Shell") || find_surface_by_title(kernel, "System Settings") ||
        find_surface_by_title(kernel, "Task Manager") || find_surface_by_title(kernel, "About ObfuscationOS") ||
        find_surface_by_title(kernel, "Notes"))
    {
        return Status::fault("system GUI apps were visible before login");
    }
    return Status::success();
}

Status test_system_gui_mouse_login_selects_user_and_starts_desktop_shell(Kernel &kernel)
{
    auto *desktop = static_cast<SystemGuiRuntime *>(kernel.extension())->loaded_gui_desktop_module();
    if (desktop == nullptr || desktop->desktop_state() != ExternalGuiDesktopState::greeter)
    {
        return Status::fault("system GUI greeter was not ready before login");
    }
    if (auto status = stage_system_gui_user_apps(kernel); !status.ok())
    {
        return status;
    }

    constexpr u32 card_width = driver::framebuffer_width > 360 ? 360u : driver::framebuffer_width - 24u;
    constexpr u32 card_height = 178u;
    const auto card_x = static_cast<i32>((driver::framebuffer_width - card_width) / 2);
    const auto card_y = static_cast<i32>((driver::framebuffer_height - card_height) / 2);
    const auto dropdown_x = card_x + 104;
    const auto dropdown_y = card_y + 82;
    const auto user_option_x = dropdown_x;
    const auto user_option_y = card_y + 116;
    const auto login_x = card_x + static_cast<i32>(card_width / 2);
    const auto login_y = card_y + 148;

    if (auto status = kernel.handle_gui_mouse_position(dropdown_x, dropdown_y, true); !status.ok())
    {
        return Status::fault("system GUI dropdown press failed");
    }
    if (auto status = kernel.handle_gui_mouse_position(dropdown_x, dropdown_y, false); !status.ok())
    {
        return Status::fault("system GUI dropdown release failed");
    }
    if (auto status = kernel.handle_gui_mouse_position(user_option_x, user_option_y, true); !status.ok())
    {
        return Status::fault("system GUI dropdown user press failed");
    }
    if (auto status = kernel.handle_gui_mouse_position(user_option_x, user_option_y, false); !status.ok())
    {
        return Status::fault("system GUI dropdown user release failed");
    }
    if (auto status = kernel.handle_gui_mouse_position(login_x, login_y, true); !status.ok())
    {
        return status;
    }
    if (auto status = kernel.handle_gui_mouse_position(login_x, login_y, false); !status.ok())
    {
        return Status::fault("system GUI login release failed");
    }
    desktop = static_cast<SystemGuiRuntime *>(kernel.extension())->loaded_gui_desktop_module();
    auto shell = desktop != nullptr ? kernel.gui().compositor().surface_info(desktop->dashboard_surface())
                                    : Result<gui::SurfaceInfo>{Status::not_found("missing desktop")};
    if (desktop == nullptr || desktop->desktop_state() != ExternalGuiDesktopState::desktop ||
        kernel.gui().compositor().shell_mode() != gui::GuiShellMode::system_shell ||
        kernel.posix().user_credentials().euid != user::default_user_uid || !shell ||
        shell.value().title != "ObfuscationOS Desktop" || shell.value().app != gui::TaskbarApp::none ||
        shell.value().chrome != gui::SurfaceChrome::plain ||
        kernel.kernel_modules().services().contains("gui.app.shell") ||
        kernel.kernel_modules().services().contains("gui.app.settings") ||
        kernel.kernel_modules().services().contains("gui.app.tasks") ||
        kernel.kernel_modules().services().contains("gui.app.about") ||
        kernel.kernel_modules().services().contains("gui.app.notes") ||
        kernel.kernel_modules().find("system-shell") != nullptr ||
        kernel.kernel_modules().find("system-settings") != nullptr ||
        kernel.kernel_modules().find("system-tasks") != nullptr ||
        kernel.kernel_modules().find("system-about") != nullptr ||
        kernel.kernel_modules().find("system-notes") != nullptr)
    {
        return Status::fault("system GUI login loaded app modules instead of user ELF apps");
    }
    const auto taskbar_y = static_cast<i32>(driver::framebuffer_height - gui::taskbar_height + 6);
    auto launcher = kernel.gui().compositor().taskbar_launcher_at(gui::task_monitor_launcher_x + 4, taskbar_y);
    if (launcher || launcher.status().code() != StatusCode::not_found)
    {
        return Status::fault("kernel taskbar was still active after system GUI took desktop ownership");
    }
    if (!find_surface_by_title(kernel, "Tiny Shell") || !find_surface_by_title(kernel, "System Settings") ||
        !find_surface_by_title(kernel, "Task Manager") || !find_surface_by_title(kernel, "About ObfuscationOS") ||
        !find_surface_by_title(kernel, "Notes"))
    {
        return Status::fault("system GUI desktop did not show app windows after login");
    }
    if (process_count_named(kernel.scheduler(), "app:oksh") != 1 ||
        process_count_named(kernel.scheduler(), "app:settings") != 1 ||
        process_count_named(kernel.scheduler(), "app:tasks") != 1 ||
        process_count_named(kernel.scheduler(), "app:notes") != 1 ||
        process_count_named(kernel.scheduler(), "app:about") != 1)
    {
        return Status::fault("system GUI desktop did not launch one user ELF process per app");
    }
    auto oksh = first_process_named(kernel.scheduler(), "app:oksh");
    const auto *oksh_process = oksh ? kernel.scheduler().find(oksh.value()) : nullptr;
    if (oksh_process == nullptr || oksh_process->execution() != sched::ProcessExecution::user_process ||
        oksh_process->credentials().euid != user::default_user_uid || oksh_process->credentials().kernel_space)
    {
        return Status::fault("system GUI shell app was not launched as the selected user's ELF process");
    }
    return kernel.posix().set_credentials(user::root_credentials());
}

Status test_start_preserves_active_greeter(Kernel &kernel)
{
    auto *desktop = static_cast<SystemGuiRuntime *>(kernel.extension())->loaded_gui_desktop_module();
    if (desktop == nullptr || desktop->desktop_state() != ExternalGuiDesktopState::greeter)
    {
        return Status::fault("repeat-start test requires an active greeter");
    }
    const auto surface = desktop->dashboard_surface();
    const auto restarts = desktop->restart_count();
    if (auto status = kernel.handle_gui_key('\t'); !status.ok())
        return status;
    const auto selected_user = desktop->selected_login_user_name();
    const auto console_size = kernel.console().buffer().size();
    for (usize i = 0; i < 2; ++i)
    {
        if (auto status = kernel.start_extension(); !status.ok())
            return status;
        if (auto status = kernel.load_external_kernel_module(os_system_gui_module_path); !status.ok())
            return status;
    }
    if (desktop->desktop_state() != ExternalGuiDesktopState::greeter || desktop->dashboard_surface() != surface ||
        desktop->restart_count() != restarts || desktop->selected_login_user_name() != selected_user)
    {
        return Status::fault("repeat start reset the active greeter or its selected user");
    }
    if (kernel.console().buffer().substr(console_size).find("OK_SYSTEM_GUI boot=complete") != std::string_view::npos)
    {
        return Status::fault("system GUI announced boot success before self-test completion");
    }
    return kernel.handle_gui_key('\t');
}

Status test_start_preserves_logged_in_session(Kernel &kernel)
{
    auto *desktop = static_cast<SystemGuiRuntime *>(kernel.extension())->loaded_gui_desktop_module();
    if (desktop == nullptr || desktop->desktop_state() != ExternalGuiDesktopState::desktop)
    {
        return Status::fault("repeat-start test requires a logged-in desktop");
    }
    constexpr std::string_view process_names[] = {"app:oksh", "app:settings", "app:tasks", "app:notes", "app:about"};
    constexpr std::string_view window_titles[] = {"Tiny Shell", "System Settings", "Task Manager", "Notes",
                                                  "About ObfuscationOS"};
    std::array<sched::ProcessId, 5> pids{};
    std::array<gui::SurfaceId, 5> surfaces{};
    for (usize i = 0; i < pids.size(); ++i)
    {
        auto process = first_process_named(kernel.scheduler(), process_names[i]);
        auto surface = find_surface_by_title(kernel, window_titles[i]);
        if (!process || !surface)
            return Status::fault("session app was missing before repeat start");
        pids[i] = process.value();
        surfaces[i] = surface.value().id;
    }
    const auto dashboard = desktop->dashboard_surface();
    const auto restarts = desktop->restart_count();
    const auto saved_credentials = kernel.posix().user_credentials();
    if (auto status = kernel.posix().set_credentials(user::default_user_credentials()); !status.ok())
        return status;
    const auto console_size = kernel.console().buffer().size();
    for (usize i = 0; i < 2; ++i)
    {
        if (auto status = kernel.start_extension(); !status.ok())
            return status;
        if (auto status = kernel.load_external_kernel_module(os_system_gui_module_path); !status.ok())
            return status;
    }
    if (auto status = kernel.vfs().write_file(os_system_gui_module_path, bytes_for("OKMOD\nname=system-gui\n"));
        !status.ok())
        return status;
    const auto invalid_package = kernel.load_external_kernel_module(os_system_gui_module_path);
    if (auto status = stage_os_system_gui_module(kernel); !status.ok())
        return status;
    if (invalid_package.ok())
        return Status::fault("active desktop accepted invalid same-name package metadata");
    if (desktop->desktop_state() != ExternalGuiDesktopState::desktop || desktop->dashboard_surface() != dashboard ||
        desktop->restart_count() != restarts ||
        kernel.gui().compositor().shell_mode() != gui::GuiShellMode::system_shell ||
        kernel.posix().user_credentials().euid != user::default_user_uid)
    {
        return Status::fault("repeat start reset the logged-in desktop or credentials");
    }
    for (usize i = 0; i < pids.size(); ++i)
    {
        auto process = first_process_named(kernel.scheduler(), process_names[i]);
        auto surface = find_surface_by_title(kernel, window_titles[i]);
        if (!process || process.value() != pids[i] || process_count_named(kernel.scheduler(), process_names[i]) != 1 ||
            !surface || surface.value().id != surfaces[i])
        {
            return Status::fault("repeat start replaced or duplicated a session app");
        }
    }
    if (kernel.console().buffer().substr(console_size).find("OK_SYSTEM_GUI boot=complete") != std::string_view::npos)
    {
        return Status::fault("system GUI announced boot success before self-test completion");
    }
    return kernel.posix().set_credentials(saved_credentials);
}

Status test_system_gui_dock_uses_system_app_launchers(Kernel &kernel)
{
    auto *desktop = static_cast<SystemGuiRuntime *>(kernel.extension())->loaded_gui_desktop_module();
    if (desktop == nullptr || desktop->desktop_state() != ExternalGuiDesktopState::desktop)
    {
        return Status::fault("system GUI desktop was not ready for dock input");
    }
    auto shell_app = find_surface_by_title(kernel, "Tiny Shell");
    auto task_app = find_surface_by_title(kernel, "Task Manager");
    if (!shell_app || !task_app)
    {
        return Status::fault("system Shell and Task Manager apps were not loaded before dock interaction");
    }

    const auto shell_surface = kernel.debug_shell().gui_surface_id();
    const auto files_surface = kernel.file_manager().surface_id();
    const auto tasks_surface = kernel.task_manager().surface_id();
    const auto system_shell_x = 32;
    const auto dock_y = static_cast<i32>(driver::framebuffer_height - 18);
    if (auto status = kernel.handle_gui_mouse_position(system_shell_x, dock_y, true); !status.ok())
    {
        return status;
    }
    if (auto status = kernel.handle_gui_mouse_position(system_shell_x, dock_y, false); !status.ok())
    {
        return status;
    }

    auto active = kernel.gui().compositor().surface_info(kernel.gui().compositor().active_surface());
    if (!active || active.value().title != "Tiny Shell")
    {
        return Status::fault("system dock did not focus the Tiny Shell app launcher");
    }
    if (kernel.debug_shell().gui_surface_id() != shell_surface || kernel.file_manager().surface_id() != files_surface ||
        kernel.task_manager().surface_id() != tasks_surface)
    {
        return Status::fault("system dock opened a kernel GUI app instead of a system app");
    }
    if (process_count_named(kernel.scheduler(), "app:oksh") != 1)
    {
        return Status::fault("system dock relaunched or lost the Tiny Shell ELF process while focusing it");
    }
    return Status::success();
}

Status test_system_gui_apps_are_user_elf_processes(Kernel &kernel)
{
    auto settings = first_process_named(kernel.scheduler(), "app:settings");
    if (!settings)
    {
        return settings.status();
    }
    const auto settings_dock_x = 157;
    const auto settings_dock_y = static_cast<i32>(driver::framebuffer_height - 18);
    if (auto status = kernel.handle_gui_mouse_position(settings_dock_x, settings_dock_y, true); !status.ok())
    {
        return status;
    }
    if (auto status = kernel.handle_gui_mouse_position(settings_dock_x, settings_dock_y, false); !status.ok())
    {
        return status;
    }

    auto info = find_surface_by_title(kernel, "System Settings");
    const auto *process = kernel.scheduler().find(settings.value());
    if (!info || process == nullptr || process->execution() != sched::ProcessExecution::user_process ||
        process->credentials().kernel_space || process->credentials().euid != user::default_user_uid)
    {
        return Status::fault("System Settings was not backed by a selected-user ELF process");
    }
    if (kernel.kernel_modules().services().contains("gui.app.settings") ||
        kernel.kernel_modules().find("system-settings") != nullptr)
    {
        return Status::fault("System Settings was still registered as a GUI app module");
    }

    const auto close_x = info.value().bounds.x + static_cast<i32>(info.value().bounds.width) - 10;
    const auto close_y = info.value().bounds.y + 5;
    auto hit = kernel.gui().compositor().surface_at(close_x, close_y);
    if (!hit || hit.value() != info.value().id)
    {
        return Status::fault("System Settings close coordinate did not hit its surface");
    }
    if (auto status = kernel.gui().compositor().set_pointer_position(close_x, close_y); !status.ok())
    {
        return status;
    }
    if (auto status = kernel.handle_gui_mouse(0, 0, true); !status.ok())
    {
        return status;
    }
    if (auto status = kernel.handle_gui_mouse(0, 0, false); !status.ok())
    {
        return status;
    }
    if (find_surface_by_title(kernel, "System Settings"))
    {
        return Status::fault("closing a System GUI ELF app did not close its surface");
    }
    if (kernel.scheduler().find(settings.value()) != nullptr)
    {
        return Status::fault("closing a System GUI ELF app did not close its user process");
    }
    return Status::success();
}

Status test_system_gui_notes_save_and_files_navigation(Kernel &kernel)
{
    constexpr auto dock_y = static_cast<i32>(driver::framebuffer_height - 18);
    auto click = [&](i32 x, i32 y) {
        if (auto status = kernel.handle_gui_mouse_position(x, y, true); !status.ok())
            return status;
        return kernel.handle_gui_mouse_position(x, y, false);
    };
    if (auto status = click(32 + 3 * 76, dock_y); !status.ok())
        return status;
    auto active = kernel.gui().compositor().surface_info(kernel.gui().compositor().active_surface());
    if (!active || active.value().title != "Notes" || !active.value().visible)
        return Status::fault("Notes launcher did not restore its window");
    auto observer = kernel.scheduler().create_process("gui-credential-guard", {});
    if (!observer)
        return observer.status();
    if (auto status = kernel.scheduler().set_credentials(observer.value(), user::kernel_credentials()); !status.ok())
        return status;
    if (auto status = kernel.posix().activate(observer.value()); !status.ok())
        return status;
    constexpr std::string_view suffix{"\nGUI note persistence"};
    for (auto ch : suffix)
        if (auto status = kernel.handle_gui_key(ch); !status.ok())
            return status;
    if (auto status = kernel.handle_gui_key(19); !status.ok())
        return status;
    const auto *guard = kernel.scheduler().find(observer.value());
    if (!guard || !guard->credentials().kernel_space || guard->credentials().euid != user::kernel_credentials().euid)
        return Status::fault("GUI input overwrote another scheduled process's credentials");
    if (auto status = kernel.scheduler().kill_process(observer.value()); !status.ok())
        return status;
    auto file = kernel.vfs().read_file("/tmp/notes-user.txt");
    auto metadata = kernel.vfs().stat("/tmp/notes-user.txt");
    if (!file || !file_contains(file.value(), "GUI note persistence") || !metadata ||
        metadata.value().uid != user::default_user_uid || (metadata.value().mode & 0777u) != 0600u)
        return Status::fault("Notes failed to save a private selected-user file through POSIX");
    if (auto status = kernel.vfs().chmod("/tmp/notes-user.txt", 0644); !status.ok())
        return status;
    if (auto status = kernel.handle_gui_key(19); !status.ok())
        return status;
    metadata = kernel.vfs().stat("/tmp/notes-user.txt");
    if (!metadata || (metadata.value().mode & 0777u) != 0600u)
        return Status::fault("Notes did not restore private permissions when saving an existing file");
    if (auto status = kernel.vfs().chown("/tmp/notes-user.txt", 0, 0); !status.ok())
        return status;
    if (auto status = kernel.handle_gui_key('!'); !status.ok())
        return status;
    if (auto status = kernel.handle_gui_key(19); !status.ok())
        return status;
    auto unchanged = kernel.vfs().read_file("/tmp/notes-user.txt");
    if (!unchanged || unchanged.value().size != file.value().size)
        return Status::fault("Notes overwrote a file owned by another user");
    if (auto status = click(32 + 5 * 76, dock_y); !status.ok())
        return status;
    active = kernel.gui().compositor().surface_info(kernel.gui().compositor().active_surface());
    if (!active || active.value().title != "Files")
        return Status::fault("Files launcher did not focus its window");
    if (auto status = click(active.value().bounds.x + 20, active.value().bounds.y + 110); !status.ok())
        return status;
    if (auto status = kernel.handle_gui_key('\n'); !status.ok())
        return status;
    if (auto status = kernel.handle_gui_key(27); !status.ok())
        return status;
    if (auto status = kernel.posix().set_credentials(user::root_credentials()); !status.ok())
        return status;
    return kernel.posix().unlink("/tmp/notes-user.txt");
}

Status test_close_debug_gui_restores_system_desktop(Kernel &kernel)
{
    auto *desktop = static_cast<SystemGuiRuntime *>(kernel.extension())->loaded_gui_desktop_module();
    if (desktop == nullptr || desktop->dashboard_surface() == 0)
    {
        return Status::fault("system desktop module was not available for debug cleanup");
    }
    if (auto status = kernel.gui().compositor().destroy_surface(desktop->dashboard_surface()); !status.ok())
    {
        return status;
    }
    if (auto status = kernel.debug_shell().show_gui(); !status.ok())
    {
        return status;
    }
    if (auto status = kernel.close_debug_gui(); !status.ok())
    {
        return status;
    }

    auto info = find_surface_by_title(kernel, "ObfuscationOS Desktop");
    if (!info || kernel.debug_shell().gui_open())
    {
        return Status::fault("debug GUI cleanup did not restore the system desktop");
    }
    return Status::success();
}

} // namespace

Status run_system_gui_integration_tests(Kernel &kernel)
{
    if (auto status = test_system_gui_module_loads_after_boot(kernel); !status.ok())
        return status;
    if (auto status = test_start_preserves_active_greeter(kernel); !status.ok())
        return status;
    if (auto status = test_system_gui_mouse_login_selects_user_and_starts_desktop_shell(kernel); !status.ok())
        return status;
    if (auto status = test_start_preserves_logged_in_session(kernel); !status.ok())
        return status;
    if (auto status = test_system_gui_dock_uses_system_app_launchers(kernel); !status.ok())
        return status;
    if (auto status = test_system_gui_apps_are_user_elf_processes(kernel); !status.ok())
        return status;
    if (auto status = test_system_gui_notes_save_and_files_navigation(kernel); !status.ok())
        return status;
    if (auto status = test_close_debug_gui_restores_system_desktop(kernel); !status.ok())
        return status;
    return Status::success();
}
} // namespace obfuscationos::modules

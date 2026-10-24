#include "system_gui_runtime.hpp"
#include "ok/core/entry.hpp"
#include "ok/net/native_udp_sdk_profile.hpp"
#include "ok/net/native_tcp_sdk_profile.hpp"
#include "ok/user/native_futex_wake_operation_sdk_profile.hpp"
#include "ok/sched/process.hpp"
#include "drivers/virtio/net.hpp"
#include "drivers/virtio/rng.hpp"

extern "C" void ok_platform_console_write_char(char value) __attribute__((weak));

namespace obfuscationos::modules
{
static_assert(net::NativeUdpSdkExtension<SystemGuiRuntime>);
namespace
{
#if defined(OK_ENABLE_TEST_POINTS)
void gui_test_trace(Kernel &kernel, std::string_view value)
{
    static_cast<void>(kernel.console().write(value));
    if (ok_platform_console_write_char != nullptr)
        for (char ch : value) ok_platform_console_write_char(ch);
}
#endif
bool starts_with(std::string_view value, std::string_view prefix)
{
    return value.size() >= prefix.size() && value.substr(0, prefix.size()) == prefix;
}
struct BootGuiModulePackage
{
    std::string_view path;
    std::string_view text;
};

constexpr std::string_view fallback_system_gui_okmod{"OKMOD\n"
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

constexpr BootGuiModulePackage boot_gui_module_fallbacks[] = {
    {"/boot/modules/system-gui.okmod", fallback_system_gui_okmod},
};

struct SystemGuiAppDefinition
{
    ExternalGuiDockApp app{ExternalGuiDockApp::none};
    std::string_view id{};
    std::string_view path{};
    std::string_view process_name{};
    std::string_view title{};
    std::string_view subtitle{};
    std::string_view body{};
    std::string_view command{};
    std::string_view line1{};
    std::string_view line2{};
    std::string_view line3{};
    gui::Rect bounds{};
    std::string_view accent{};
};

constexpr SystemGuiAppDefinition system_gui_apps[] = {
    {.app = ExternalGuiDockApp::shell,
     .id = "shell",
     .path = "/bin/oksh",
     .process_name = "app:oksh",
     .title = "Tiny Shell",
     .subtitle = "tiny-c shell ELF",
     .body = "Standalone user app",
     .command = "/bin/oksh",
     .line1 = "help ls cat stat pwd cd",
     .line2 = "whoami uname uptime touch",
     .line3 = "runs as the selected user",
     .bounds = gui::Rect{.x = 64, .y = 38, .width = 352, .height = 176},
     .accent = "blue"},
    {.app = ExternalGuiDockApp::settings,
     .id = "settings",
     .path = "/bin/settings",
     .process_name = "app:settings",
     .title = "System Settings",
     .subtitle = "settings ELF",
     .body = "Display, input, session",
     .command = "/bin/settings",
     .line1 = "palette mint / blue / rose",
     .line2 = "pointer and keyboard enabled",
     .line3 = "user session controls",
     .bounds = gui::Rect{.x = 80, .y = 40, .width = 344, .height = 174},
     .accent = "blue"},
    {.app = ExternalGuiDockApp::tasks,
     .id = "tasks",
     .path = "/bin/tasks",
     .process_name = "app:tasks",
     .title = "Task Manager",
     .subtitle = "task manager ELF",
     .body = "Live scheduler snapshot",
     .command = "/bin/tasks",
     .line3 = "kernel tools stay outside System dock",
     .bounds = gui::Rect{.x = 64, .y = 38, .width = 360, .height = 176},
     .accent = "blue"},
    {.app = ExternalGuiDockApp::notes,
     .id = "notes",
     .path = "/bin/notes",
     .process_name = "app:notes",
     .title = "Notes",
     .subtitle = "notes ELF",
     .body = "Small user scratchpad",
     .command = "/bin/notes",
     .line1 = "notes are owned by userland",
     .line2 = "CLI tools use libokcrt",
     .bounds = gui::Rect{.x = 76, .y = 42, .width = 352, .height = 174},
     .accent = "blue"},
    {.app = ExternalGuiDockApp::about,
     .id = "about",
     .path = "/bin/about",
     .process_name = "app:about",
     .title = "About ObfuscationOS",
     .subtitle = "about ELF",
     .body = "ObfuscationOS user desktop",
     .command = "/bin/about",
     .line1 = "standalone tiny-c app",
     .line2 = "launched from /bin",
     .bounds = gui::Rect{.x = 86, .y = 40, .width = 344, .height = 176},
     .accent = "blue"},
    {.app = ExternalGuiDockApp::files,
     .id = "files",
     .path = "/bin/ls",
     .process_name = "app:files",
     .title = "Files",
     .subtitle = "Browse your files",
     .bounds = gui::Rect{.x = 48, .y = 38, .width = 384, .height = 176},
     .accent = "blue"},
};

Result<SystemGuiAppDefinition> system_gui_app_definition(ExternalGuiDockApp app)
{
    for (const auto &definition : system_gui_apps)
    {
        if (definition.app == app)
        {
            return definition;
        }
    }
    return Status::not_found("system GUI app definition not found");
}

Result<fs::FileBuffer> boot_gui_module_fallback(std::string_view path)
{
    for (const auto &package : boot_gui_module_fallbacks)
    {
        if (package.path != path)
        {
            continue;
        }
        if (package.text.size() > fs::max_file_data)
        {
            return Status::overflow("boot GUI module fallback exceeds file buffer");
        }
        fs::FileBuffer file{};
        for (usize i = 0; i < package.text.size(); ++i)
        {
            file.data[i] = static_cast<std::byte>(package.text[i]);
        }
        file.size = package.text.size();
        return file;
    }
    return Status::not_found("boot GUI module fallback not found");
}

Result<FixedString<fs::simplefs_name_capacity>> simplefs_flat_rootfs_path(std::string_view path)
{
    if (path.empty())
    {
        return Status::invalid_argument("rootfs path is empty");
    }
    if (path.front() == '/')
    {
        path.remove_prefix(1);
    }
    FixedString<fs::simplefs_name_capacity> out;
    constexpr std::string_view bin_prefix{"bin/"};
    constexpr std::string_view etc_prefix{"etc/"};
    constexpr std::string_view apps_prefix{"boot/modules/apps/"};
    constexpr std::string_view modules_prefix{"boot/modules/"};
    if (starts_with(path, bin_prefix))
    {
        if (auto status = out.assign(path.substr(bin_prefix.size())); !status.ok())
        {
            return status;
        }
        return out;
    }
    if (starts_with(path, etc_prefix))
    {
        if (auto status = out.assign(path.substr(etc_prefix.size())); !status.ok())
        {
            return status;
        }
        return out;
    }
    if (starts_with(path, apps_prefix))
    {
        if (auto status = out.append("apps_"); !status.ok())
        {
            return status;
        }
        if (auto status = out.append(path.substr(apps_prefix.size())); !status.ok())
        {
            return status;
        }
        return out;
    }
    if (starts_with(path, modules_prefix))
    {
        if (auto status = out.assign(path.substr(modules_prefix.size())); !status.ok())
        {
            return status;
        }
        return out;
    }
    for (const auto value : path)
    {
        if (auto status = out.append(value == '/' ? '_' : value); !status.ok())
        {
            return status;
        }
    }
    return out;
}

bool point_hits_window_close(const gui::SurfaceInfo &surface, i32 x, i32 y)
{
    if (surface.chrome != gui::SurfaceChrome::decorated || surface.bounds.width < 34)
    {
        return false;
    }
    const auto local_x = x - surface.bounds.x;
    const auto local_y = y - surface.bounds.y;
    if (local_x < 0 || local_y < 3 || local_y > 8)
    {
        return false;
    }
    const auto right = static_cast<i32>(surface.bounds.width) - local_x;
    return right >= 8 && right <= 13;
}

} // namespace

Result<net::NativeUdpLink> SystemGuiRuntime::network_link(Kernel &)
{
    if (shutdown_started_) return Status::busy("distribution shutdown closed ordinary admission");
    auto &device = os::drivers::virtio_net_device();
    if (!network_started_)
    {
        if (auto status = device.start(); !status) return status;
        network_started_ = true;
    }
#if defined(OK_PRIVATE_NATIVE_TCP_SLIRP_FIXTURE)
    return net::NativeUdpLink{device.mac(), {0x52, 0x55, 0x0a, 0, 2, 2},
                              {10, 0, 2, 15}, {10, 0, 2, 2}};
#else
    return net::NativeUdpLink{device.mac(), {2, 0xaa, 0xbb, 0xcc, 0xdd, 0xee},
                              {192, 0, 2, 2}, {192, 0, 2, 1}};
#endif
}

Result<usize> SystemGuiRuntime::network_receive(Kernel &, std::span<std::byte> frame)
{
    if (shutdown_started_) return Status::busy("distribution shutdown closed ordinary admission");
    if (!network_started_) return Status::not_initialized("native UDP link is inactive");
    return os::drivers::virtio_net_device().receive(frame);
}

Status SystemGuiRuntime::network_transmit(Kernel &, std::span<const std::byte> frame)
{
    if (shutdown_started_) return Status::busy("distribution shutdown closed ordinary admission");
    if (!network_started_) return Status::not_initialized("native UDP link is inactive");
    return os::drivers::virtio_net_device().transmit(frame);
}

Status SystemGuiRuntime::network_try_transmit(Kernel &, std::span<const std::byte> frame)
{
    if (shutdown_started_) return Status::busy("distribution shutdown closed ordinary admission");
    if (!network_started_) return Status::not_initialized("native UDP link is inactive");
    return os::drivers::virtio_net_device().try_transmit(frame);
}

Result<net::NativeUdpTransmitState> SystemGuiRuntime::network_poll_transmit(Kernel &, usize budget)
{
    if (shutdown_started_) return Status::busy("distribution shutdown closed ordinary admission");
    if (!network_started_) return Status::not_initialized("native UDP link is inactive");
    auto &device = os::drivers::virtio_net_device();
    auto completed = device.poll_transmit(budget);
    if (!completed) return completed.status();
    return net::NativeUdpTransmitState{completed.value(), device.transmit_credit()};
}

Status SystemGuiRuntime::bind_session_context()
{
    auto credentials = kernel_->user_space().credentials_for(external_gui_desktop_module_.selected_login_user_name());
    if (!credentials)
        return credentials.status();
    // The prelinked GUI executes as a kernel service. Do not rewrite whichever
    // modeled process happened to be selected by the scheduler's last tick.
    if (auto status = kernel_->posix().activate(0); !status.ok())
        return status;
    return kernel_->posix().set_credentials(credentials.value());
}

Status SystemGuiRuntime::shutdown_preflight(Kernel &kernel)
{
    if (shutdown_started_)
        return shutdown_failure_ ? Status::busy("distribution shutdown already consumed its producers") : shutdown_failure_;
    if (kernel_ != &kernel || network_started_)
        return Status::unsupported("distribution shutdown has an unknown kernel or active unqualified network owner");
    if (auto status = os::drivers::virtio_net_device().shutdown_preflight_unused(); !status) return status;
    if (kernel.gui().desktop().shared_buffer_count())
        return Status::unsupported("distribution shutdown has an undeclared GUI shared-buffer owner");
    if (auto status = os::drivers::preflight_virtio_rng_shutdown(kernel.posix().entropy_source()); !status) return status;
    std::array<gui::SurfaceId, max_external_gui_apps + 1> surfaces{};
    usize surface_count{};
    auto observe_surface = [&](gui::SurfaceId surface) -> Status {
        if (!surface) return {};
        for (usize index = 0; index < surface_count; ++index)
            if (surfaces[index] == surface) return Status::unsupported("distribution shutdown has aliased window owners");
        if (!kernel.gui().compositor().surface_info(surface))
            return Status::unsupported("distribution shutdown has an unavailable window owner");
        surfaces[surface_count++] = surface; return {};
    };
    if (external_gui_desktop_module_.configured())
    {
        if (kernel.kernel_modules().find(external_gui_desktop_module_.module_name()) != &external_gui_desktop_module_)
            return Status::unsupported("distribution shutdown desktop is not the registered original module");
        if (auto status = external_gui_desktop_module_.shutdown_preflight(); !status) return status;
        if (auto status = observe_surface(external_gui_desktop_module_.dashboard_surface()); !status) return status;
    }
    for (const auto &app : external_gui_app_modules_)
    {
        // This slice admits the original desktop with every application
        // already closed. Model process records do not prove native retirement.
        if (app.configured())
            return Status::unsupported("shutdown requires all application windows closed before prepare");
        if (auto status = app.shutdown_preflight(); !status) return status;
    }
    if (surface_count != kernel.gui().compositor().surface_count())
        return Status::unsupported("distribution shutdown has an undeclared window owner");
    return {};
}

Status SystemGuiRuntime::shutdown_stop_producers(Kernel &kernel)
{
    if (shutdown_started_)
        return !shutdown_failure_ ? shutdown_failure_ : shutdown_stopped_ ? Status{} :
            Status::busy("distribution shutdown callback is active");
    if (auto status = shutdown_preflight(kernel); !status) return status;
    shutdown_started_ = true;
    auto fail = [&](Status status) { shutdown_failure_ = status; return status; };
    // Application owners were refused before PREPARE. The coordinator has
    // closed ordinary admission; ModuleManager alone stops the desktop once.
    const auto *source = kernel.posix().entropy_source();
    kernel.posix().set_entropy_source(nullptr);
    if (auto status = os::drivers::stop_virtio_rng_shutdown(source); !status) return fail(status);
    shutdown_stopped_ = true;
    return {};
}

Status SystemGuiRuntime::start_selected_system_gui_session(ExternalGuiDesktopModule &desktop)
{
    static_cast<void>(desktop);
    if (auto status = bind_session_context(); !status.ok())
        return status;
    return launch_system_gui_app_session();
}

Status SystemGuiRuntime::handle_system_gui_dock_launcher(ExternalGuiDockApp app)
{
    return app == ExternalGuiDockApp::none ? Status::success() : focus_system_gui_app(app);
}

Status SystemGuiRuntime::focus_system_gui_app(ExternalGuiDockApp app)
{
    auto definition = system_gui_app_definition(app);
    if (!definition)
    {
        return definition.status();
    }
    for (auto &instance : external_gui_app_modules_)
    {
        if (!instance.configured() || instance.app_id() != definition.value().id)
        {
            continue;
        }
        if (instance.process_id() == 0 || kernel_->scheduler().find(instance.process_id()) == nullptr)
        {
            instance.reset();
            break;
        }
        if (auto status = bind_session_context(); !status.ok())
            return status;
        if (auto status = instance.refresh(); !status.ok())
        {
            return status;
        }
        auto info = kernel_->gui().compositor().surface_info(instance.surface());
        if (!info)
        {
            return info.status();
        }
        if (info.value().window_state == gui::WindowState::minimized)
            if (auto status = kernel_->gui().compositor().restore_surface(instance.surface()); !status.ok())
                return status;
        if (auto status = kernel_->gui().compositor().set_visible(instance.surface(), true); !status.ok())
            return status;
        if (auto status = kernel_->gui().compositor().raise_surface(instance.surface()); !status.ok())
        {
            return status;
        }
        return kernel_->gui().compositor().present();
    }
    return launch_system_gui_app(app);
}

Status SystemGuiRuntime::route_notes_request(ExternalGuiAppModule &files)
{
    if (!files.has_notes_request()) return Status::success();
    const auto request = files.notes_request();
    auto find_notes = [&]() -> ExternalGuiAppModule * {
        for (auto &instance : external_gui_app_modules_)
            if (instance.configured() && instance.app_id() == "notes" && instance.process_id() != 0 &&
                kernel_->scheduler().find(instance.process_id())) return &instance;
        return nullptr;
    };
    auto *notes = find_notes();
    Status accepted{};
    if (!notes)
    {
        accepted = focus_system_gui_app(ExternalGuiDockApp::notes);
        if (accepted) notes = find_notes();
    }
    if (accepted && !notes) accepted = Status::not_found("Default Notes is unavailable");
    if (accepted) accepted = surface_action(*kernel_, notes->surface(), ExtensionSurfaceAction::focus);
    if (accepted) accepted = notes->open_notes_target(request);
    // Policy refusals are visible in Files and retain the previous Notes text.
    if (!accepted)
    {
#if defined(OK_ENABLE_TEST_POINTS)
        gui_test_trace(*kernel_, "OK_SYSTEM_GUI_HANDOFF_REFUSED reason=");
        gui_test_trace(*kernel_, accepted.message());
        gui_test_trace(*kernel_, "\n");
#endif
        if (auto status = kernel_->gui().compositor().raise_surface(files.surface()); !status) return status;
    }
    // A successful Notes transaction is the final render/present gate. Files
    // renders its acknowledgement on its next refresh, without another failure
    // after replacing the previous document.
    return files.finish_notes_request(accepted, !accepted.ok());
}

Result<usize> SystemGuiRuntime::read_user_program_file(std::string_view path)
{
    auto file = kernel_->vfs().read_file(path);
    if (file)
    {
        if (file.value().size > user_program_image_.size())
        {
            return Status::overflow("user program image exceeds loader buffer");
        }
        for (usize i = 0; i < file.value().size; ++i)
        {
            user_program_image_[i] = file.value().data[i];
        }
        return file.value().size;
    }
    if (file.status().code() != StatusCode::not_found)
    {
        return file.status();
    }
    if (!kernel_->simplefs().mounted())
    {
        return file.status();
    }
    auto flat_path = simplefs_flat_rootfs_path(path);
    if (!flat_path)
    {
        return flat_path.status();
    }
    return kernel_->simplefs().read_file_into(
        flat_path.value().view(), std::span<std::byte>{user_program_image_.data(), user_program_image_.size()});
}

Status SystemGuiRuntime::load_external_gui_desktop_module(std::string_view path, const ModuleImageInfo &image)
{
    // Validate even repeated requests without modifying the running session.
    ExternalGuiDesktopModule candidate;
    if (auto status = candidate.configure_from_image(path, image); !status.ok())
    {
        return status;
    }
    if (external_gui_desktop_module_.configured() &&
        external_gui_desktop_module_.desktop_state() != ExternalGuiDesktopState::stopped)
    {
        return Status::success();
    }
    external_gui_desktop_module_.bind_metrics(kernel_->scheduler(), kernel_->topology());
    if (auto status = external_gui_desktop_module_.configure_from_image(path, image); !status.ok())
    {
        return status;
    }
    auto *module = kernel_->kernel_modules().find(external_gui_desktop_module_.module_name());
    if (module == nullptr)
    {
        if (auto status = kernel_->kernel_modules().register_module(external_gui_desktop_module_); !status.ok())
        {
            return status;
        }
    }
    else
    {
        return kernel_->kernel_modules().restart_module(external_gui_desktop_module_.module_name());
    }
    return kernel_->kernel_modules().start_registered_module(external_gui_desktop_module_.module_name());
}

Status SystemGuiRuntime::launch_system_gui_app(ExternalGuiDockApp app)
{
    if (external_gui_desktop_module_.configured() &&
        external_gui_desktop_module_.desktop_state() == ExternalGuiDesktopState::greeter)
    {
        return Status::would_block("system GUI apps are blocked until login");
    }
    auto definition = system_gui_app_definition(app);
    if (!definition)
    {
        return definition.status();
    }
    auto program_size = read_user_program_file(definition.value().path);
    if (!program_size)
    {
        return program_size.status();
    }
    sched::ElfLoader loader;
    auto loaded = loader.load(std::span<const std::byte>{user_program_image_.data(), program_size.value()},
                              arch_ptr_->architecture());
    if (!loaded)
    {
        return loaded.status();
    }

    ExternalGuiAppModule *slot = nullptr;
    for (auto &instance : external_gui_app_modules_)
    {
        if (!instance.configured())
        {
            slot = &instance;
            break;
        }
    }
    if (slot == nullptr)
    {
        return Status::overflow("system GUI app table is full");
    }

    if (auto status = bind_session_context(); !status.ok())
        return status;
    const auto credentials = kernel_->posix().user_credentials();
    auto process = kernel_->create_ui_process(definition.value().process_name, loaded.value().entry,
                                              loaded.value().stack_pointer, credentials);
    if (!process)
    {
        return process.status();
    }

    slot->bind_metrics(kernel_->scheduler(), kernel_->topology());
    slot->bind_environment(kernel_->vfs(), kernel_->posix());
    if (auto status = slot->configure_from_elf(
            definition.value().id, definition.value().path, definition.value().title, definition.value().subtitle,
            definition.value().body, definition.value().command, definition.value().line1, definition.value().line2,
            definition.value().line3, definition.value().bounds, definition.value().accent, process.value());
        !status.ok())
    {
        static_cast<void>(kernel_->scheduler().kill_process(process.value()));
        slot->reset();
        return status;
    }
    slot->set_accent(session_accent_);
    if (auto status = slot->start(kernel_->gui().compositor(), kernel_->gui().desktop()); !status.ok())
    {
        static_cast<void>(kernel_->scheduler().kill_process(process.value()));
        slot->reset();
        return status;
    }
    return Status::success();
}

Status SystemGuiRuntime::launch_system_gui_app_session()
{
    for (const auto &definition : system_gui_apps)
    {
        if (auto status = focus_system_gui_app(definition.app); !status.ok() && status.code() != StatusCode::not_found)
        {
            return status;
        }
    }
    // Keep the existing app records, with a quiet workspace until a launcher is selected.
    for (auto &app : external_gui_app_modules_)
        if (app.configured() && app.surface() != 0)
            if (auto status = kernel_->gui().compositor().set_visible(app.surface(), false); !status.ok())
                return status;
    // The greeter-to-desktop resize has already been redrawn synchronously.
    static_cast<void>(kernel_->gui().compositor().consume_window_event());
    return refresh_external_gui_modules(false);
}

Result<usize> SystemGuiRuntime::find_system_gui_app_by_surface(gui::SurfaceId surface) const
{
    for (usize i = 0; i < external_gui_app_modules_.size(); ++i)
    {
        if (external_gui_app_modules_[i].configured() && external_gui_app_modules_[i].surface() == surface)
        {
            return i;
        }
    }
    return Status::not_found("system GUI app surface not found");
}

Result<usize> SystemGuiRuntime::find_system_gui_app_by_process(sched::ProcessId pid) const
{
    for (usize i = 0; i < external_gui_app_modules_.size(); ++i)
    {
        if (external_gui_app_modules_[i].configured() && external_gui_app_modules_[i].process_id() == pid)
        {
            return i;
        }
    }
    return Status::not_found("system GUI app process not found");
}

Status SystemGuiRuntime::close_system_gui_app_at(usize index, bool kill_process)
{
    if (index >= external_gui_app_modules_.size() || !external_gui_app_modules_[index].configured())
    {
        return Status::invalid_argument("system GUI app index out of range");
    }
    auto &app = external_gui_app_modules_[index];
    const auto process = app.process_id();
    const auto surface = app.surface();
    if (surface != 0)
    {
        // Kernel owns generic window-close bookkeeping.
    }
    if (auto status = app.stop(); !status.ok() && status.code() != StatusCode::not_found)
    {
        app.reset();
        return status;
    }
    if (kill_process && process != 0 && kernel_->scheduler().find(process) != nullptr)
    {
        static_cast<void>(kernel_->scheduler().kill_process(process));
    }
    if (process != 0)
    {
        kernel_->debug_shell().notify_process_exit(process);
    }
    app.reset();
    return kernel_->gui().compositor().present();
}

Status SystemGuiRuntime::refresh_external_gui_modules(bool focus_desktop)
{
    auto &compositor = kernel_->gui().compositor();
    if (compositor.state() != gui::GuiState::running)
    {
        return Status::success();
    }
    auto *desktop = loaded_gui_desktop_module();
    if (desktop != nullptr && (desktop->desktop_state() == ExternalGuiDesktopState::greeter ||
                               desktop->desktop_state() == ExternalGuiDesktopState::desktop))
    {
        if (auto status = desktop->refresh(); !status.ok())
        {
            return status;
        }
        if (focus_desktop && desktop->desktop_state() == ExternalGuiDesktopState::greeter &&
            desktop->dashboard_surface() != 0)
        {
            if (auto info = compositor.surface_info(desktop->dashboard_surface()))
            {
                if (info.value().window_state == gui::WindowState::minimized)
                {
                    if (auto status = compositor.restore_surface(desktop->dashboard_surface()); !status.ok())
                    {
                        return status;
                    }
                }
                if (auto status = compositor.raise_surface(desktop->dashboard_surface()); !status.ok())
                {
                    return status;
                }
            }
        }
    }
    for (auto &app : external_gui_app_modules_)
    {
        if (app.configured() && app.app_state() == ExternalGuiAppState::running)
        {
            if (auto status = app.refresh(); !status.ok())
            {
                return status;
            }
        }
    }
    return compositor.present();
}

Status SystemGuiRuntime::self_test(Kernel &kernel)
{
#if defined(OK_ENABLE_TEST_POINTS)
    self_test_passed_ = false;
    kernel_ = &kernel;
    arch_ptr_ = &kernel.arch();
    if (auto status = kernel.close_debug_gui(); !status.ok())
        return status;
    if (auto status = run_system_gui_integration_tests(kernel); !status.ok())
        return status;
    for (usize i = 0; i < external_gui_app_modules_.size(); ++i)
        if (external_gui_app_modules_[i].configured())
            if (auto status = close_system_gui_app_at(i, true); !status.ok())
                return status;
    if (auto status = external_gui_desktop_module_.stop(); !status.ok())
        return status;
    if (auto status = kernel.posix().set_credentials(user::root_credentials()); !status.ok())
        return status;
    self_test_passed_ = true;
    return Status::success();
#else
    static_cast<void>(kernel);
    return Status::success();
#endif
}

Status SystemGuiRuntime::start(Kernel &kernel)
{
    if (shutdown_started_) return Status::busy("distribution shutdown closed ordinary admission");
    kernel_ = &kernel;
    arch_ptr_ = &kernel.arch();
    if (!external_gui_desktop_module_.configured())
    {
        if (auto status = kernel.load_external_kernel_module("/boot/modules/system-gui.okmod"); !status.ok())
            return status;
    }
    else if (external_gui_desktop_module_.desktop_state() == ExternalGuiDesktopState::stopped)
    {
        // self_test leaves the registered desktop stopped. An already active
        // greeter/session must retain its selected user, surfaces and app PIDs.
        if (auto status = kernel.kernel_modules().restart_module(external_gui_desktop_module_.module_name());
            !status.ok())
            return status;
    }
    if (auto status = kernel.close_debug_gui(); !status.ok())
        return status;
    // Synchronous startup cleanup must not consume the user's first pointer event.
    static_cast<void>(kernel.gui().compositor().consume_window_event());

#if defined(OK_ENABLE_TEST_POINTS)
    // Tests exercise start() themselves. Only the post-test boot start may
    // announce success, after every test and its cleanup has succeeded.
    if (!self_test_passed_)
        return Status::success();
#endif
    if (!boot_announced_)
    {
        constexpr std::string_view marker{"OK_SYSTEM_GUI boot=complete\n"};
        static_cast<void>(kernel.console().write(marker));
        if (ok_platform_console_write_char != nullptr)
        {
            for (const char value : marker)
                ok_platform_console_write_char(value);
        }
        boot_announced_ = true;
    }
    return Status::success();
}

Result<fs::FileBuffer> SystemGuiRuntime::read_package(Kernel &kernel, std::string_view path)
{
    if (kernel.simplefs().mounted())
    {
        auto flat = simplefs_flat_rootfs_path(path);
        if (flat)
        {
            auto file = kernel.simplefs().read_file(flat.value().view());
            if (file || file.status().code() != StatusCode::not_found)
                return file;
        }
    }
    return boot_gui_module_fallback(path);
}

Status SystemGuiRuntime::load_package(Kernel &kernel, std::string_view path, const ModuleImageInfo &image)
{
    if (shutdown_started_) return Status::busy("distribution shutdown closed ordinary admission");
    kernel_ = &kernel;
    arch_ptr_ = &kernel.arch();
    if (image.name.view() != "system-gui")
        return Status::unsupported("unknown prelinked OS package");
    return load_external_gui_desktop_module(path, image);
}

Result<bool> SystemGuiRuntime::pointer_click(Kernel &kernel, i32 x, i32 y)
{
    if (shutdown_started_) return Status::busy("distribution shutdown closed ordinary admission");
    kernel_ = &kernel;
    auto *desktop = loaded_gui_desktop_module();
    if (desktop == nullptr)
        return false;
    if (desktop->desktop_state() == ExternalGuiDesktopState::greeter)
    {
        if (auto status = desktop->handle_pointer_click(x, y); !status.ok())
            return status;
        if (desktop->desktop_state() == ExternalGuiDesktopState::desktop)
            if (auto status = start_selected_system_gui_session(*desktop); !status.ok())
                return status;
        return true;
    }
    auto &compositor = kernel.gui().compositor();
    auto hit = compositor.surface_at(x, y);
    auto surface = hit ? hit.value() : compositor.active_surface();
    auto info = compositor.surface_info(surface);
    if (info && point_hits_window_close(info.value(), x, y))
        if (auto app = find_system_gui_app_by_surface(surface))
        {
            if (auto status = close_system_gui_app_at(app.value(), true); !status.ok())
                return status;
            return true;
        }
    if (desktop->desktop_state() == ExternalGuiDesktopState::desktop)
    {
        auto app = desktop->dock_launcher_at(x, y);
        if (!app && app.status().code() != StatusCode::not_found)
            return app.status();
        if (app && app.value() != ExternalGuiDockApp::none)
        {
            if (auto status = handle_system_gui_dock_launcher(app.value()); !status.ok())
                return status;
            return true;
        }
    }
    if (info && y - info.value().bounds.y >= 18)
        if (auto app = find_system_gui_app_by_surface(surface))
        {
            if (auto status = surface_action(kernel, surface, ExtensionSurfaceAction::focus); !status.ok())
                return status;
            if (auto status = compositor.raise_surface(surface); !status.ok())
                return status;
            auto &instance = external_gui_app_modules_[app.value()];
            const auto before = instance.accent();
            if (auto status = instance.handle_pointer(x - info.value().bounds.x, y - info.value().bounds.y);
                !status.ok())
                return status;
            if (instance.accent() != before)
            {
                session_accent_ = instance.accent();
                for (auto &other : external_gui_app_modules_)
                    if (other.configured())
                    {
                        other.set_accent(session_accent_);
                        if (auto status = other.refresh(); !status.ok())
                            return status;
                    }
            }
            if (auto status = route_notes_request(instance); !status) return status;
            return true;
        }
    return false;
}

Result<bool> SystemGuiRuntime::key(Kernel &kernel, int value)
{
    if (shutdown_started_) return Status::busy("distribution shutdown closed ordinary admission");
    kernel_ = &kernel;
    auto *desktop = loaded_gui_desktop_module();
    if (desktop == nullptr)
        return false;
    if (desktop->desktop_state() == ExternalGuiDesktopState::greeter)
    {
        if (auto status = desktop->handle_key(value); !status.ok())
            return status;
        if (desktop->desktop_state() == ExternalGuiDesktopState::desktop)
            if (auto status = start_selected_system_gui_session(*desktop); !status.ok())
                return status;
        return true;
    }
    if (value == ok_input_open_shell || value == ok_input_open_file_manager)
        return false;
    const auto surface = kernel.gui().compositor().active_surface();
    auto app = find_system_gui_app_by_surface(surface);
    if (!app)
        return false;
    if (auto status = surface_action(kernel, surface, ExtensionSurfaceAction::focus); !status.ok())
        return status;
    if (auto status = external_gui_app_modules_[app.value()].handle_key(value); !status.ok())
        return status;
#if defined(OK_ENABLE_TEST_POINTS)
    if (external_gui_app_modules_[app.value()].app_id() == "files" && (value == '\n' || value == '\r'))
    {
        gui_test_trace(kernel, "OK_SYSTEM_GUI_FILES_ENTER status=");
        gui_test_trace(kernel, external_gui_app_modules_[app.value()].app_status());
        gui_test_trace(kernel, "\n");
    }
#endif
    if (auto status = route_notes_request(external_gui_app_modules_[app.value()]); !status) return status;
    return true;
}

Status SystemGuiRuntime::surface_action(Kernel &kernel, gui::SurfaceId surface, ExtensionSurfaceAction action)
{
    if (shutdown_started_) return Status::busy("distribution shutdown closed ordinary admission");
    kernel_ = &kernel;
    auto app = find_system_gui_app_by_surface(surface);
    if (!app)
        return app.status();
    if (action == ExtensionSurfaceAction::close)
        return close_system_gui_app_at(app.value(), true);
    if (action == ExtensionSurfaceAction::refresh)
        return external_gui_app_modules_[app.value()].refresh();
    auto *pcb = kernel.scheduler().find(external_gui_app_modules_[app.value()].process_id());
    if (pcb == nullptr)
        return Status::success();
    const auto credentials = pcb->credentials();
    if (auto status = kernel.posix().activate(0); !status.ok())
        return status;
    return kernel.posix().set_credentials(credentials);
}

Status SystemGuiRuntime::process_exited(Kernel &kernel, sched::ProcessId pid)
{
    if (shutdown_started_) return {};
    kernel_ = &kernel;
    auto app = find_system_gui_app_by_process(pid);
    return app ? close_system_gui_app_at(app.value(), false) : Status::success();
}

Status SystemGuiRuntime::refresh(Kernel &kernel, bool focus)
{
    if (shutdown_started_) return Status::busy("distribution shutdown closed ordinary admission");
    kernel_ = &kernel;
    return refresh_external_gui_modules(focus);
}

KernelExtension *system_gui_extension()
{
    static SystemGuiRuntime runtime;
    return &runtime;
}
} // namespace obfuscationos::modules

// Optional distribution hook; kernel boot works without this symbol.
extern "C" ok::KernelExtension *ok_boot_extension()
{
    return obfuscationos::modules::system_gui_extension();
}

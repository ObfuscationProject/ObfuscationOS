#include "external_module.hpp"
#include "ok/gui/paint.hpp"

namespace ok
{
namespace
{

constexpr u32 dashboard_background = gui::theme::canvas;
constexpr u32 dashboard_panel = gui::theme::surface;
constexpr u32 dashboard_panel_alt = gui::theme::subtle;
constexpr u32 dashboard_accent = gui::theme::accent;
constexpr u32 dashboard_warm = gui::theme::accent;
constexpr u32 dashboard_text = gui::theme::text;
constexpr u32 dashboard_muted = gui::theme::muted;
constexpr u32 app_background = gui::theme::surface;
constexpr u32 app_panel = gui::theme::subtle;
constexpr u32 app_panel_alt = gui::theme::accent_soft;
constexpr u32 app_text = gui::theme::text;
constexpr u32 app_muted = gui::theme::muted;
constexpr u32 greeter_card_height = 178;
constexpr u32 greeter_card_max_width = 360;
constexpr u32 greeter_card_margin = 24;
constexpr u32 greeter_dropdown_height = 24;
constexpr u32 greeter_dropdown_option_height = 18;
constexpr u32 greeter_login_height = 26;
constexpr u32 system_dock_height = 44;
constexpr u32 system_dock_tile_width = 72;
constexpr u32 system_dock_tile_height = 30;
constexpr u32 system_dock_tile_gap = 4;
constexpr u32 system_dock_tile_left = 14;

template <usize Capacity> bool has_symbol(const StaticVector<ModuleSymbol, Capacity> &symbols, std::string_view name)
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

bool has_parameter(const ModuleImageInfo &image, std::string_view name, std::string_view value)
{
    for (const auto &parameter : image.parameters)
    {
        if (parameter.name.view() == name && parameter.value.view() == value)
        {
            return true;
        }
    }
    return false;
}

template <usize Capacity> Status append_decimal(FixedString<Capacity> &out, u64 value)
{
    constexpr u64 powers[] = {
        10'000'000'000'000'000'000ull,
        1'000'000'000'000'000'000ull,
        100'000'000'000'000'000ull,
        10'000'000'000'000'000ull,
        1'000'000'000'000'000ull,
        100'000'000'000'000ull,
        10'000'000'000'000ull,
        1'000'000'000'000ull,
        100'000'000'000ull,
        10'000'000'000ull,
        1'000'000'000ull,
        100'000'000ull,
        10'000'000ull,
        1'000'000ull,
        100'000ull,
        10'000ull,
        1'000ull,
        100ull,
        10ull,
        1ull,
    };
    bool started = false;
    for (const auto power : powers)
    {
        u8 digit = 0;
        while (value >= power)
        {
            value -= power;
            ++digit;
        }
        if (digit != 0 || started || power == 1)
        {
            if (auto status = out.append(static_cast<char>('0' + digit)); !status.ok())
            {
                return status;
            }
            started = true;
        }
    }
    return Status::success();
}

template <usize Capacity> Status assign_metric(FixedString<Capacity> &out, std::string_view label, u64 value)
{
    out.clear();
    if (auto status = out.append(label); !status.ok())
    {
        return status;
    }
    return append_decimal(out, value);
}

Result<u32> parse_decimal_u32(std::string_view value)
{
    if (value.empty())
    {
        return Status::invalid_argument("empty decimal parameter");
    }
    u32 out = 0;
    for (const auto ch : value)
    {
        if (ch < '0' || ch > '9')
        {
            return Status::invalid_argument("decimal parameter contains a non-digit");
        }
        const auto digit = static_cast<u32>(ch - '0');
        if (out > (0xffff'ffffu - digit) / 10u)
        {
            return Status::overflow("decimal parameter overflow");
        }
        out = out * 10u + digit;
    }
    return out;
}

std::string_view process_state_label(sched::ProcessState state)
{
    switch (state)
    {
    case sched::ProcessState::created:
        return "New";
    case sched::ProcessState::runnable:
        return "Ready";
    case sched::ProcessState::running:
        return "Running";
    case sched::ProcessState::blocked:
        return "Waiting";
    case sched::ProcessState::zombie:
        return "Zombie";
    case sched::ProcessState::exited:
        return "Exited";
    }
    return "Unknown";
}

Result<FixedString<96>> app_path(std::string_view directory, std::string_view name)
{
    FixedString<96> path;
    if (!name.empty() && name.front() == '/')
    {
        if (auto status = path.assign(name); !status.ok())
            return status;
        return path;
    }
    if (auto status = path.assign(directory); !status.ok())
        return status;
    if (name == "..")
    {
        auto parent = directory;
        const auto slash = parent.find_last_of('/');
        static_cast<void>(path.assign(slash == 0 ? std::string_view{"/"} : parent.substr(0, slash)));
        return path;
    }
    if (name.empty() || name == ".")
        return path;
    if (directory != "/")
        if (auto status = path.append('/'); !status.ok())
            return status;
    if (auto status = path.append(name); !status.ok())
        return status;
    return path;
}

u32 accent_for(std::string_view value)
{
    if (value == "rose")
    {
        return 0xffff7799u;
    }
    if (value == "blue")
    {
        return gui::theme::accent;
    }
    if (value == "mint")
    {
        return gui::theme::positive;
    }
    if (value == "violet")
    {
        return 0xff7665b2u;
    }
    return dashboard_warm;
}

[[nodiscard]] bool rect_contains(gui::Rect rect, i32 x, i32 y)
{
    return x >= rect.x && y >= rect.y && x < rect.x + static_cast<i32>(rect.width) &&
           y < rect.y + static_cast<i32>(rect.height);
}

[[nodiscard]] gui::Rect greeter_card_bounds(u32 width, u32 height)
{
    const auto card_width = width > greeter_card_max_width + greeter_card_margin
                                ? greeter_card_max_width
                                : (width > greeter_card_margin ? width - greeter_card_margin : width);
    const auto card_height =
        height > greeter_card_height + 8 ? greeter_card_height : (height > 8 ? height - 8 : height);
    return gui::Rect{.x = static_cast<i32>(width > card_width ? (width - card_width) / 2 : 0),
                     .y = static_cast<i32>(height > card_height ? (height - card_height) / 2 : 0),
                     .width = card_width,
                     .height = card_height};
}

[[nodiscard]] gui::Rect greeter_dropdown_bounds(gui::Rect card)
{
    return gui::Rect{.x = card.x + 96,
                     .y = card.y + 72,
                     .width = card.width > 120 ? card.width - 120 : card.width,
                     .height = greeter_dropdown_height};
}

[[nodiscard]] gui::Rect greeter_dropdown_option_bounds(gui::Rect card, usize index)
{
    const auto field = greeter_dropdown_bounds(card);
    return gui::Rect{.x = field.x,
                     .y = field.y + static_cast<i32>(field.height + index * greeter_dropdown_option_height),
                     .width = field.width,
                     .height = greeter_dropdown_option_height};
}

[[nodiscard]] gui::Rect greeter_dropdown_menu_bounds(gui::Rect card)
{
    const auto field = greeter_dropdown_bounds(card);
    return gui::Rect{.x = field.x,
                     .y = field.y + static_cast<i32>(field.height),
                     .width = field.width,
                     .height = greeter_dropdown_option_height * 2};
}

[[nodiscard]] gui::Rect greeter_login_bounds(gui::Rect card)
{
    return gui::Rect{.x = card.x + 24,
                     .y = card.y + 138,
                     .width = card.width > 48 ? card.width - 48 : card.width,
                     .height = greeter_login_height};
}

[[nodiscard]] gui::Rect system_dock_bounds(u32 width, u32 height)
{
    const auto dock_height = height > system_dock_height ? system_dock_height : height / 4;
    return gui::Rect{.x = 0,
                     .y = static_cast<i32>(height > dock_height ? height - dock_height : 0),
                     .width = width,
                     .height = dock_height};
}

[[nodiscard]] gui::Rect system_dock_tile_bounds(gui::Rect dock, usize index)
{
    const auto x =
        dock.x + static_cast<i32>(system_dock_tile_left + index * (system_dock_tile_width + system_dock_tile_gap));
    const auto y =
        dock.y +
        static_cast<i32>(dock.height > system_dock_tile_height ? (dock.height - system_dock_tile_height) / 2 : 0);
    return gui::Rect{.x = x, .y = y, .width = system_dock_tile_width, .height = system_dock_tile_height};
}

gui::Rect fit_bounds(gui::Rect bounds, gui::Rect desktop)
{
    if (bounds.width > desktop.width)
    {
        bounds.width = desktop.width;
        bounds.x = 0;
    }
    if (bounds.height + gui::taskbar_height > desktop.height)
    {
        bounds.height = desktop.height > gui::taskbar_height ? desktop.height - gui::taskbar_height : desktop.height;
        bounds.y = 0;
    }
    const auto work_height =
        desktop.height > gui::taskbar_height ? desktop.height - gui::taskbar_height : desktop.height;
    if (bounds.x < 0)
    {
        bounds.x = 0;
    }
    if (bounds.y < 0)
    {
        bounds.y = 0;
    }
    if (static_cast<u32>(bounds.x) + bounds.width > desktop.width)
    {
        bounds.x = desktop.width > bounds.width ? static_cast<i32>(desktop.width - bounds.width) : 0;
    }
    if (static_cast<u32>(bounds.y) + bounds.height > work_height)
    {
        bounds.y = work_height > bounds.height ? static_cast<i32>(work_height - bounds.height) : 0;
    }
    return bounds;
}

} // namespace

Status ExternalGuiDesktopModule::configure_from_image(std::string_view path, const ModuleImageInfo &image)
{
    if (image.format != ModuleImageFormat::okmod)
    {
        return Status::unsupported("external C++ OOP module must use OKMOD metadata");
    }
    if (!has_parameter(image, "entry", "oop") || !has_parameter(image, "class", "desktop"))
    {
        return Status::unsupported("external GUI module requires entry:oop and class:desktop");
    }
    if (!has_symbol(image.imports, gui::gui_service_id) || !has_symbol(image.imports, gui::gui_desktop_service_id) ||
        image.exports.empty())
    {
        return Status::invalid_argument("external GUI module metadata is incomplete");
    }
    if (image.name.empty())
    {
        return Status::invalid_argument("external GUI module name is empty");
    }

    if (auto status = name_.assign(image.name.view()); !status.ok())
    {
        return status;
    }
    if (auto status = version_.assign(image.version.empty() ? std::string_view{"1"} : image.version.view());
        !status.ok())
    {
        return status;
    }
    if (auto status = service_id_.assign(image.exports[0].name.view()); !status.ok())
    {
        return status;
    }
    if (auto status = load_path_.assign(path); !status.ok())
    {
        return status;
    }
    exported_services_[0] = service_id_.view();
    for (const auto &parameter : image.parameters)
    {
        if (auto status = assign_parameter(parameter.name.view(), parameter.value.view()); !status.ok())
        {
            return status;
        }
    }
    configured_ = true;
    desktop_state_ = ExternalGuiDesktopState::stopped;
    dashboard_surface_ = 0;
    render_count_ = 0;
    return Status::success();
}

Status ExternalGuiDesktopModule::assign_parameter(std::string_view name, std::string_view value)
{
    if (name == "brand")
    {
        return brand_.assign(value);
    }
    if (name == "title")
    {
        return title_.assign(value);
    }
    if (name == "subtitle")
    {
        return subtitle_.assign(value);
    }
    return Status::success();
}

ModuleManifest ExternalGuiDesktopModule::manifest() const
{
    return ModuleManifest{
        .name = name_.empty() ? std::string_view{"external-gui-desktop"} : name_.view(),
        .version = version_.empty() ? std::string_view{"1"} : version_.view(),
        .module_class = "desktop",
        .dependencies = dependencies_,
        .exported_services = exported_services_,
        .required_services = required_services_,
        .built_in = false,
        .execution = ModuleExecution::inline_core,
        .init_priority = 85,
        .threading = ModuleThreading::single_threaded,
        .capability_mask = module_capability_bit(ModuleCapability::exports_services) |
                           module_capability_bit(ModuleCapability::requires_services) |
                           module_capability_bit(ModuleCapability::handles_gui),
        .restart_policy = ModuleRestartPolicy::manual,
        .resources =
            ModuleResourceBudget{
                .max_threads = 1, .max_services = exported_services_.size(), .max_memory_pages = 1, .max_handles = 2},
    };
}

void *ExternalGuiDesktopModule::service(std::string_view service_id)
{
    return service_id == service_id_.view() ? this : nullptr;
}

Status ExternalGuiDesktopModule::start(ServiceRegistry &services)
{
    if (!configured_)
    {
        return Status::not_initialized("external GUI desktop module is not configured");
    }
    compositor_ = services.query<gui::GuiCompositor>(gui::gui_service_id);
    desktop_ = services.query<gui::GuiDesktopService>(gui::gui_desktop_service_id);
    if (compositor_ == nullptr || desktop_ == nullptr)
    {
        return Status::not_initialized("external GUI desktop module requires GUI services");
    }
    if (scheduler_ == nullptr || topology_ == nullptr)
    {
        return Status::not_initialized("external GUI desktop metrics are not bound");
    }
    selected_login_user_ = ExternalGuiLoginUser::root;
    login_dropdown_open_ = false;
    desktop_state_ = ExternalGuiDesktopState::greeter;
    if (auto status = open_shell_surface(title_.view(), gui::GuiShellMode::system_greeter); !status.ok())
    {
        return status;
    }
    return render_greeter();
}

Status ExternalGuiDesktopModule::stop()
{
    if (compositor_ != nullptr && compositor_->state() == gui::GuiState::running)
    {
        static_cast<void>(compositor_->set_shell_mode(gui::GuiShellMode::kernel_shell));
    }
    if (desktop_ != nullptr && dashboard_surface_ != 0)
    {
        auto status = desktop_->close_window(dashboard_surface_);
        if (!status.ok() && status.code() != StatusCode::not_found)
        {
            return status;
        }
    }
    dashboard_surface_ = 0;
    desktop_state_ = configured_ ? ExternalGuiDesktopState::stopped : ExternalGuiDesktopState::unloaded;
    compositor_ = nullptr;
    desktop_ = nullptr;
    return Status::success();
}

Status ExternalGuiDesktopModule::shutdown()
{
    return stop();
}

Status ExternalGuiDesktopModule::refresh()
{
    if (desktop_state_ != ExternalGuiDesktopState::greeter && desktop_state_ != ExternalGuiDesktopState::desktop)
    {
        return Status::not_initialized("external GUI desktop is not running");
    }
    if (dashboard_surface_ == 0)
    {
        return open_shell_surface(desktop_state_ == ExternalGuiDesktopState::greeter
                                      ? title_.view()
                                      : std::string_view{"ObfuscationOS Desktop"},
                                  desktop_state_ == ExternalGuiDesktopState::greeter ? gui::GuiShellMode::system_greeter
                                                                                     : gui::GuiShellMode::system_shell);
    }
    auto status = desktop_state_ == ExternalGuiDesktopState::greeter ? render_greeter() : render_desktop_shell();
    if (status.code() == StatusCode::not_found)
    {
        dashboard_surface_ = 0;
        return refresh();
    }
    return status;
}

Status ExternalGuiDesktopModule::handle_key(int key)
{
    if (desktop_state_ != ExternalGuiDesktopState::greeter)
    {
        return Status::success();
    }
    if (key == '\t')
    {
        selected_login_user_ = selected_login_user_ == ExternalGuiLoginUser::root ? ExternalGuiLoginUser::user
                                                                                  : ExternalGuiLoginUser::root;
        login_dropdown_open_ = false;
        return render_greeter();
    }
    if (key == 27)
    {
        login_dropdown_open_ = false;
        return render_greeter();
    }
    if (key == '\r' || key == '\n' || key == ' ')
    {
        return login_default_user();
    }
    return Status::success();
}

Status ExternalGuiDesktopModule::handle_pointer_click(i32 x, i32 y)
{
    if (desktop_state_ != ExternalGuiDesktopState::greeter || compositor_ == nullptr || dashboard_surface_ == 0)
    {
        return Status::success();
    }
    auto info = compositor_->surface_info(dashboard_surface_);
    if (!info)
    {
        return info.status();
    }
    const auto card = greeter_card_bounds(info.value().bounds.width, info.value().bounds.height);
    const auto field = greeter_dropdown_bounds(card);
    if (login_dropdown_open_ && rect_contains(greeter_dropdown_option_bounds(card, 0), x, y))
    {
        selected_login_user_ = ExternalGuiLoginUser::root;
        login_dropdown_open_ = false;
        return render_greeter();
    }
    if (login_dropdown_open_ && rect_contains(greeter_dropdown_option_bounds(card, 1), x, y))
    {
        selected_login_user_ = ExternalGuiLoginUser::user;
        login_dropdown_open_ = false;
        return render_greeter();
    }
    if (rect_contains(field, x, y))
    {
        login_dropdown_open_ = !login_dropdown_open_;
        return render_greeter();
    }
    if (rect_contains(greeter_login_bounds(card), x, y))
    {
        login_dropdown_open_ = false;
        return login_default_user();
    }
    if (login_dropdown_open_)
    {
        login_dropdown_open_ = false;
        return render_greeter();
    }
    return Status::success();
}

std::string_view ExternalGuiDesktopModule::selected_login_user_name() const
{
    return selected_login_user_ == ExternalGuiLoginUser::root ? std::string_view{"root"} : std::string_view{"user"};
}

Result<ExternalGuiDockApp> ExternalGuiDesktopModule::dock_launcher_at(i32 x, i32 y) const
{
    if (desktop_state_ != ExternalGuiDesktopState::desktop || compositor_ == nullptr || dashboard_surface_ == 0)
    {
        return Status::not_found("system shell dock is not active");
    }
    auto info = compositor_->surface_info(dashboard_surface_);
    if (!info)
    {
        return info.status();
    }
    const auto bounds = info.value().bounds;
    if (x < bounds.x || y < bounds.y || x >= bounds.x + static_cast<i32>(bounds.width) ||
        y >= bounds.y + static_cast<i32>(bounds.height))
    {
        return Status::not_found("system shell dock miss");
    }

    const auto local_x = static_cast<u32>(x - bounds.x);
    const auto local_y = static_cast<u32>(y - bounds.y);
    const auto dock = system_dock_bounds(bounds.width, bounds.height);
    if (!rect_contains(dock, static_cast<i32>(local_x), static_cast<i32>(local_y)))
    {
        return Status::not_found("system shell dock miss");
    }

    const auto point_x = static_cast<i32>(local_x);
    const auto point_y = static_cast<i32>(local_y);
    if (rect_contains(system_dock_tile_bounds(dock, 0), point_x, point_y))
    {
        return ExternalGuiDockApp::shell;
    }
    if (rect_contains(system_dock_tile_bounds(dock, 1), point_x, point_y))
    {
        return ExternalGuiDockApp::settings;
    }
    if (rect_contains(system_dock_tile_bounds(dock, 2), point_x, point_y))
    {
        return ExternalGuiDockApp::tasks;
    }
    if (rect_contains(system_dock_tile_bounds(dock, 3), point_x, point_y))
    {
        return ExternalGuiDockApp::notes;
    }
    if (rect_contains(system_dock_tile_bounds(dock, 4), point_x, point_y))
    {
        return ExternalGuiDockApp::about;
    }
    if (rect_contains(system_dock_tile_bounds(dock, 5), point_x, point_y))
        return ExternalGuiDockApp::files;
    return Status::not_found("system shell dock launcher miss");
}

Status ExternalGuiDesktopModule::login_default_user()
{
    if (desktop_state_ == ExternalGuiDesktopState::desktop)
    {
        return Status::success();
    }
    if (desktop_state_ != ExternalGuiDesktopState::greeter)
    {
        return Status::not_initialized("system GUI greeter is not active");
    }
    desktop_state_ = ExternalGuiDesktopState::desktop;
    login_dropdown_open_ = false;
    if (auto status = open_shell_surface("ObfuscationOS Desktop", gui::GuiShellMode::system_shell); !status.ok())
    {
        return status;
    }
    if (auto status = render_desktop_shell(); !status.ok())
    {
        return status;
    }
    return Status::success();
}

Status ExternalGuiDesktopModule::open_shell_surface(std::string_view title, gui::GuiShellMode mode)
{
    auto desktop = compositor_->desktop_bounds();
    if (!desktop)
    {
        return desktop.status();
    }
    if (auto status = compositor_->set_shell_mode(mode); !status.ok())
    {
        return status;
    }
    if (dashboard_surface_ != 0)
    {
        if (auto status = compositor_->set_title(dashboard_surface_, title);
            !status.ok() && status.code() != StatusCode::not_found)
        {
            return status;
        }
        if (auto status = compositor_->resize_surface(dashboard_surface_, desktop.value());
            !status.ok() && status.code() != StatusCode::not_found)
        {
            return status;
        }
        if (auto status = compositor_->move_surface(dashboard_surface_, 0, 0);
            !status.ok() && status.code() != StatusCode::not_found)
        {
            return status;
        }
        if (auto status = compositor_->set_surface_chrome(dashboard_surface_, gui::SurfaceChrome::plain);
            !status.ok() && status.code() != StatusCode::not_found)
        {
            return status;
        }
        auto info = compositor_->surface_info(dashboard_surface_);
        if (info)
        {
            return compositor_->raise_surface(dashboard_surface_);
        }
        dashboard_surface_ = 0;
    }

    auto surface = desktop_->open_window(gui::DesktopWindowRequest{
        .bounds = desktop.value(),
        .title = title,
        .app = gui::TaskbarApp::none,
    });
    if (!surface)
    {
        return surface.status();
    }
    dashboard_surface_ = surface.value();
    if (auto status = compositor_->set_surface_chrome(dashboard_surface_, gui::SurfaceChrome::plain); !status.ok())
    {
        return status;
    }
    return compositor_->raise_surface(dashboard_surface_);
}

Status ExternalGuiDesktopModule::render_greeter()
{
    if (dashboard_surface_ == 0)
        return Status::not_initialized("greeter is not open");
    auto info = compositor_->surface_info(dashboard_surface_);
    if (!info)
    {
        dashboard_surface_ = 0;
        return info.status();
    }
    using namespace gui::theme;
    const auto width = info.value().bounds.width, height = info.value().bounds.height;
    static_cast<void>(compositor_->fill(dashboard_surface_, canvas));
    gui::Painter p(*compositor_, dashboard_surface_);
    p.rect(0, 0, width, 30, surface);
    p.text(16, 11, brand_.view());
    p.text(static_cast<i32>(width) - 86, 11, "WORKSPACE", muted);
    const auto card = greeter_card_bounds(width, height);
    p.rounded({card.x + 2, card.y + 3, card.width, card.height}, border, 5);
    p.rounded(card, surface, 5);
    p.rounded({card.x + 24, card.y + 18, 28, 28}, accent_soft, 5);
    p.rect(card.x + 32, card.y + 25, 12, 12, accent);
    p.rect(card.x + 36, card.y + 29, 4, 4, surface);
    p.text(card.x + 66, card.y + 18, "Welcome back", text, surface, 276, 2);
    p.text(card.x + 66, card.y + 42, "Choose your workspace.", muted);
    p.text(card.x + 24, card.y + 80, "Account", muted);
    const auto field = greeter_dropdown_bounds(card);
    p.rounded(field, subtle, 3);
    p.outline(field);
    p.text(field.x + 12, field.y + 8, selected_login_user_name(), text, subtle);
    p.text(field.x + static_cast<i32>(field.width) - 18, field.y + 8, "v", muted, subtle);
    p.text(card.x + 24, card.y + 113, "Tab to switch accounts", muted);
    const auto login = greeter_login_bounds(card);
    p.rounded(login, accent, 4);
    p.text(login.x + static_cast<i32>((login.width - 96) / 2), login.y + 9, "Enter workspace", surface, accent);
    if (login_dropdown_open_)
    {
        const auto menu = greeter_dropdown_menu_bounds(card);
        p.rect(menu.x, menu.y + 2, menu.width, menu.height, border);
        p.rect(menu.x, menu.y, menu.width, menu.height, surface);
        p.outline(menu);
        constexpr std::string_view labels[]{"root   Administrator", "user   Personal account"};
        for (usize i = 0; i < 2; ++i)
        {
            const auto option = greeter_dropdown_option_bounds(card, i);
            const bool selected = (i == 0) == (selected_login_user_ == ExternalGuiLoginUser::root);
            const auto bg = selected ? accent_soft : surface;
            p.rect(option.x + 1, option.y + 1, option.width - 2, option.height - 2, bg);
            p.text(option.x + 10, option.y + 5, labels[i], selected ? accent : text, bg, option.width - 18);
        }
    }
    p.text(140, static_cast<i32>(height) - 20, "A quiet place to build.", muted, canvas);
    if (!p.status().ok())
        return p.status();
    ++render_count_;
    return compositor_->present();
}
Status ExternalGuiDesktopModule::render_desktop_shell()
{
    if (dashboard_surface_ == 0)
        return Status::not_initialized("desktop is not open");
    auto info = compositor_->surface_info(dashboard_surface_);
    if (!info)
    {
        dashboard_surface_ = 0;
        return info.status();
    }
    using namespace gui::theme;
    const auto width = info.value().bounds.width, height = info.value().bounds.height;
    static_cast<void>(compositor_->fill(dashboard_surface_, canvas));
    gui::Painter p(*compositor_, dashboard_surface_);
    p.rect(0, 0, width, 25, surface);
    p.rect(0, 24, width, 1, border);
    p.text(14, 9, brand_.view());
    p.text(304, 9, selected_login_user_name(), muted);
    p.rect(350, 9, 4, 5, positive);
    p.text(362, 9, "System ready", muted);
    p.text(25, 57, "Your workspace.", text, canvas, 300, 2);
    p.text(26, 86, "Everything you need, within reach.", muted, canvas);
    p.rounded({26, 113, 205, 66}, surface, 4);
    p.text(39, 127, "MAKE SOMETHING", accent);
    p.text(39, 147, "Files, notes and a terminal.", muted);
    p.text(39, 162, "Choose an app from the dock.", muted);
    p.rounded({300, 61, 154, 100}, surface, 4);
    p.text(314, 76, "YOUR SESSION", muted);
    p.text(314, 96, selected_login_user_name(), text);
    FixedString<64> metric;
    static_cast<void>(assign_metric(metric, "Apps         ", 6));
    p.text(314, 119, metric.view(), muted);
    static_cast<void>(assign_metric(metric, "Processes    ", scheduler_->process_count()));
    p.text(314, 139, metric.view(), muted);
    const auto dock = system_dock_bounds(width, height);
    p.rect(0, dock.y, width, dock.height, surface);
    p.rect(0, dock.y, width, 1, border);
    constexpr std::string_view labels[]{"Terminal", "Settings", "Tasks", "Notes", "About", "Files"};
    constexpr std::string_view icons[]{">", "+", "||", "=", "i", "+"};
    for (usize i = 0; i < 6; ++i)
    {
        const auto tile = system_dock_tile_bounds(dock, i);
        p.rounded(tile, subtle, 4);
        p.text(tile.x + 7, tile.y + 11, icons[i], accent, subtle, 18);
        p.text(tile.x + 20, tile.y + 11, labels[i], text, subtle, tile.width - 20);
    }
    if (!p.status().ok())
        return p.status();
    ++render_count_;
    return compositor_->present();
}
Status ExternalGuiAppModule::configure_from_image(std::string_view path, const ModuleImageInfo &image)
{
    if (image.format != ModuleImageFormat::okmod)
    {
        return Status::unsupported("external C++ OOP module must use OKMOD metadata");
    }
    if (!has_parameter(image, "entry", "oop") || !has_parameter(image, "class", "app"))
    {
        return Status::unsupported("external GUI app requires entry:oop and class:app");
    }
    if (!has_symbol(image.imports, gui::gui_service_id) || !has_symbol(image.imports, gui::gui_desktop_service_id) ||
        image.exports.empty())
    {
        return Status::invalid_argument("external GUI app metadata is incomplete");
    }
    if (image.name.empty())
    {
        return Status::invalid_argument("external GUI app name is empty");
    }

    if (auto status = name_.assign(image.name.view()); !status.ok())
    {
        return status;
    }
    if (auto status = version_.assign(image.version.empty() ? std::string_view{"1"} : image.version.view());
        !status.ok())
    {
        return status;
    }
    if (auto status = service_id_.assign(image.exports[0].name.view()); !status.ok())
    {
        return status;
    }
    if (auto status = load_path_.assign(path); !status.ok())
    {
        return status;
    }

    exported_services_[0] = service_id_.view();
    required_services_[0] = gui::gui_service_id;
    required_services_[1] = gui::gui_desktop_service_id;
    required_services_[2] = {};
    required_service_count_ = 2;
    if (has_symbol(image.imports, "gui.system-desktop"))
    {
        required_services_[2] = "gui.system-desktop";
        required_service_count_ = 3;
    }

    if (auto status = title_.assign(image.name.view()); !status.ok())
    {
        return status;
    }
    if (auto status = subtitle_.assign("C++ OOP GUI module"); !status.ok())
    {
        return status;
    }
    if (auto status = body_.assign("Loaded from /boot/modules"); !status.ok())
    {
        return status;
    }
    command_.clear();
    line1_.clear();
    line2_.clear();
    line3_.clear();
    bounds_ = gui::Rect{.x = 72, .y = 64, .width = 330, .height = 154};
    accent_ = dashboard_warm;
    for (const auto &parameter : image.parameters)
    {
        if (auto status = assign_parameter(parameter.name.view(), parameter.value.view()); !status.ok())
        {
            return status;
        }
    }
    configured_ = true;
    app_state_ = ExternalGuiAppState::stopped;
    surface_ = 0;
    render_count_ = 0;
    return Status::success();
}

Status ExternalGuiAppModule::configure_from_elf(std::string_view app_id, std::string_view path, std::string_view title,
                                                std::string_view subtitle, std::string_view body,
                                                std::string_view command, std::string_view line1,
                                                std::string_view line2, std::string_view line3, gui::Rect bounds,
                                                std::string_view accent, sched::ProcessId process_id)
{
    if (app_id.empty() || path.empty() || process_id == 0)
    {
        return Status::invalid_argument("system GUI ELF app descriptor is incomplete");
    }
    FixedString<max_module_name> name;
    if (auto status = name.assign("app-"); !status.ok())
    {
        return status;
    }
    if (auto status = name.append(app_id); !status.ok())
    {
        return status;
    }
    if (auto status = name_.assign(name.view()); !status.ok())
    {
        return status;
    }
    if (auto status = version_.assign("elf"); !status.ok())
    {
        return status;
    }
    if (auto status = service_id_.assign(app_id); !status.ok())
    {
        return status;
    }
    if (auto status = load_path_.assign(path); !status.ok())
    {
        return status;
    }
    if (auto status = title_.assign(title.empty() ? app_id : title); !status.ok())
    {
        return status;
    }
    if (auto status = subtitle_.assign(subtitle); !status.ok())
    {
        return status;
    }
    if (auto status = body_.assign(body); !status.ok())
    {
        return status;
    }
    if (auto status = command_.assign(command.empty() ? path : command); !status.ok())
    {
        return status;
    }
    if (auto status = line1_.assign(line1); !status.ok())
    {
        return status;
    }
    if (auto status = line2_.assign(line2); !status.ok())
    {
        return status;
    }
    if (auto status = line3_.assign(line3); !status.ok())
    {
        return status;
    }
    bounds_ = bounds;
    accent_ = accent_for(accent);
    if (app_id == "tasks")
        static_cast<void>(status_line_.assign("J/K scroll process list"));
    if (app_id == "files")
        static_cast<void>(status_line_.assign("Enter opens  J/K selects"));
    process_id_ = process_id;
    configured_ = true;
    app_state_ = ExternalGuiAppState::stopped;
    surface_ = 0;
    render_count_ = 0;
    exported_services_[0] = {};
    required_services_[0] = {};
    required_services_[1] = {};
    required_services_[2] = {};
    required_service_count_ = 0;
    return Status::success();
}

Status ExternalGuiAppModule::assign_parameter(std::string_view name, std::string_view value)
{
    if (name == "title")
    {
        return title_.assign(value);
    }
    if (name == "subtitle")
    {
        return subtitle_.assign(value);
    }
    if (name == "body")
    {
        return body_.assign(value);
    }
    if (name == "command")
    {
        return command_.assign(value);
    }
    if (name == "line1")
    {
        return line1_.assign(value);
    }
    if (name == "line2")
    {
        return line2_.assign(value);
    }
    if (name == "line3")
    {
        return line3_.assign(value);
    }
    if (name == "accent")
    {
        accent_ = accent_for(value);
        return Status::success();
    }
    if (name == "x" || name == "y" || name == "width" || name == "height")
    {
        auto parsed = parse_decimal_u32(value);
        if (!parsed)
        {
            return parsed.status();
        }
        if (name == "x")
        {
            bounds_.x = static_cast<i32>(parsed.value());
        }
        else if (name == "y")
        {
            bounds_.y = static_cast<i32>(parsed.value());
        }
        else if (name == "width")
        {
            bounds_.width = parsed.value();
        }
        else
        {
            bounds_.height = parsed.value();
        }
    }
    return Status::success();
}

ModuleManifest ExternalGuiAppModule::manifest() const
{
    return ModuleManifest{
        .name = name_.empty() ? std::string_view{"external-gui-app"} : name_.view(),
        .version = version_.empty() ? std::string_view{"1"} : version_.view(),
        .module_class = "gui-app",
        .dependencies = dependencies_,
        .exported_services = exported_services_,
        .required_services = std::span<const std::string_view>{required_services_.data(), required_service_count_},
        .built_in = false,
        .execution = ModuleExecution::inline_core,
        .init_priority = 90,
        .threading = ModuleThreading::single_threaded,
        .capability_mask = module_capability_bit(ModuleCapability::exports_services) |
                           module_capability_bit(ModuleCapability::requires_services) |
                           module_capability_bit(ModuleCapability::handles_gui),
        .restart_policy = ModuleRestartPolicy::manual,
        .resources =
            ModuleResourceBudget{
                .max_threads = 1, .max_services = exported_services_.size(), .max_memory_pages = 1, .max_handles = 2},
    };
}

void *ExternalGuiAppModule::service(std::string_view service_id)
{
    return service_id == service_id_.view() ? this : nullptr;
}

Status ExternalGuiAppModule::start(ServiceRegistry &services)
{
    if (!configured_)
    {
        return Status::not_initialized("external GUI app module is not configured");
    }
    compositor_ = services.query<gui::GuiCompositor>(gui::gui_service_id);
    desktop_ = services.query<gui::GuiDesktopService>(gui::gui_desktop_service_id);
    if (compositor_ == nullptr || desktop_ == nullptr)
    {
        return Status::not_initialized("external GUI app requires GUI services");
    }
    if (auto status = open_window(); !status.ok())
    {
        return status;
    }
    app_state_ = ExternalGuiAppState::running;
    return Status::success();
}

Status ExternalGuiAppModule::start(gui::GuiCompositor &compositor, gui::GuiDesktopService &desktop)
{
    if (!configured_)
    {
        return Status::not_initialized("system GUI ELF app is not configured");
    }
    compositor_ = &compositor;
    desktop_ = &desktop;
    if (auto status = open_window(); !status.ok())
    {
        return status;
    }
    app_state_ = ExternalGuiAppState::running;
    return Status::success();
}

Status ExternalGuiAppModule::stop()
{
    if (desktop_ != nullptr && surface_ != 0)
    {
        auto status = desktop_->close_window(surface_);
        if (!status.ok() && status.code() != StatusCode::not_found)
        {
            return status;
        }
    }
    surface_ = 0;
    app_state_ = configured_ ? ExternalGuiAppState::stopped : ExternalGuiAppState::unloaded;
    compositor_ = nullptr;
    desktop_ = nullptr;
    return Status::success();
}

Status ExternalGuiAppModule::shutdown()
{
    return stop();
}

void ExternalGuiAppModule::reset()
{
    vfs_ = nullptr;
    posix_ = nullptr;
    static_cast<void>(document_.assign("A little space for your ideas.\n\nType to edit. Ctrl+S to save."));
    static_cast<void>(output_.assign("ObfuscationOS terminal\nType help to see available commands."));
    input_.clear();
    static_cast<void>(directory_.assign("/"));
    static_cast<void>(status_line_.assign("Ready"));
    document_dirty_ = false;
    file_preview_ = false;
    selected_entry_ = 0;
    configured_ = false;
    name_.clear();
    version_.clear();
    service_id_.clear();
    load_path_.clear();
    static_cast<void>(title_.assign("System App"));
    static_cast<void>(subtitle_.assign("ELF user app"));
    static_cast<void>(body_.assign("Launched from /bin"));
    command_.clear();
    line1_.clear();
    line2_.clear();
    line3_.clear();
    exported_services_[0] = {};
    required_services_[0] = {};
    required_services_[1] = {};
    required_services_[2] = {};
    required_service_count_ = 0;
    compositor_ = nullptr;
    desktop_ = nullptr;
    scheduler_ = nullptr;
    topology_ = nullptr;
    app_state_ = ExternalGuiAppState::unloaded;
    surface_ = 0;
    bounds_ = gui::Rect{.x = 72, .y = 64, .width = 276, .height = 112};
    accent_ = dashboard_warm;
    process_id_ = 0;
    render_count_ = 0;
}

Status ExternalGuiAppModule::refresh()
{
    if (app_state_ != ExternalGuiAppState::running)
    {
        return Status::not_initialized("external GUI app is not running");
    }
    if (surface_ == 0)
    {
        return open_window();
    }
    auto status = render_window();
    if (status.code() == StatusCode::not_found)
    {
        return open_window();
    }
    return status;
}

Status ExternalGuiAppModule::open_window()
{
    auto desktop_bounds = compositor_->desktop_bounds();
    if (!desktop_bounds)
    {
        return desktop_bounds.status();
    }
    auto surface = desktop_->open_window(gui::DesktopWindowRequest{
        .bounds = fit_bounds(bounds_, desktop_bounds.value()),
        .title = title_.view(),
        .app = gui::TaskbarApp::none,
    });
    if (!surface)
    {
        return surface.status();
    }
    surface_ = surface.value();
    if (service_id_.view() == "notes" && posix_ && !document_dirty_)
    {
        const auto path = posix_->euid() == 0 ? "/tmp/notes-root.txt" : "/tmp/notes-user.txt";
        if (auto fd = posix_->open(path, posix::o_RDONLY))
        {
            std::array<std::byte, 1023> bytes{};
            auto count = posix_->read(fd.value(), bytes);
            static_cast<void>(posix_->close(fd.value()));
            if (count)
            {
                static_cast<void>(document_.assign({reinterpret_cast<const char *>(bytes.data()), count.value()}));
                static_cast<void>(status_line_.assign("Loaded from /tmp"));
            }
        }
    }
    return render_window();
}

Status ExternalGuiAppModule::save_notes()
{
    if (posix_ == nullptr)
        return Status::not_initialized("Filesystem unavailable");
    const auto path = posix_->euid() == 0 ? "/tmp/notes-root.txt" : "/tmp/notes-user.txt";
    auto existing = posix_->stat(path);
    if (existing)
    {
        if (existing.value().type != fs::NodeType::regular || existing.value().uid != posix_->euid() ||
            existing.value().link_count != 1)
            return Status::denied("Note path is not a private file owned by this user");
        if (auto status = posix_->chmod(path, 0600); !status.ok())
            return status;
    }
    else if (existing.status().code() != StatusCode::not_found)
        return existing.status();
    auto fd = posix_->open(path, posix::o_WRONLY | posix::o_CREAT | posix::o_TRUNC, 0600);
    if (!fd)
        return fd.status();
    auto written =
        posix_->write(fd.value(), {reinterpret_cast<const std::byte *>(document_.view().data()), document_.size()});
    auto closed = posix_->close(fd.value());
    if (!written)
        return written.status();
    if (written.value() != document_.size())
        return Status::fault("Note was only partially saved");
    if (!closed.ok())
        return closed;
    document_dirty_ = false;
    return status_line_.assign("Saved in /tmp");
}

Status ExternalGuiAppModule::execute_command()
{
    if (!posix_ || !vfs_)
        return Status::not_initialized("Filesystem unavailable");
    auto command = input_.view();
    while (!command.empty() && command.front() == ' ')
        command.remove_prefix(1);
    while (!command.empty() && command.back() == ' ')
        command.remove_suffix(1);
    const auto split = command.find(' ');
    const auto verb = command.substr(0, split);
    auto arg = split == std::string_view::npos ? std::string_view{} : command.substr(split + 1);
    while (!arg.empty() && arg.front() == ' ')
        arg.remove_prefix(1);
    if (command.empty())
        return Status::success();
    output_.clear();
    if (verb == "clear")
        return Status::success();
    if (verb == "help")
        return output_.assign("help  clear  pwd  ls [path]  cd [path]\ncat <file>  whoami\n\nFiles and notes use your "
                              "session permissions.");
    if (verb == "pwd")
        return output_.assign(directory_.view());
    if (verb == "whoami")
        return output_.assign(posix_->euid() == 0 ? "root" : "user");
    auto path = app_path(directory_.view(), arg);
    if (!path)
        return path.status();
    if (verb == "cd")
    {
        if (auto status = posix_->access(path.value().view(), posix::r_OK | posix::x_OK); !status.ok())
            return status;
        auto listing = vfs_->list(path.value().view());
        if (!listing)
            return listing.status();
        if (auto status = directory_.assign(path.value().view()); !status.ok())
            return status;
        return output_.assign(directory_.view());
    }
    if (verb == "ls")
    {
        if (auto status = posix_->access(path.value().view(), posix::r_OK | posix::x_OK); !status.ok())
            return status;
        auto listing = vfs_->list(path.value().view());
        if (!listing)
            return listing.status();
        for (const auto &entry : std::span{listing.value().entries.data(), listing.value().count})
        {
            if (auto status = output_.append(entry.name.view()); !status.ok())
                break;
            if (entry.metadata.type == fs::NodeType::directory)
                static_cast<void>(output_.append('/'));
            static_cast<void>(output_.append("  "));
        }
        return Status::success();
    }
    if (verb == "cat")
    {
        auto fd = posix_->open(path.value().view(), posix::o_RDONLY);
        if (!fd)
            return fd.status();
        std::array<std::byte, 900> buffer{};
        auto count = posix_->read(fd.value(), buffer);
        auto closed = posix_->close(fd.value());
        if (!count)
            return count.status();
        if (!closed.ok())
            return closed;
        for (usize i = 0; i < count.value(); ++i)
        {
            const auto ch = std::to_integer<unsigned char>(buffer[i]);
            static_cast<void>(output_.append(ch == '\n' || (ch >= 32 && ch < 127) ? static_cast<char>(ch) : '.'));
        }
        return Status::success();
    }
    return Status::unsupported("Unknown command. Type help.");
}

Status ExternalGuiAppModule::open_file_entry(usize index)
{
    if (!vfs_ || !posix_)
        return Status::not_initialized("Filesystem unavailable");
    if (auto status = posix_->access(directory_.view(), posix::r_OK | posix::x_OK); !status.ok())
        return status;
    auto listing = vfs_->list(directory_.view());
    if (!listing)
        return listing.status();
    if (index >= listing.value().count)
        return Status::success();
    const auto &entry = listing.value().entries[index];
    auto path = app_path(directory_.view(), entry.name.view());
    if (!path)
        return path.status();
    if (entry.metadata.type == fs::NodeType::directory)
    {
        if (auto status = posix_->access(path.value().view(), posix::r_OK | posix::x_OK); !status.ok())
            return status;
        if (auto status = directory_.assign(path.value().view()); !status.ok())
            return status;
        selected_entry_ = 0;
        file_preview_ = false;
        return status_line_.assign("Enter opens  J/K moves");
    }
    auto fd = posix_->open(path.value().view(), posix::o_RDONLY);
    if (!fd)
        return fd.status();
    std::array<std::byte, 900> buffer{};
    auto count = posix_->read(fd.value(), buffer);
    auto closed = posix_->close(fd.value());
    if (!count)
        return count.status();
    if (!closed.ok())
        return closed;
    document_.clear();
    for (usize i = 0; i < count.value(); ++i)
    {
        const auto ch = std::to_integer<unsigned char>(buffer[i]);
        static_cast<void>(document_.append(ch == '\n' || (ch >= 32 && ch < 127) ? static_cast<char>(ch) : '.'));
    }
    file_preview_ = true;
    return status_line_.assign(entry.name.view());
}

Status ExternalGuiAppModule::handle_key(int key)
{
    Status action{};
    if (service_id_.view() == "notes")
    {
        if (key == 19)
            action = save_notes();
        else if (key == 8 || key == 127)
        {
            document_.pop_back();
            document_dirty_ = true;
            static_cast<void>(status_line_.assign("Unsaved changes"));
        }
        else if (key == '\r' || key == '\n' || (key >= 32 && key < 127))
        {
            action = document_.append(key == '\r' ? '\n' : static_cast<char>(key));
            if (action.ok())
            {
                document_dirty_ = true;
                static_cast<void>(status_line_.assign("Unsaved changes"));
            }
        }
    }
    else if (service_id_.view() == "shell")
    {
        if (key == '\r' || key == '\n')
        {
            action = execute_command();
            input_.clear();
            if (!action.ok())
                static_cast<void>(output_.assign(action.message()));
        }
        else if (key == 8 || key == 127)
            input_.pop_back();
        else if (key == 3)
        {
            input_.clear();
            static_cast<void>(output_.assign("Input cancelled."));
        }
        else if (key >= 32 && key < 127)
            action = input_.append(static_cast<char>(key));
    }
    else if (service_id_.view() == "tasks")
    {
        if (key == 'j' && scheduler_ && selected_entry_ + 1 < scheduler_->process_count())
            ++selected_entry_;
        else if (key == 'k' && selected_entry_ > 0)
            --selected_entry_;
        static_cast<void>(status_line_.assign("J/K scroll process list"));
    }
    else if (service_id_.view() == "files")
    {
        if (key == 8 || key == 127 || key == 27)
            return handle_pointer(20, 29);
        if (key == '\r' || key == '\n')
            action = open_file_entry(selected_entry_);
        else if (key == 'j' && vfs_)
        {
            auto entries = vfs_->list(directory_.view());
            if (entries && selected_entry_ + 1 < entries.value().count)
                ++selected_entry_;
        }
        else if (key == 'k' && selected_entry_ > 0)
            --selected_entry_;
    }
    if (!action.ok())
        static_cast<void>(status_line_.assign(action.message().substr(0, 80)));
    return refresh();
}

Status ExternalGuiAppModule::handle_pointer(i32 x, i32 y)
{
    Status action{};
    if (service_id_.view() == "settings" && y >= 122 && y < 142)
    {
        constexpr u32 colors[]{gui::theme::accent, gui::theme::positive, 0xff7665b2u};
        for (usize i = 0; i < 3; ++i)
            if (x >= 96 + static_cast<i32>(i * 38) && x < 122 + static_cast<i32>(i * 38))
            {
                accent_ = colors[i];
                static_cast<void>(status_line_.assign("Accent updated"));
            }
    }
    else if (service_id_.view() == "files")
    {
        if (x < 76 && y >= 18 && y < 47)
        {
            if (file_preview_)
                file_preview_ = false;
            else
            {
                auto parent = app_path(directory_.view(), "..");
                if (parent)
                    action = directory_.assign(parent.value().view());
            }
            selected_entry_ = 0;
        }
        else if (x < 78 && y >= 78 && y < 119)
        {
            action = directory_.assign(y < 98 ? "/" : "/tmp");
            selected_entry_ = 0;
            file_preview_ = false;
        }
        else if (x >= 86 && y >= 76 && !file_preview_)
        {
            auto info = compositor_->surface_info(surface_);
            const auto rows = info && info.value().bounds.height > 108 ? (info.value().bounds.height - 108) / 18 : 1;
            const auto first = selected_entry_ >= rows ? selected_entry_ - rows + 1 : 0;
            const auto row = static_cast<usize>((y - 76) / 18);
            if (row < rows && vfs_)
            {
                auto listing = vfs_->list(directory_.view());
                if (listing && first + row < listing.value().count)
                {
                    selected_entry_ = first + row;
                    action = open_file_entry(selected_entry_);
                }
            }
        }
    }
    if (!action.ok())
        static_cast<void>(status_line_.assign(action.message().substr(0, 80)));
    return refresh();
}

Status ExternalGuiAppModule::render_window()
{
    if (surface_ == 0)
        return Status::not_initialized("app window is not open");
    auto info = compositor_->surface_info(surface_);
    if (!info)
    {
        surface_ = 0;
        return info.status();
    }
    using namespace gui::theme;
    const auto width = info.value().bounds.width, height = info.value().bounds.height;
    static_cast<void>(compositor_->fill(surface_, gui::theme::surface));
    gui::Painter p(*compositor_, surface_);
    if (width < 280 || height < 158)
    {
        p.text(8, 24, "Enlarge to view", muted, gui::theme::surface, width > 16 ? width - 16 : 1);
        if (!p.status().ok())
            return p.status();
        return compositor_->present();
    }
    const auto footer = height > 18 ? static_cast<i32>(height) - 16 : 0;
    const auto id = service_id_.view();
    const auto content_width = width > 104 ? width - 104 : 1;
    auto paragraph = [&](i32 x, i32 y, std::string_view value, u32 columns, u32 color, u32 bg, bool tail = false) {
        usize offset = 0, line_count = 0;
        const auto row_count = footer > y + 9 ? static_cast<usize>((footer - y - 10) / 12 + 1) : 1;
        if (tail)
        {
            for (usize index = 0, column = 0; index < value.size(); ++index)
            {
                if (value[index] == '\n' || ++column == columns)
                {
                    ++line_count;
                    column = 0;
                }
            }
        }
        usize skip = tail && line_count + 1 > row_count ? line_count + 1 - row_count : 0;
        gui::Rect cursor{x, y, 1, 8};
        while (offset < value.size() && y + 9 < footer)
        {
            usize length = 0;
            while (offset + length < value.size() && value[offset + length] != '\n' && length < columns)
                ++length;
            if (skip == 0)
            {
                p.text(x, y, value.substr(offset, length), color, bg, columns * gui::gui_glyph_width);
                cursor = {x + static_cast<i32>(length * gui::gui_glyph_width), y, 1, 8};
            }
            offset += length;
            if (offset < value.size() && value[offset] == '\n')
            {
                ++offset;
                cursor = {x, y + 12, 1, 8};
            }
            if (skip > 0)
                --skip;
            else
                y += 12;
        }
        return cursor;
    };
    if (id == "shell")
    {
        p.rect(1, 18, width - 2, height > 34 ? height - 34 : 1, terminal);
        p.text(13, 28, "TERMINAL", 0xff8ca9ceu, terminal);
        paragraph(13, 49, output_.view(), (width - 28) / gui::gui_glyph_width, terminal_text, terminal);
        p.rect(1, footer - 18, width - 2, 18, terminal);
        p.text(13, footer - 13, ">", 0xff88b8ffu, terminal);
        p.text(25, footer - 13, input_.view(), terminal_text, terminal, width - 44);
        const auto cursor = 25 + static_cast<i32>(input_.size() * gui::gui_glyph_width);
        if (cursor + 5 < static_cast<i32>(width))
            p.rect(cursor, footer - 13, 5, 8, 0xff88b8ffu);
    }
    else if (id == "settings")
    {
        p.rect(1, 18, 80, height - 35, subtle);
        p.rounded({7, 31, 67, 20}, accent_soft, 3);
        p.text(14, 38, "Appearance", accent_, accent_soft);
        p.text(14, 65, "Display", muted, subtle);
        p.text(14, 89, "Session", muted, subtle);
        p.text(96, 31, "Make it yours", text);
        p.text(96, 51, "COLOR MODE", muted);
        p.rounded({96, 65, content_width, 32}, subtle, 3);
        p.rect(107, 74, 14, 14, gui::theme::surface);
        p.outline({107, 74, 14, 14});
        p.text(131, 78, "Light", text, subtle);
        p.text(static_cast<i32>(width) - 70, 78, "Active", accent_, subtle);
        p.text(96, 108, "ACCENT COLOR", muted);
        constexpr u32 choices[]{gui::theme::accent, positive, 0xff7665b2u};
        for (usize i = 0; i < 3; ++i)
        {
            const auto x = 96 + static_cast<i32>(i * 38);
            p.rounded({x, 122, 26, 20}, choices[i], 3);
            if (accent_ == choices[i])
                p.text(x + 10, 129, "+", gui::theme::surface, choices[i]);
        }
    }
    else if (id == "tasks")
    {
        p.rounded({12, 27, 150, 29}, subtle, 3);
        p.rounded({170, 27, width > 182 ? width - 182 : 1, 29}, subtle, 3);
        FixedString<64> metric;
        static_cast<void>(assign_metric(metric, "Processes  ", scheduler_ ? scheduler_->process_count() : 0));
        p.text(22, 38, metric.view(), text, subtle);
        static_cast<void>(assign_metric(metric, "CPU slots  ", topology_ ? topology_->cpu_count() : 0));
        p.text(180, 38, metric.view(), text, subtle);
        p.text(14, 67, "PID", muted);
        p.text(57, 67, "PROCESS", muted);
        p.text(width - 78, 67, "STATE", muted);
        p.rect(12, 80, width - 24, 1, border);
        i32 y = 88;
        usize index = 0;
        if (scheduler_)
            for (const auto &process : scheduler_->processes())
            {
                if (index++ < selected_entry_)
                    continue;
                if (y + 9 >= footer)
                    break;
                metric.clear();
                static_cast<void>(append_decimal(metric, process.pid()));
                p.text(14, y, metric.view());
                p.text(57, y, process.name(), text, gui::theme::surface, width - 150);
                p.text(width - 78, y, process_state_label(process.state()), muted);
                y += 15;
            }
    }
    else if (id == "notes")
    {
        p.rect(1, 18, 80, height - 35, subtle);
        p.text(13, 31, "MY NOTES", muted, subtle);
        p.rounded({7, 49, 67, 29}, accent_soft, 3);
        p.text(13, 56, "Scratchpad", accent_, accent_soft);
        p.text(13, 68, "Personal", muted, accent_soft);
        p.text(96, 31, "Scratchpad", text);
        p.text(width - 79, 31, "Ctrl+S", muted);
        p.rect(94, 46, content_width, 1, border);
        const auto cursor =
            paragraph(96, 58, document_.view(), content_width / gui::gui_glyph_width, text, gui::theme::surface, true);
        if (info.value().focused && cursor.y + 9 < footer)
            p.rect(cursor.x, cursor.y, 1, 8, accent_);
    }
    else if (id == "files")
    {
        p.rect(1, 18, width - 2, 29, subtle);
        p.text(12, 29, "< Back", accent_, subtle);
        p.text(88, 29, directory_.view(), text, subtle, width - 105);
        p.rect(1, 47, 78, height - 64, subtle);
        p.text(13, 60, "PLACES", muted, subtle);
        p.text(13, 83, "Root", directory_.view() == "/" ? accent_ : muted, subtle);
        p.text(13, 107, "Temporary", directory_.view() == "/tmp" ? accent_ : muted, subtle);
        p.text(92, 58, "NAME", muted);
        p.text(width - 80, 58, "KIND", muted);
        p.rect(90, 71, width - 102, 1, border);
        auto listing = vfs_ ? vfs_->list(directory_.view())
                            : Result<fs::DirectoryListing>{Status::not_initialized("no filesystem")};
        if (listing && posix_ && !posix_->access(directory_.view(), posix::r_OK | posix::x_OK).ok())
            listing = Status::denied("Folder access denied");
        if (file_preview_)
        {
            p.rect(80, 48, width - 81, height - 65, gui::theme::surface);
            p.text(92, 58, "FILE PREVIEW", muted);
            paragraph(92, 79, document_.view(), (width - 106) / gui::gui_glyph_width, text, gui::theme::surface);
        }
        else if (listing)
        {
            i32 y = 80;
            const auto rows = height > 108 ? (height - 108) / 18 : 1;
            const auto first = selected_entry_ >= rows ? selected_entry_ - rows + 1 : 0;
            for (usize i = first; i < listing.value().count && y + 13 < footer; ++i, y += 18)
            {
                const auto &entry = listing.value().entries[i];
                const auto bg = i == selected_entry_ ? accent_soft : gui::theme::surface;
                p.rounded({86, y - 4, width - 96, 17}, bg, 2);
                p.rect(93, y, 7, 7, entry.metadata.type == fs::NodeType::directory ? accent_ : muted);
                p.text(108, y, entry.name.view(), text, bg, width - 200);
                p.text(width - 80, y, entry.metadata.type == fs::NodeType::directory ? "Folder" : "File", muted, bg);
            }
            if (listing.value().count == 0)
                p.text(96, 91, "This folder is empty.", muted);
        }
        else
            p.text(96, 91, "Folder unavailable", muted);
    }
    else
    {
        p.rounded({18, 32, 43, 43}, accent_soft, 5);
        p.rect(29, 43, 21, 21, accent_);
        p.rect(36, 50, 7, 7, gui::theme::surface);
        p.text(76, 34, "ObfuscationOS", text, gui::theme::surface, width - 90, 2);
        p.text(77, 61, "A small system. Room to grow.", muted, gui::theme::surface, width - 91);
        p.rect(18, 91, width - 36, 1, border);
        p.text(20, 106, "VERSION", muted);
        p.text(114, 106, "0.1  /  Development", text);
        p.text(20, 127, "WORKSPACE", muted);
        p.text(114, 127, accent_ == gui::theme::accent ? "Light  /  Blue" : "Light  /  Custom", text);
        p.text(20, 148, "Built with care in C++.", muted);
    }
    p.rect(1, footer, width - 2, 15, subtle);
    p.rect(1, footer, width - 2, 1, border);
    p.text(12, footer + 5, status_line_.view(), muted, subtle, width - 90);
    p.rect(width - 54, footer + 6, 3, 3, positive);
    p.text(width - 46, footer + 5, "Ready", muted, subtle);
    if (!p.status().ok())
        return p.status();
    ++render_count_;
    return compositor_->present();
}
} // namespace ok

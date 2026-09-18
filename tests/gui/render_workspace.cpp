// Hosted rendering fixture: all pixels come from the production compositor and OS GUI.
#include "../../modules/system-gui/system_gui_tests.cpp"
#include "system_gui_runtime.hpp"
#include <cstdio>
#include <cstdlib>
#include <string>

using namespace ok;
using namespace obfuscationos::modules;

static Kernel kernel;
static SystemGuiRuntime runtime;

// Native execution is never entered by this hosted fixture.
extern "C" void ok_platform_console_write_char(char value)
{
    std::putchar(value);
}

void require(Status status)
{
    if (!status.ok())
    {
        std::fprintf(stderr, "%.*s\n", static_cast<int>(status.message().size()), status.message().data());
        std::exit(1);
    }
}

void capture(const char *directory, const char *name)
{
    const auto path = std::string(directory) + "/" + name + ".ppm";
    auto *file = std::fopen(path.c_str(), "wb");
    if (file == nullptr)
        std::exit(2);
    std::fprintf(file, "P6\n%zu %zu\n255\n", driver::framebuffer_width, driver::framebuffer_height);
    require(kernel.gui().compositor().set_pointer_position(470, 218));
    require(kernel.gui().compositor().present());
    for (u32 y = 0; y < driver::framebuffer_height; ++y)
        for (u32 x = 0; x < driver::framebuffer_width; ++x)
        {
            const auto pixel = kernel.display().pixel_at(x, y);
            if (!pixel)
                require(pixel.status());
            const unsigned char rgb[]{static_cast<unsigned char>(pixel.value() >> 16),
                                      static_cast<unsigned char>(pixel.value() >> 8),
                                      static_cast<unsigned char>(pixel.value())};
            std::fwrite(rgb, 1, sizeof(rgb), file);
        }
    std::fclose(file);
}

void click(i32 x, i32 y)
{
    require(kernel.handle_gui_mouse_position(x, y, true));
    require(kernel.handle_gui_mouse_position(x, y, false));
}

void type(std::string_view text)
{
    for (const auto ch : text)
        require(kernel.handle_gui_key(ch));
}

void launch(usize index)
{
    for (gui::SurfaceId id = 1; id < 64; ++id)
    {
        auto info = kernel.gui().compositor().surface_info(id);
        if (info && info.value().chrome == gui::SurfaceChrome::decorated)
            require(kernel.gui().compositor().set_visible(id, false));
    }
    click(32 + static_cast<i32>(index * 76), 248);
    constexpr std::string_view titles[]{"Tiny Shell", "System Settings",     "Task Manager",
                                        "Notes",      "About ObfuscationOS", "Files"};
    auto active = kernel.gui().compositor().surface_info(kernel.gui().compositor().active_surface());
    if (!active || !active.value().visible || active.value().title != titles[index])
        require(Status::fault("Launcher did not focus the expected application"));
}

int main(int argc, char **argv)
{
    if (argc != 2)
        return 2;
    KernelConfig config;
    config.extension = &runtime;
    require(kernel.boot(config));
    require(kernel.close_debug_gui());
    capture(argv[1], "01-kernel");
    require(stage_system_gui_user_apps(kernel));
    require(runtime.start(kernel));
    capture(argv[1], "02-login");
    require(kernel.handle_gui_key('\n'));
    capture(argv[1], "03-desktop");
    launch(0);
    type("help\n");
    capture(argv[1], "04-terminal");
    launch(1);
    capture(argv[1], "05-settings");
    launch(2);
    capture(argv[1], "06-tasks");
    launch(3);
    for (int i = 0; i < 100; ++i)
        require(kernel.handle_gui_key(8));
    type("Ideas for today\n\nKeep the core small.\nMake the desktop useful.\nBuild one good thing at a time.");
    require(kernel.handle_gui_key(19));
    capture(argv[1], "07-notes");
    auto saved = kernel.vfs().read_file("/tmp/notes-root.txt");
    if (!saved || !file_contains(saved.value(), "Ideas for today"))
        return 3;
    const auto notes = kernel.gui().compositor().surface_info(kernel.gui().compositor().active_surface());
    if (!notes)
        require(notes.status());
    click(notes.value().bounds.x + static_cast<i32>(notes.value().bounds.width) - 10, notes.value().bounds.y + 5);
    launch(3);
    // The same production view reloads saved text after its original process/window is closed.
    capture(argv[1], "07-notes");
    launch(5);
    click(48 + 25, 38 + 110);
    capture(argv[1], "08-files");
    launch(4);
    capture(argv[1], "09-about");
    std::puts("GUI_RENDER interactions=pass notes_saved=pass screenshots=9");
}

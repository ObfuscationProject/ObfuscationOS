// Reference C++ OOP definitions for the OS-side GUI app packages.
// The current OKMOD loader consumes the metadata files while the native
// relocating module ABI is still on the kernel roadmap.

namespace obfuscationos::gui_apps
{

class SystemGuiApp
{
  public:
    constexpr SystemGuiApp(const char *service, const char *title) : service_(service), title_(title)
    {
    }

    [[nodiscard]] constexpr const char *service() const
    {
        return service_;
    }

    [[nodiscard]] constexpr const char *title() const
    {
        return title_;
    }

  private:
    const char *service_;
    const char *title_;
};

class AboutApp final : public SystemGuiApp
{
  public:
    constexpr AboutApp() : SystemGuiApp("gui.app.about", "About ObfuscationOS")
    {
    }
};

class PreferencesApp final : public SystemGuiApp
{
  public:
    constexpr PreferencesApp() : SystemGuiApp("gui.app.prefs", "System Preferences")
    {
    }
};

class NotesApp final : public SystemGuiApp
{
  public:
    constexpr NotesApp() : SystemGuiApp("gui.app.notes", "Notes")
    {
    }
};

} // namespace obfuscationos::gui_apps

#include "modules/system-gui/notes_save.hpp"
obfuscationos::desktop::NotesSaveOutcome desktop_notes_object(ok::posix::PosixService &provider,
    std::span<const std::byte> bytes)
{
    return obfuscationos::desktop::save_default_notes(provider, bytes);
}

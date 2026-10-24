#include "modules/system-gui/notes_handoff.hpp"
obfuscationos::desktop::NotesTargetSaveOutcome desktop_handoff_save_object(ok::posix::PosixService &provider,
    const obfuscationos::desktop::NotesTarget &target, std::span<const std::byte> bytes)
{
    return obfuscationos::desktop::save_selected_notes(provider, target, bytes);
}
ok::Result<obfuscationos::desktop::NotesOpenDocument> desktop_handoff_open_object(ok::posix::PosixService &provider,
    const obfuscationos::desktop::NotesTarget &target)
{
    return obfuscationos::desktop::open_selected_notes(provider, target);
}
ok::Result<ok::posix::FileStatus> desktop_handoff_display_object(ok::posix::PosixService &provider,
    std::string_view directory, ok::fs::DirectoryListing &listing)
{
    return obfuscationos::desktop::capture_notes_display(provider, directory, listing);
}

#include "modules/system-gui/files_actions.hpp"
obfuscationos::desktop::FilesOutcome desktop_files_object(ok::posix::PosixService &provider,
    std::string_view directory, obfuscationos::desktop::FilesAction action, std::string_view name,
    std::string_view destination, const ok::posix::FileStatus *expected, const ok::posix::FileStatus *expected_directory)
{
    return obfuscationos::desktop::perform_file_action(provider, directory, action, name, destination, expected, expected_directory);
}

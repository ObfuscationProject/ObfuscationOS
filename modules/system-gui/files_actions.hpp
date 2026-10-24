#pragma once
#include <ok/posix/posix.hpp>
#include <concepts>

namespace obfuscationos::desktop
{
using namespace ok;
enum class FilesAction : u8 { none, new_file, new_folder, rename, remove };
struct FilesOutcome
{
    Status status{}, cleanup{};
    bool publication_attempted{}, changed{};
    [[nodiscard]] bool complete() const { return status.ok() && cleanup.ok() && changed; }
};
struct FilesSelection
{
    posix::FileStatus directory{}, item{};
};
template <typename Provider>
concept FilesProvider = requires(Provider &p, posix::Fd fd, std::string_view path)
{
    { p.euid() } -> std::same_as<u32>;
    { p.open(path, u32{}, u32{}) } -> std::same_as<Result<posix::Fd>>;
    { p.openat(fd, path, u32{}, u32{}) } -> std::same_as<Result<posix::Fd>>;
    { p.mkdirat(fd, path, u32{}) } -> std::same_as<Status>;
    { p.fstat(fd) } -> std::same_as<Result<posix::FileStatus>>;
    { p.statat(fd, path, u32{}) } -> std::same_as<Result<posix::FileStatus>>;
    { p.renameat(fd, path, fd, path) } -> std::same_as<Status>;
    { p.unlinkat(fd, path, u32{}) } -> std::same_as<Status>;
    { p.fsync(fd) } -> std::same_as<Status>;
    { p.close(fd) } -> std::same_as<Status>;
};
inline constexpr usize files_name_limit = fs::max_path_segment - 1;
inline bool files_name_valid(std::string_view name)
{
    if (name.empty() || name.size() > files_name_limit || name == "." || name == "..") return false;
    for (unsigned char c : name)
        if (c < 32 || c >= 127 || c == '/' || c == '\\') return false;
    return true;
}
inline bool files_metadata_valid(const posix::FileStatus &s)
{
    return (s.type == fs::NodeType::regular || s.type == fs::NodeType::directory) &&
        (s.type != fs::NodeType::regular || s.link_count == 1) &&
        s.attributes.has(fs::Attribute::inode) && s.attributes.has(fs::Attribute::device);
}
inline bool files_same_selection(const posix::FileStatus &a, const posix::FileStatus &b)
{
    return files_metadata_valid(a) && files_metadata_valid(b) && a.type == b.type &&
        a.size == b.size && a.mode == b.mode && a.uid == b.uid && a.gid == b.gid &&
        a.link_count == b.link_count && a.attributes.inode == b.attributes.inode &&
        a.attributes.device == b.attributes.device;
}
inline constexpr u32 files_directory_open = posix::o_RDONLY | posix::o_DIRECTORY | posix::o_NOFOLLOW | posix::o_CLOEXEC;
inline bool files_same_directory(const posix::FileStatus &a, const posix::FileStatus &b)
{
    return a.type == fs::NodeType::directory && b.type == fs::NodeType::directory &&
        files_metadata_valid(a) && files_metadata_valid(b) && a.mode == b.mode && a.uid == b.uid && a.gid == b.gid &&
        a.attributes.inode == b.attributes.inode && a.attributes.device == b.attributes.device;
}

template <FilesProvider Provider>
Result<FilesSelection> capture_file_action(Provider &p, std::string_view parent, std::string_view name = {})
{
    if (!name.empty() && !files_name_valid(name)) return Status::invalid_argument("Invalid file name");
    auto fd = p.open(parent, files_directory_open, 0);
    if (!fd) return fd.status();
    auto folder = p.fstat(fd.value());
    Result<posix::FileStatus> item{posix::FileStatus{}};
    if (folder && !name.empty()) item = p.statat(fd.value(), name, posix::at_SYMLINK_NOFOLLOW);
    auto closed = p.close(fd.value());
    if (!folder) return folder.status();
    if (!item) return item.status();
    if (!closed) return closed;
    if (!files_same_directory(folder.value(), folder.value())) return Status::denied("Folder identity is unavailable");
    if (!name.empty() && !files_metadata_valid(item.value())) return Status::denied("Select an ordinary file or folder");
    return FilesSelection{folder.value(), item.value()};
}

// Captures actual object identity for a prompt. No descriptor crosses the UI boundary.
template <FilesProvider Provider>
Result<posix::FileStatus> select_file_action(Provider &p, std::string_view parent, std::string_view name)
{
    if (!files_name_valid(name)) return Status::invalid_argument("Invalid file name");
    auto fd = p.open(parent, files_directory_open, 0);
    if (!fd) return fd.status();
    auto item = p.statat(fd.value(), name, posix::at_SYMLINK_NOFOLLOW);
    auto closed = p.close(fd.value());
    if (!item) return item.status();
    if (!closed) return closed;
    if (!files_metadata_valid(item.value())) return Status::denied("Select an ordinary file or folder");
    return item;
}

// Serialized desktop policy. Metadata prechecks do not provide namespace CAS
// against external same-user writers. Backend errors can follow publication.
template <FilesProvider Provider>
FilesOutcome perform_file_action(Provider &p, std::string_view parent, FilesAction action,
    std::string_view name, std::string_view destination = {}, const posix::FileStatus *expected = nullptr,
    const posix::FileStatus *expected_directory = nullptr)
{
    posix::Fd directory = -1, created = -1;
    bool attempted{}, changed{};
    auto finish = [&](Status cause) -> FilesOutcome {
        Status cleanup{};
        if (created >= 0) { const auto fd = created; created = -1; cleanup = p.close(fd); }
        if (directory >= 0)
        {
            const auto fd = directory; directory = -1;
            auto closed = p.close(fd); if (cleanup.ok() && !closed) cleanup = closed;
        }
        return {cause, cleanup, attempted, changed};
    };
    if (!files_name_valid(name) || (action == FilesAction::rename && !files_name_valid(destination)))
        return finish(Status::invalid_argument("Use a single file name of 1 to 31 English characters"));
    if (action != FilesAction::new_file && action != FilesAction::new_folder &&
        action != FilesAction::rename && action != FilesAction::remove)
        return finish(Status::invalid_argument("No file action selected"));
    if (action == FilesAction::rename && name == destination)
        return finish(Status::invalid_argument("Choose a different file name"));
    if (!expected_directory) return finish(Status::invalid_argument("File action requires a captured folder"));
    auto opened = p.open(parent, files_directory_open, 0);
    if (!opened) return finish(opened.status());
    directory = opened.value();
    auto parent_status = p.fstat(directory);
    if (!parent_status) return finish(parent_status.status());
    if (parent_status.value().type != fs::NodeType::directory)
        return finish(Status::not_directory("File action parent is not a folder"));
    if (!files_same_directory(*expected_directory, parent_status.value()))
        return finish(Status::busy("Folder changed; select it again"));
    const bool selected_action = action == FilesAction::rename || action == FilesAction::remove;
    if (selected_action)
    {
        if (!expected) return finish(Status::invalid_argument("File action requires a captured selection"));
        auto current = p.statat(directory, name, posix::at_SYMLINK_NOFOLLOW);
        if (!current) return finish(current.status());
        if (!files_same_selection(*expected, current.value()))
            return finish(Status::busy("Selected file changed; select it again"));
    }
    if (action != FilesAction::remove)
    {
        const auto target = action == FilesAction::rename ? destination : name;
        auto existing = p.statat(directory, target, posix::at_SYMLINK_NOFOLLOW);
        if (existing) return finish(Status::already_exists("That name already exists"));
        if (existing.status().code() != StatusCode::not_found) return finish(existing.status());
    }
    if (selected_action)
    {
        auto final = p.statat(directory, name, posix::at_SYMLINK_NOFOLLOW);
        if (!final) return finish(final.status());
        if (!files_same_selection(*expected, final.value()))
            return finish(Status::busy("Selected file changed; select it again"));
    }
    attempted = true;
    if (action == FilesAction::new_file)
    {
        auto file = p.openat(directory, name, posix::o_WRONLY | posix::o_CREAT | posix::o_EXCL |
            posix::o_NOFOLLOW | posix::o_CLOEXEC, 0600);
        if (!file) return finish(file.status());
        created = file.value(); changed = true;
        auto actual = p.fstat(created);
        if (!actual) return finish(actual.status());
        if (actual.value().type != fs::NodeType::regular || !files_metadata_valid(actual.value()) || actual.value().uid != p.euid() ||
            actual.value().size != 0 || (actual.value().mode & 07777u) != 0600u)
            return finish(Status::denied("New file metadata is invalid"));
        auto synced = p.fsync(created); if (!synced) return finish(synced);
        const auto fd = created; created = -1;
        auto closed = p.close(fd); if (!closed) return finish(closed);
    }
    else
    {
        Status mutation{};
        if (action == FilesAction::new_folder) mutation = p.mkdirat(directory, name, 0700);
        else if (action == FilesAction::rename) mutation = p.renameat(directory, name, directory, destination);
        else if (action == FilesAction::remove)
        {
            // ABI55 PosixService unlinkat supports 0x0200 (empty directory
            // removal); its public header does not yet name that flag.
            mutation = p.unlinkat(directory, name, expected->type == fs::NodeType::directory ? 0x0200u : 0);
        }
        else return finish(Status::invalid_argument("Unknown file action"));
        if (!mutation) return finish(mutation);
        changed = true;
        if (action == FilesAction::new_folder)
        {
            auto folder = p.openat(directory, name, files_directory_open, 0);
            if (!folder) return finish(folder.status());
            created = folder.value();
            auto actual = p.fstat(created);
            if (!actual) return finish(actual.status());
            if (actual.value().type != fs::NodeType::directory || !files_metadata_valid(actual.value()) ||
                actual.value().uid != p.euid() || (actual.value().mode & 07777u) != 0700u)
                return finish(Status::denied("New folder metadata is invalid"));
            auto synced = p.fsync(created); if (!synced) return finish(synced);
            const auto fd = created; created = -1;
            auto closed = p.close(fd); if (!closed) return finish(closed);
        }
    }
    auto synced = p.fsync(directory); if (!synced) return finish(synced);
    return finish(Status::success());
}
} // namespace obfuscationos::desktop

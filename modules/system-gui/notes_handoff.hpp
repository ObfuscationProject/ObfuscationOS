#pragma once
#include "files_actions.hpp"
#include "notes_save.hpp"

namespace obfuscationos::desktop
{
inline constexpr usize notes_text_capacity = 1023;
inline constexpr u32 notes_interruption_limit = 32;
struct NotesTarget
{
    FixedString<96> parent{}, path{};
    FixedString<fs::max_path_segment> name{};
    posix::FileStatus directory{}, file{};
};
struct NotesOpenDocument
{
    FixedString<1024> text{};
    NotesTarget target{};
};
struct NotesTargetSaveOutcome
{
    Status status{}, cleanup{};
    bool publication_attempted{}, replaced{};
    posix::FileStatus published{};
    [[nodiscard]] bool complete() const { return status.ok() && cleanup.ok() && replaced; }
};
template <typename Provider>
concept NotesHandoffProvider = NotesFileProvider<Provider> && requires(Provider &p, posix::Fd fd, std::span<std::byte> bytes)
{
    { p.read(fd, bytes) } -> std::same_as<Result<usize>>;
};
inline bool notes_private_directory(const posix::FileStatus &s, u32 uid, u32 gid)
{
    return s.type == fs::NodeType::directory && s.uid == uid && s.gid == gid &&
        s.mode == fs::mode_for(fs::NodeType::directory, 0700) && files_metadata_valid(s);
}
inline bool notes_private_file(const posix::FileStatus &s, u32 uid, u32 gid)
{
    return notes_owned_file(s, uid, gid) && s.mode == fs::mode_for(fs::NodeType::regular, 0600);
}
inline bool notes_same_timestamp(const fs::FileAttributes &a, const fs::FileAttributes &b, fs::Attribute field)
{
    if (a.has(field) != b.has(field)) return false;
    if (!a.has(field)) return true;
    const auto &left = field == fs::Attribute::modification_time ? a.modification : a.change;
    const auto &right = field == fs::Attribute::modification_time ? b.modification : b.change;
    return left.seconds == right.seconds && left.nanoseconds == right.nanoseconds && left.source == right.source;
}
inline bool notes_handoff_same_file(const posix::FileStatus &a, const posix::FileStatus &b)
{
    return files_same_selection(a, b) && notes_same_timestamp(a.attributes, b.attributes, fs::Attribute::modification_time) &&
        notes_same_timestamp(a.attributes, b.attributes, fs::Attribute::change_time);
}
inline posix::FileStatus notes_listing_status(const fs::Metadata &s)
{
    return {.type=s.type, .size=s.size, .mode=s.mode, .uid=s.uid, .gid=s.gid, .link_count=s.link_count,
        .block_size=s.block_size, .blocks=s.blocks, .attributes=s.attributes};
}
inline bool notes_listing_matches(const fs::Metadata &shown, const posix::FileStatus &actual)
{
    if (shown.type != actual.type || shown.size != actual.size || shown.mode != actual.mode || shown.uid != actual.uid ||
        shown.gid != actual.gid || shown.link_count != actual.link_count) return false;
    if (shown.attributes.has(fs::Attribute::inode) && (!actual.attributes.has(fs::Attribute::inode) ||
        shown.attributes.inode != actual.attributes.inode)) return false;
    if (shown.attributes.has(fs::Attribute::device) && (!actual.attributes.has(fs::Attribute::device) ||
        shown.attributes.device != actual.attributes.device)) return false;
    return true;
}

// ABI55 raw directory listings need not complete the filesystem device field.
// Bind the rendered value-only snapshot to actual POSIX identities before use.
// The caller owns the listing storage; this avoids another large stack copy.
template <FilesProvider Provider>
Result<posix::FileStatus> capture_notes_display(Provider &p, std::string_view path, fs::DirectoryListing &listing)
{
    if (listing.count > listing.entries.size()) return Status::invalid_argument("Folder listing count exceeds its capacity");
    auto opened = p.open(path, files_directory_open, 0);
    if (!opened) return opened.status();
    const auto fd = opened.value();
    auto before = p.fstat(fd);
    Status checked = before ? Status::success() : before.status();
    if (checked && !files_same_directory(before.value(), before.value())) checked = Status::denied("Folder identity is unavailable");
    for (usize i = 0; checked && i < listing.count; ++i)
    {
        auto &entry = listing.entries[i];
        // Unsupported names remain visible but cannot authorize a text open.
        if (!files_name_valid(entry.name.view())) { entry.metadata.attributes.valid = 0; continue; }
        auto actual = p.statat(fd, entry.name.view(), posix::at_SYMLINK_NOFOLLOW);
        if (!actual) { checked = actual.status(); break; }
        if (!notes_listing_matches(entry.metadata, actual.value())) { checked = Status::busy("Folder row changed during rendering"); break; }
        const auto &s = actual.value();
        entry.metadata = {.type=s.type, .size=s.size, .mode=s.mode, .uid=s.uid, .gid=s.gid, .link_count=s.link_count,
            .block_size=s.block_size, .blocks=s.blocks, .attributes=s.attributes};
    }
    if (checked)
    {
        auto after = p.fstat(fd);
        if (!after) checked = after.status();
        else if (!files_same_directory(before.value(), after.value())) checked = Status::busy("Folder changed during rendering");
    }
    auto closed = p.close(fd);
    if (!checked) return checked;
    if (!closed) return closed;
    return before.value();
}
inline bool notes_english_text(std::span<const std::byte> bytes)
{
    for (auto byte : bytes)
    {
        const auto c = std::to_integer<unsigned char>(byte);
        if (c != '\n' && c != '\t' && (c < 32 || c >= 127)) return false;
    }
    return true;
}
inline bool notes_parent_path_valid(std::string_view parent)
{
    if (parent.empty() || parent.front() != '/' || parent.size() >= 96) return false;
    if (parent == "/") return true;
    usize begin = 1;
    while (begin < parent.size())
    {
        const auto end = parent.find('/', begin);
        if (!files_name_valid(parent.substr(begin, end == std::string_view::npos ? parent.size() - begin : end - begin)))
            return false;
        if (end == std::string_view::npos) return true;
        begin = end + 1;
    }
    return false;
}
inline Result<NotesTarget> make_notes_target(std::string_view parent, std::string_view name, const FilesSelection &selection)
{
    if (!notes_parent_path_valid(parent) || !files_name_valid(name)) return Status::invalid_argument("Select a single English file name");
    NotesTarget target;
    if (auto s = target.parent.assign(parent); !s) return s;
    if (auto s = target.name.assign(name); !s) return s;
    if (auto s = target.path.assign(parent); !s) return s;
    if (parent != "/") if (auto s = target.path.append('/'); !s) return s;
    if (auto s = target.path.append(name); !s) return s;
    target.directory = selection.directory; target.file = selection.item;
    return target;
}
inline bool notes_target_valid(const NotesTarget &target)
{
    auto canonical = make_notes_target(target.parent.view(), target.name.view(), {target.directory, target.file});
    return canonical && canonical.value().path.view() == target.path.view();
}

// All bytes and target state are returned only after both descriptors close.
// Metadata checks cannot provide namespace CAS against same-user writers.
template <NotesHandoffProvider Provider>
Result<NotesOpenDocument> open_selected_notes(Provider &p, const NotesTarget &target)
{
    posix::Fd directory = -1, file = -1;
    auto finish = [&](Status cause) -> Status {
        if (file >= 0) { const auto fd = file; file = -1; auto closed = p.close(fd); if (cause.ok() && !closed) cause = closed; }
        if (directory >= 0) { const auto fd = directory; directory = -1; auto closed = p.close(fd); if (cause.ok() && !closed) cause = closed; }
        return cause;
    };
    const auto uid = p.euid(), gid = p.egid();
    if (!notes_target_valid(target)) return finish(Status::invalid_argument("Invalid Notes target path"));
    if (!notes_private_directory(target.directory, uid, gid))
        return finish(Status::denied("Edit files only in an owned private 0700 folder"));
    if (!notes_private_file(target.file, uid, gid))
        return finish(Status::denied("Edit an owned 0600 ordinary file with one link"));
    if (target.file.size > notes_text_capacity) return finish(Status::message_size("File exceeds Notes capacity of 1023 bytes"));
    auto opened = p.open(target.parent.view(), files_directory_open, 0);
    if (!opened) return finish(opened.status());
    directory = opened.value();
    auto parent = p.fstat(directory);
    if (!parent) return finish(parent.status());
    if (!notes_private_directory(parent.value(), uid, gid) || !files_same_directory(target.directory, parent.value()))
        return finish(Status::busy("Folder changed; select the file again"));
    auto selected = p.statat(directory, target.name.view(), posix::at_SYMLINK_NOFOLLOW);
    if (!selected) return finish(selected.status());
    if (!notes_private_file(selected.value(), uid, gid) || !notes_handoff_same_file(target.file, selected.value()))
        return finish(Status::busy("Selected file changed; select it again"));
    opened = p.openat(directory, target.name.view(), posix::o_RDONLY | posix::o_NOFOLLOW | posix::o_CLOEXEC, 0);
    if (!opened) return finish(opened.status());
    file = opened.value();
    auto actual = p.fstat(file);
    if (!actual) return finish(actual.status());
    if (!notes_private_file(actual.value(), uid, gid) || !notes_handoff_same_file(target.file, actual.value()))
        return finish(Status::busy("Opened file does not match the selection"));
    std::array<std::byte, notes_text_capacity> bytes{};
    usize offset{}; u32 interrupted{};
    while (offset < target.file.size)
    {
        auto read = p.read(file, std::span<std::byte>{bytes}.subspan(offset, target.file.size - offset));
        if (!read)
        {
            if (read.status().code() == StatusCode::interrupted && interrupted++ < notes_interruption_limit) continue;
            return finish(read.status());
        }
        if (!read.value() || read.value() > target.file.size - offset)
            return finish(Status::io_error("File read made invalid or incomplete progress"));
        offset += read.value();
    }
    std::array<std::byte, 1> probe{};
    for (;;)
    {
        auto eof = p.read(file, probe);
        if (!eof)
        {
            if (eof.status().code() == StatusCode::interrupted && interrupted++ < notes_interruption_limit) continue;
            return finish(eof.status());
        }
        if (eof.value()) return finish(Status::busy("File grew while opening; select it again"));
        break;
    }
    if (!notes_english_text(std::span<const std::byte>{bytes}.first(offset)))
        return finish(Status::unsupported("Notes accepts English text, LF and TAB only"));
    actual = p.fstat(file);
    if (!actual) return finish(actual.status());
    selected = p.statat(directory, target.name.view(), posix::at_SYMLINK_NOFOLLOW);
    if (!selected) return finish(selected.status());
    parent = p.fstat(directory);
    if (!parent) return finish(parent.status());
    if (!notes_handoff_same_file(target.file, actual.value()) || !notes_handoff_same_file(target.file, selected.value()) ||
        !files_same_directory(target.directory, parent.value()))
        return finish(Status::busy("File or folder changed during opening"));
    auto closed = finish(Status::success()); if (!closed) return closed;
    NotesOpenDocument result; result.target = target;
    auto assigned = result.text.assign({reinterpret_cast<const char *>(bytes.data()), offset});
    if (!assigned) return assigned;
    return result;
}

template <NotesHandoffProvider Provider>
NotesTargetSaveOutcome save_selected_notes(Provider &p, const NotesTarget &target, std::span<const std::byte> bytes)
{
    posix::Fd directory = -1, staging = -1;
    bool created{}, attempted{}, replaced{}, stage_known{};
    FixedString<64> temporary;
    posix::FileStatus staged{}, published{};
    auto finish = [&](Status cause) -> NotesTargetSaveOutcome {
        Status cleanup{};
        auto remember = [&](Status status) { if (cleanup.ok() && !status) cleanup = status; };
        if (staging >= 0) { const auto fd = staging; staging = -1; remember(p.close(fd)); }
        if (created && !attempted)
        {
            auto current = p.statat(directory, temporary.view(), posix::at_SYMLINK_NOFOLLOW);
            if (!current) remember(current.status());
            else if (!stage_known || !files_same_selection(staged, current.value()))
                remember(Status::busy("Temporary identity unavailable; inspect the folder"));
            else remember(p.unlinkat(directory, temporary.view(), 0));
        }
        if (directory >= 0) { const auto fd = directory; directory = -1; remember(p.close(fd)); }
        return {cause, cleanup, attempted, replaced, published};
    };
    const auto uid = p.euid(), gid = p.egid();
    if (!notes_target_valid(target)) return finish(Status::invalid_argument("Invalid Notes target path"));
    if (bytes.size() > notes_text_capacity || !notes_english_text(bytes))
        return finish(Status::unsupported("Save English text of at most 1023 bytes"));
    if (!notes_private_directory(target.directory, uid, gid) || !notes_private_file(target.file, uid, gid))
        return finish(Status::denied("Selected target must remain private and owned"));
    auto opened = p.open(target.parent.view(), files_directory_open, 0);
    if (!opened) return finish(opened.status());
    directory = opened.value();
    auto parent = p.fstat(directory);
    if (!parent) return finish(parent.status());
    if (!files_same_directory(target.directory, parent.value())) return finish(Status::busy("Save folder changed; reopen the file"));
    auto before = p.statat(directory, target.name.view(), posix::at_SYMLINK_NOFOLLOW);
    if (!before) return finish(before.status());
    if (!notes_handoff_same_file(target.file, before.value())) return finish(Status::busy("Save target changed; reopen the file"));
    for (u32 attempt = 0; attempt < 32; ++attempt)
    {
        static_cast<void>(temporary.assign(".nt-")); notes_number(temporary, p.getpid());
        static_cast<void>(temporary.append('-')); notes_number(temporary, attempt); static_cast<void>(temporary.append(".tmp"));
        opened = p.openat(directory, temporary.view(), posix::o_WRONLY | posix::o_CREAT | posix::o_EXCL |
            posix::o_NOFOLLOW | posix::o_CLOEXEC, 0600);
        if (opened) { staging = opened.value(); created = true; break; }
        if (opened.status().code() != StatusCode::already_exists) return finish(opened.status());
    }
    if (staging < 0) return finish(Status::already_exists("Notes temporary names are exhausted"));
    auto metadata = p.fstat(staging);
    if (!metadata) return finish(metadata.status());
    staged = metadata.value(); stage_known = notes_private_file(staged, uid, gid) && staged.size == 0;
    if (!stage_known)
        return finish(Status::denied("Notes temporary file metadata is invalid"));
    usize offset{}; u32 interrupted{};
    while (offset < bytes.size())
    {
        auto written = p.write(staging, bytes.subspan(offset));
        if (!written)
        {
            if (written.status().code() == StatusCode::interrupted && interrupted++ < notes_interruption_limit) continue;
            return finish(written.status());
        }
        if (!written.value() || written.value() > bytes.size() - offset)
            return finish(Status::io_error("Notes write made invalid progress"));
        offset += written.value();
        staged.size = offset;
    }
    auto synced = p.fsync(staging); if (!synced) return finish(synced);
    metadata = p.fstat(staging);
    if (!metadata) return finish(metadata.status());
    if (!files_same_selection(staged, metadata.value())) return finish(Status::busy("Notes temporary file changed"));
    staged = metadata.value();
    { const auto fd = staging; staging = -1; auto closed = p.close(fd); if (!closed) return finish(closed); }
    before = p.statat(directory, target.name.view(), posix::at_SYMLINK_NOFOLLOW);
    if (!before) return finish(before.status());
    parent = p.fstat(directory);
    if (!parent) return finish(parent.status());
    if (!notes_handoff_same_file(target.file, before.value()) || !files_same_directory(target.directory, parent.value()))
        return finish(Status::busy("Selected save target changed before replacement"));
    auto source = p.statat(directory, temporary.view(), posix::at_SYMLINK_NOFOLLOW);
    if (!source) return finish(source.status());
    if (!notes_handoff_same_file(staged, source.value())) return finish(Status::busy("Notes temporary name changed"));
    attempted = true;
    auto renamed = p.renameat(directory, temporary.view(), directory, target.name.view());
    if (!renamed) return finish(renamed);
    created = false; replaced = true;
    synced = p.fsync(directory); if (!synced) return finish(synced);
    auto current = p.statat(directory, target.name.view(), posix::at_SYMLINK_NOFOLLOW);
    if (!current) return finish(current.status());
    if (!files_same_selection(staged, current.value())) return finish(Status::busy("Published Notes file identity is uncertain"));
    parent = p.fstat(directory);
    if (!parent) return finish(parent.status());
    if (!files_same_directory(target.directory, parent.value())) return finish(Status::busy("Published Notes folder changed"));
    published = current.value();
    return finish(Status::success());
}
} // namespace obfuscationos::desktop

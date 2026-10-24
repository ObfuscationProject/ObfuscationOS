#pragma once
#include <ok/posix/posix.hpp>
#include <concepts>

namespace obfuscationos::desktop
{
using namespace ok;
struct NotesSaveOutcome
{
    Status status{}, cleanup{};
    bool replaced{}, publication_attempted{};
    [[nodiscard]] bool complete() const { return status.ok() && cleanup.ok() && replaced; }
};

template <typename Provider>
concept NotesFileProvider = requires(Provider &p, posix::Fd fd, std::string_view path,
                                    std::span<const std::byte> bytes)
{
    { p.euid() } -> std::same_as<u32>;
    { p.egid() } -> std::same_as<u32>;
    { p.getpid() } -> std::same_as<sched::ProcessId>;
    { p.open(path, u32{}, u32{}) } -> std::same_as<Result<posix::Fd>>;
    { p.openat(fd, path, u32{}, u32{}) } -> std::same_as<Result<posix::Fd>>;
    { p.mkdirat(fd, path, u32{}) } -> std::same_as<Status>;
    { p.fstat(fd) } -> std::same_as<Result<posix::FileStatus>>;
    { p.statat(fd, path, u32{}) } -> std::same_as<Result<posix::FileStatus>>;
    { p.write(fd, bytes) } -> std::same_as<Result<usize>>;
    { p.fsync(fd) } -> std::same_as<Status>;
    { p.close(fd) } -> std::same_as<Status>;
    { p.renameat(fd, path, fd, path) } -> std::same_as<Status>;
    { p.unlinkat(fd, path, u32{}) } -> std::same_as<Status>;
};

inline bool notes_owned_file(const posix::FileStatus &s, u32 uid, u32 gid)
{
    return s.type == fs::NodeType::regular && s.uid == uid && s.gid == gid && s.link_count == 1 &&
           !(s.mode & 07000u) && (s.mode & 0200u) &&
           s.attributes.has(fs::Attribute::inode) && s.attributes.has(fs::Attribute::device);
}
inline bool notes_same_file(const posix::FileStatus &a, const posix::FileStatus &b)
{
    return a.type == b.type && a.size == b.size && a.mode == b.mode && a.uid == b.uid &&
           a.gid == b.gid && a.link_count == b.link_count && a.attributes.inode == b.attributes.inode &&
           a.attributes.device == b.attributes.device && b.attributes.has(fs::Attribute::inode) &&
           b.attributes.has(fs::Attribute::device);
}
inline void notes_number(FixedString<64> &name, u64 value)
{
    char digits[20]{}; usize count{};
    do { digits[count++] = static_cast<char>('0' + value % 10); value /= 10; } while (value);
    while (count) static_cast<void>(name.append(digits[--count]));
}

// Owns both returned descriptors. close consumes a descriptor even on error,
// matching the installed POSIX service. Caller bytes are copied synchronously.
template <NotesFileProvider Provider>
NotesSaveOutcome save_default_notes(Provider &provider, std::span<const std::byte> bytes)
{
    posix::Fd root = -1, directory = -1, staging = -1;
    bool created{}, replaced{}, publication_attempted{};
    FixedString<64> temporary;
    const u32 uid = provider.euid(), gid = provider.egid();
    const std::string_view folder = uid == 0 ? "notes-root" : "notes-user";
    auto fail = [&](Status cause) -> NotesSaveOutcome {
        Status cleanup{};
        auto remember = [&](Status status) { if (cleanup.ok() && !status.ok()) cleanup = status; };
        if (staging >= 0) { const auto fd = staging; staging = -1; remember(provider.close(fd)); }
        // rename errors can follow partial namespace publication. Preserve
        // the uncertain temporary path instead of assuming it is still ours.
        if (created && !publication_attempted) remember(provider.unlinkat(directory, temporary.view(), 0));
        if (directory >= 0) { const auto fd = directory; directory = -1; remember(provider.close(fd)); }
        if (root >= 0) { const auto fd = root; root = -1; remember(provider.close(fd)); }
        return {cause, cleanup, replaced, publication_attempted};
    };
    auto opened_root = provider.open("/tmp", posix::o_RDONLY | posix::o_DIRECTORY | posix::o_CLOEXEC | posix::o_NOFOLLOW, 0);
    if (!opened_root) return fail(opened_root.status());
    root = opened_root.value();
    auto made = provider.mkdirat(root, folder, 0700);
    if (!made && made.code() != StatusCode::already_exists) return fail(made);
    auto opened = provider.openat(root, folder, posix::o_RDONLY | posix::o_DIRECTORY | posix::o_CLOEXEC | posix::o_NOFOLLOW, 0);
    if (!opened) return fail(opened.status());
    directory = opened.value();
    auto parent = provider.fstat(directory);
    if (!parent) return fail(parent.status());
    if (parent.value().type != fs::NodeType::directory || parent.value().uid != uid || parent.value().gid != gid ||
        (parent.value().mode & 07777u) != 0700u)
        return fail(Status::denied("Notes folder must be private and owned by this user"));
    { auto synced = provider.fsync(root); if (!synced) return fail(synced); }
    { const auto fd = root; root = -1; auto closed = provider.close(fd); if (!closed) return fail(closed); }
    auto before = provider.statat(directory, "note.txt", posix::at_SYMLINK_NOFOLLOW);
    if (before && !notes_owned_file(before.value(), uid, gid))
        return fail(Status::denied("Note must be an ordinary private owner file"));
    if (!before && before.status().code() != StatusCode::not_found) return fail(before.status());
    for (u32 attempt = 0; attempt < 32; ++attempt)
    {
        static_cast<void>(temporary.assign(".notes-"));
        notes_number(temporary, provider.getpid());
        static_cast<void>(temporary.append('-')); notes_number(temporary, attempt);
        static_cast<void>(temporary.append(".tmp"));
        auto file = provider.openat(directory, temporary.view(),
            posix::o_WRONLY | posix::o_CREAT | posix::o_EXCL | posix::o_CLOEXEC | posix::o_NOFOLLOW, 0600);
        if (file) { staging = file.value(); created = true; break; }
        if (file.status().code() != StatusCode::already_exists) return fail(file.status());
    }
    if (staging < 0) return fail(Status::already_exists("Notes temporary names are exhausted"));
    auto actual = provider.fstat(staging);
    if (!actual) return fail(actual.status());
    if (!notes_owned_file(actual.value(), uid, gid) || (actual.value().mode & 07777u) != 0600u)
        return fail(Status::denied("Notes temporary file metadata is invalid"));
    usize offset{};
    while (offset < bytes.size())
    {
        const usize capacity = 1024 - offset % 1024;
        const usize count = bytes.size() - offset < capacity ? bytes.size() - offset : capacity;
        auto written = provider.write(staging, bytes.subspan(offset, count));
        if (!written)
        {
            if (written.status().code() == StatusCode::interrupted) continue;
            return fail(written.status());
        }
        if (!written.value() || written.value() > count) return fail(Status::io_error("Notes write made invalid progress"));
        offset += written.value();
    }
    auto synced = provider.fsync(staging); if (!synced) return fail(synced);
    { const auto fd = staging; staging = -1; auto closed = provider.close(fd); if (!closed) return fail(closed); }
    auto current = provider.statat(directory, "note.txt", posix::at_SYMLINK_NOFOLLOW);
    if (before)
    {
        if (!current || !notes_same_file(before.value(), current.value()))
            return fail(Status::busy("Note destination changed before replacement"));
    }
    else if (current || current.status().code() != StatusCode::not_found)
        return fail(current ? Status::busy("Note destination appeared before replacement") : current.status());
    publication_attempted = true;
    auto renamed = provider.renameat(directory, temporary.view(), directory, "note.txt");
    if (!renamed) return fail(renamed);
    created = false; replaced = true;
    synced = provider.fsync(directory); if (!synced) return fail(synced);
    { const auto fd = directory; directory = -1; auto closed = provider.close(fd); if (!closed) return fail(closed); }
    return {Status::success(), Status::success(), true, true};
}
} // namespace obfuscationos::desktop

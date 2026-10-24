#include "modules/system-gui/notes_handoff.hpp"
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
using namespace ok;
using namespace obfuscationos::desktop;
static usize checks{};
static void check(bool condition)
{
    ++checks;
    if (!condition) { std::fprintf(stderr, "HANDOFF_CHECK_FAILED check=%zu\n", checks); std::abort(); }
}
struct Provider final
{
    std::string text{"Original English\n"}, temporary;
    posix::FileStatus directory{}, selected{}, stage{};
    std::array<bool, 6> fds{};
    std::vector<std::string> events;
    int calls{}, fail_at{-1}, second_fail_at{-1}, collisions{}, interrupts{}, read_calls{}, write_calls{};
    int file_stats{}, parent_stats{}, namespace_stats{}, temporary_stats{};
    bool short_io{}, zero_io{}, overreport{}, extra_eof{}, stage_exists{}, renamed{}, mutate_rename_error{};
    bool swap_after_open{}, change_after_read{}, change_before_rename{}, replace_folder{}, postpublish_wrong{}, replace_temporary{};
    Provider()
    {
        directory = metadata(fs::NodeType::directory, 3, 0700);
        selected = metadata(fs::NodeType::regular, 10, 0600); selected.size = text.size();
        stage = metadata(fs::NodeType::regular, 11, 0600);
    }
    static posix::FileStatus metadata(fs::NodeType type, u64 inode, u32 mode)
    {
        posix::FileStatus s{}; s.type = type; s.mode = fs::mode_for(type, mode); s.uid = s.gid = 1000;
        s.attributes.inode = inode; s.attributes.device = {0, 1};
        s.attributes.mark(fs::Attribute::inode); s.attributes.mark(fs::Attribute::device); return s;
    }
    u32 euid() const { return 1000; }
    u32 egid() const { return 1000; }
    sched::ProcessId getpid() const { return ~u64{0}; }
    Status mkdirat(posix::Fd, std::string_view, u32) { check(false); return Status::unsupported(); }
    bool fault(const char *label) { events.emplace_back(label); const auto at = calls++; return at == fail_at || at == second_fail_at; }
    static Status error() { return Status::io_error("Injected handoff boundary failure"); }
    NotesTarget target() const
    {
        auto result = make_notes_target("/tmp/private", "draft.txt", {directory, selected});
        check(result.ok()); return result.value();
    }
    Result<posix::Fd> open(std::string_view path, u32 flags, u32 mode)
    {
        check(path == "/tmp/private" && flags == files_directory_open && mode == 0 && !fds[3]);
        if (fault("open-parent")) return error();
        fds[3] = true; return 3;
    }
    Result<posix::Fd> openat(posix::Fd fd, std::string_view name, u32 flags, u32 mode)
    {
        check(fd == 3 && fds[3] && (flags & posix::o_NOFOLLOW) && (flags & posix::o_CLOEXEC));
        if (name == "draft.txt")
        {
            check(flags == (posix::o_RDONLY | posix::o_NOFOLLOW | posix::o_CLOEXEC) && mode == 0 && !fds[4]);
            if (fault("open-selected")) return error();
            fds[4] = true; return 4;
        }
        check(name.starts_with(".nt-18446744073709551615-") && name.ends_with(".tmp") && files_name_valid(name));
        check(flags == (posix::o_WRONLY | posix::o_CREAT | posix::o_EXCL | posix::o_NOFOLLOW | posix::o_CLOEXEC) && mode == 0600 && !fds[5]);
        if (fault("open-staging")) return error();
        if (collisions) { --collisions; return Status::already_exists(); }
        stage_exists = fds[5] = true; temporary.clear(); stage.size = 0; return 5;
    }
    Result<posix::FileStatus> fstat(posix::Fd fd)
    {
        check(fd >= 3 && fd <= 5 && fds[fd]);
        if (fault(fd == 3 ? "stat-parent" : fd == 4 ? "stat-open-file" : "stat-staging")) return error();
        if (fd == 3)
        {
            ++parent_stats; auto value = directory;
            if (replace_folder && parent_stats > 1) ++value.attributes.inode;
            return value;
        }
        if (fd == 5) { auto value = stage; value.size = temporary.size(); return value; }
        ++file_stats; auto value = selected;
        if ((swap_after_open && file_stats == 1) || (change_after_read && file_stats > 1)) ++value.attributes.inode;
        return value;
    }
    Result<posix::FileStatus> statat(posix::Fd fd, std::string_view name, u32 flags)
    {
        check(fd == 3 && fds[3] && flags == posix::at_SYMLINK_NOFOLLOW);
        if (fault(name == "draft.txt" ? "stat-selected-name" : "stat-temporary-name")) return error();
        if (name != "draft.txt")
        {
            ++temporary_stats;
            if (!stage_exists) return Status::not_found();
            auto value = stage; value.size = temporary.size();
            if (replace_temporary) ++value.attributes.inode;
            return value;
        }
        ++namespace_stats; auto value = selected;
        if (change_before_rename && namespace_stats > 1) ++value.attributes.inode;
        if (postpublish_wrong && renamed) ++value.attributes.inode;
        return value;
    }
    Result<usize> read(posix::Fd fd, std::span<std::byte> bytes)
    {
        check(fd == 4 && fds[4] && !bytes.empty()); ++read_calls;
        if (fault("read")) return error();
        if (interrupts) { --interrupts; return Status::interrupted(); }
        if (overreport) return bytes.size() + 1;
        if (zero_io) return usize{0};
        if (read_offset == text.size())
        {
            if (extra_eof) { bytes[0] = std::byte{'!'}; return usize{1}; }
            return usize{0};
        }
        usize count = text.size() - read_offset;
        if (count > bytes.size()) count = bytes.size();
        if (short_io && count > 1) count = 1;
        for (usize i = 0; i < count; ++i) bytes[i] = static_cast<std::byte>(text[read_offset + i]);
        read_offset += count; return count;
    }
    Result<usize> write(posix::Fd fd, std::span<const std::byte> bytes)
    {
        check(fd == 5 && fds[5] && !bytes.empty()); ++write_calls;
        if (fault("write")) return error();
        if (interrupts) { --interrupts; return Status::interrupted(); }
        if (overreport) return bytes.size() + 1;
        if (zero_io) return usize{0};
        const usize count = short_io ? 1 : bytes.size();
        temporary.append(reinterpret_cast<const char *>(bytes.data()), count); return count;
    }
    Status fsync(posix::Fd fd)
    {
        check((fd == 3 || fd == 5) && fds[fd]);
        return fault(fd == 3 ? "sync-parent" : "sync-staging") ? error() : Status::success();
    }
    Status close(posix::Fd fd)
    {
        check(fd >= 3 && fd <= 5 && fds[fd]); fds[fd] = false;
        return fault(fd == 3 ? "close-parent" : fd == 4 ? "close-selected" : "close-staging") ? error() : Status::success();
    }
    Status unlinkat(posix::Fd fd, std::string_view name, u32 flags)
    {
        check(fd == 3 && fds[3] && stage_exists && name.starts_with(".nt-") && flags == 0 && !renamed);
        if (fault("cleanup-staging")) return error();
        stage_exists = false; return Status::success();
    }
    Status renameat(posix::Fd from, std::string_view oldname, posix::Fd to, std::string_view newname)
    {
        check(from == 3 && to == 3 && fds[3] && oldname.starts_with(".nt-") && newname == "draft.txt" && stage_exists && !fds[5]);
        const bool failed = fault("rename");
        if (!failed || mutate_rename_error)
        {
            renamed = true; stage_exists = false; text = temporary; selected = stage; selected.size = temporary.size();
        }
        return failed ? error() : Status::success();
    }
    usize read_offset{};
};
static_assert(NotesHandoffProvider<Provider> && NotesHandoffProvider<posix::PosixService>);
static std::span<const std::byte> bytes(std::string_view value)
{
    return {reinterpret_cast<const std::byte *>(value.data()), value.size()};
}
static void retired(const Provider &p) { check(!p.fds[3] && !p.fds[4] && !p.fds[5]); }
int main()
{
    Provider display;
    fs::DirectoryListing listing{}; listing.count = 1;
    static_cast<void>(listing.entries[0].name.assign("draft.txt"));
    listing.entries[0].metadata = {.type=display.selected.type, .size=display.selected.size, .mode=display.selected.mode,
        .uid=display.selected.uid, .gid=display.selected.gid, .link_count=1, .attributes=display.selected.attributes};
    listing.entries[0].metadata.attributes.valid &= ~static_cast<u32>(fs::Attribute::device);
    auto captured_display = capture_notes_display(display, "/tmp/private", listing); retired(display);
    check(captured_display && notes_handoff_same_file(notes_listing_status(listing.entries[0].metadata), display.selected));
    const auto display_boundaries = display.calls;
    for (int failure = 0; failure < display_boundaries; ++failure)
    {
        Provider p; auto rows = listing; p.fail_at = failure;
        auto result = capture_notes_display(p, "/tmp/private", rows); retired(p); check(!result);
    }
    Provider stale_display; auto stale_rows = listing; stale_rows.entries[0].metadata.attributes.inode++;
    check(!capture_notes_display(stale_display, "/tmp/private", stale_rows)); retired(stale_display);
    Provider changed_display; changed_display.replace_folder = true;
    check(!capture_notes_display(changed_display, "/tmp/private", listing)); retired(changed_display);
    Provider impossible; auto excessive = listing; excessive.count = excessive.entries.size() + 1;
    check(!capture_notes_display(impossible, "/tmp/private", excessive) && !impossible.calls); retired(impossible);
    Provider opening; auto opened = open_selected_notes(opening, opening.target()); retired(opening);
    check(opened && opened.value().text.view() == opening.text && opened.value().target.path.view() == "/tmp/private/draft.txt");
    const auto open_boundaries = opening.calls;
    for (int failure = 0; failure < open_boundaries; ++failure)
    {
        Provider p; p.fail_at = failure;
        auto result = open_selected_notes(p, p.target()); retired(p);
        check(!result && p.text == "Original English\n" && !p.renamed);
    }
    for (usize count : {usize{0}, usize{1}, usize{1023}})
    {
        Provider p; p.text.assign(count, 'A'); p.selected.size = count; p.short_io = true; p.interrupts = 32;
        auto result = open_selected_notes(p, p.target()); retired(p); check(result && result.value().text.view() == p.text);
    }
    for (int condition = 0; condition < 7; ++condition)
    {
        Provider p;
        if (condition == 0) p.interrupts = 33;
        if (condition == 1) p.zero_io = true;
        if (condition == 2) p.overreport = true;
        if (condition == 3) p.extra_eof = true;
        if (condition == 4) p.swap_after_open = true;
        if (condition == 5) p.change_after_read = true;
        if (condition == 6) p.replace_folder = true;
        auto result = open_selected_notes(p, p.target()); retired(p); check(!result && !p.renamed);
        if (condition == 0) check(p.read_calls == 33);
    }
    for (int mutation = 0; mutation < 12; ++mutation)
    {
        Provider p; auto target = p.target();
        if (mutation == 0) target.file.uid++;
        if (mutation == 1) target.file.gid++;
        if (mutation == 2) target.file.link_count++;
        if (mutation == 3) target.file.type = fs::NodeType::directory;
        if (mutation == 4) target.file.type = fs::NodeType::symlink;
        if (mutation == 5) target.file.mode |= 0040;
        if (mutation == 6) target.directory.mode |= 0001;
        if (mutation == 7) target.directory.uid++;
        if (mutation == 8) target.file.attributes.valid = 0;
        if (mutation == 9) target.file.attributes.inode++;
        if (mutation == 10) target.file.size = 1024;
        if (mutation == 11) static_cast<void>(target.path.assign("/tmp/private/other.txt"));
        auto result = open_selected_notes(p, target); retired(p); check(!result && !p.renamed);
    }
    for (int c = 0; c < 256; ++c)
    {
        Provider p; p.text.assign(1, static_cast<char>(c)); p.selected.size = 1;
        auto result = open_selected_notes(p, p.target()); retired(p);
        check(result.ok() == (c == '\n' || c == '\t' || (c >= 32 && c < 127)));
        if (result) check(result.value().text.size() == 1 && result.value().text.view()[0] == static_cast<char>(c));
    }
    const std::string changed{"Changed English\n"};
    Provider saving; const auto target = saving.target();
    auto saved = save_selected_notes(saving, target, bytes(changed)); retired(saving);
    check(saved.complete() && saving.text == changed && saved.published.attributes.inode != target.file.attributes.inode);
    const auto save_boundaries = saving.calls;
    for (int failure = 0; failure < save_boundaries; ++failure)
    {
        for (bool mutate : {false, true})
        {
            Provider p; p.fail_at = failure; p.mutate_rename_error = mutate;
            auto result = save_selected_notes(p, p.target(), bytes(changed)); retired(p);
            check(!result.complete() && (result.publication_attempted || p.text == "Original English\n"));
            check(!p.renamed || result.publication_attempted);
            if (result.publication_attempted)
                for (const auto &event : p.events) check(event != "cleanup-staging");
        }
    }
    for (int condition = 0; condition < 8; ++condition)
    {
        Provider p;
        if (condition == 0) p.interrupts = 33;
        if (condition == 1) p.zero_io = true;
        if (condition == 2) p.overreport = true;
        if (condition == 3) p.change_before_rename = true;
        if (condition == 4) p.replace_folder = true;
        if (condition == 5) p.postpublish_wrong = true;
        if (condition == 6) p.replace_temporary = true;
        if (condition == 7) p.collisions = 32;
        auto result = save_selected_notes(p, p.target(), bytes(changed)); retired(p); check(!result.complete());
        check(condition == 5 ? result.publication_attempted && result.replaced : !result.publication_attempted && !p.renamed);
        if (condition == 0) check(p.write_calls == 33);
        if (condition == 6) check(p.stage_exists && !result.cleanup.ok());
    }
    for (usize count : {usize{0}, usize{1}, usize{1023}})
    {
        Provider p; std::string content(count, 'X'); p.short_io = true; p.interrupts = 32;
        auto result = save_selected_notes(p, p.target(), bytes(content)); retired(p);
        check(result.complete() && p.text == content && result.published.size == content.size());
    }
    for (int malformed = 0; malformed < 7; ++malformed)
    {
        Provider p;
        if (malformed == 0) p.stage.uid++;
        if (malformed == 1) p.stage.gid++;
        if (malformed == 2) p.stage.link_count++;
        if (malformed == 3) p.stage.type = fs::NodeType::symlink;
        if (malformed == 4) p.stage.type = fs::NodeType::directory;
        if (malformed == 5) p.stage.mode |= 0004;
        if (malformed == 6) p.stage.attributes.valid = 0;
        auto result = save_selected_notes(p, p.target(), bytes(changed)); retired(p);
        check(!result.complete() && !result.publication_attempted && p.stage_exists && !result.cleanup.ok() && p.text == "Original English\n");
        for (const auto &event : p.events) check(event != "cleanup-staging");
    }
    Provider twice; auto captured = twice.target();
    auto first = save_selected_notes(twice, captured, bytes("First")); retired(twice); check(first.complete());
    auto stale = save_selected_notes(twice, captured, bytes("Wrong")); retired(twice); check(!stale.publication_attempted && twice.text == "First");
    captured.file = first.published;
    auto second = save_selected_notes(twice, captured, bytes("Second")); retired(twice); check(second.complete() && twice.text == "Second");
    for (std::string_view name : {"", ".", "..", "bad/name", "bad\\name", "line\n", "12345678901234567890123456789012"})
        check(!make_notes_target("/tmp/private", name, {twice.directory, twice.selected}));
    for (std::string_view path : {"tmp/private", "/tmp//private", "/tmp/../private", "/tmp/private/", "/tmp/./private"})
        check(!make_notes_target(path, "draft.txt", {twice.directory, twice.selected}));
    Provider invalid; check(!save_selected_notes(invalid, invalid.target(), bytes(std::string(1024, 'X'))).publication_attempted);
    check(!save_selected_notes(invalid, invalid.target(), bytes(std::string{"A\0B", 3})).publication_attempted); retired(invalid);
    std::printf("DESKTOP_HANDOFF_HOSTED_PASS checks=%zu isolated_execution=0 hardware_execution=0\n", checks);
}

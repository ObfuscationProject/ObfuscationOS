#include "modules/system-gui/notes_save.hpp"
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

using namespace ok;
using namespace obfuscationos::desktop;
static usize checks{};
static void check(bool value)
{
    ++checks;
    if (!value) { std::fprintf(stderr, "DESKTOP_NOTES_CHECK_FAILED check=%zu\n", checks); std::abort(); }
}
struct Provider final
{
    u32 owner{1000}; int fail_at{-1}, second_fail_at{-1}, calls{}, collisions{}, writes{}, destination_stats{};
    bool folder_exists{true}, destination_exists{true}, temporary_exists{}, renamed{}, interrupted{}, short_write{},
         zero_write{}, oversized_write{}, changed{}, cleanup_failure{}, staging_wrong_mode{}, metadata_missing{}, mutate_rename_error{}, appeared{}, disappeared{}, changed_gid{}, changed_mode{}, changed_device{};
    u32 directory_mode{0700}, destination_uid{1000}, destination_links{1};
    fs::NodeType destination_type{fs::NodeType::regular};
    std::string destination{"original"}, staging;
    std::vector<std::string> events;
    std::array<bool, 6> descriptors{};
    u32 euid() const { return owner; }
    u32 egid() const { return owner; }
    sched::ProcessId getpid() const { return 7; }
    bool fault(const char *name) { events.emplace_back(name); const int call = calls++; return call == fail_at || call == second_fail_at; }
    static Status error() { return Status::io_error("injected storage failure"); }
    Result<posix::Fd> open(std::string_view path, u32 flags, u32 mode)
    {
        check(path == "/tmp" && mode == 0 && (flags & posix::o_NOFOLLOW) && (flags & posix::o_DIRECTORY));
        if (fault("open-root")) return error();
        descriptors[3] = true; return 3;
    }
    Status mkdirat(posix::Fd fd, std::string_view path, u32 mode)
    {
        check(fd == 3 && descriptors[3] && path == (owner ? "notes-user" : "notes-root") && mode == 0700);
        if (fault("mkdir")) return error();
        if (folder_exists) return Status::already_exists();
        folder_exists = true; return Status::success();
    }
    Result<posix::Fd> openat(posix::Fd fd, std::string_view path, u32 flags, u32 mode)
    {
        check(fd >= 3 && fd <= 4 && descriptors[fd] && (flags & posix::o_NOFOLLOW) && (flags & posix::o_CLOEXEC));
        if (fd == 3)
        {
            check(path == (owner ? "notes-user" : "notes-root") && (flags & posix::o_DIRECTORY) && mode == 0);
            if (fault("open-directory")) return error();
            descriptors[4] = true; return 4;
        }
        check(path.starts_with(".notes-7-") && path.ends_with(".tmp") && (flags & posix::o_CREAT) &&
              (flags & posix::o_EXCL) && !(flags & posix::o_TRUNC) && mode == 0600);
        if (fault("open-staging")) return error();
        if (collisions) { --collisions; return Status::already_exists(); }
        temporary_exists = true; staging.clear(); descriptors[5] = true; return 5;
    }
    Result<posix::FileStatus> fstat(posix::Fd fd)
    {
        check((fd == 4 || fd == 5) && descriptors[fd]);
        if (fault(fd == 4 ? "stat-directory" : "stat-staging")) return error();
        posix::FileStatus metadata{};
        metadata.type = fd == 4 ? fs::NodeType::directory : fs::NodeType::regular;
        metadata.uid = metadata.gid = owner;
        metadata.mode = fs::mode_for(metadata.type, fd == 4 ? directory_mode : staging_wrong_mode ? 0644 : 0600);
        metadata.attributes.inode = fd; metadata.attributes.device = {0, 1};
        if (!metadata_missing) { metadata.attributes.mark(fs::Attribute::inode); metadata.attributes.mark(fs::Attribute::device); }
        return metadata;
    }
    Result<posix::FileStatus> statat(posix::Fd fd, std::string_view path, u32 flags)
    {
        check(fd == 4 && descriptors[4] && path == "note.txt" && flags == posix::at_SYMLINK_NOFOLLOW);
        if (fault("stat-destination")) return error();
        ++destination_stats;
        if (appeared && destination_stats == 1) return Status::not_found();
        if (disappeared && destination_stats == 2) return Status::not_found();
        if (!destination_exists) return Status::not_found();
        posix::FileStatus metadata{}; metadata.type = destination_type;
        metadata.uid = destination_uid; metadata.gid = owner; metadata.link_count = destination_links;
        metadata.mode = fs::mode_for(metadata.type, 0644); metadata.size = destination.size();
        metadata.attributes.inode = changed && !staging.empty() ? 11 : 10; metadata.attributes.device = {0, 1};
        if (destination_stats == 2)
        {
            if (changed_gid) ++metadata.gid;
            if (changed_mode) metadata.mode ^= 0020;
            if (changed_device) ++metadata.attributes.device.minor;
        }
        metadata.attributes.mark(fs::Attribute::inode); metadata.attributes.mark(fs::Attribute::device); return metadata;
    }
    Result<usize> write(posix::Fd fd, std::span<const std::byte> bytes)
    {
        check(fd == 5 && descriptors[5] && !bytes.empty() && staging.size() % 1024 + bytes.size() <= 1024);
        ++writes;
        if (fault("write")) return error();
        if (interrupted) { interrupted = false; return Status::interrupted(); }
        if (zero_write) return usize{0};
        if (oversized_write) return bytes.size() + 1;
        const usize count = short_write && bytes.size() > 3 ? 3 : bytes.size();
        staging.append(reinterpret_cast<const char *>(bytes.data()), count); return count;
    }
    Status fsync(posix::Fd fd)
    {
        check(fd >= 3 && fd <= 5 && descriptors[fd]);
        if (fault(fd == 3 ? "sync-root" : fd == 4 ? "sync-directory" : "sync-staging")) return error();
        return Status::success();
    }
    Status close(posix::Fd fd)
    {
        check(fd >= 3 && fd <= 5 && descriptors[fd]); descriptors[fd] = false;
        if (fault(fd == 3 ? "close-root" : fd == 4 ? "close-directory" : "close-staging")) return error();
        return Status::success();
    }
    Status renameat(posix::Fd oldfd, std::string_view oldpath, posix::Fd newfd, std::string_view newpath)
    {
        check(oldfd == 4 && newfd == 4 && descriptors[4] && !descriptors[5] && temporary_exists &&
              oldpath.starts_with(".notes-") && newpath == "note.txt");
        const bool failed = fault("rename");
        if (failed && !mutate_rename_error) return error();
        destination = staging; destination_exists = true; temporary_exists = false; renamed = true; return failed ? error() : Status::success();
    }
    Status unlinkat(posix::Fd fd, std::string_view path, u32 flags)
    {
        check(fd == 4 && descriptors[4] && !descriptors[5] && temporary_exists && path.starts_with(".notes-") && flags == 0);
        if (fault("unlink") || cleanup_failure) return error();
        temporary_exists = false; return Status::success();
    }
};
static_assert(NotesFileProvider<Provider> && NotesFileProvider<posix::PosixService>);
static NotesSaveOutcome save(Provider &p, std::string_view text)
{
    auto result = save_default_notes(p, {reinterpret_cast<const std::byte *>(text.data()), text.size()});
    check(!p.descriptors[3] && !p.descriptors[4] && !p.descriptors[5]);
    check(result.replaced == p.renamed || (result.publication_attempted && !result.status.ok())); return result;
}
int main()
{
    const std::string text(2051, 'a');
    Provider healthy; auto complete = save(healthy, text);
    check(complete.complete() && healthy.destination == text && !healthy.temporary_exists && healthy.writes == 3);
    const int external_calls = healthy.calls;
    for (int fail = 0; fail < external_calls; ++fail)
    {
        Provider p; p.fail_at = fail; auto r = save(p, text);
        check(!r.complete() && !r.status.ok());
        check(p.destination == (p.renamed ? text : "original"));
        check(!p.temporary_exists || (r.publication_attempted && !r.replaced));
    }
    Provider mutate;
    for (int index = 0; index < external_calls; ++index)
        if (healthy.events[static_cast<usize>(index)] == "rename") mutate.fail_at = index;
    mutate.mutate_rename_error = true;
    auto uncertain = save(mutate, text);
    check(!uncertain.complete() && uncertain.publication_attempted && !uncertain.replaced && mutate.destination == text);
    bool destructive_cleanup{}; for (const auto &event : mutate.events) destructive_cleanup |= event == "unlink";
    check(!destructive_cleanup);
    Provider partial; partial.short_write = partial.interrupted = true;
    check(save(partial, text).complete() && partial.destination == text && partial.writes > 600);
    Provider empty; check(save(empty, "").complete() && empty.destination.empty() && empty.writes == 0);
    Provider fresh; fresh.folder_exists = fresh.destination_exists = false;
    check(save(fresh, "new").complete() && fresh.destination == "new");
    Provider root; root.owner = root.destination_uid = 0; check(save(root, "root").complete());
    Provider collisions; collisions.collisions = 31; check(save(collisions, "last").complete());
    Provider exhausted; exhausted.collisions = 32; check(!save(exhausted, "x").complete() && exhausted.destination == "original");
    for (unsigned int control = 0; control < 15; ++control)
    {
        Provider p;
        switch (control)
        {
        case 0: p.zero_write = true; break;
        case 1: p.oversized_write = true; break;
        case 2: p.destination_uid = 2000; break;
        case 3: p.destination_links = 2; break;
        case 4: p.destination_type = fs::NodeType::symlink; break;
        case 5: p.destination_type = fs::NodeType::directory; break;
        case 6: p.directory_mode = 0777; break;
        case 7: p.staging_wrong_mode = true; break;
        case 8: p.metadata_missing = true; break;
        case 9: p.changed = true; break;
        case 10: p.appeared = true; break;
        case 11: p.disappeared = true; break;
        case 12: p.changed_gid = true; break;
        case 13: p.changed_mode = true; break;
        case 14: p.changed_device = true; break;
        }
        auto result = save(p, "control");
        check(!result.complete() && !result.replaced && p.destination == "original" && !p.temporary_exists);
    }
    for (int cleanup_call : {4, 5})
    {
        Provider p; p.fail_at = 3; p.second_fail_at = cleanup_call;
        auto result = save(p, text); check(!result.complete() && !result.cleanup.ok() && !result.publication_attempted);
    }
    int write_call{};
    for (int i = 0; i < external_calls; ++i) if (healthy.events[static_cast<usize>(i)] == "write") { write_call = i; break; }
    for (int cleanup_offset : {1, 3})
    {
        Provider p; p.fail_at = write_call; p.second_fail_at = write_call + cleanup_offset;
        auto result = save(p, text); check(!result.complete() && !result.cleanup.ok() && !p.temporary_exists);
    }
    Provider cleanup; cleanup.zero_write = cleanup.cleanup_failure = true;
    auto failed = save(cleanup, "control");
    check(!failed.complete() && !failed.cleanup.ok() && cleanup.temporary_exists && cleanup.destination == "original");
    // A failed root sync must also be retried when the folder already exists.
    Provider retry; retry.folder_exists = false; retry.fail_at = 4;
    check(!save(retry, "retry").complete() && retry.folder_exists);
    retry.fail_at = -1; retry.events.clear();
    check(save(retry, "retry").complete());
    bool root_sync{}; for (const auto &event : retry.events) root_sync |= event == "sync-root"; check(root_sync);
    std::printf("DESKTOP_NOTES_HOSTED_PASS checks=%zu isolated_execution=0 hardware_execution=0\n", checks);
}

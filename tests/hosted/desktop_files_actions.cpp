#include "modules/system-gui/files_actions.hpp"
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
    if (!condition) { std::fprintf(stderr, "FILES_CHECK_FAILED check=%zu\n", checks); std::abort(); }
}
struct Provider final
{
    int calls{}, fail_at{-1}, source_stats{};
    bool source_exists{true}, target_exists{}, mutation{}, mutate_error{}, wrong_metadata{}, stale{}, nonempty{}, replaced_parent{};
    std::array<bool, 5> descriptors{};
    fs::NodeType source_type{fs::NodeType::regular}, created_type{fs::NodeType::regular};
    std::vector<std::string> events;
    u32 euid() const { return 1000; }
    static Status error() { return Status::io_error("Injected Files failure"); }
    bool fault(const char *label) { events.emplace_back(label); return calls++ == fail_at; }
    static posix::FileStatus metadata(fs::NodeType type, u64 inode, u32 mode)
    {
        posix::FileStatus item{}; item.type = type; item.uid = item.gid = 1000;
        item.mode = fs::mode_for(type, mode); item.attributes.inode = inode; item.attributes.device = {0, 1};
        item.attributes.mark(fs::Attribute::inode); item.attributes.mark(fs::Attribute::device); return item;
    }
    Result<posix::Fd> open(std::string_view parent, u32 flags, u32 mode)
    {
        check(parent == "/tmp" && flags == files_directory_open && mode == 0);
        if (fault("open-parent")) return error();
        check(!descriptors[3]); descriptors[3] = true; return 3;
    }
    Result<posix::Fd> openat(posix::Fd fd, std::string_view name, u32 flags, u32 mode)
    {
        check(fd == 3 && descriptors[3] && name == "new" && (flags & posix::o_NOFOLLOW) && (flags & posix::o_CLOEXEC));
        const bool failed = fault("open-new");
        if (flags & posix::o_CREAT)
        {
            check((flags & posix::o_EXCL) && !(flags & posix::o_TRUNC) && mode == 0600);
            if (!failed || mutate_error) { mutation = target_exists = true; created_type = fs::NodeType::regular; }
        }
        else check(flags == files_directory_open && mode == 0 && target_exists && created_type == fs::NodeType::directory);
        if (failed) return error();
        check(!descriptors[4]); descriptors[4] = true; return 4;
    }
    Status mkdirat(posix::Fd fd, std::string_view name, u32 mode)
    {
        check(fd == 3 && descriptors[3] && name == "new" && mode == 0700);
        const bool failed = fault("mkdir-new");
        if (!failed || mutate_error) { mutation = target_exists = true; created_type = fs::NodeType::directory; }
        return failed ? error() : Status::success();
    }
    Result<posix::FileStatus> fstat(posix::Fd fd)
    {
        check((fd == 3 || fd == 4) && descriptors[fd]);
        if (fault(fd == 3 ? "stat-parent" : "stat-created")) return error();
        if (fd == 3) return metadata(fs::NodeType::directory, replaced_parent ? 30 : 3, 0777);
        auto item = metadata(created_type, 4, created_type == fs::NodeType::regular ? 0600 : 0700);
        if (wrong_metadata) item.uid = 1001;
        return item;
    }
    Result<posix::FileStatus> statat(posix::Fd fd, std::string_view name, u32 flags)
    {
        check(fd == 3 && descriptors[3] && (name == "old" || name == "new") && flags == posix::at_SYMLINK_NOFOLLOW);
        if (fault(name == "old" ? "stat-source" : "stat-target")) return error();
        if (name == "new") return target_exists ? Result<posix::FileStatus>{metadata(created_type, 4, 0600)} : Status::not_found();
        ++source_stats;
        if (!source_exists) return Status::not_found();
        auto item = metadata(source_type, 10, 0600);
        if (stale && source_stats == 2) ++item.attributes.inode;
        return item;
    }
    Status renameat(posix::Fd from, std::string_view oldname, posix::Fd to, std::string_view newname)
    {
        check(from == 3 && to == 3 && descriptors[3] && oldname == "old" && newname == "new" && source_exists && !target_exists);
        const bool failed = fault("rename");
        if (!failed || mutate_error) { mutation = target_exists = true; source_exists = false; }
        return failed ? error() : Status::success();
    }
    Status unlinkat(posix::Fd fd, std::string_view name, u32 flags)
    {
        check(fd == 3 && descriptors[3] && name == "old" && source_exists &&
            flags == (source_type == fs::NodeType::directory ? 0x0200u : 0));
        const bool failed = fault("remove");
        if (nonempty) return Status::busy("Folder is not empty");
        if (!failed || mutate_error) { mutation = true; source_exists = false; }
        return failed ? error() : Status::success();
    }
    Status fsync(posix::Fd fd)
    {
        check((fd == 3 || fd == 4) && descriptors[fd]);
        return fault(fd == 3 ? "sync-parent" : "sync-created") ? error() : Status::success();
    }
    Status close(posix::Fd fd)
    {
        check((fd == 3 || fd == 4) && descriptors[fd]); descriptors[fd] = false;
        return fault(fd == 3 ? "close-parent" : "close-created") ? error() : Status::success();
    }
};
static_assert(FilesProvider<Provider> && FilesProvider<posix::PosixService>);
static FilesOutcome act(Provider &p, FilesAction action, const posix::FileStatus *expected)
{
    const auto parent = Provider::metadata(fs::NodeType::directory, 3, 0777);
    auto result = perform_file_action(p, "/tmp", action,
        action == FilesAction::rename || action == FilesAction::remove ? "old" : "new", "new", expected, &parent);
    check(!p.descriptors[3] && !p.descriptors[4]);
    check(!result.changed || p.mutation); return result;
}
int main()
{
    for (const auto action : {FilesAction::new_file, FilesAction::new_folder, FilesAction::rename, FilesAction::remove})
    {
        for (const auto type : {fs::NodeType::regular, fs::NodeType::directory})
        {
            const auto expected = Provider::metadata(type, 10, 0600);
            Provider healthy; healthy.source_type = type;
            check(act(healthy, action, &expected).complete() && healthy.mutation);
            const int boundaries = healthy.calls;
            for (int fault = 0; fault < boundaries; ++fault)
            {
                for (bool mutate_error : {false, true})
                {
                    Provider p; p.source_type = type; p.fail_at = fault; p.mutate_error = mutate_error;
                    auto result = act(p, action, &expected);
                    check(!result.complete());
                    check(result.publication_attempted || !p.mutation);
                    if (p.mutation && !result.changed) check(!result.status.ok() && result.publication_attempted);
                }
            }
        }
    }
    auto expected = Provider::metadata(fs::NodeType::regular, 10, 0600);
    for (FilesAction action : {FilesAction::rename, FilesAction::remove})
    {
        Provider stale; stale.stale = true;
        check(!act(stale, action, &expected).publication_attempted && !stale.mutation);
        Provider changed; auto old = expected; ++old.uid;
        check(!act(changed, action, &old).publication_attempted && !changed.mutation);
        Provider missing; missing.source_exists = false;
        check(!act(missing, action, &expected).publication_attempted && !missing.mutation);
        Provider unselected; check(!act(unselected, action, nullptr).publication_attempted);
    }
    for (const auto action : {FilesAction::new_file, FilesAction::new_folder, FilesAction::rename})
    {
        Provider collision; collision.target_exists = true;
        check(!act(collision, action, &expected).publication_attempted && !collision.mutation);
    }
    for (auto name : {"", ".", "..", "../old", "a/b", "a\\b", "a\n", "a\x7f", "\xc3\xa9"})
    {
        Provider p; auto result = perform_file_action(p, "/tmp", FilesAction::new_file, name);
        check(!result.publication_attempted && !result.complete() && p.calls == 0);
    }
    for (usize length : {usize{1}, usize{31}, usize{32}})
        check(files_name_valid(std::string(length, 'a')) == (length <= files_name_limit));
    for (auto type : {fs::NodeType::symlink, fs::NodeType::device})
    {
        Provider p; p.source_type = type;
        auto selected = select_file_action(p, "/tmp", "old");
        check(!selected && !p.descriptors[3] && !p.mutation);
    }
    auto multiple = expected; multiple.link_count = 2; check(!files_metadata_valid(multiple));
    auto missing_inode = expected; missing_inode.attributes = {}; check(!files_metadata_valid(missing_inode));
    for (FilesAction action : {FilesAction::new_file, FilesAction::new_folder})
    {
        Provider wrong; wrong.wrong_metadata = true;
        auto result = act(wrong, action, nullptr);
        check(!result.complete() && result.changed && result.publication_attempted);
    }
    Provider nonempty; nonempty.source_type = fs::NodeType::directory; nonempty.nonempty = true;
    auto folder = Provider::metadata(fs::NodeType::directory, 10, 0600);
    auto refused = act(nonempty, FilesAction::remove, &folder);
    check(!refused.complete() && refused.publication_attempted && nonempty.source_exists && !nonempty.mutation);
    for (int fault = 0; fault < 3; ++fault)
    {
        Provider p; p.fail_at = fault;
        auto result = select_file_action(p, "/tmp", "old");
        check(!result && !p.descriptors[3] && !p.mutation);
    }
    Provider selected; check(select_file_action(selected, "/tmp", "old").ok() && !selected.descriptors[3]);
    for (auto action : {FilesAction::new_file, FilesAction::new_folder, FilesAction::rename, FilesAction::remove})
    {
        Provider moved; moved.replaced_parent = true;
        check(!act(moved, action, &expected).publication_attempted && !moved.mutation);
    }
    for (bool item : {false, true})
    {
        Provider captured; auto selection = capture_file_action(captured, "/tmp", item ? "old" : "");
        check(selection && !captured.descriptors[3] && selection.value().directory.attributes.inode == 3);
        for (int fault = 0; fault < captured.calls; ++fault)
        {
            Provider failed; failed.fail_at = fault;
            check(!capture_file_action(failed, "/tmp", item ? "old" : "") && !failed.descriptors[3] && !failed.mutation);
        }
    }
    std::printf("DESKTOP_FILES_HOSTED_PASS checks=%zu isolated_execution=0 hardware_execution=0\n", checks);
}

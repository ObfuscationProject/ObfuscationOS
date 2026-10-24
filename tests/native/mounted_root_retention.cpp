#include "../../drivers/virtio/block.hpp"
#include <ok/arch/clock.hpp>
#include <ok/arch/realtime.hpp>
#include <ok/core/entry.hpp>
#include <ok/fs/ext4_completion.hpp>
#include <ok/fs/ext4_mounted_metadata.hpp>
#include <ok/user/runtime.hpp>
#include <new>
#include "journalled_root_fixture.hpp"

using namespace ok;
extern "C" void ok_platform_console_init();
extern "C" void ok_platform_console_write_char(char);
extern "C" void ok_platform_debug_exit(u32);
extern "C" const std::byte mroot_archive_start[], mroot_archive_end[];

namespace
{
void emit(std::string_view text)
{ for (const char value : text) ok_platform_console_write_char(value); }
void number(u64 value)
{
    char digits[20]; usize count{};
    do { digits[count++] = static_cast<char>('0' + value % 10); value /= 10; } while (value);
    while (count) ok_platform_console_write_char(digits[--count]);
}
void field(std::string_view name, u64 value)
{ emit(" "); emit(name); emit("="); number(value); }
[[noreturn]] void stop(bool success)
{
    ok_platform_debug_exit(success ? 0x10u : 0x11u);
    for (;;) asm volatile("" ::: "memory");
}
void check(bool success, std::string_view reason)
{
    if (success) return;
    emit("MROOT_FIXTURE_FAIL reason="); emit(reason); emit("\n"); stop(false);
}
u32 crc(std::span<const std::byte> bytes)
{
    return fs::jbd2::detail::crc32c(~u32{0},
        {reinterpret_cast<const u8 *>(bytes.data()), bytes.size()});
}

// Fault controls are armed only for final sealing. Completed events bind real
// Virtio calls; an injected error explicitly records that the device was not called.
class ObservedDevice final : public driver::BlockDevice
{
  public:
    struct Counts { u64 reads{}, writes{}, flushes{}; bool operator==(const Counts &) const = default; };
    void bind(driver::BlockDevice &device)
    { check(!device_, "single transport binding"); device_ = &device; }
    void select(u8 action) { check(action <= 2, "bounded seal fault action"); action_ = action; }
    void arm()
    {
        check(!armed_, "one seal control arm"); armed_ = true; seal_start_ = ordinal;
        emit("MROOT_SEAL_ARM"); field("action", action_); field("ordinal", seal_start_); emit("\n");
    }
    [[nodiscard]] u8 action() const { return action_; }
    [[nodiscard]] Counts counts() const { return {reads, writes, flushes}; }
    [[nodiscard]] Status injected_status() const
    { return Status::io_error("injected native clean-seal transport failure"); }
    driver::BlockGeometry geometry() const override { return device_->geometry(); }
    Status read_blocks(u64 sector, std::span<std::byte> bytes) override
    { ++reads; return device_->read_blocks(sector, bytes); }
    Status write_blocks(u64 sector, std::span<const std::byte> bytes) override
    {
        const bool injected = armed_ && action_ == 2 && ordinal + 1 == seal_start_ + 4;
        const auto status = injected ? injected_status() : device_->write_blocks(sector, bytes);
        ++ordinal; ++writes;
        emit("MROOT_IO"); field("ordinal", ordinal); emit(" kind=write");
        field("sector", sector); field("bytes", bytes.size()); field("crc32c", crc(bytes));
        field("status", static_cast<u32>(status.code())); field("device_called", !injected); emit("\n");
        if (injected) { injected_ = true; emit("MROOT_INJECTED kind=write before-device=1\n"); }
        return status;
    }
    Status flush() override
    {
        const bool injected = armed_ && action_ == 1 && ordinal + 1 == seal_start_ + 1;
        const auto status = injected ? injected_status() : device_->flush();
        ++ordinal; ++flushes;
        emit("MROOT_IO"); field("ordinal", ordinal); emit(" kind=flush sector=0 bytes=0 crc32c=0");
        field("status", static_cast<u32>(status.code())); field("device_called", !injected); emit("\n");
        if (injected) { injected_ = true; emit("MROOT_INJECTED kind=flush before-device=1\n"); }
        return status;
    }
    [[nodiscard]] bool injected() const { return injected_; }
    u64 ordinal{}, reads{}, writes{}, flushes{};
  private:
    driver::BlockDevice *device_{};
    u64 seal_start_{};
    u8 action_{};
    bool armed_{}, injected_{};
};

using Mount = fs::Ext4MountedMetadata<1>;
struct CleanProbe
{
    fs::Ext4RecoveryBinding binding;
    fs::Ext4ReplayPreview<6, 2> preview{true, true};
};
ObservedDevice transport;
Mount::Registry registry;
Mount::Registry::Registration registration;
alignas(Mount) std::array<std::byte, sizeof(Mount)> filesystem_storage{}, fresh_storage{};
alignas(CleanProbe) std::array<std::byte, sizeof(CleanProbe)> clean_storage{};
// Borrower storage follows provider storage and is destroyed explicitly first.
alignas(fs::VirtualFileSystem) std::array<std::byte, sizeof(fs::VirtualFileSystem)> alias_storage{};
Mount *filesystem{}, *fresh{};
fs::VirtualFileSystem *aliases{};
fs::VfsMountHandle root_attachment, child_attachment, alias_attachment;
ObservedDevice::Counts mounted_counts;
u64 original_session{};
constexpr std::string_view payload{"ROOT-RETENTION-V1"};

u32 holds(u32 inode)
{
    auto snapshot = filesystem->lifetime_snapshot(inode);
    check(snapshot.ok(), "mounted lifetime snapshot");
    check(snapshot.value().total() == snapshot.value().holds[static_cast<usize>(fs::Ext4InodeHold::descriptor)],
          "all fixture node holds are real descriptor/path/cwd retains");
    emit("MROOT_INODE_HOLDS"); field("inode", inode); field("total", snapshot.value().total());
    field("phase", static_cast<u32>(snapshot.value().phase)); emit("\n");
    return snapshot.value().total();
}
void unchanged(ObservedDevice::Counts before, std::string_view reason)
{ check(transport.counts() == before, reason); }
void stale_context(fs::VirtualFileSystem &vfs, fs::PathHandle handle, bool root)
{
    fs::ResolveContext context{};
    if (root) context.root = handle; else context.start = handle;
    const auto before = transport.counts();
    auto denied = vfs.resolve(context, root ? "/seed" : "seed");
    check(!denied && denied.status().code() == StatusCode::not_found, "stale mount context refused");
    unchanged(before, "stale context refused before provider I/O");
}
void check_seed(fs::Node &node)
{
    auto metadata = node.query_metadata();
    check(metadata && metadata.value().type == fs::NodeType::regular && metadata.value().size == 4096 &&
          metadata.value().uid == 1000 && metadata.value().gid == 1001 &&
          (metadata.value().mode & 07777u) == 0600u, "retained seed metadata");
    auto bytes = node.read(0, 4096);
    check(bytes && bytes.value().size == 4096, "full retained seed read");
    for (usize i = 0; i != 4096; ++i)
    {
        const auto expected = i >= 100 && i < 100 + payload.size() ?
            static_cast<u8>(payload[i - 100]) : static_cast<u8>(i * 17 + 29);
        check(bytes.value().data[i] == std::byte{expected}, "fresh exact seed bytes");
    }
    emit("MROOT_DATA"); field("bytes", bytes.value().size); field("payload_bytes", payload.size());
    field("crc32c", crc(std::span<const std::byte>{bytes.value().data}.first(bytes.value().size))); emit("\n");
}

class Fixture final : public KernelExtension
{
  public:
    Status start(Kernel &kernel) override
    {
        check(!kernel_, "single fixture start"); kernel_ = &kernel;
        usize count{};
        for (const auto &process : kernel.scheduler().processes())
            if (!process.threads().empty() && process.threads()[0].native_active)
            {
                ++count; pid_ = process.pid();
                check(process.name() == "init" && process.parent_pid() == 0 &&
                      process.resources().personality == sched::UserPersonality::linux,
                      "unique direct Linux /init");
            }
        check(count == 1, "one initial native executable");
        auto reaper = kernel.scheduler().create_process("retention-fixture-holder", {});
        check(reaper.ok(), "diagnostic holder reservation"); holder_ = reaper.value();
        auto *process = kernel.scheduler().find(pid_);
        auto *holder = kernel.scheduler().find(holder_);
        check(process && holder && holder->add_child(pid_).ok(), "init diagnostic parent reservation");
        process->set_parent(holder_);
        const auto &credentials = process->credentials();
        check(credentials.uid == 1000 && credentials.euid == 1000 && credentials.gid == 1000 &&
              credentials.egid == 1000 && !credentials.kernel_space, "initial unprivileged credentials");
        emit("MROOT_CREDENTIALS uid=1000 euid=1000 gid=1000 egid=1000 before-entry=1\n");
        return {};
    }
    bool after_step()
    {
        check(ok_userland_status().ok(), "native runtime status");
        auto &scheduler = kernel_->scheduler();
        const auto *process = scheduler.find(pid_);
        check(process != nullptr, "init diagnostic retained");
        const auto &resources = process->resources();
        if (!captured_ && resources.files.contains(3) && resources.files.contains(4) &&
            resources.files.contains(5) && resources.cwd_node && resources.cwd_mount_id == child_attachment.id())
        {
            seed_description_ = resources.files.entry(3)->description;
            directory_description_ = resources.files.entry(5)->description;
            const auto *seed = scheduler.open_description(seed_description_);
            const auto *directory = scheduler.open_description(directory_description_);
            check(seed && directory && seed->node && directory->node && seed->readable && seed->writable &&
                  seed->mount_id == root_attachment.id() && directory->mount_id == child_attachment.id() &&
                  directory->node == resources.cwd_node &&
                  resources.files.entry(4)->description == seed_description_, "actual fd/dup/cwd identity");
            auto &holder = scheduler.find(holder_)->resources();
            check(scheduler.install_descriptor(holder, 10, seed_description_).ok() &&
                  scheduler.install_descriptor(holder, 11, seed_description_).ok() &&
                  scheduler.install_descriptor(holder, 12, directory_description_).ok(), "retain actual shared OFDs");
            check(resources.cwd_node->retain().ok(), "retain actual cwd for later drainage");
            holder.cwd_node = resources.cwd_node; holder.cwd_mount_id = resources.cwd_mount_id;
            check(holder.cwd.assign("/child").ok(), "diagnostic cwd path");
            captured_ = true;
            check(holds(journalled_fixture::seed.number) == 1 && holds(journalled_fixture::root.number) == 4 &&
                  holds(journalled_fixture::child.number) == 1, "captured OFD/cwd/covered hold counts");
            emit("MROOT_CAPTURE shared_ofd=1 dup=1 directory_ofd=1 cwd=1 boot_cwd=1 seed_holds=1 root_holds=4 covered_holds=1\n");
        }
        if (captured_)
            for (const auto &child : scheduler.processes())
                if (child.parent_pid() == pid_ && !child.threads().empty() && child.threads()[0].native_active &&
                    child.resources().files.contains(6))
                {
                    const auto &child_resources = child.resources();
                    const auto *own = scheduler.open_description(child_resources.files.entry(6)->description);
                    const auto *seed = scheduler.open_description(seed_description_);
                    check(own && seed && own->node == seed->node &&
                          child_resources.files.entry(3)->description == seed_description_ &&
                          child_resources.files.entry(4)->description == seed_description_ &&
                          child_resources.files.entry(5)->description == directory_description_ &&
                          child_resources.cwd_mount_id == child_attachment.id(), "native inherited descriptor/cwd effects");
                    if (!child_observed_)
                    {
                        child_observed_ = true; child_ = child.pid();
                        check(holds(journalled_fixture::seed.number) == 2 &&
                              holds(journalled_fixture::root.number) == 5, "live native child node holds");
                        emit("MROOT_NATIVE_CHILD execution=active inherited_ofd=1 own_ofd=1 cwd=1 boot_cwd=1 seed_holds=2 root_holds=5\n");
                    }
                }
        if (child_observed_ && !child_reaped_ && !scheduler.find(child_))
        {
            child_reaped_ = true;
            check(holds(journalled_fixture::seed.number) == 1 && holds(journalled_fixture::root.number) == 4,
                  "real child exit releases separate OFD and cloned cwd");
            emit("MROOT_CHILD_REAP observed=1 seed_holds=1 root_holds=4 boot_cwd=1\n");
        }
        if (process->state() != sched::ProcessState::zombie) return false;
        check(process->wait_status() == 0 && captured_ && child_observed_ && child_reaped_ &&
              process->children().empty(), "real user completion and child wait");
        for (const auto &slot : resources.files.entries()) check(!slot.used, "parent exit consumed all fds");
        check(!resources.cwd_node && resources.cwd_mount_id == 0, "parent exit consumed cwd identity");
        check(holds(journalled_fixture::seed.number) == 1 && holds(journalled_fixture::root.number) == 3,
              "diagnostic OFD/cwd and original boot cwd remain");
        const auto mounted = filesystem->report();
        check(mounted.phase == fs::Ext4MountPhase::readable && mounted.status.ok() && mounted.epoch == 2 &&
              transport.writes == mounted_counts.writes + 8 && transport.flushes == mounted_counts.flushes + 9,
              "actual single bounded write and fsync effects");
        const auto *seed = scheduler.open_description(seed_description_);
        check(seed && seed->node, "diagnostic seed OFD remains live");
        auto metadata = seed->node->query_metadata();
        check(metadata && metadata.value().attributes.has(fs::Attribute::change_time) &&
              metadata.value().attributes.has(fs::Attribute::modification_time), "actual write timestamp visibility");
        emit("MROOT_EPOCH epoch=2 size=4096");
        field("ctime_seconds", static_cast<u64>(metadata.value().attributes.change.seconds));
        field("ctime_nanoseconds", metadata.value().attributes.change.nanoseconds);
        field("mtime_seconds", static_cast<u64>(metadata.value().attributes.modification.seconds));
        field("mtime_nanoseconds", metadata.value().attributes.modification.nanoseconds); emit("\n");
        check_seed(*seed->node);
        emit("MROOT_USER_EFFECTS epoch=2 writes=1 fsync=1 parent_exit=0 child_exit=23 child_reaped=1\n");
        finish();
        return true;
    }
  private:
    void finish()
    {
        auto &vfs = kernel_->vfs();
        auto &scheduler = kernel_->scheduler();
        const auto &boot = scheduler.boot_resources();
        check(boot.cwd_node && boot.cwd_mount_id == root_attachment.id(), "original boot cwd is a real root hold");
        emit("MROOT_BOOT_CWD retained=1 root_mount=original drain=required\n");
        auto retained = vfs.resolve({}, "/"); check(retained.ok(), "deliberate retained root path");
        auto path = std::move(retained.value());
        const auto old_root = path.handle();
        const auto &holder = scheduler.find(holder_)->resources();
        const fs::PathHandle old_start{holder.cwd_node, holder.cwd_mount_id};
        check(holds(journalled_fixture::root.number) == 4, "deliberate path adds exact hold");
        const auto before = transport.counts();
        check(vfs.detach(root_attachment).code() == StatusCode::busy, "parent detach waits for covered child");
        check(filesystem->begin_drain().code() == StatusCode::busy, "root attachments block drain");
        unchanged(before, "attachment refusal performs no provider I/O");
        emit("MROOT_ATTACHMENTS_BLOCK child_first=1 begin_drain=busy provider_io=0\n");
        check(vfs.detach(child_attachment).ok(), "detach actual covered child attachment");
        check(holds(journalled_fixture::child.number) == 0, "child detach releases covered path");
        emit("MROOT_DETACH kind=child"); field("id", child_attachment.id()); emit(" covered_release=1\n");
        check(filesystem->begin_drain().code() == StatusCode::busy, "aliases still block drain");
        check(aliases->detach(alias_attachment).ok(), "detach independently cloned alias");
        emit("MROOT_DETACH kind=alias"); field("id", alias_attachment.id()); emit(" own_clone=1\n");
        check(filesystem->begin_drain().code() == StatusCode::busy, "primary root still blocks drain");
        check(vfs.detach(root_attachment).ok(), "detach primary owned root");
        emit("MROOT_DETACH kind=root"); field("id", root_attachment.id()); emit(" own_reference=1\n");
        unchanged(before, "detach and root obligations perform no provider I/O");
        stale_context(vfs, old_root, true); stale_context(vfs, old_start, false);
        check(vfs.detach(root_attachment).code() == StatusCode::bad_descriptor &&
              vfs.detach(child_attachment).code() == StatusCode::bad_descriptor, "permanent attachment tombstones");
        emit("MROOT_STALE root=refused start=refused repeat_detach=refused provider_io=0\n");
        check(filesystem->begin_drain().ok() && filesystem->report().phase == fs::Ext4MountPhase::draining,
              "one-way provider drain admission");
        auto new_root = filesystem->retain_root();
        check(!new_root && new_root.status().code() == StatusCode::busy, "drain closes fresh publication");
        check(path.node()->retain().code() == StatusCode::busy, "drain closes fresh node retains");
        auto denied_read = path.node()->read(0, 1);
        check(!denied_read && denied_read.status().code() == StatusCode::busy, "drain closes provider I/O");
        check(filesystem->freeze_clean().code() == StatusCode::busy, "fd/cwd/path obligations prevent seal");
        unchanged(before, "busy drain/freeze has no provider I/O");
        emit("MROOT_DRAIN_BEGIN fresh_root=refused fresh_node=refused io=refused seal=busy provider_io=0\n");
        check(scheduler.drain_all_resources().ok(), "consume all actual process and boot resources");
        check(!boot.cwd_node && !boot.cwd_mount_id, "fallible drain consumes original boot cwd");
        const auto report = scheduler.resource_drain_report();
        check(report.first_failure.ok() && !report.failed_releases && !report.descriptions_remaining &&
              !report.reservations_remaining && !report.active, "fallible scheduler drain report");
        const auto &consumed = scheduler.find(holder_)->resources();
        check(!consumed.cwd_node && !consumed.cwd_mount_id && !consumed.files.contains(10) &&
              !consumed.files.contains(11) && !consumed.files.contains(12), "consumed diagnostic fd/cwd ownership");
        check(holds(journalled_fixture::seed.number) == 0 && holds(journalled_fixture::root.number) == 1,
              "only deliberate path remains after Scheduler drain");
        emit("MROOT_RESOURCE_DRAIN all=1 first_failure=0 descriptions=0 reservations=0 seed_holds=0 root_holds=1");
        field("descriptors", report.descriptors_consumed); field("cwd", report.cwd_consumed); emit("\n");
        check(filesystem->freeze_clean().code() == StatusCode::busy, "deliberate retained path alone prevents seal");
        unchanged(before, "path-only busy seal performs no provider I/O");
        check(path.release().ok() && !path.node() && holds(journalled_fixture::root.number) == 0,
              "last deliberate path consumed");
        emit("MROOT_PATH_RELEASE last=1 root_holds=0\n");
        transport.arm();
        const auto seal_before = transport.counts();
        const auto sealed = filesystem->freeze_clean();
        if (transport.action())
        {
            const auto failure = transport.injected_status();
            check(transport.injected() && !sealed && sealed.code() == failure.code() &&
                  sealed.message() == failure.message() && filesystem->report().phase == fs::Ext4MountPhase::failed &&
                  filesystem->report().status.code() == failure.code() &&
                  filesystem->report().status.message() == failure.message(), "seal preserves original transport failure");
            const auto failed_counts = transport.counts();
            const auto again = filesystem->freeze_clean();
            check(!again && again.code() == StatusCode::denied &&
                  filesystem->report().status.code() == failure.code() &&
                  filesystem->report().status.message() == failure.message(),
                  "quarantined seal retry is denied and original failure remains recorded");
            unchanged(failed_counts, "failed provider retry performs no I/O");
            emit("MROOT_FAILURE_CONTROL_PASS"); field("action", transport.action());
            emit(" original_error=1 phase=failed clean_success=0 provider_retry_io=0 physical=0 smp=0\n");
            return;
        }
        check(sealed.ok() && filesystem->report().phase == fs::Ext4MountPhase::clean_sealed &&
              transport.writes == seal_before.writes + 2 && transport.flushes == seal_before.flushes + 3,
              "completed exact clean-seal transport sequence");
        emit("MROOT_SEALED writes=2 flushes=3 clean=1\n");
        auto retired_root = filesystem->retain_root();
        check(!retired_root && !filesystem->mount(registry, registration,
              {journalled_fixture::origin, journalled_fixture::sectors}), "sealed provider is one-shot and cannot republish");
        const auto clean_before = transport.counts();
        auto *clean = ::new (clean_storage.data()) CleanProbe{};
        check(clean->binding.inspect(transport, {journalled_fixture::origin, journalled_fixture::sectors}).ok() &&
              clean->binding.info() && !clean->binding.info()->needs_recovery &&
              clean->preview.open(transport, {journalled_fixture::origin, journalled_fixture::sectors}).ok() &&
              clean->preview.ready() && clean->preview.report().empty_log &&
              transport.writes == clean_before.writes && transport.flushes == clean_before.flushes,
              "fresh public read-only clean flag and empty-log inspection");
        clean->~CleanProbe();
        emit("MROOT_CLEAN_PROBE recovery=0 empty=1 checksums=valid\n");
        const auto fresh_before = transport.counts();
        fresh = ::new (fresh_storage.data()) Mount{fs::Ext4MountedPolicy::maintained_noatime};
        check(fresh->mount(registry, registration, {journalled_fixture::origin, journalled_fixture::sectors}).ok(),
              "fresh same-registry mount after original final seal");
        auto reference = fresh->retain_root(); check(reference.ok(), "fresh owned publication");
        auto attached = vfs.mount_owned("/", std::move(reference.value()));
        check(attached && attached.value().id() > child_attachment.id() &&
              attached.value().id() != root_attachment.id(), "fresh attachment uses a new permanent ID");
        auto reopened = vfs.resolve({}, "/seed"); check(reopened.ok(), "fresh retained seed resolution");
        const auto snapshot = fresh->lifetime_snapshot(journalled_fixture::seed.number);
        check(snapshot && snapshot.value().key.session != original_session && snapshot.value().total() == 1,
              "fresh runtime identity and exact retained path");
        emit("MROOT_FRESH_MOUNT same_registry=1 new_session=1"); field("id", attached.value().id()); emit("\n");
        check_seed(*reopened.value().node());
        check(reopened.value().release().ok(), "fresh successful path release");
        stale_context(vfs, old_root, true); stale_context(vfs, old_start, false);
        check(vfs.detach(attached.value()).ok() && fresh->begin_drain().ok() && fresh->close().ok(),
              "fresh detach/drain/close while borrowers alive");
        check(transport.writes == fresh_before.writes && transport.flushes == fresh_before.flushes,
              "fresh reopen preserves sealed disk bytes");
        check(registry.detach(registration).ok(), "original registry can retire after both owners close");
        aliases->~VirtualFileSystem(); aliases = nullptr;
        fresh->~Mount(); fresh = nullptr;
        filesystem->~Mount(); filesystem = nullptr;
        emit("MROOT_FIXTURE_PASS user=executed child=23 reaped=1 attachments=detached resources=drained seal=clean reopen=exact registry=retired physical=0 smp=0");
        field("reads", transport.reads); field("writes", transport.writes); field("flushes", transport.flushes); emit("\n");
    }
    Kernel *kernel_{};
    sched::ProcessId pid_{}, holder_{}, child_{};
    u16 seed_description_{sched::invalid_description}, directory_description_{sched::invalid_description};
    bool captured_{}, child_observed_{}, child_reaped_{};
};
}

extern "C" Status ok_boot_filesystem(fs::VirtualFileSystem &vfs)
{
    if (auto status = arch::initialize_clock(); !status) return status;
    static_cast<void>(arch::initialize_realtime());
    auto anchor = arch::monotonic_sample(); if (!anchor) return anchor.status();
    if (auto status = arch::set_realtime({1700000000, 123456789}, anchor.value()); !status) return status;
    auto disk = os::drivers::probe_virtio_block(); if (!disk) return disk.status();
    transport.bind(*disk.value());
    std::array<std::byte, 512> control{};
    if (auto status = disk.value()->read_blocks(0, control); !status) return status;
    constexpr std::string_view magic{"MROOTCTL"};
    bool selected = true;
    for (usize i = 0; i != magic.size(); ++i)
        if (control[i] != std::byte{static_cast<u8>(magic[i])}) selected = false;
    if (selected)
    {
        const auto action = std::to_integer<u8>(control[8]);
        if (action < 1 || action > 2) return Status::invalid_argument("invalid native clean-seal fault action");
        transport.select(action);
    }
    auto key = registry.register_device(transport, 17, 1024); if (!key) return key.status();
    registration = key.value();
    filesystem = ::new (filesystem_storage.data()) Mount{fs::Ext4MountedPolicy::ordered_data_dirty_noatime};
    if (auto status = filesystem->mount(registry, registration,
            {journalled_fixture::origin, journalled_fixture::sectors}); !status) return status;
    mounted_counts = transport.counts();
    auto identity = filesystem->lifetime_snapshot(journalled_fixture::root.number);
    check(identity.ok(), "initial provider session identity"); original_session = identity.value().key.session;
    auto root = filesystem->retain_root(); if (!root) return root.status();
    auto child = root.value().clone(); if (!child) return child.status();
    auto alias = root.value().clone(); if (!alias) return alias.status();
    auto root_mount = vfs.mount_owned("/", std::move(root.value())); if (!root_mount) return root_mount.status();
    root_attachment = root_mount.value();
    auto child_mount = vfs.mount_owned("/child", std::move(child.value())); if (!child_mount) return child_mount.status();
    child_attachment = child_mount.value();
    aliases = ::new (alias_storage.data()) fs::VirtualFileSystem{};
    auto alias_mount = aliases->mount_owned("/", std::move(alias.value())); if (!alias_mount) return alias_mount.status();
    alias_attachment = alias_mount.value();
    vfs.set_mode(fs::FileSystemMode::ext4_journaled);
    check(holds(journalled_fixture::child.number) == 1, "child mount retains actual covered disk path");
    check(transport.writes == mounted_counts.writes && transport.flushes == mounted_counts.flushes,
          "owned publication performs no disk mutation");
    emit("MROOT_STORAGE virtio=1 policy=ordered-data-dirty-noatime root=owned aliases=cloned child=covered");
    field("root_id", root_attachment.id()); field("child_id", child_attachment.id());
    field("alias_id", alias_attachment.id()); field("action", transport.action()); emit("\n");
    return {};
}

extern "C" [[noreturn]] void kernel_main()
{
    ok_platform_console_init();
    emit("MROOT_FIXTURE_BEGIN scope=actual-musl-user-mode experimental_sdk=52 sdk_abi=51 module_abi=51 sdk-only=1 root=disk physical=0 smp=0\n");
    check(user::native::prepare_memory().ok(), "native memory preparation");
    Fixture fixture;
    KernelEntryConfig config{};
    config.mode = KernelBootMode::normal;
    config.kernel.architecture = arch::configured_architecture(); config.kernel.extension = &fixture;
    check(ok_kernel_entry(config).ok(), "kernel boot");
    check(ok_start_userland({mroot_archive_start, static_cast<usize>(mroot_archive_end - mroot_archive_start),
          "/init", user::default_user_credentials()}).ok(), "actual disk /init loader");
    check(ok_start_boot_extension().ok(), "native lifecycle diagnostic extension");
    for (;;)
    {
        static_cast<void>(ok_step_userland());
        if (fixture.after_step()) stop(true);
    }
}

#include "../../drivers/virtio/block.hpp"
#include <ok/arch/clock.hpp>
#include <ok/arch/realtime.hpp>
#include <ok/arch/terminal_power.hpp>
#include <ok/core/shutdown_storage.hpp>
#include <ok/fs/devfs.hpp>
#include <ok/fs/ext4/layout.hpp>
#include <ok/fs/fat_fs.hpp>
#include <ok/fs/ext4_mounted_common_profile.hpp>
#include <new>

extern "C" void ok_platform_console_write_char(char);
namespace
{
void report(const char *text)
{
    while (*text) ok_platform_console_write_char(*text++);
}
ok::fs::Ext4FileSystem root_filesystem;
ok::fs::DeviceFileSystem device_filesystem;
ok::fs::FatFileSystem media_filesystem;
using JournalRoot = ok::fs::Ext4MountedMetadata<1>;
JournalRoot::Registry journal_registry;
alignas(JournalRoot::CommonStorage)
    std::array<std::byte, sizeof(JournalRoot::CommonStorage)> journal_common_storage{};
alignas(JournalRoot) std::array<std::byte, sizeof(JournalRoot)> journal_storage{};
bool journal_constructed{};
ok::fs::VfsMountHandle journal_attachment{};
ok::fs::VfsMountHandle run_attachment{};
ok::fs::VirtualFileSystem *journal_vfs{};
ok::driver::BlockDevice *journal_device{};
ok::driver::BlockGeometry journal_geometry{};
JournalRoot::Registry::Registration journal_registration{};
bool journal_boot_complete{};
enum class StorageShutdownPhase : ok::u8 { idle, detaching_run, detaching_root, freezing, resetting, sealed, failed };
StorageShutdownPhase storage_shutdown_phase{StorageShutdownPhase::idle};
ok::ShutdownTicket storage_shutdown_ticket{};
ok::Status storage_shutdown_failure{};

JournalRoot &original_journal_root()
{
    return *std::launder(reinterpret_cast<JournalRoot *>(journal_storage.data()));
}

ok::Status storage_shutdown_fail(ok::Status status)
{
    if (storage_shutdown_failure) storage_shutdown_failure = status;
    storage_shutdown_phase = StorageShutdownPhase::failed;
    return storage_shutdown_failure;
}

ok::Status admit_shutdown_action(ok::SystemPowerAction action)
{
    if (action != ok::SystemPowerAction::halt && action != ok::SystemPowerAction::reboot &&
        action != ok::SystemPowerAction::poweroff)
        return ok::Status::invalid_argument("storage shutdown action is invalid");
    if (!ok::arch::terminal_power_action_supported(action))
        return ok::Status::unsupported("storage shutdown action has no selected terminal backend");
    // Selected preflight is non-consuming and repeatable before owner detachment.
    return ok::arch::preflight_terminal_power_action(action);
}

ok::Status admit_shutdown_storage(ok::fs::VirtualFileSystem &vfs, ok::SystemPowerAction action)
{
    if (auto status = admit_shutdown_action(action); !status) return status;
    if (!journal_constructed || !journal_boot_complete || journal_vfs != &vfs || !journal_device ||
        !journal_attachment.valid() || !run_attachment.valid() || vfs.mode() != ok::fs::FileSystemMode::ext4_journaled)
        return ok::Status::unsupported("clean shutdown requires the original owned journalled root and runtime mount");
    const std::array<ok::fs::OwnedMountExpectation, 2> expected{{
        {journal_attachment, "/", ok::fs::OwnedMountKind::provider, {}},
        {run_attachment, "/run", ok::fs::OwnedMountKind::ram, journal_attachment}}};
    if (auto status = vfs.preflight_owned_mounts(expected); !status) return status;
    const auto &filesystem = original_journal_root();
    const auto state = filesystem.report();
    if (filesystem.policy() != ok::fs::Ext4MountedPolicy::ordered_data_dirty_noatime ||
        state.phase != ok::fs::Ext4MountPhase::readable || !state.status || !state.published || !state.epoch)
        return ok::Status::unsupported("original journalled provider is not qualified for clean freeze");
    if (state.reading) return ok::Status::busy("original journalled provider has an active reader");
    auto session = journal_registry.inspect(journal_registration);
    if (!session) return session.status();
    const auto &owner = session.value();
    const auto buffers = filesystem.buffers();
    if (owner.state != ok::block::DeviceState::owned || owner.first_error != ok::StatusCode::ok ||
        buffers.state != ok::fs::MetadataOwnerState::ready || buffers.first_error != ok::StatusCode::ok ||
        owner.identity != buffers.device_identity || owner.registration_generation != buffers.registration_generation ||
        owner.session_serial != buffers.session_serial || buffers.first_sector || buffers.sectors != journal_geometry.block_count)
        return ok::Status::unsupported("original journalled block owner identity differs");
    if (owner.in_flight || owner.pending_writes || buffers.read_pins || buffers.in_flight || buffers.transaction_active)
        return ok::Status::busy("original journalled block owner has active or unflushed work");
    const auto geometry = journal_device->geometry();
    if (!geometry.writable || geometry.block_size != 512 || geometry.block_count != journal_geometry.block_count ||
        geometry.block_size != journal_geometry.block_size || geometry.writable != journal_geometry.writable)
        return ok::Status::unsupported("original journalled block geometry changed");
    return os::drivers::preflight_virtio_block_shutdown(*journal_device);
}

ok::Status ensure_runtime_mountpoint(ok::fs::VirtualFileSystem &vfs,
                                     const ok::fs::ResolveContext &context)
{
    auto validate = [](const ok::fs::Metadata &metadata, bool created) -> ok::Status {
        if (metadata.type == ok::fs::NodeType::symlink)
            return ok::Status::too_many_symlinks("runtime mount point must not be a symlink");
        if (metadata.type != ok::fs::NodeType::directory)
            return ok::Status::not_directory("runtime mount point is not a directory");
        if (!metadata.link_count)
            return ok::Status::not_found("runtime mount point was removed");
        if (created && (metadata.uid != 0 || metadata.gid != 0 ||
                        (metadata.mode & ok::fs::mode_permission_mask) != 0755))
            return ok::Status::denied("new runtime mount point has unexpected initial attributes");
        return {};
    };
    // Inspect the direct final component without following a disk symlink.
    // The checked stat consumes its path reference before returning metadata.
    auto existing = vfs.try_stat_absolute("/run", context.credentials, ok::fs::FinalComponent::no_follow);
    if (existing.result) return validate(existing.result.value(), false);
    if (existing.result.status().code() != ok::StatusCode::not_found)
        return existing.result.status();
    if (auto status = vfs.create(context, "/run", ok::fs::NodeType::directory, 0755, 0, 0); !status)
        return status;
    auto created = vfs.try_stat_absolute("/run", context.credentials, ok::fs::FinalComponent::no_follow);
    if (!created.result) return created.result.status();
    return validate(created.result.value(), true);
}

ok::Status mount_runtime_directory(ok::fs::VirtualFileSystem &vfs)
{
    if (run_attachment.valid()) return ok::Status::busy("volatile runtime directory is already attached");
    ok::fs::ResolveContext context{.credentials = {.uid = 0, .gid = 0}, .check_search = true};
    if (auto status = ensure_runtime_mountpoint(vfs, context); !status) return status;
    auto attached = vfs.mount_ram_owned("/run", 0755, 0, 0);
    if (!attached) return attached.status();
    run_attachment = attached.value();
    if (auto status = vfs.create(context, "/run/user", ok::fs::NodeType::directory, 0755, 0, 0); !status) return status;
    if (auto status = vfs.create(context, "/run/user/1000", ok::fs::NodeType::directory, 0700, 1000, 1000); !status) return status;
    report("OK_RUN source=ram mode=volatile pathname_sockets=bounded\n");
    // The kernel's null, zero and full character devices, over the image's /dev.
    if (auto status = vfs.mount("/dev", device_filesystem.root()); !status)
    {
        char text[96]{}; const auto message = status.message();
        for (ok::usize i = 0; i < message.size() && i + 1 < sizeof(text); ++i) text[i] = message[i];
        report("OK_DEV_FAIL "); report(text); report("\n");
        return status;
    }
    report("OK_DEV source=kernel devices=null,zero,full\n");
    return {};
}

// A no-RTC machine can use the validated volume's last write time as a
// provisional metadata clock. Login/security services must still wait for a
// trusted time source; this anchor carries no accuracy guarantee.
bool realtime_for_root(ok::u32 last_write_seconds)
{
    if (auto status = ok::arch::initialize_clock(); !status) return false;
    static_cast<void>(ok::arch::initialize_realtime());
    if (ok::arch::realtime_sample()) return true;
    if (last_write_seconds < 1577836800u || last_write_seconds > 0x7fffffffu) return false;
    auto point = ok::arch::monotonic_sample();
    if (!point || !ok::arch::set_realtime({last_write_seconds, 0}, point.value())) return false;
    report("OK_STORAGE_CLOCK source=ext4-last-write provisional=1\n");
    return true;
}

ok::Status mount_journalled_root(ok::driver::BlockDevice &disk, ok::fs::VirtualFileSystem &vfs,
                                  ok::u32 last_write_seconds)
{
    if (journal_constructed)
        return ok::Status::busy("journalled root storage already constructed");
    const auto geometry = disk.geometry();
    if (geometry.block_size != 512 || !geometry.writable)
        return ok::Status::unsupported("journalled root requires writable 512-byte sectors");
    auto key = journal_registry.register_device(disk, 1, 1024);
    if (!key) return key.status();
    auto *common = ::new (journal_common_storage.data()) JournalRoot::CommonStorage{};
    auto *filesystem = ::new (journal_storage.data()) JournalRoot{*common};
    journal_constructed = true;
    if (auto status = filesystem->mount(journal_registry, key.value(), {0, geometry.block_count}); !status)
        return status;
    auto root = filesystem->retain_root();
    if (!root) return root.status();
    auto attachment = vfs.mount_owned("/", std::move(root.value()));
    if (!attachment) return attachment.status();
    journal_attachment = attachment.value();
    journal_vfs = &vfs;
    journal_device = &disk;
    journal_geometry = geometry;
    journal_registration = key.value();
    vfs.set_mode(ok::fs::FileSystemMode::ext4_journaled);
    static_cast<void>(realtime_for_root(last_write_seconds));
    report("OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=ordered-data\n");
    auto runtime = mount_runtime_directory(vfs);
    if (runtime) journal_boot_complete = true;
    return runtime;
}
}

// Ext4 supplies the system root; FAT media is mounted beneath the archive root
// at /media with fixed mount permissions. Validation failures never format media.
extern "C" ok::Status ok_boot_filesystem(ok::fs::VirtualFileSystem &vfs)
{
    auto disk = os::drivers::probe_virtio_block();
    if (!disk)
    {
        if (disk.status().code() != ok::StatusCode::not_found && disk.status().code() != ok::StatusCode::unsupported)
            return disk.status();
        report("OK_STORAGE source=archive reason=no-supported-device\n");
        return mount_runtime_directory(vfs);
    }
    std::array<std::byte, 1024> super{};
    if (auto status = disk.value()->read_blocks(2, super); !status.ok()) return status;
    if (super[56] != std::byte{0x53} || super[57] != std::byte{0xef})
    {
        std::array<std::byte, 512> boot{};
        if (auto status = disk.value()->read_blocks(0, boot); !status) return status;
        const auto signature = [&](ok::usize offset, std::string_view value) {
            for (ok::usize i = 0; i < value.size(); ++i)
                if (boot[offset + i] != static_cast<std::byte>(value[i])) return false;
            return true;
        };
        // The FAT32 type string is informational; admit valid unlabelled BPBs
        // through the checked kernel parser, then validate the entire provider.
        ok::fs::FatVolume candidate;
        const auto fat_probe = candidate.mount(*disk.value());
        if (!fat_probe && fat_probe.code() == ok::StatusCode::io_error) return fat_probe;
        if (fat_probe || signature(3, "EXFAT   ") || signature(82, "FAT32   "))
        {
            if (auto status = media_filesystem.mount(*disk.value(), true); !status) return status;
            auto existing = vfs.try_stat_absolute("/media", {.uid = 0, .gid = 0},
                                                  ok::fs::FinalComponent::no_follow);
            if (!existing.result)
            {
                if (existing.result.status().code() != ok::StatusCode::not_found)
                    return existing.result.status();
                if (auto status = vfs.create({}, "/media", ok::fs::NodeType::directory, 0755, 0, 0); !status)
                    return status;
            }
            else if (existing.result.value().type != ok::fs::NodeType::directory)
                return ok::Status::not_directory("FAT mount point must be a directory");
            if (auto status = vfs.mount("/media", *media_filesystem.root()); !status) return status;
            report(media_filesystem.info().variant == ok::fs::FatVariant::fat32 ?
                "OK_STORAGE scope=hardware source=virtio filesystem=fat32 mode=rw mount=/media\n" :
                "OK_STORAGE scope=hardware source=virtio filesystem=exfat mode=rw mount=/media\n");
        }
        else
            report("OK_STORAGE source=archive reason=unrecognized-media\n");
        return mount_runtime_directory(vfs);
    }
    const ok::u32 last_write_seconds = std::to_integer<ok::u32>(super[48]) |
        (std::to_integer<ok::u32>(super[49]) << 8) |
        (std::to_integer<ok::u32>(super[50]) << 16) |
        (std::to_integer<ok::u32>(super[51]) << 24);
    // The journal bit selects an independently validated mount. Never pass a
    // journalled disk to the legacy writer or fall back after mount failure.
    if ((std::to_integer<ok::u8>(super[92]) & 0x04u) != 0)
        return mount_journalled_root(*disk.value(), vfs, last_write_seconds);
    // The kernel answers Linux stat only for ext4 metadata whose timestamps it
    // maintains, so an image with the musl userland needs a maintained root.
    // That policy needs an active realtime sample, physical or provisional;
    // without either the unqualified writer remains and says so. okcrt-only
    // images keep the unqualified root. Neither falls back after failure.
#ifdef OK_MAINTAINED_ROOT
    const bool maintained = realtime_for_root(last_write_seconds);
#else
    constexpr bool maintained = false;
#endif
    const ok::fs::Ext4MountOptions options{true, maintained ? ok::fs::Ext4TimestampPolicy::maintained
                                                            : ok::fs::Ext4TimestampPolicy::unqualified};
    if (auto status = root_filesystem.mount(*disk.value(), options); !status.ok()) return status;
    if (auto status = vfs.mount("/", *root_filesystem.root()); !status.ok()) return status;
    vfs.set_mode(ok::fs::FileSystemMode::ext4_read_write);
    report("OK_STORAGE scope=hardware source=virtio filesystem=ext4 mode=rw journal=none\n");
#ifdef OK_MAINTAINED_ROOT
    report(maintained ? "OK_ROOT_TIMESTAMPS policy=maintained\n" : "OK_ROOT_TIMESTAMPS policy=unqualified reason=no-clock\n");
#endif
    return mount_runtime_directory(vfs);
}

// These callbacks are serialized by the trusted boot-CPU coordinator. Storage
// inventory is only one part of its preflight; unknown GUI/module/network/RNG
// producers must be refused by their owners before service quiescence.
extern "C" ok::Status ok_shutdown_storage_preflight(ok::fs::VirtualFileSystem &vfs, ok::SystemPowerAction action)
{
    if (storage_shutdown_phase == StorageShutdownPhase::failed) return storage_shutdown_failure;
    if (storage_shutdown_phase != StorageShutdownPhase::idle)
        return ok::Status::busy("storage shutdown has already consumed its owners");
    return admit_shutdown_storage(vfs, action);
}

extern "C" ok::Status ok_shutdown_storage_seal(ok::fs::VirtualFileSystem &vfs,
                                               const ok::ShutdownStorageBarrier &barrier)
{
    const auto &ticket = barrier.ticket();
    if (!ticket.coordinator || !ticket.owner.runtime || !ticket.owner.incarnation ||
        ticket.owner.process != 1 || !ticket.owner.leader || !ticket.generation)
        return ok::Status::denied("storage shutdown requires an original coordinator barrier");
    if (storage_shutdown_phase == StorageShutdownPhase::failed) return storage_shutdown_failure;
    if (storage_shutdown_phase == StorageShutdownPhase::sealed)
        return storage_shutdown_ticket == ticket ? ok::Status{} :
            ok::Status::denied("storage shutdown barrier differs from its sealed generation");
    if (storage_shutdown_phase != StorageShutdownPhase::idle)
        return ok::Status::busy("storage shutdown callback is active");
    if (auto status = admit_shutdown_action(ticket.action); !status) return status;
    storage_shutdown_ticket = ticket;
    // Latch before the final admission callbacks. A reentrant or later call
    // cannot repeat any attempted detach, including failure after consumption.
    storage_shutdown_phase = StorageShutdownPhase::detaching_run;
    if (auto status = admit_shutdown_storage(vfs, ticket.action); !status) return storage_shutdown_fail(status);
    if (auto status = vfs.shutdown_reference_status(); !status) return storage_shutdown_fail(status);
    if (auto status = vfs.detach(run_attachment); !status) return storage_shutdown_fail(status);
    storage_shutdown_phase = StorageShutdownPhase::detaching_root;
    if (auto status = vfs.detach(journal_attachment); !status) return storage_shutdown_fail(status);
    if (auto status = vfs.shutdown_reference_status(); !status) return storage_shutdown_fail(status);
    storage_shutdown_phase = StorageShutdownPhase::freezing;
    auto &filesystem = original_journal_root();
    if (auto status = filesystem.freeze_clean(); !status) return storage_shutdown_fail(status);
    if (filesystem.report().phase != ok::fs::Ext4MountPhase::clean_sealed)
        return storage_shutdown_fail(ok::Status::fault("original journalled provider did not publish clean seal"));
    storage_shutdown_phase = StorageShutdownPhase::resetting;
    if (auto status = os::drivers::stop_virtio_block_shutdown(*journal_device); !status)
        return storage_shutdown_fail(status);
    storage_shutdown_phase = StorageShutdownPhase::sealed;
    report("OK_STORAGE_SHUTDOWN scope=provider state=clean_sealed platform=0\n");
    return {};
}

#include "../../drivers/virtio/block.hpp"
#include <ok/arch/clock.hpp>
#include <ok/arch/realtime.hpp>
#include <ok/core/entry.hpp>
#include <ok/fs/ext4_mounted_metadata.hpp>
#include <ok/fs/ext4_completion.hpp>
#include <ok/user/runtime.hpp>
#include <new>
#include "journalled_root_fixture.hpp"

using namespace ok;
extern "C" void ok_platform_console_init();
extern "C" void ok_platform_console_write_char(char);
extern "C" void ok_platform_debug_exit(u32);
extern "C" const std::byte jroot_archive_start[], jroot_archive_end[];

#ifndef JROOT_UID
#define JROOT_UID 1000
#endif
#ifndef JROOT_NEGATIVE_CLOCK
#define JROOT_NEGATIVE_CLOCK 0
#endif
static_assert(JROOT_UID == 1000);
static_assert(!JROOT_NEGATIVE_CLOCK);

namespace
{
void emit(std::string_view text)
{
    for (char value : text) ok_platform_console_write_char(value);
}
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
    emit("JROOT_FIXTURE_FAIL reason="); emit(reason); emit("\n"); stop(false);
}
// Successful events describe completed calls to the actual Virtio transport.
// A test control in the guard sector can inject a reported I/O error before a
// call or stop after a completed call; neither fabricates a successful write.
class ObservedDevice final : public driver::BlockDevice
{
  public:
    void bind(driver::BlockDevice &device) { check(!device_, "single transport binding"); device_ = &device; }
    void control(u8 action, u32 selected) { action_ = action; selected_ = selected; }
    driver::BlockGeometry geometry() const override { return device_->geometry(); }
    Status read_blocks(u64 sector, std::span<std::byte> bytes) override
    { ++reads; return device_->read_blocks(sector, bytes); }
    Status write_blocks(u64 sector, std::span<const std::byte> bytes) override
    {
        const bool injected = action_ == 3 && ordinal + 1 == selected_;
        const auto status = injected ? Status::io_error("injected Virtio write error") :
                                       device_->write_blocks(sector, bytes);
        ++ordinal; ++writes;
        const auto crc = fs::jbd2::detail::crc32c(~u32{0},
            {reinterpret_cast<const u8 *>(bytes.data()), bytes.size()});
        emit("JROOT_IO"); field("ordinal", ordinal); emit(" kind=write");
        field("sector", sector); field("bytes", bytes.size()); field("crc32c", crc);
        field("status", static_cast<u32>(status.code())); emit("\n");
        if (injected) emit("JROOT_INJECTED kind=write before-device=1\n");
        if (status && action_ == 1 && ordinal == selected_) cut();
        return status;
    }
    Status flush() override
    {
        const bool injected = action_ == 2 && ordinal + 1 == selected_;
        const auto status = injected ? Status::io_error("injected Virtio FLUSH error") : device_->flush();
        ++ordinal; ++flushes;
        emit("JROOT_IO"); field("ordinal", ordinal); emit(" kind=flush sector=0 bytes=0 crc32c=0");
        field("status", static_cast<u32>(status.code())); emit("\n");
        if (injected) emit("JROOT_INJECTED kind=flush before-device=1\n");
        if (status && action_ == 1 && ordinal == selected_) cut();
        return status;
    }
    u64 ordinal{}, reads{}, writes{}, flushes{};
  private:
    [[noreturn]] void cut()
    {
        emit("JROOT_CUT"); field("ordinal", ordinal); field("writes", writes);
        field("flushes", flushes); emit(" after-completed-call=1\n");
        ok_platform_debug_exit(0x12u);
        for (;;) asm volatile("" ::: "memory");
    }
    driver::BlockDevice *device_{};
    u8 action_{};
    u32 selected_{};
};
using Mount = fs::Ext4MountedMetadata<1>;
ObservedDevice transport;
Mount::Registry registry;
Mount::Registry::Session recovery_session, rejected_alias;
alignas(fs::Ext4RecoveryCompletion<>) std::array<std::byte, sizeof(fs::Ext4RecoveryCompletion<>)> recovery_storage{};
u64 recovered_writes{}, recovered_flushes{};
alignas(Mount) std::array<std::byte, sizeof(Mount)> filesystem_storage{};
Mount *filesystem{};
time::RealtimeInfo initial_clock;

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
                      "direct Linux executable identity");
            }
        check(count == 1, "unique initial Linux process");
        auto reaper = kernel.scheduler().create_process("jmode-fixture-reaper", {});
        check(reaper.ok(), "reaper reservation"); reaper_ = reaper.value();
        auto *process = kernel.scheduler().find(pid_);
        auto *owner = kernel.scheduler().find(reaper_);
        check(process && owner && owner->add_child(pid_).ok(), "fixture child reservation");
        process->set_parent(reaper_);
        const auto credentials = JROOT_UID ? user::default_user_credentials() : user::root_credentials();
        check(kernel.scheduler().set_credentials(pid_, credentials).ok(), "initial user credentials");
        emit("JROOT_CREDENTIALS"); field("uid", JROOT_UID); field("euid", JROOT_UID);
        field("gid", JROOT_UID); field("egid", JROOT_UID); emit(" before-entry=1 personality=linux\n");
        return {};
    }
    bool after_step()
    {
        check(ok_userland_status().ok(), "runtime status");
        const auto *process = kernel_->scheduler().find(pid_);
        check(process != nullptr, "child retained");
        const auto &c = process->credentials();
        check(c.uid == JROOT_UID && c.euid == JROOT_UID && c.suid == JROOT_UID &&
              c.gid == JROOT_UID && c.egid == JROOT_UID && c.sgid == JROOT_UID && !c.kernel_space,
              "retained process credentials");
        check(process->resources().personality == sched::UserPersonality::linux, "retained Linux personality");
        const auto active = arch::realtime_clock_info();
        check(active.origin == time::RealtimeOrigin::administrator_software && active.state == initial_clock.state,
              "retained active software clock");
        if (JROOT_UID) check(active.wall_generation == initial_clock.wall_generation, "unprivileged clock identity");
        if (process->state() != sched::ProcessState::zombie) return false;
        check(process->wait_status() == 0, "user exit status");
        const auto mounted = filesystem->report();
        check(mounted.phase == fs::Ext4MountPhase::readable && mounted.status.ok() && mounted.published &&
              !mounted.reading && mounted.epoch >= 1 && mounted.epoch <= 3, "healthy disk root epoch");
        const auto mutations = mounted.epoch - 1;
        check(mutations <= 2 &&
              transport.writes == recovered_writes + mutations * 11 &&
              transport.flushes == recovered_flushes + mutations * 9 + 2,
              "bounded mutations and user fsync calls");
        // SDK34 retains PID 1 as a terminal diagnostic even when a fixture
        // reaper owns it; the exit state is observed, but reaping is denied.
        auto waited = kernel_->scheduler().wait_process(reaper_, pid_);
        check(!waited && waited.status().code() == StatusCode::busy,
              "init retained for recovery diagnosis");
        emit("JROOT_FIXTURE_PASS"); field("uid", JROOT_UID); emit(" exit=0 reaped=0 retained=1 personality=linux");
        field("epoch", mounted.epoch); field("mutations", mounted.epoch - 1); field("reads", transport.reads); field("writes", transport.writes); field("flushes", transport.flushes);
        emit("\n"); return true;
    }
  private:
    Kernel *kernel_{};
    sched::ProcessId pid_{}, reaper_{};
};
}

extern "C" Status ok_boot_filesystem(fs::VirtualFileSystem &vfs)
{
    if (auto status = arch::initialize_clock(); !status) return status;
    static_cast<void>(arch::initialize_realtime());
    auto anchor = arch::monotonic_sample(); if (!anchor) return anchor.status();
    if (auto status = arch::set_realtime({JROOT_NEGATIVE_CLOCK ? -123456789 : 1700000000, 123456789}, anchor.value()); !status) return status;
    initial_clock = arch::realtime_clock_info();
    check(initial_clock.origin == time::RealtimeOrigin::administrator_software, "explicit software clock");
    auto disk = os::drivers::probe_virtio_block(); if (!disk) return disk.status();
    transport.bind(*disk.value());
    std::array<std::byte, 512> control{};
    if (auto status = disk.value()->read_blocks(0, control); !status) return status;
    constexpr char magic[] = "JROOTCTL";
    bool selected = true;
    for (usize i = 0; i < 8; ++i)
        if (control[i] != std::byte{static_cast<u8>(magic[i])}) selected = false;
    if (selected)
    {
        const u8 action = std::to_integer<u8>(control[8]);
        const u32 ordinal = std::to_integer<u32>(control[12]) |
            (u32{std::to_integer<u8>(control[13])} << 8) |
            (u32{std::to_integer<u8>(control[14])} << 16) |
            (u32{std::to_integer<u8>(control[15])} << 24);
        if (action < 1 || action > 3 || ordinal < 1 || ordinal > 43)
            return Status::invalid_argument("invalid journalled-root test control");
        transport.control(action, ordinal);
        emit("JROOT_CONTROL"); field("action", action); field("ordinal", ordinal); emit("\n");
    }
    check(!filesystem, "single maintained mount construction");
    auto key = registry.register_device(transport, 17, 1024); if (!key) return key.status();
    // Recovery owns the actual bounded Kernel device session before a filesystem
    // cache or mount exists. The registration is handed to the mount only after
    // durable completion and retirement of this recovery session.
    check(registry.acquire(key.value(), {journalled_fixture::origin, journalled_fixture::sectors},
          block::SessionAccess::writable, recovery_session).ok(), "exclusive recovery session");
    check(registry.acquire(key.value(), {journalled_fixture::origin, 2}, block::SessionAccess::readonly,
          rejected_alias).code() == StatusCode::busy && registry.detach(key.value()).code() == StatusCode::busy,
          "recovery excludes aliases and detach");
    emit("JROOT_OWNER acquired=1 aliases=excluded mount=none\n");
    auto &completion = *::new (recovery_storage.data()) fs::Ext4RecoveryCompletion<>;
    const auto recovered = completion.run(recovery_session, {0, journalled_fixture::sectors});
    if (!recovered) { emit("JROOT_RECOVERY_ERROR reason="); emit(recovered.message()); emit("\n"); }
    check(recovered.ok() && completion.report().complete(), "durable recovery completion");
    const auto report = completion.report();
    check(report.home_durable && report.journal_durable && report.filesystem_durable &&
          report.write_attempts == report.completed_writes && report.flush_attempts == report.completed_flushes &&
          transport.writes == report.completed_writes && transport.flushes == report.completed_flushes,
          "actual recovery completion accounting");
    recovered_writes = transport.writes; recovered_flushes = transport.flushes;
    emit("JROOT_RECOVERY_PASS"); field("clean", report.already_clean); field("empty", report.empty_log);
    field("actions", report.validated_actions); field("checked", report.checked_inodes); field("reads", transport.reads);
    field("writes", transport.writes); field("flushes", transport.flushes); field("sequence", report.journal_sequence);
    emit(" home=1 journal=1 filesystem=1\n");
    check(recovery_session.close().ok(), "recovery session retirement");
    const auto before = transport.ordinal;
    check(recovery_session.flush().code() == StatusCode::bad_descriptor && transport.ordinal == before,
          "retired recovery session denies transport access");
    emit("JROOT_OWNER retired=1 stale=denied\n");
    filesystem = ::new (filesystem_storage.data()) Mount{fs::Ext4MountedPolicy::maintained_noatime};
    if (auto status = filesystem->mount(registry, key.value(),
            {journalled_fixture::origin, journalled_fixture::sectors}); !status) return status;
    auto *root = filesystem->root(); check(root != nullptr, "maintained disk root");
    if (auto status = vfs.mount("/", *root); !status) return status;
    vfs.set_mode(fs::FileSystemMode::ext4_journaled);
    check(transport.writes == recovered_writes && transport.flushes == recovered_flushes &&
          filesystem->report().epoch == 1 && vfs.mode() == fs::FileSystemMode::ext4_journaled,
          "recovered disk root admission");
    emit("JROOT_STORAGE virtio=1 policy=maintained-noatime aliases=0 root=disk epoch=1");
    field("reads", transport.reads); emit("\n");
    return {};
}

extern "C" [[noreturn]] void kernel_main()
{
    ok_platform_console_init();
    emit("JROOT_FIXTURE_BEGIN scope=actual-musl-user-mode sdk=34 sdk-only=1 root=disk"); field("uid", JROOT_UID);
    emit("\n");
    check(user::native::prepare_memory().ok(), "native memory preparation");
    Fixture fixture;
    KernelEntryConfig config{};
    config.mode = KernelBootMode::normal;
    config.kernel.architecture = arch::configured_architecture(); config.kernel.extension = &fixture;
    check(ok_kernel_entry(config).ok(), "kernel boot");
    check(ok_start_userland({jroot_archive_start, static_cast<usize>(jroot_archive_end - jroot_archive_start),
          "/init"}).ok(), "Linux disk root loader");
    check(ok_start_boot_extension().ok(), "initial credential fixture");
    for (;;)
    {
        static_cast<void>(ok_step_userland());
        if (fixture.after_step()) stop(true);
    }
}

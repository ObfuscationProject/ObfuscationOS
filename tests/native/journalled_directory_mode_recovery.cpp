#include "../../drivers/virtio/block.hpp"
#include <ok/arch/clock.hpp>
#include <ok/arch/realtime.hpp>
#include <ok/core/entry.hpp>
#include <ok/fs/ext4_mounted_metadata.hpp>
#include <ok/fs/ext4_completion.hpp>
#include <ok/user/runtime.hpp>
#include <new>
#include "journalled_directory_mode_fixture.hpp"

using namespace ok;
extern "C" void ok_platform_console_init();
extern "C" void ok_platform_console_write_char(char);
extern "C" void ok_platform_debug_exit(u32);
extern "C" const std::byte jdrec_archive_start[], jdrec_archive_end[];

#ifndef JDREC_UID
#define JDREC_UID 1000
#endif
#ifndef JDREC_NEGATIVE_CLOCK
#define JDREC_NEGATIVE_CLOCK 0
#endif
static_assert(JDREC_UID == 1000);
static_assert(!JDREC_NEGATIVE_CLOCK);

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
    emit("JDREC_FIXTURE_FAIL reason="); emit(reason); emit("\n"); stop(false);
}
// Every event describes a completed call to the actual Virtio transport. The
// wrapper neither manufactures successful completions nor modifies the payload.
class ObservedDevice final : public driver::BlockDevice
{
  public:
    void bind(driver::BlockDevice &device) { check(!device_, "single transport binding"); device_ = &device; }
    driver::BlockGeometry geometry() const override { return device_->geometry(); }
    Status read_blocks(u64 sector, std::span<std::byte> bytes) override
    { ++reads; return device_->read_blocks(sector, bytes); }
    Status write_blocks(u64 sector, std::span<const std::byte> bytes) override
    {
        const auto status = device_->write_blocks(sector, bytes);
        ++ordinal; ++writes;
        const auto crc = fs::jbd2::detail::crc32c(~u32{0},
            {reinterpret_cast<const u8 *>(bytes.data()), bytes.size()});
        emit("JDREC_IO"); field("ordinal", ordinal); emit(" kind=write");
        field("sector", sector); field("bytes", bytes.size()); field("crc32c", crc);
        field("status", static_cast<u32>(status.code())); emit("\n");
        return status;
    }
    Status flush() override
    {
        const auto status = device_->flush();
        ++ordinal; ++flushes;
        emit("JDREC_IO"); field("ordinal", ordinal); emit(" kind=flush sector=0 bytes=0 crc32c=0");
        field("status", static_cast<u32>(status.code())); emit("\n");
        return status;
    }
    u64 ordinal{}, reads{}, writes{}, flushes{};
  private:
    driver::BlockDevice *device_{};
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
        auto reaper = kernel.scheduler().create_process("jdmode-fixture-reaper", {});
        check(reaper.ok(), "reaper reservation"); reaper_ = reaper.value();
        auto *process = kernel.scheduler().find(pid_);
        auto *owner = kernel.scheduler().find(reaper_);
        check(process && owner && owner->add_child(pid_).ok(), "fixture child reservation");
        process->set_parent(reaper_);
        const auto credentials = JDREC_UID ? user::default_user_credentials() : user::root_credentials();
        check(kernel.scheduler().set_credentials(pid_, credentials).ok(), "initial user credentials");
        emit("JDREC_CREDENTIALS"); field("uid", JDREC_UID); field("euid", JDREC_UID);
        field("gid", JDREC_UID); field("egid", JDREC_UID); emit(" before-entry=1 personality=linux\n");
        return {};
    }
    bool after_step()
    {
        check(ok_userland_status().ok(), "runtime status");
        const auto *process = kernel_->scheduler().find(pid_);
        check(process != nullptr, "child retained");
        const auto &c = process->credentials();
        check(c.uid == JDREC_UID && c.euid == JDREC_UID && c.suid == JDREC_UID &&
              c.gid == JDREC_UID && c.egid == JDREC_UID && c.sgid == JDREC_UID && !c.kernel_space,
              "retained process credentials");
        check(process->resources().personality == sched::UserPersonality::linux, "retained Linux personality");
        const auto active = arch::realtime_clock_info();
        check(active.origin == time::RealtimeOrigin::administrator_software && active.state == initial_clock.state,
              "retained active software clock");
        if (JDREC_UID) check(active.wall_generation == initial_clock.wall_generation, "unprivileged clock identity");
        if (process->state() != sched::ProcessState::zombie) return false;
        check(process->wait_status() == 0, "user exit status");
        const auto mounted = filesystem->report();
        check(mounted.phase == fs::Ext4MountPhase::readable && mounted.status.ok() && mounted.published &&
              !mounted.reading && mounted.epoch == 1, "healthy recovered mount epoch");
        check(transport.writes == recovered_writes && transport.flushes == recovered_flushes + 2,
              "read-only public guest and two successful user fsync calls");
        auto waited = kernel_->scheduler().wait_process(reaper_, pid_);
        check(waited && waited.value() == 0, "fixture reap");
        emit("JDREC_FIXTURE_PASS"); field("uid", JDREC_UID); emit(" exit=0 reaped=1 personality=linux");
        field("epoch", mounted.epoch); field("reads", transport.reads); field("writes", transport.writes); field("flushes", transport.flushes);
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
    if (auto status = arch::set_realtime({JDREC_NEGATIVE_CLOCK ? -123456789 : 1700000000, 123456789}, anchor.value()); !status) return status;
    initial_clock = arch::realtime_clock_info();
    check(initial_clock.origin == time::RealtimeOrigin::administrator_software, "explicit software clock");
    auto disk = os::drivers::probe_virtio_block(); if (!disk) return disk.status();
    transport.bind(*disk.value());
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
    emit("JDREC_OWNER acquired=1 aliases=excluded mount=none\n");
    auto &completion = *::new (recovery_storage.data()) fs::Ext4RecoveryCompletion<>;
    const auto recovered = completion.run(recovery_session, {0, journalled_fixture::sectors});
    if (!recovered) { emit("JDREC_RECOVERY_ERROR reason="); emit(recovered.message()); emit("\n"); }
    check(recovered.ok() && completion.report().complete(), "durable recovery completion");
    const auto report = completion.report();
    check(report.home_durable && report.journal_durable && report.filesystem_durable &&
          report.write_attempts == report.completed_writes && report.flush_attempts == report.completed_flushes &&
          transport.writes == report.completed_writes && transport.flushes == report.completed_flushes,
          "actual recovery completion accounting");
    recovered_writes = transport.writes; recovered_flushes = transport.flushes;
    emit("JDREC_RECOVERY_PASS"); field("clean", report.already_clean); field("empty", report.empty_log);
    field("actions", report.validated_actions); field("checked", report.checked_inodes); field("reads", transport.reads);
    field("writes", transport.writes); field("flushes", transport.flushes); field("sequence", report.journal_sequence);
    emit(" home=1 journal=1 filesystem=1\n");
    check(recovery_session.close().ok(), "recovery session retirement");
    const auto before = transport.ordinal;
    check(recovery_session.flush().code() == StatusCode::bad_descriptor && transport.ordinal == before,
          "retired recovery session denies transport access");
    emit("JDREC_OWNER retired=1 stale=denied\n");
    filesystem = ::new (filesystem_storage.data()) Mount{fs::Ext4MountedPolicy::maintained_noatime};
    if (auto status = filesystem->mount(registry, key.value(),
            {journalled_fixture::origin, journalled_fixture::sectors}); !status) return status;
    auto *root = filesystem->root(); check(root != nullptr, "maintained side mount root");
    for (const auto path : {"/journal", "/alias"})
    {
        if (auto status = vfs.create(path, fs::NodeType::directory); !status) return status;
        if (auto status = vfs.mount(path, *root); !status) return status;
    }
    check(transport.writes == recovered_writes && transport.flushes == recovered_flushes &&
          filesystem->report().epoch == 1, "read-only recovered mount admission");
    emit("JDREC_STORAGE virtio=1 policy=maintained-noatime aliases=2 root=archive epoch=1");
    field("reads", transport.reads); emit("\n");
    return {};
}

extern "C" [[noreturn]] void kernel_main()
{
    ok_platform_console_init();
    emit("JDREC_FIXTURE_BEGIN scope=actual-musl-user-mode sdk=31 sdk-only=1"); field("uid", JDREC_UID);
    emit("\n");
    check(user::native::prepare_memory().ok(), "native memory preparation");
    Fixture fixture;
    KernelEntryConfig config{};
    config.mode = KernelBootMode::normal;
    config.kernel.architecture = arch::configured_architecture(); config.kernel.extension = &fixture;
    check(ok_kernel_entry(config).ok(), "kernel boot");
    check(ok_start_userland({jdrec_archive_start, static_cast<usize>(jdrec_archive_end - jdrec_archive_start),
          "/bin/musl-jdir-recovery"}).ok(), "Linux archive loader");
    check(ok_start_boot_extension().ok(), "initial credential fixture");
    for (;;)
    {
        static_cast<void>(ok_step_userland());
        if (fixture.after_step()) stop(true);
    }
}

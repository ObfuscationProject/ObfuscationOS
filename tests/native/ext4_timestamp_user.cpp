#include "../../drivers/virtio/block.hpp"
#include <ok/arch/clock.hpp>
#include <ok/arch/realtime.hpp>
#include <ok/core/entry.hpp>
#include <ok/fs/ext4_fs.hpp>
#include <ok/user/runtime.hpp>

using namespace ok;
extern "C" void ok_platform_console_init();
extern "C" void ok_platform_console_write_char(char);
extern "C" void ok_platform_debug_exit(u32);

namespace
{
void emit(std::string_view text)
{
    for (char value : text) ok_platform_console_write_char(value);
}
[[noreturn]] void stop(bool success)
{
    ok_platform_debug_exit(success ? 0x10u : 0x11u);
    for (;;) asm volatile("" ::: "memory");
}
void check(bool success, std::string_view reason)
{
    if (success) return;
    emit("EXT4_TIME_USER_FIXTURE_FAIL reason="); emit(reason); emit("\n"); stop(false);
}
fs::Ext4FileSystem filesystem;
time::RealtimeInfo initial_clock;

class Fixture final : public KernelExtension
{
  public:
    Status start(Kernel &kernel) override
    {
        check(kernel_ == nullptr, "duplicate fixture start");
        kernel_ = &kernel;
        usize count = 0;
        for (const auto &process : kernel.scheduler().processes())
            if (!process.threads().empty() && process.threads()[0].native_active)
            {
                ++count; pid_ = process.pid();
                check(process.name() == "init" && process.parent_pid() == 0 &&
                      process.resources().personality == sched::UserPersonality::native,
                      "initial native identity");
            }
        check(count == 1, "unique initial native process");
        auto reaper = kernel.scheduler().create_process("timestamp-fixture-reaper", {});
        check(reaper.ok(), "fixture reaper reservation");
        reaper_ = reaper.value();
        auto *process = kernel.scheduler().find(pid_);
        auto *owner = kernel.scheduler().find(reaper_);
        check(process && owner && owner->add_child(pid_).ok(), "fixture child reservation");
        process->set_parent(reaper_);
        check(kernel.scheduler().set_credentials(pid_, user::default_user_credentials()).ok(), "initial UID1000");
        emit("EXT4_TIME_USER_CREDENTIALS uid=1000 euid=1000 gid=1000 egid=1000 before-entry=1\n");
        return {};
    }
    bool after_step()
    {
        check(ok_userland_status().ok(), "runtime status");
        const auto active = arch::realtime_clock_info();
        check(active.wall_generation == initial_clock.wall_generation && active.origin == initial_clock.origin &&
              active.state == initial_clock.state, "unprivileged operation changed clock");
        const auto *process = kernel_->scheduler().find(pid_);
        check(process != nullptr, "child retained");
        const auto &credentials = process->credentials();
        check(credentials.uid == 1000 && credentials.euid == 1000 && credentials.gid == 1000 &&
              credentials.egid == 1000 && !credentials.kernel_space, "authority across exec");
        if (process->state() != sched::ProcessState::zombie) return false;
        check(process->resources().personality == sched::UserPersonality::linux, "final musl personality");
        check(process->wait_status() == 0, "user program exit");
        auto waited = kernel_->scheduler().wait_process(reaper_, pid_);
        check(waited && waited.value() == 0, "fixture reap");
        check(filesystem.sync().ok(), "final maintained sync");
        emit("EXT4_TIME_USER_FIXTURE_PASS exit=0 actual-native-and-musl=1 uid=1000 linux-stat=qualified\n");
        return true;
    }
  private:
    Kernel *kernel_{};
    sched::ProcessId pid_{}, reaper_{};
};
constexpr std::byte archive[]{std::byte{'O'},std::byte{'K'},std::byte{'A'},std::byte{'R'},std::byte{1},
    std::byte{},std::byte{},std::byte{},std::byte{},std::byte{},std::byte{},std::byte{},
    std::byte{},std::byte{},std::byte{},std::byte{}};
}

// Explicit test-only policy: select a real software wall clock before admitting
// this retained private baseline. The ordinary OS storage hook is unchanged.
extern "C" Status ok_boot_filesystem(fs::VirtualFileSystem &vfs)
{
    if (auto status = arch::initialize_clock(); !status) return status;
    static_cast<void>(arch::initialize_realtime());
    auto anchor = arch::monotonic_sample();
    if (!anchor) return anchor.status();
    if (auto status = arch::set_realtime({2208988800LL, 123456789}, anchor.value()); !status) return status;
    initial_clock = arch::realtime_clock_info();
    check(initial_clock.origin == time::RealtimeOrigin::administrator_software, "explicit software clock");
    auto disk = os::drivers::probe_virtio_block();
    if (!disk) return disk.status();
    if (auto status = filesystem.mount(*disk.value(), fs::Ext4MountOptions{true, fs::Ext4TimestampPolicy::maintained}); !status)
        return status;
    if (auto status = vfs.mount("/", *filesystem.root()); !status) return status;
    vfs.set_mode(fs::FileSystemMode::ext4_read_write);
    emit("EXT4_TIME_USER_STORAGE virtio=1 maintained=1 baseline=retained-fixture clock=administrator-software\n");
    return {};
}

extern "C" [[noreturn]] void kernel_main()
{
    ok_platform_console_init();
    emit("EXT4_TIME_USER_FIXTURE_BEGIN scope=actual-user-mode sdk-only=1\n");
    check(user::native::prepare_memory().ok(), "native memory preparation");
    Fixture fixture;
    KernelEntryConfig config{};
    config.mode = KernelBootMode::normal;
    config.kernel.architecture = arch::configured_architecture();
    config.kernel.extension = &fixture;
    check(ok_kernel_entry(config).ok(), "kernel boot");
    check(ok_start_userland({archive, sizeof(archive), "/apps/ext4-timestamps-runner.elf"}).ok(), "native loader");
    check(ok_start_boot_extension().ok(), "initial credential fixture");
    for (;;)
    {
        static_cast<void>(ok_step_userland());
        if (fixture.after_step()) stop(true);
    }
}

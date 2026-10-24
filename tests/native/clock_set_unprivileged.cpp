#include <ok/abi/linux_native.hpp>
#include <ok/arch/clock.hpp>
#include <ok/arch/realtime.hpp>
#include <ok/core/entry.hpp>
#include <ok/syscall/linux.hpp>
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
void number(u64 value)
{
    char buffer[24]{};
    usize length = 0;
    do { buffer[length++] = static_cast<char>('0' + value % 10); value /= 10; } while (value);
    while (length) ok_platform_console_write_char(buffer[--length]);
}
void field(std::string_view name, u64 value) { emit(" "); emit(name); emit("="); number(value); }
[[noreturn]] void stop(bool success)
{
    ok_platform_debug_exit(success ? 0x10u : 0x11u);
    for (;;) asm volatile("" ::: "memory");
}
void check(bool success, std::string_view reason)
{
    if (success) return;
    emit("CLOCK_SET_FIXTURE_FAIL reason="); emit(reason); emit("\n"); stop(false);
}

#if defined(CLOCK_SET_FIXTURE_ROOT)
constexpr bool root_mode = true;
#else
constexpr bool root_mode = false;
#endif

// A real privileged test extension sets initial authority before user entry.
// The reaper is an unscheduled lifecycle record, never an execution claim.
class Fixture final : public KernelExtension
{
  public:
    Status start(Kernel &kernel) override
    {
        check(kernel_ == nullptr, "fixture started twice");
        kernel_ = &kernel;
        usize count = 0;
        for (const auto &process : kernel.scheduler().processes())
            if (!process.threads().empty() && process.threads()[0].native_active)
            {
                ++count; pid_ = process.pid();
                check(process.name() == "init" && process.parent_pid() == 0 &&
                      process.resources().personality == sched::UserPersonality::native,
                      "unexpected initial native process");
            }
        check(count == 1, "initial native process is not unique");
        auto reaper = kernel.scheduler().create_process("clock-fixture-reaper", {});
        check(reaper.ok(), "fixture reaper reservation");
        reaper_ = reaper.value();
        auto *process = kernel.scheduler().find(pid_);
        auto *owner = kernel.scheduler().find(reaper_);
        check(process && owner && owner->add_child(pid_).ok(), "fixture retained child");
        process->set_parent(reaper_);
        const auto credentials = root_mode ? user::root_credentials() : user::default_user_credentials();
        check(kernel.scheduler().set_credentials(pid_, credentials).ok(), "initial credentials");
        emit("CLOCK_SET_FIXTURE_CREDENTIALS");
        field("pid", pid_); field("uid", process->credentials().uid); field("euid", process->credentials().euid);
        field("gid", process->credentials().gid); field("egid", process->credentials().egid);
        emit(" before-user-entry=1\n");
        initial_ = arch::realtime_clock_info();
        return {};
    }

    void before_step()
    {
        waiters_.clear();
        wall_before_ = arch::realtime_clock_info().wall_generation;
        auto current = arch::monotonic_nanoseconds(); check(current.ok(), "monotonic before step");
        before_ = current.value();
        for (const auto &process : kernel_->scheduler().processes())
            for (const auto &thread : process.threads())
                if (thread.native_active && thread.state == sched::ProcessState::blocked &&
                    (thread.wait_reason == sched::ThreadWaitReason::deadline || thread.wait_reason == sched::ThreadWaitReason::poll))
                {
                    const char *api = "sleep";
                    if (thread.wait_reason == sched::ThreadWaitReason::poll)
                    {
                        api = "poll";
                        if (process.resources().personality == sched::UserPersonality::linux)
                        {
                            using Bridge = abi::linux_user::NativeBridge<abi::linux_user::configured_native_profile()>;
                            using Codec = abi::linux_user::Codec<abi::linux_user::configured_native_profile()>;
                            const auto snapshot = Bridge::snapshot(thread.native_frame);
                            const auto nr = snapshot.integer[Codec::profile.number_register];
                            for (auto operation : {abi::linux_user::Operation::select, abi::linux_user::Operation::_newselect,
                                    abi::linux_user::Operation::pselect6, abi::linux_user::Operation::pselect6_time64})
                                if (const auto expected = Codec::syscall_number(operation); expected && nr == *expected) api = "select";
                        }
                    }
                    check(waiters_.push_back({process.pid(), thread.tid, thread.wait_reason, thread.wait_key,
                         thread.native_deadline.deadline(), thread.native_deadline.generation(),
                         thread.native_deadline.armed(), thread.syscall_pending, api}).ok(), "waiter snapshot capacity");
                }
    }

    bool after_step()
    {
        check(ok_userland_status().ok(), "native runtime status");
        const auto wall = arch::realtime_clock_info();
        auto current = arch::monotonic_nanoseconds(); check(current.ok(), "monotonic after step");
        check(current.value() >= before_, "monotonic moved backward");
        if (wall.wall_generation != wall_before_)
            for (const auto &wait : waiters_)
            {
                const auto *process = kernel_->scheduler().find(wait.pid);
                if (!process) continue;
                for (const auto &thread : process->threads())
                    if (thread.tid == wait.tid && thread.native_active &&
                        thread.state == sched::ProcessState::blocked && thread.wait_reason == wait.reason)
                    {
                        check(thread.wait_key == wait.key && thread.syscall_pending == wait.pending,
                              "waiting ownership changed during clock set");
                        if (wait.reason == sched::ThreadWaitReason::deadline)
                            check(wait.armed && thread.native_deadline.armed() &&
                                  thread.native_deadline.deadline() == wait.deadline &&
                                  thread.native_deadline.generation() == wait.generation,
                                  "sleep deadline changed during clock set");
                        else
                            check(wait.pending && thread.syscall_pending, "poll/select syscall is not pending");
                        emit("CLOCK_SET_FIXTURE_WAIT_SET api="); emit(wait.api);
                        field("pid", wait.pid); field("tid", wait.tid);
                        field("wall_before", wall_before_); field("wall_after", wall.wall_generation);
                        field("monotonic_before", before_); field("monotonic_after", current.value());
                        field("wait_key", wait.key);
                        if (wait.reason == sched::ThreadWaitReason::deadline)
                        { field("deadline", wait.deadline); field("wait_generation", wait.generation); }
                        else emit(" deadline=private pending-syscall=1");
                        emit(" held=1\n");
                    }
            }
        if (!root_mode)
            check(wall.wall_generation == initial_.wall_generation && wall.origin == initial_.origin &&
                  wall.state == initial_.state, "denied calls changed realtime state");
        const auto *process = kernel_->scheduler().find(pid_);
        check(process != nullptr, "fixture child was reaped early");
        const auto expected = root_mode ? user::root_credentials() : user::default_user_credentials();
        check(process->credentials().uid == expected.uid && process->credentials().euid == expected.euid &&
              process->credentials().gid == expected.gid && process->credentials().egid == expected.egid &&
              !process->credentials().kernel_space, "process authority changed across exec");
        if (process->state() != sched::ProcessState::zombie) return false;
        check(process->wait_status() == 0, "user probe exit status");
        auto waited = kernel_->scheduler().wait_process(reaper_, pid_);
        check(waited && waited.value() == 0, "fixture wait status");
        emit("CLOCK_SET_FIXTURE_PASS mode="); emit(root_mode ? "root" : "deny");
        emit(" exit=0 actual-native-and-musl=1\n");
        return true;
    }
  private:
    struct Waiter
    {
        sched::ProcessId pid{}; sched::ThreadId tid{}; sched::ThreadWaitReason reason{};
        u64 key{}, deadline{}, generation{}; bool armed{}, pending{}; const char *api{};
    };
    Kernel *kernel_{};
    sched::ProcessId pid_{}, reaper_{};
    StaticVector<Waiter, sched::max_processes> waiters_{};
    time::RealtimeInfo initial_{};
    u64 wall_before_{}, before_{};
};

// Empty immutable rescue archive; the unchanged OS storage hook mounts the
// separately prepared Virtio ext4 image before loading the initial native ELF.
constexpr std::byte archive[]{std::byte{'O'},std::byte{'K'},std::byte{'A'},std::byte{'R'},std::byte{1},
    std::byte{},std::byte{},std::byte{},std::byte{},std::byte{},std::byte{},std::byte{},
    std::byte{},std::byte{},std::byte{},std::byte{}};
} // namespace

extern "C" [[noreturn]] void kernel_main()
{
    ok_platform_console_init();
    emit("CLOCK_SET_FIXTURE_BEGIN scope=actual-user-mode sdk-only=1\n");
    check(user::native::prepare_memory().ok(), "native memory preparation");
    Fixture fixture;
    KernelEntryConfig config{};
    config.mode = KernelBootMode::normal;
    config.kernel.architecture = arch::configured_architecture();
    config.kernel.extension = &fixture;
    check(ok_kernel_entry(config).ok(), "kernel boot");
    check(ok_start_userland({archive, sizeof(archive), "/apps/clock-set-runner.elf"}).ok(), "native fixture loader");
    check(ok_start_boot_extension().ok(), "initial credential fixture");
    for (;;)
    {
        fixture.before_step();
        static_cast<void>(ok_step_userland());
        if (fixture.after_step()) stop(true);
    }
}

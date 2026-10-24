#include "../../drivers/virtio/block.hpp"
#include <ok/arch/clock.hpp>
#include <ok/arch/realtime.hpp>
#include <ok/core/entry.hpp>
#include <ok/fs/ext4_mounted_metadata.hpp>
#include <ok/user/runtime.hpp>
#include <new>
#include "journalled_directory_mode_fixture.hpp"

using namespace ok;
extern "C" void ok_platform_console_init();
extern "C" void ok_platform_console_write_char(char);
extern "C" void ok_platform_debug_exit(u32);
extern "C" const std::byte jdmode_archive_start[], jdmode_archive_end[];

#ifndef JDMODE_UID
#define JDMODE_UID 1000
#endif
#ifndef JDMODE_NEGATIVE_CLOCK
#define JDMODE_NEGATIVE_CLOCK 0
#endif
static_assert(JDMODE_UID == 0 || JDMODE_UID == 1000);
static_assert(!JDMODE_NEGATIVE_CLOCK || JDMODE_UID == 0);

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
    emit("JDMODE_FIXTURE_FAIL reason="); emit(reason); emit("\n"); stop(false);
}
u16 little16(const std::byte *p)
{ return std::to_integer<u16>(p[0]) | (std::to_integer<u16>(p[1]) << 8); }
u32 little32(const std::byte *p)
{ return little16(p) | (u32{little16(p + 2)} << 16); }

// Every event describes a completed call to the actual Virtio transport. The
// wrapper neither manufactures successful completions nor modifies the payload.
class ObservedDevice final : public driver::BlockDevice
{
  public:
    void bind(driver::BlockDevice &device) { check(!device_, "single transport binding"); device_ = &device; }
    driver::BlockGeometry geometry() const override { return device_->geometry(); }
    Status read_blocks(u64 sector, std::span<std::byte> bytes) override
    { return device_->read_blocks(sector, bytes); }
    Status write_blocks(u64 sector, std::span<const std::byte> bytes) override
    {
        const auto status = device_->write_blocks(sector, bytes);
        ++ordinal; ++writes;
        const auto crc = fs::jbd2::detail::crc32c(~u32{0},
            {reinterpret_cast<const u8 *>(bytes.data()), bytes.size()});
        emit("JDMODE_IO"); field("ordinal", ordinal); emit(" kind=write");
        field("sector", sector); field("bytes", bytes.size()); field("crc32c", crc);
        field("status", static_cast<u32>(status.code())); emit("\n");
        if (status)
        {
            inode(sector, bytes, journalled_fixture::child);
        }
        return status;
    }
    Status flush() override
    {
        const auto status = device_->flush();
        ++ordinal; ++flushes;
        emit("JDMODE_IO"); field("ordinal", ordinal); emit(" kind=flush sector=0 bytes=0 crc32c=0");
        field("status", static_cast<u32>(status.code())); emit("\n");
        return status;
    }
    u64 ordinal{}, writes{}, flushes{};
  private:
    void inode(u64 sector, std::span<const std::byte> bytes, journalled_fixture::Inode target)
    {
        const auto home = journalled_fixture::origin + target.block * 2;
        if (sector > home || home - sector > bytes.size() / 512) return;
        const auto offset = static_cast<usize>((home - sector) * 512) + target.offset;
        if (offset > bytes.size() || bytes.size() - offset < 256) return;
        const auto *p = bytes.data() + offset;
        emit("JDMODE_INODE"); field("io", ordinal); field("inode", target.number);
        field("mode", little16(p));
        field("uid", little16(p + 2) | (u32{little16(p + 120)} << 16));
        field("gid", little16(p + 24) | (u32{little16(p + 122)} << 16));
        field("ctime_sec", little32(p + 12)); field("ctime_nsec", little32(p + 132) >> 2);
        field("version", little32(p + 36) | (u64{little32(p + 152)} << 32)); emit("\n");
    }
    driver::BlockDevice *device_{};
};
using Mount = fs::Ext4MountedMetadata<1>;
ObservedDevice transport;
Mount::Registry registry;
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
        const auto credentials = JDMODE_UID ? user::default_user_credentials() : user::root_credentials();
        check(kernel.scheduler().set_credentials(pid_, credentials).ok(), "initial user credentials");
        emit("JDMODE_CREDENTIALS"); field("uid", JDMODE_UID); field("euid", JDMODE_UID);
        field("gid", JDMODE_UID); field("egid", JDMODE_UID); emit(" before-entry=1 personality=linux\n");
        return {};
    }
    bool after_step()
    {
        check(ok_userland_status().ok(), "runtime status");
        const auto *process = kernel_->scheduler().find(pid_);
        check(process != nullptr, "child retained");
        const auto &c = process->credentials();
        check(c.uid == JDMODE_UID && c.euid == JDMODE_UID && c.suid == JDMODE_UID &&
              c.gid == JDMODE_UID && c.egid == JDMODE_UID && c.sgid == JDMODE_UID && !c.kernel_space,
              "retained process credentials");
        check(process->resources().personality == sched::UserPersonality::linux, "retained Linux personality");
        const auto active = arch::realtime_clock_info();
        check(active.origin == time::RealtimeOrigin::administrator_software && active.state == initial_clock.state,
              "retained active software clock");
        if (JDMODE_UID) check(active.wall_generation == initial_clock.wall_generation, "unprivileged clock identity");
        if (process->state() != sched::ProcessState::zombie) return false;
        check(process->wait_status() == 0, "user exit status");
        const auto mounted = filesystem->report();
        constexpr u64 mutations = JDMODE_NEGATIVE_CLOCK ? 0 : 6;
        check(mounted.phase == fs::Ext4MountPhase::readable && mounted.status.ok() && mounted.published &&
              !mounted.reading && mounted.epoch == mutations + 1, "healthy completed mount epoch");
        check(transport.writes == mutations * 11 && transport.flushes == mutations * 9 + 2,
              "completed transaction and user fsync counts");
        auto waited = kernel_->scheduler().wait_process(reaper_, pid_);
        check(waited && waited.value() == 0, "fixture reap");
        emit("JDMODE_FIXTURE_PASS"); field("uid", JDMODE_UID); emit(" exit=0 reaped=1 personality=linux");
        field("epoch", mounted.epoch); field("writes", transport.writes); field("flushes", transport.flushes);
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
    if (auto status = arch::set_realtime({JDMODE_NEGATIVE_CLOCK ? -123456789 : 1700000000, 123456789}, anchor.value()); !status) return status;
    initial_clock = arch::realtime_clock_info();
    check(initial_clock.origin == time::RealtimeOrigin::administrator_software, "explicit software clock");
    auto disk = os::drivers::probe_virtio_block(); if (!disk) return disk.status();
    transport.bind(*disk.value());
    check(!filesystem, "single maintained mount construction");
    filesystem = ::new (filesystem_storage.data()) Mount{fs::Ext4MountedPolicy::maintained_noatime};
    auto key = registry.register_device(transport, 17, 1024); if (!key) return key.status();
    if (auto status = filesystem->mount(registry, key.value(),
            {journalled_fixture::origin, journalled_fixture::sectors}); !status) return status;
    auto *root = filesystem->root(); check(root != nullptr, "maintained side mount root");
    for (const auto path : {"/journal", "/alias"})
    {
        if (auto status = vfs.create(path, fs::NodeType::directory); !status) return status;
        if (auto status = vfs.mount(path, *root); !status) return status;
    }
    check(!transport.writes && !transport.flushes && filesystem->report().epoch == 1, "read-only mount admission");
    emit("JDMODE_STORAGE virtio=1 policy=maintained-noatime aliases=2 root=archive clock=administrator-software\n");
    return {};
}

extern "C" [[noreturn]] void kernel_main()
{
    ok_platform_console_init();
    emit("JDMODE_FIXTURE_BEGIN scope=actual-musl-user-mode sdk=31 sdk-only=1"); field("uid", JDMODE_UID);
    emit(JDMODE_NEGATIVE_CLOCK ? " clock=negative\n" : " clock=in-range\n");
    check(user::native::prepare_memory().ok(), "native memory preparation");
    Fixture fixture;
    KernelEntryConfig config{};
    config.mode = KernelBootMode::normal;
    config.kernel.architecture = arch::configured_architecture(); config.kernel.extension = &fixture;
    check(ok_kernel_entry(config).ok(), "kernel boot");
    check(ok_start_userland({jdmode_archive_start, static_cast<usize>(jdmode_archive_end - jdmode_archive_start),
          "/bin/musl-journalled-directory-mode"}).ok(), "Linux archive loader");
    check(ok_start_boot_extension().ok(), "initial credential fixture");
    for (;;)
    {
        static_cast<void>(ok_step_userland());
        if (fixture.after_step()) stop(true);
    }
}

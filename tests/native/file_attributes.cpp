#include "drivers/virtio/block.hpp"
#include <ok/fs/ext4_fs.hpp>
#include <ok/posix/posix.hpp>
#include <new>
#include "attribute_fixture.hpp"
using namespace ok;
namespace {
void emit(const char *text)
{
    while (*text)
    {
#if defined(__x86_64__) || defined(__i386__)
        u8 ready;
        do { asm volatile("inb %1, %0" : "=a"(ready) : "Nd"(u16{0x3fd})); } while (!(ready & 32));
        asm volatile("outb %0, %1" :: "a"(static_cast<u8>(*text++)), "Nd"(u16{0x3f8}));
#elif defined(__aarch64__) || defined(__arm__)
        while (*reinterpret_cast<volatile u32 *>(0x09000018) & 32) {}
        *reinterpret_cast<volatile u32 *>(0x09000000) = static_cast<u8>(*text++);
#elif defined(__riscv)
        *reinterpret_cast<volatile u8 *>(0x10000000) = static_cast<u8>(*text++);
#elif defined(__loongarch__)
        while (!(*reinterpret_cast<volatile u8 *>(0x1fe001e5) & 32)) {}
        *reinterpret_cast<volatile u8 *>(0x1fe001e0) = static_cast<u8>(*text++);
#elif defined(__mips__)
#if __SIZEOF_POINTER__ == 8
        constexpr uptr uart = 0xffffffffb80003f8ull;
#else
        constexpr uptr uart = 0xb80003f8;
#endif
        while (!(*reinterpret_cast<volatile u8 *>(uart + 5) & 32)) {}
        *reinterpret_cast<volatile u8 *>(uart) = static_cast<u8>(*text++);
#elif defined(__powerpc__) || defined(__PPC__)
        while (!(*reinterpret_cast<volatile u8 *>(0xe0004505) & 32)) {}
        *reinterpret_cast<volatile u8 *>(0xe0004500) = static_cast<u8>(*text++);
#else
#error "Every supported probe profile requires its explicit serial backend"
#endif
    }
}

[[noreturn]] void stop(bool success = false)
{
#if defined(__x86_64__) || defined(__i386__)
    asm volatile("outl %0, %1" :: "a"(success ? 16U : 17U), "Nd"(u16{0xf4}));
#else
    static_cast<void>(success);
#endif
    for (;;) asm volatile("" ::: "memory");
}

void check(bool value, const char *reason)
{
    if (value) return;
    emit("FILE_ATTRIBUTES_FAIL "); emit(reason); emit("\n"); stop();
}

} // namespace
// Minimal freestanding probe runtime; RTTI remains enabled as in the SDK.
extern "C" void *memcpy(void *to, const void *from, usize size)
{
    auto *out = static_cast<volatile std::byte *>(to);
    const auto *in = static_cast<const std::byte *>(from);
    for (usize index = 0; index < size; ++index) out[index] = in[index];
    return to;
}
extern "C" void *memset(void *to, int value, usize size)
{
    auto *out = static_cast<volatile u8 *>(to);
    for (usize index = 0; index < size; ++index) out[index] = static_cast<u8>(value);
    return to;
}
extern "C" int memcmp(const void *one, const void *two, usize size)
{
    const auto *a = static_cast<const u8 *>(one);
    const auto *b = static_cast<const u8 *>(two);
    for (usize index = 0; index < size; ++index)
        if (a[index] != b[index]) return a[index] < b[index] ? -1 : 1;
    return 0;
}
extern "C" void *memchr(const void *source, int value, usize size)
{
    const auto *bytes = static_cast<const u8 *>(source);
    for (usize index = 0; index < size; ++index)
        if (bytes[index] == static_cast<u8>(value))
            return const_cast<u8 *>(bytes + index);
    return nullptr;
}
extern "C" usize strlen(const char *text)
{
    usize count = 0;
    while (text[count]) ++count;
    return count;
}
extern "C" int atexit(void (*)()) { return 0; }
extern "C" void __cxa_pure_virtual() { stop(); }
namespace std { [[noreturn]] void terminate() noexcept { stop(); } }
void operator delete(void *) noexcept { stop(); }
void operator delete(void *, usize) noexcept { stop(); }
namespace __cxxabiv1
{
class __class_type_info { public: virtual ~__class_type_info(); };
class __si_class_type_info : public __class_type_info { public: ~__si_class_type_info() override; };
class __vmi_class_type_info : public __class_type_info { public: ~__vmi_class_type_info() override; };
__class_type_info::~__class_type_info() = default;
__si_class_type_info::~__si_class_type_info() = default;
__vmi_class_type_info::~__vmi_class_type_info() = default;
} // namespace __cxxabiv1

namespace {
alignas(fs::VirtualFileSystem) std::array<std::byte, sizeof(fs::VirtualFileSystem)> vfs_storage{}, other_storage{};
alignas(fs::Ext4FileSystem) std::array<std::byte, sizeof(fs::Ext4FileSystem)> ext4_storage{};
alignas(sched::Scheduler) std::array<std::byte, sizeof(sched::Scheduler)> scheduler_storage{};
alignas(posix::PosixService) std::array<std::byte, sizeof(posix::PosixService)> service_storage{};
alignas(driver::ConsoleDriver) std::array<std::byte, sizeof(driver::ConsoleDriver)> console_storage{};
class ObservedDisk final : public driver::BlockDevice {
    driver::BlockDevice &device_;
  public:
    usize reads{}, writes{}, flushes{};
    explicit ObservedDisk(driver::BlockDevice &device) : device_(device) {}
    driver::BlockGeometry geometry() const override { return device_.geometry(); }
    Status read_blocks(u64 first, std::span<std::byte> out) override { ++reads; return device_.read_blocks(first, out); }
    Status write_blocks(u64, std::span<const std::byte>) override { ++writes; return Status::denied("attribute probe is readonly"); }
    Status flush() override { ++flushes; return Status::denied("attribute probe is readonly"); }
};
void absent_times(const fs::FileAttributes &attributes) {
    check(!attributes.has(fs::Attribute::access_time) && !attributes.has(fs::Attribute::modification_time) &&
          !attributes.has(fs::Attribute::change_time) && attributes.access.source == fs::TimestampSource::unavailable &&
          attributes.modification.source == fs::TimestampSource::unavailable && attributes.change.source == fs::TimestampSource::unavailable,
          "unavailable timestamps acquired provenance");
}
fs::FileAttributes status(posix::PosixService &service, std::string_view path) {
    auto value = service.statat(posix::at_FDCWD, path); check(value.ok(), "checked path metadata");
    auto result = value.value().attributes;
    check(result.has(fs::Attribute::inode) && result.inode && result.has(fs::Attribute::device) && result.device.minor, "path identity");
    return result;
}
void same(posix::PosixService &service, posix::Fd fd, const fs::FileAttributes &expected) {
    auto value = service.fstat(fd); check(value.ok(), "checked descriptor metadata");
    check(value.value().attributes.inode == expected.inode && value.value().attributes.device == expected.device, "retained descriptor identity changed");
    absent_times(value.value().attributes);
}
} // namespace
extern "C" [[noreturn]] void kernel_main() {
    emit("FILE_ATTRIBUTES_BEGIN scope=qemu-device-service\n");
    auto found = os::drivers::probe_virtio_block(); check(found.ok(), "actual virtio block device");
    ObservedDisk disk(*found.value());
    auto &filesystem = *::new(ext4_storage.data()) fs::Ext4FileSystem;
    check(filesystem.mount(disk, false).ok(), "readonly ext4 admission");
    auto &vfs = *::new(vfs_storage.data()) fs::VirtualFileSystem;
    for (auto path : {"/disk", "/alias", "/other"}) check(vfs.create(path, fs::NodeType::directory).ok(), "RAM mount point");
    check(vfs.mount("/disk", *filesystem.root()).ok() && vfs.mount("/alias", *filesystem.root()).ok(), "provider aliases");
    auto &other = *::new(other_storage.data()) fs::VirtualFileSystem;
    check(vfs.mount("/other", *other.lookup("/")).ok(), "distinct provider");
    auto &scheduler = *::new(scheduler_storage.data()) sched::Scheduler;
    auto &console = *::new(console_storage.data()) driver::ConsoleDriver;
    auto &service = *::new(service_storage.data()) posix::PosixService;
    check(console.start().ok() && service.initialize(vfs, console, scheduler).ok(), "native services");
    auto process = scheduler.create_user_process("attribute-probe", arch::configured_arch_operations().make_user_context({0x400000, 0x800000, 0}));
    check(process.ok() && service.activate(process.value()).ok(), "service process resources");
    const auto ext4 = status(service, "/disk/sample"), alias = status(service, "/alias/sample");
    check(ext4.inode == attribute_fixture::inode && ext4.inode == alias.inode && ext4.device == alias.device, "real inode and alias device");
    check(status(service, "/other").device != ext4.device, "distinct provider device");
    const fs::EpochTimestamp times[] = {ext4.access, ext4.modification, ext4.change};
    const fs::Attribute fields[] = {fs::Attribute::access_time, fs::Attribute::modification_time, fs::Attribute::change_time};
    for (usize i = 0; i < 3; ++i)
        check(ext4.has(fields[i]) && times[i].source == fs::TimestampSource::readonly_ext4 &&
              times[i].seconds == attribute_fixture::seconds[i] && times[i].nanoseconds == attribute_fixture::nanoseconds[i], "raw inode time oracle");
    auto readonlyfd = service.open("/disk/sample", posix::o_RDONLY); check(readonlyfd.ok(), "readonly descriptor");
    auto diskstat = service.fstat(readonlyfd.value());
    check(diskstat.ok() && diskstat.value().attributes.inode == ext4.inode && diskstat.value().attributes.device == ext4.device &&
          diskstat.value().attributes.access.seconds == ext4.access.seconds, "descriptor provider attributes");
    check(service.close(readonlyfd.value()).ok(), "readonly close");
    auto opened = service.open("/tmp/original", posix::o_CREAT | posix::o_RDWR); check(opened.ok(), "RAM open");
    auto original = status(service, "/tmp/original"); absent_times(original);
    check(service.link("/tmp/original", "/tmp/link").ok() && service.rename("/tmp/original", "/tmp/renamed").ok(), "link rename");
    check(status(service, "/tmp/link").inode == original.inode && status(service, "/tmp/renamed").inode == original.inode, "link rename inode stability");
    auto duplicate = service.duplicate(opened.value()); check(duplicate.ok(), "native dup");
    auto child = service.fork(); check(child.ok() && service.activate(child.value()).ok(), "native service fork");
    same(service, opened.value(), original); same(service, duplicate.value(), original);
    check(service.close(opened.value()).ok() && service.close(duplicate.value()).ok() && service.activate(process.value()).ok(), "child description retirement");
    check(service.unlink("/tmp/link").ok() && service.unlink("/tmp/renamed").ok(), "retained unlink");
    same(service, opened.value(), original); same(service, duplicate.value(), original);
    check(service.close(opened.value()).ok() && service.close(duplicate.value()).ok(), "last description retirement");
    for (usize i = 0; i < 48; ++i) {
        auto fd = service.open("/tmp/reused", posix::o_CREAT | posix::o_RDWR); check(fd.ok(), "reuse open");
        auto current = status(service, "/tmp/reused"); check(current.inode > original.inode, "reused slot acquired old identity");
        original = current; check(service.close(fd.value()).ok() && service.unlink("/tmp/reused").ok(), "reuse retire");
    }
    static constexpr std::array<std::byte, 1> archive{std::byte{'x'}};
    check(vfs.create_readonly_file("/tmp/archive", archive).ok(), "archive projection"); absent_times(status(service, "/tmp/archive"));
    check(service.fstat(1).value().attributes.valid == 0, "console remains incomplete");
    auto pipe = service.pipe(); check(pipe.ok(), "native pipe");
    for (auto fd : pipe.value()) { check(service.fstat(fd).value().attributes.valid == 0, "pipe remains incomplete"); check(service.close(fd).ok(), "pipe close"); }
    check(disk.reads && !disk.writes && !disk.flushes, "attribute reads modified actual disk");
    emit("FILE_ATTRIBUTES_PASS scope=qemu-device-service disk-writes=0 linux-stat=not-executed\n"); stop(true);
}

#include "drivers/virtio/block.hpp"
#include <ok/fs/ext4_mounted_metadata.hpp>
#include <ok/posix/posix.hpp>
#include <new>
#include "linux_fixture.hpp"

using namespace ok;
using namespace ok::fs::jbd2;
namespace
{
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
    emit("JBD2_NATIVE_FAIL "); emit(reason); emit("\n"); stop();
}

alignas(4096) std::array<std::byte,1024> data{};
[[maybe_unused]] alignas(fs::Ext4RecoveryCompletion<>) std::array<std::byte,sizeof(fs::Ext4RecoveryCompletion<>)> completion_storage{};
[[maybe_unused]] alignas(fs::Ext4MetadataTransaction) std::array<std::byte,sizeof(fs::Ext4MetadataTransaction)> transaction_storage{};
[[maybe_unused]] alignas(fs::Ext4ReplayPreview<>) std::array<std::byte,sizeof(fs::Ext4ReplayPreview<>)> preview_storage{};
u16 little16(const std::byte *p) { return std::to_integer<u16>(p[0]) | (std::to_integer<u16>(p[1]) << 8); }
u32 little32(const std::byte *p) { return little16(p) | (u32{little16(p + 2)} << 16); }
[[maybe_unused]] void verify_inode(driver::BlockDevice &disk, bool recovered)
{
    check(disk.read_blocks(fixture::seed_block * 2, data).ok(), "read actual seeded inode block");
    const auto *inode = data.data() + fixture::seed_offset;
    check(little16(inode) == (recovered ? 0100640 : 0100600), "seed mode reflects replay");
    check(little16(inode + 2) == (recovered ? 2000 : 1000) && little16(inode + 24) == (recovered ? 2001 : 1001),
          "seed ownership reflects replay");
    check(little32(inode + 4) == 4096 && little16(inode + 26) == 1, "seed size and link count");
    std::array<u8,256> bytes{};
    for (usize index = 0; index < bytes.size(); ++index) bytes[index] = std::to_integer<u8>(inode[index]);
    const u32 recorded = little16(inode + 124) | (u32{little16(inode + 130)} << 16);
    bytes[124] = bytes[125] = bytes[130] = bytes[131] = 0;
    const std::array<u8,4> number{12,0,0,0};
    u32 crc = detail::crc32c(~u32{0}, fixture::uuid);
    crc = detail::crc32c(crc, number);
    crc = detail::crc32c(crc, std::span<const u8>{bytes}.subspan(100,4));
    check(detail::crc32c(crc, bytes) == recorded, "replayed inode ext4 CRC32C");
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

using Mount = fs::Ext4MountedMetadata<1>;
struct Services
{
    sched::Scheduler scheduler;
    fs::VirtualFileSystem vfs;
    driver::ConsoleDriver console;
    posix::PosixService posix;
};
alignas(Mount) std::array<std::byte,sizeof(Mount)> mount_storage{};
alignas(Services) std::array<std::byte,sizeof(Services)> services_storage{};
#ifndef OK_MOUNT_CASE
#define OK_MOUNT_CASE "repeated"
#endif
#ifndef OK_MOUNT_FAIL_WRITE
#define OK_MOUNT_FAIL_WRITE 0
#endif
#ifndef OK_MOUNT_FAIL_FLUSH
#define OK_MOUNT_FAIL_FLUSH 0
#endif
constexpr u64 origin=11, sectors=65536;
constexpr fs::Ext4InodeMetadataUpdate first{12,2000,2001,1700000000,123456789,0640};
constexpr fs::Ext4InodeMetadataUpdate second{16,5000,6000,1700000001,42,0604};
class ObservedDevice final : public driver::BlockDevice
{
  public:
    explicit ObservedDevice(driver::BlockDevice &device) : device_(device) {}
    driver::BlockGeometry geometry() const override { return device_.geometry(); }
    Status read_blocks(u64 sector,std::span<std::byte> bytes) override
    { ++reads;return device_.read_blocks(sector,bytes); }
    void gate()
    {
        if(!mount)return;
        check(!root->query_metadata()&&mount->update_metadata(first).code()==StatusCode::busy,"mounted callback admission gate");
    }
    Status write_blocks(u64 sector,std::span<const std::byte> bytes) override
    {
        gate();++writes;auto status=device_.write_blocks(sector,bytes);if(!status)return status;
        return armed&&writes==11+OK_MOUNT_FAIL_WRITE&&OK_MOUNT_FAIL_WRITE?Status::io_error("completed mounted write fault"):Status{};
    }
    Status flush() override
    {
        gate();++flushes;auto status=device_.flush();if(!status)return status;
        return armed&&flushes==9+OK_MOUNT_FAIL_FLUSH&&OK_MOUNT_FAIL_FLUSH?Status::io_error("completed mounted flush fault"):Status{};
    }
    Mount *mount{};fs::Node *root{};bool armed{};usize reads{},writes{},flushes{};
  private: driver::BlockDevice &device_;
};
extern "C" [[noreturn]] void kernel_main()
{
    emit("EXT4_MOUNTED_BEGIN scope=internal-metadata posix-mutation=unsupported\n");
    auto found=os::drivers::probe_virtio_block();check(found.ok(),"actual device probe");
    ObservedDevice transport(*found.value());Mount::Registry registry;
    auto key=registry.register_device(transport,17,1024);check(key.ok(),"mounted authoritative registration");
#if defined(OK_MOUNT_RECOVER)
    Mount::Registry::Session session;
    check(registry.acquire(key.value(),{origin,sectors},block::SessionAccess::writable,session).ok(),"fresh restart session");
    auto &recovery=*::new(completion_storage.data()) fs::Ext4RecoveryCompletion<>;
    check(recovery.run(session,{0,sectors}).ok()&&recovery.report().complete(),"fresh restart checkpoint");
    check(session.close().ok()&&registry.detach(key.value()).ok(),"restart owner drainage");
#else
    auto &mount=*::new(mount_storage.data()) Mount;
    check(mount.mount(registry,key.value(),{origin,sectors}).ok(),"checked mounted admission");
    auto *root=mount.root();check(root,"publish checked root");
    auto &services=*::new(services_storage.data()) Services;
    check(services.console.start().ok()&&services.posix.initialize(services.vfs,services.console,services.scheduler).ok(),"actual VFS/POSIX services");
    auto process=services.scheduler.create_user_process("mounted",arch::configured_arch_operations().make_user_context({0x400000,0x800000,0}));
    check(process.ok()&&services.posix.activate(process.value()).ok(),"mounted native process record");
    check(services.vfs.create("/journal",fs::NodeType::directory).ok()&&services.vfs.create("/alias",fs::NodeType::directory).ok(),"native mount directories");
    check(services.vfs.mount("/journal",*root).ok()&&services.vfs.mount("/alias",*root).ok(),"native provider aliases");
    auto fd=services.posix.open("/journal/seed",posix::o_RDONLY);check(fd.ok(),"native retained fd");
    auto duplicate=services.posix.duplicate(fd.value());check(duplicate.ok(),"native retained duplicate");
    auto before=services.posix.fstat(fd.value());check(before.ok()&&before.value().uid==1000&&before.value().blocks==8,"native exact initial metadata");
    auto directory=services.posix.open("/journal",posix::o_RDONLY);check(directory.ok(),"native open directory");
    check(services.posix.read(directory.value(),std::span<std::byte>{data}.first(4)).status().code()==StatusCode::is_directory,"directory error remains nonfatal");
    check(services.posix.close(directory.value()).ok(),"close native directory");
    auto node=root->lookup_child("seed");check(node.ok()&&!node.value()->chmod(0777)&&!node.value()->truncate(0)&&!transport.writes,"ordinary mutations refused before I/O");
    transport.mount=&mount;transport.root=root;
    check(mount.update_metadata(first).ok()&&transport.writes==11&&transport.flushes==9,"first synchronous checkpoint");
    auto after=services.posix.fstat(duplicate.value());
    check(after.ok()&&after.value().uid==2000&&after.value().mode==0100640&&after.value().attributes.inode==before.value().attributes.inode&&
          after.value().attributes.device==before.value().attributes.device,"native retained fd metadata renewal");
    auto alias=services.posix.stat("/alias/seed");check(alias.ok()&&alias.value().uid==2000,"native live alias metadata renewal");
    transport.armed=true;auto result=mount.update_metadata(second);
#if OK_MOUNT_FAIL_WRITE || OK_MOUNT_FAIL_FLUSH
    check(!result&&mount.report().phase==fs::Ext4MountPhase::failed,"second operation fault quarantines live mounted provider");
    const auto calls=transport.reads+transport.writes+transport.flushes;
    check(!root->query_metadata()&&!root->sync()&&!services.posix.fstat(fd.value())&&!mount.update_metadata(first)&&!mount.close(),"checked operations denied after quarantine");
    check(!registry.detach(key.value())&&calls==transport.reads+transport.writes+transport.flushes,"quarantine retains device without I/O");
#else
    check(result.ok()&&mount.report().epoch==3&&mount.buffers().session_serial==1&&mount.buffers().first_sector==origin,"different participant repeated persistent session");
    auto other=services.posix.stat("/journal/other3");check(other.ok()&&other.value().uid==5000&&other.value().gid==6000&&other.value().mode==0100604,"different table block renewal");
    check(!mount.close()&&services.posix.close(fd.value()).ok()&&services.posix.close(duplicate.value()).ok(),"published provider lifetime retained");
#endif
#endif
    emit("EXT4_MOUNTED_PASS scope=qemu-device case=" OK_MOUNT_CASE " internal-metadata=1\n");stop(true);
}

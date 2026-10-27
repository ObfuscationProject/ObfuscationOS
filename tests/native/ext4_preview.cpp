#include "drivers/virtio/block.hpp"
#include <ok/fs/ext4/txn.hpp>
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
alignas(fs::Ext4ReplayPreview<>) std::array<std::byte,sizeof(fs::Ext4ReplayPreview<>)> preview_storage{};
u16 little16(const std::byte *p) { return std::to_integer<u16>(p[0]) | (std::to_integer<u16>(p[1]) << 8); }
u32 little32(const std::byte *p) { return little16(p) | (u32{little16(p + 2)} << 16); }
void verify_inode(driver::BlockDevice &disk, bool recovered)
{
    check(disk.read_blocks(fixture::seed_block * 2, data).ok(), "read actual seeded inode block");
    const auto *inode = data.data() + fixture::seed_offset;
    check(little16(inode) == (recovered ? 0100600 : 0100644), "seed mode reflects replay");
    check(little16(inode + 2) == (recovered ? 1000 : 0) && little16(inode + 24) == (recovered ? 1001 : 0),
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

class ObservedDevice final : public driver::BlockDevice
{
  public:
    explicit ObservedDevice(driver::BlockDevice &device) : actual(device) {}
    driver::BlockGeometry geometry() const override { return actual.geometry(); }
    Status read_blocks(u64 sector, std::span<std::byte> bytes) override { return actual.read_blocks(sector, bytes); }
    Status write_blocks(u64 sector, std::span<const std::byte> bytes) override
    {
        ++writes; return actual.write_blocks(sector, bytes);
    }
    Status flush() override { ++flushes; return actual.flush(); }
    driver::BlockDevice &actual;
    usize writes{}, flushes{};
};
extern "C" [[noreturn]] void kernel_main()
{
    emit("EXT4_PREVIEW_BEGIN source=linux-created-journal mount=none home-writes=none\n");
    auto found = os::drivers::probe_virtio_block();
    check(found.ok(), "probe actual Virtio device");
    auto &disk = *found.value();
    check(disk.geometry().block_size == 512 && disk.geometry().block_count == 65536 &&
          !disk.geometry().writable, "preview uses the explicit read-only Linux fixture");
    verify_inode(disk, false);
    ObservedDevice observed(disk);
    auto &preview = *::new (preview_storage.data()) fs::Ext4ReplayPreview<>;
    const auto opened = preview.open(observed, {0, disk.geometry().block_count});
#if defined(OK_EXT4_PREVIEW_MAPPING_REJECT)
    check(!opened && opened.code() == StatusCode::unsupported && !preview.ready(), "unsafe mapping payload rejected");
    check(!preview.lookup(2, "seed"), "rejected preview published no namespace");
#elif defined(OK_EXT4_PREVIEW_PAYLOAD_CORRUPT)
    check(!opened && opened.code() == StatusCode::io_error && !preview.ready(), "corrupt payload rejected");
    check(!preview.lookup(2, "seed"), "corrupt preview published no namespace");
#else
    if (!opened) { emit(opened.message().data()); emit("\n"); }
    check(opened.ok() && preview.ready() && preview.report().planned_actions == 2 &&
          preview.report().validated_actions == 2 && preview.report().committed_transactions == 1 &&
          preview.report().next_sequence == 3, "complete checked final metadata view");
    const auto number = preview.lookup(2, "seed");
    check(number.ok() && number.value() == 12, "checked directory lookup");
    const auto inode = preview.inode(number.value());
    check(inode.ok() && inode.value().mode == 0100600 && inode.value().uid == 1000 &&
          inode.value().gid == 1001 && inode.value().size == 4096, "final journal inode metadata");
    std::array<u8,4096> bytes{};
    const auto read = preview.read(number.value(), 0, bytes);
    check(read.ok() && read.value() == bytes.size(), "checked file read");
    for (usize index = 0; index < bytes.size(); ++index)
        check(bytes[index] == u8(index * 17 + 29), "file data matches independent fixture");
    usize entries = 0;
    check(preview.directory(2, [&](const fs::Ext4ReadOnlyDirent &) { ++entries; return Status::success(); }).ok() &&
          entries == 4, "checked streaming directory entries");
    const auto absent = preview.lookup(2, "absent");
    check(!absent && absent.status().code() == StatusCode::not_found && preview.ready(), "missing component preserves view");
#endif
    check(preview.open(observed, {0, disk.geometry().block_count}).code() == StatusCode::already_exists,
          "preview object cannot be retried");
    verify_inode(disk, false);
    check(!observed.writes && !observed.flushes && !disk.io_stats().bytes_written && !disk.io_stats().errors,
          "preview performed no write or flush and kept home inode unchanged");
#if defined(OK_EXT4_PREVIEW_MAPPING_REJECT)
    emit("EXT4_PREVIEW_PASS scope=hardware case=mapping-reject writes=0 flushes=0 mount=none\n");
#elif defined(OK_EXT4_PREVIEW_PAYLOAD_CORRUPT)
    emit("EXT4_PREVIEW_PASS scope=hardware case=payload-corrupt writes=0 flushes=0 mount=none\n");
#else
    emit("EXT4_PREVIEW_PASS scope=hardware case=metadata-preview writes=0 flushes=0 mount=none\n");
#endif
    stop(true);
}

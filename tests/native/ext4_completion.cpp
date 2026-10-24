#include "drivers/virtio/block.hpp"
#include <ok/fs/ext4_completion.hpp>
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
alignas(fs::Ext4RecoveryCompletion<>) std::array<std::byte,sizeof(fs::Ext4RecoveryCompletion<>)> completion_storage{};
[[maybe_unused]] alignas(fs::Ext4ReplayPreview<>) std::array<std::byte,sizeof(fs::Ext4ReplayPreview<>)> preview_storage{};
u16 little16(const std::byte *p) { return std::to_integer<u16>(p[0]) | (std::to_integer<u16>(p[1]) << 8); }
u32 little32(const std::byte *p) { return little16(p) | (u32{little16(p + 2)} << 16); }
[[maybe_unused]] void verify_inode(driver::BlockDevice &disk, bool recovered)
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

#ifndef OK_COMPLETION_CASE
#define OK_COMPLETION_CASE "complete"
#endif
#ifndef OK_COMPLETION_FAIL_WRITE
#define OK_COMPLETION_FAIL_WRITE 0
#endif
#ifndef OK_COMPLETION_FAIL_FLUSH
#define OK_COMPLETION_FAIL_FLUSH 0
#endif

// This disposable boot has one CPU/device owner, no mount or cache, and no
// published disk handle. The wrapper serializes recovery acquisition. It is a
// concrete probe ownership setup, not a general kernel storage-lease service.
class ScratchOwner final : public driver::BlockDevice
{
  public:
    explicit ScratchOwner(driver::BlockDevice &disk) : disk_(disk) {}
    Status acquire()
    {
        if (active_) return Status::busy("scratch recovery session already owned");
        active_ = true; return {};
    }
    void release() { check(active_, "scratch owner release"); active_ = false; }
    driver::BlockGeometry geometry() const override { return disk_.geometry(); }
    Status read_blocks(u64 sector, std::span<std::byte> bytes) override
    {
        check(active_, "read outside exclusive scratch session");
        return disk_.read_blocks(sector, bytes);
    }
    Status write_blocks(u64 sector, std::span<const std::byte> bytes) override
    {
        check(active_, "write outside exclusive scratch session");
        ++writes;
        const auto status = disk_.write_blocks(sector, bytes);
        if (!status) return status;
        if (writes == OK_COMPLETION_FAIL_WRITE)
            return Status::io_error("injected error after completed native write");
        return {};
    }
    Status flush() override
    {
        check(active_, "flush outside exclusive scratch session");
        ++flushes;
        const auto status = disk_.flush();
        if (!status) return status;
        if (flushes == OK_COMPLETION_FAIL_FLUSH)
            return Status::io_error("injected error after completed native flush");
        return {};
    }
    usize writes{}, flushes{};
  private:
    driver::BlockDevice &disk_;
    bool active_{};
};
extern "C" [[noreturn]] void kernel_main()
{
    emit("EXT4_COMPLETION_BEGIN owner=exclusive-boot mount=none writer=none\n");
    auto found = os::drivers::probe_virtio_block();check(found.ok(),"probe actual scratch device");
    ScratchOwner owner(*found.value());
    check(owner.acquire().ok()&&owner.acquire().code()==StatusCode::busy,"single active scratch ownership");
    check(owner.geometry().writable&&owner.geometry().block_size==512&&owner.geometry().block_count==65536,
          "explicit writable 32 MiB scratch device");
    auto &completion=*::new(completion_storage.data()) fs::Ext4RecoveryCompletion<>;
    const auto result=completion.run(owner,{0,owner.geometry().block_count});
#if defined(OK_COMPLETION_REJECT)
    check(!result&&!completion.report().complete()&&!owner.writes&&!owner.flushes,
          "unsupported metadata rejected before write or flush");
#elif OK_COMPLETION_FAIL_WRITE || OK_COMPLETION_FAIL_FLUSH
    check(!result&&!completion.report().complete()&&result.code()==StatusCode::io_error,
          "native prefix injection did not stop completion");
#if OK_COMPLETION_FAIL_WRITE
    check(owner.writes==OK_COMPLETION_FAIL_WRITE&&completion.report().write_attempts==owner.writes,
          "write prefix continued after error");
#else
    check(owner.flushes==OK_COMPLETION_FAIL_FLUSH&&completion.report().flush_attempts==owner.flushes,
          "flush prefix continued after error");
#endif
#else
    if(!result){emit(result.message().data());emit("\n");}
    check(result.ok()&&completion.report().complete()&&completion.report().journal_sequence==4&&
          completion.report().checked_inodes==2,"durable checked recovery completion");
    check(completion.report().already_clean ? owner.writes==0&&owner.flushes==1 :
          completion.report().empty_log ? owner.writes==1&&owner.flushes==2 : owner.writes==4&&owner.flushes==4,
          "completion/resume operation count");
    verify_inode(owner,true);
    check(owner.read_blocks(2,data).ok(),"read cleaned filesystem superblock");
    check(little32(data.data()+96)==0x42,"filesystem needs-recovery cleared");
    std::array<u8,1024> super{};
    for(usize i=0;i<super.size();++i)super[i]=std::to_integer<u8>(data[i]);
    check(detail::crc32c(~u32{0},std::span<const u8>{super}.first(1020))==little32(data.data()+1020),
          "clean filesystem checksum");
    check(owner.read_blocks(fixture::layout.journal_first_block*2,data).ok(),"read cleaned journal superblock");
    for(usize i=0;i<super.size();++i)super[i]=std::to_integer<u8>(data[i]);
    const auto codec=Codec::open(super,fixture::layout.journal_blocks,fixture::uuid,DescriptorUuidPolicy::linux_internal_zero);
    check(codec&&codec.value().superblock().start_block==0&&codec.value().superblock().sequence==4,
          "clean journal checksum/sequence/start");
    auto &view=*::new(preview_storage.data()) fs::Ext4ReplayPreview<>;
    check(view.open(owner,{0,owner.geometry().block_count}).ok()&&view.report().empty_log,
          "fresh post-completion read-only view");
    const auto inode=view.lookup(2,"seed");check(inode&&inode.value()==12,"post-completion namespace");
    std::array<u8,4096> bytes{};const auto got=view.read(12,0,bytes);
    check(got&&got.value()==4096,"post-completion read length");
    for(usize i=0;i<bytes.size();++i)check(bytes[i]==u8(i*17+29),"post-completion payload");
#endif
    const auto writes=owner.writes,flushes=owner.flushes;
    check(completion.run(owner,{0,owner.geometry().block_count}).code()==StatusCode::already_exists&&
          owner.writes==writes&&owner.flushes==flushes,"completion attempt reused");
    owner.release();
    emit("EXT4_COMPLETION_PASS scope=qemu-device case=" OK_COMPLETION_CASE " owner=exclusive-boot mount=none\n");
    stop(true);
}

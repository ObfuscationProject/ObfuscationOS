#include "drivers/virtio/block.hpp"
#include <ok/fs/ext4_metadata_transaction.hpp>
#include <ok/block/sessions.hpp>
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

#ifndef OK_TRANSACTION_CASE
#define OK_TRANSACTION_CASE "complete"
#endif
#ifndef OK_TRANSACTION_FAIL_WRITE
#define OK_TRANSACTION_FAIL_WRITE 0
#endif
#ifndef OK_TRANSACTION_FAIL_FLUSH
#define OK_TRANSACTION_FAIL_FLUSH 0
#endif

// This disposable boot has one CPU/device owner, no mount or cache, and no
// published disk handle. The wrapper serializes recovery acquisition. It is a
// concrete probe ownership setup, not a general kernel storage-lease service.
class FaultDevice final : public driver::BlockDevice
{
  public:
    explicit FaultDevice(driver::BlockDevice &disk) : disk_(disk) {}
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
        ++reads_; return disk_.read_blocks(sector, bytes);
    }
    Status write_blocks(u64 sector, std::span<const std::byte> bytes) override
    {
        check(active_, "write outside exclusive scratch session");
        ++writes;
        const auto status = disk_.write_blocks(sector, bytes);
        if (!status) return status;
        if (writes == OK_TRANSACTION_FAIL_WRITE)
            return Status::io_error("injected error after completed native write");
        return {};
    }
    Status flush() override
    {
        check(active_, "flush outside exclusive scratch session");
        ++flushes;
        const auto status = disk_.flush();
        if (!status) return status;
        if (flushes == OK_TRANSACTION_FAIL_FLUSH)
            return Status::io_error("injected error after completed native flush");
        return {};
    }
    usize writes{}, flushes{};
    usize reads() const { return reads_; }
  private:
    driver::BlockDevice &disk_;
    bool active_{};
    usize reads_{};
};
extern "C" [[noreturn]] void kernel_main()
{
    emit("BLOCK_SESSION_BEGIN owner=exclusive-boot mount=none\n");
    auto found=os::drivers::probe_virtio_block();check(found.ok(),"probe actual scratch device");
    FaultDevice transport(*found.value());check(transport.acquire().ok(),"private fault transport");
    block::BlockSessions<1> service;
    block::BlockSessions<1>::Session owner, alias;
    const auto registration=service.register_device(transport,1);
    check(registration.ok(),"Kernel service registration");
    check(!service.register_device(transport,2),"raw device alias registration");
    check(service.acquire(registration.value(),{0,65536},block::SessionAccess::writable,owner).ok(),"Kernel exclusive session");
    check(service.acquire(registration.value(),{100,100},block::SessionAccess::readonly,alias).code()==StatusCode::busy,
          "partition alias owner excluded");
    check(service.detach(registration.value()).code()==StatusCode::busy,"owned detach excluded");
    check(owner.geometry().writable&&owner.geometry().block_size==512&&owner.geometry().block_count==65536,
          "explicit writable 32 MiB scratch device");
#if defined(OK_TRANSACTION_RECOVER)
    auto &recovery=*::new(completion_storage.data()) fs::Ext4RecoveryCompletion<>;
    const auto result=recovery.run(owner,{0,owner.geometry().block_count});
    check(result.ok()&&recovery.report().complete(),"restart completion");
    verify_inode(owner,OK_TRANSACTION_EXPECT_NEW);
    check(recovery.report().journal_sequence==(OK_TRANSACTION_EXPECT_NEW?7:4),"recovery sequence");
    check(owner.read_blocks(2,data).ok()&&little32(data.data()+96)==0x42,"clean recovery bit");
#else
    auto &transaction=*::new(transaction_storage.data()) fs::Ext4MetadataTransaction;
    fs::Ext4InodeMetadataUpdate update{12,2000,2001,1700000000,123456789,0640};
#if defined(OK_TRANSACTION_REJECT)
    update.inode=2;
#endif
    const auto result=transaction.commit(owner,{0,owner.geometry().block_count},update);
#if defined(OK_TRANSACTION_REJECT)
    check(!result&&!transaction.report().published()&&!transport.writes&&!transport.flushes,"nonregular metadata rejected before mutation");
#elif OK_TRANSACTION_FAIL_WRITE || OK_TRANSACTION_FAIL_FLUSH
    check(!result&&!transaction.report().published()&&result.code()==StatusCode::io_error,"native injected writer error ignored");
#if OK_TRANSACTION_FAIL_WRITE
    check(transport.writes==OK_TRANSACTION_FAIL_WRITE&&transaction.report().write_attempts==transport.writes,"write error continuation");
#else
    check(transport.flushes==OK_TRANSACTION_FAIL_FLUSH&&transaction.report().flush_attempts==transport.flushes,"flush error continuation");
#endif
#else
    if(!result){emit(result.message().data());emit("\n");}
    check(result.ok()&&transaction.report().published()&&transaction.report().sequence==5,"durable publication");
    check(transport.writes==7&&transport.flushes==5,"writer operation counts");
    verify_inode(owner,false);
    auto &view=*::new(preview_storage.data()) fs::Ext4ReplayPreview<>;
    check(view.open(owner,{0,owner.geometry().block_count}).ok()&&view.report().validated_actions==2,"published final view");
    const auto inode=view.inode(12);check(inode&&inode.value().mode==0100640&&inode.value().uid==2000&&inode.value().gid==2001,
          "published metadata differs from unchanged home inode");
    std::array<u8,4096> bytes{};const auto got=view.read(12,0,bytes);check(got&&got.value()==4096,"unchanged published file data");
    for(usize i=0;i<bytes.size();++i)check(bytes[i]==u8(i*17+29),"published payload bytes");
#endif
    const auto writes=transport.writes,flushes=transport.flushes;
    check(transaction.commit(owner,{0,owner.geometry().block_count},update).code()==StatusCode::already_exists&&
          transport.writes==writes&&transport.flushes==flushes,"writer reused");
#endif
#if OK_TRANSACTION_FAIL_WRITE || OK_TRANSACTION_FAIL_FLUSH
    const auto before=transport.reads()+transport.writes+transport.flushes;
    check(service.inspect(registration.value()).value().state==block::DeviceState::quarantined,"I/O fault quarantine");
    check(owner.flush().code()==StatusCode::denied&&owner.close().code()==StatusCode::denied,"quarantined I/O and close denied");
    check(service.acquire(registration.value(),{0,65536},block::SessionAccess::readonly,alias).code()==StatusCode::denied&&
          service.detach(registration.value()).code()==StatusCode::denied,"quarantine has no unfenced reuse path");
    check(before==transport.reads()+transport.writes+transport.flushes,"quarantine issued I/O");
#else
    check(owner.close().ok(),"drained session close");
    check(owner.read_blocks(0,data).code()==StatusCode::bad_descriptor,"closed view rejected");
    check(service.acquire(registration.value(),{1,2},block::SessionAccess::readonly,alias).ok(),"fresh bounded readonly owner");
    check(alias.read_blocks(0,data).ok(),"relative partition view");
    check(alias.read_blocks(2,data).code()==StatusCode::invalid_argument&&alias.write_blocks(0,data).code()==StatusCode::denied,
          "partition and readonly request admission");
    check(alias.close().ok()&&service.detach(registration.value()).ok(),"clean registration retirement");
#endif
    transport.release();
    emit("BLOCK_SESSION_PASS scope=qemu-device case=" OK_TRANSACTION_CASE " owner=exclusive-boot mount=none\n");
    stop(true);
}

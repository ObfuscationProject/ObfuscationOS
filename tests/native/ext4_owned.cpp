#include "drivers/virtio/block.hpp"
#include <ok/fs/ext4_owned_transaction.hpp>
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

using Owner = fs::Ext4OwnedTransaction<1>;
alignas(Owner) std::array<std::byte, sizeof(Owner)> owned_storage{};
#ifndef OK_OWNED_CASE
#define OK_OWNED_CASE "checkpoint"
#endif
#ifndef OK_OWNED_FAIL_WRITE
#define OK_OWNED_FAIL_WRITE 0
#endif
#ifndef OK_OWNED_FAIL_FLUSH
#define OK_OWNED_FAIL_FLUSH 0
#endif
class ObservedDevice final : public driver::BlockDevice
{
  public:
    explicit ObservedDevice(driver::BlockDevice &disk) : disk_(disk) {}
    driver::BlockGeometry geometry() const override { return disk_.geometry(); }
    Status read_blocks(u64 sector, std::span<std::byte> bytes) override { return disk_.read_blocks(sector,bytes); }
    void check_admission()
    {
        if (!owner) return;
        Owner::Pin reader;
        check(owner->pin(1,reader).code()==StatusCode::busy,"device callback reader admission");
        check(owner->close().code()==StatusCode::busy,"device callback close admission");
    }
    Status write_blocks(u64 sector, std::span<const std::byte> bytes) override
    {
        check_admission();++writes;const auto result=disk_.write_blocks(sector,bytes);
        if(!result)return result;
        return writes==OK_OWNED_FAIL_WRITE?Status::io_error("injected completed owned write"):Status{};
    }
    Status flush() override
    {
        check_admission();++flushes;const auto result=disk_.flush();
        if(!result)return result;
        return flushes==OK_OWNED_FAIL_FLUSH?Status::io_error("injected completed owned flush"):Status{};
    }
    Owner *owner{};
    usize writes{},flushes{};
  private:
    driver::BlockDevice &disk_;
};
void canonical(Owner &owner, bool changed)
{
    Owner::Pin pin;
    check(owner.pin(fixture::seed_block,pin).ok()&&pin.read(0,data).ok(),"canonical inode read");
    const auto *inode=data.data()+fixture::seed_offset;
    check(little16(inode)==(changed?0100640:0100600)&&little16(inode+2)==(changed?2000:1000)&&
          little16(inode+24)==(changed?2001:1001),"canonical inode metadata visibility");
    check(pin.release().ok(),"canonical reader retirement");
}
extern "C" [[noreturn]] void kernel_main()
{
    emit("EXT4_OWNED_BEGIN owner=private-session mount=none\n");
    auto found=os::drivers::probe_virtio_block();check(found.ok(),"probe actual private device");
    ObservedDevice transport(*found.value());Owner::Registry registry;
    const auto key=registry.register_device(transport,1,1024);check(key.ok(),"authoritative registration");
#if defined(OK_OWNED_RECOVER)
    Owner::Registry::Session session;
    check(registry.acquire(key.value(),{0,65536},block::SessionAccess::writable,session).ok(),"fresh recovery session");
    auto &recovery=*::new(completion_storage.data()) fs::Ext4RecoveryCompletion<>;
    check(recovery.run(session,{0,65536}).ok()&&recovery.report().complete(),"fresh session recovery");
    verify_inode(session,OK_OWNED_EXPECT_NEW);
    check(session.close().ok()&&registry.detach(key.value()).ok(),"fresh recovery drainage");
#else
    auto &owner=*::new(owned_storage.data()) Owner;
    check(owner.open(registry,key.value(),{0,65536}).ok(),"canonical private owner");
    Owner::Registry::Session alias;
    check(registry.acquire(key.value(),{100,100},block::SessionAccess::readonly,alias).code()==StatusCode::busy,"competing session excluded");
    fs::Ext4InodeMetadataUpdate update{12,2000,2001,1700000000,123456789,0640};
#if defined(OK_OWNED_REJECT)
    update.inode=2;
    check(owner.prepare(update).code()==StatusCode::unsupported&&owner.report().phase==fs::Ext4OwnedPhase::rejected&&
          !transport.writes&&!transport.flushes&&owner.close().ok()&&registry.detach(key.value()).ok(),"clean rejection drains private owner");
#else
    Owner::Pin old;
    check(owner.pin(fixture::seed_block,old).ok(),"old canonical reader");
    check(owner.prepare(update).ok()&&!transport.writes&&!transport.flushes,"full private prepare before mutation");
    canonical(owner,false);
    check(owner.commit().code()==StatusCode::busy&&!transport.writes&&!transport.flushes,"old reader gates commit before I/O");
    check(old.release().ok(),"old reader retirement");
#if defined(OK_OWNED_DISCARD)
    check(owner.discard().ok()&&!transport.writes&&!transport.flushes,"private discard has no I/O");
    canonical(owner,false);check(owner.close().ok()&&registry.detach(key.value()).ok(),"discard drainage");
#else
    transport.owner=&owner;
    auto result=owner.commit();
#if !defined(OK_OWNED_PUBLISH_ONLY)
    if(result)
    {
        canonical(owner,true);
        Owner::Pin held;
        check(owner.pin(1,held).ok(),"durable canonical reader");
        check(owner.checkpoint().code()==StatusCode::busy&&transport.writes==7&&transport.flushes==5,"durable reader gates checkpoint");
        check(held.release().ok(),"durable reader retirement");
        result=owner.checkpoint();
    }
#endif
#if OK_OWNED_FAIL_WRITE || OK_OWNED_FAIL_FLUSH
    check(!result&&result.code()==StatusCode::io_error&&owner.report().phase==fs::Ext4OwnedPhase::failed,"owned fault propagates");
    check(owner.buffers().transaction_active&&owner.buffers().read_pins==3&&owner.buffers().state==fs::MetadataOwnerState::failed,"failed owner retains versions");
    check(registry.inspect(key.value()).value().state==block::DeviceState::quarantined&&registry.detach(key.value()).code()==StatusCode::denied,"failed device retains quarantine");
    Owner::Pin denied;const auto writes=transport.writes,flushes=transport.flushes;
    check(owner.pin(1,denied).code()==StatusCode::denied&&owner.close().code()==StatusCode::denied&&owner.checkpoint().code()==StatusCode::denied&&
          writes==transport.writes&&flushes==transport.flushes,"quarantine performs no more I/O");
#else
    check(result.ok()&&owner.report().writer.published(),"owned durable publication");
    canonical(owner,true);
#if defined(OK_OWNED_PUBLISH_ONLY)
    check(transport.writes==7&&transport.flushes==5&&owner.buffers().transaction_active&&owner.close().code()==StatusCode::busy,"publication retains journal dependency");
#else
    check(transport.writes==11&&transport.flushes==9&&owner.report().completion.complete()&&!owner.buffers().transaction_active,"complete durable checkpoint");
    check(owner.close().ok()&&registry.detach(key.value()).ok(),"checkpoint drainage");
#endif
#endif
#endif
#endif
#endif
    // Nonreturning stop preserves every owner, pin and transport lifetime.
    emit("EXT4_OWNED_PASS scope=qemu-device case=" OK_OWNED_CASE " owner=private-session mount=none\n");stop(true);
}

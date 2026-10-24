#include "drivers/virtio/block.hpp"
#include <ok/fs/jbd2_replay.hpp>
#include <ok/fs/metadata_buffers.hpp>
#include <ok/block/sessions.hpp>
#include <new>
#include "linux_fixture.hpp"
#include "metadata_fixture.hpp"

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

[[maybe_unused]] alignas(4096) std::array<std::byte,1024> data{}, copy{};
using Cache=fs::MetadataBuffers<2,1024,1>;
alignas(Cache) std::array<std::byte,sizeof(Cache)> owner_storage{}, alias_storage{}, readonly_storage{}, limited_storage{};
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

#ifndef OK_METADATA_CASE
#define OK_METADATA_CASE "ownership"
#endif
#ifndef OK_METADATA_FAIL_READ
#define OK_METADATA_FAIL_READ 0
#endif
class ObservedDevice final : public driver::BlockDevice
{
  public:
    explicit ObservedDevice(driver::BlockDevice &disk):disk_(disk){}
    driver::BlockGeometry geometry() const override {return disk_.geometry();}
    Status read_blocks(u64 first,std::span<std::byte> out) override
    {
        ++reads;
        const auto result=disk_.read_blocks(first,out);
        if(!result)return result;
        return reads==OK_METADATA_FAIL_READ?Status::io_error("injected completed metadata read"):Status{};
    }
    Status write_blocks(u64,std::span<const std::byte>) override
    {++writes;return Status::io_error("metadata cache attempted home write");}
    Status flush() override {++flushes;return Status::io_error("metadata cache attempted flush");}
    usize reads{},writes{},flushes{};
  private:
    driver::BlockDevice &disk_;
};
void compare(std::span<const std::byte> actual,const std::array<u8,1024> &expected)
{
    for(usize index=0;index<actual.size();++index)
        check(std::to_integer<u8>(actual[index])==expected[index],"canonical metadata byte differs from independent fixture");
}
[[noreturn]] void passed()
{
    emit("METADATA_BUFFER_PASS scope=qemu-device case=" OK_METADATA_CASE " home-writes=0 mount=none\n");stop(true);
}
void load(Cache &cache,Cache::Registry &service,Cache::Registry::Registration key,
          ObservedDevice &transport,u64 block,Cache::Pin &pin)
{
    const auto result=cache.pin(block,pin);
    if(result)return;
    check(OK_METADATA_FAIL_READ&&transport.reads==OK_METADATA_FAIL_READ&&result.code()==StatusCode::io_error,"unexpected native metadata read failure");
    check(cache.report().state==fs::MetadataOwnerState::failed&&!cache.report().in_flight,"metadata error owner state");
    const auto before=transport.reads;
    Cache::Pin rejected;
    check(!cache.pin(1,rejected)&&!pin.read(0,data)&&!cache.close(),"metadata quarantine rejects reuse/copy/close");
    auto &alias=*::new(readonly_storage.data()) Cache;
    check(alias.open(service,key,{0,65536},block::SessionAccess::readonly).code()==StatusCode::denied&&
          service.detach(key).code()==StatusCode::denied,"quarantine has no backing reclamation path");
    check(service.inspect(key).value().state==block::DeviceState::quarantined&&before==transport.reads&&
          !transport.writes&&!transport.flushes,"quarantine submits no more device work");
    // All owner/handle/backing lifetimes remain live at this nonreturning stop.
    passed();
}
extern "C" [[noreturn]] void kernel_main()
{
    emit("METADATA_BUFFER_BEGIN owner=canonical-private-session mount=none\n");
    auto found=os::drivers::probe_virtio_block();check(found.ok(),"probe actual private device");
    ObservedDevice transport(*found.value());Cache::Registry service;
    const auto limited_key=service.register_device(transport,1,512);check(limited_key.ok(),"limited transfer registration");
    auto &limited=*::new(limited_storage.data()) Cache;
    check(limited.open(service,limited_key.value(),{0,65536},block::SessionAccess::readonly).code()==StatusCode::unsupported&&
          !transport.reads&&service.inspect(limited_key.value()).value().state==block::DeviceState::ready,
          "metadata transfer limit rejects before raw I/O without quarantine");
    check(service.detach(limited_key.value()).ok(),"incompatible transfer geometry permits clean detach");
    limited.~Cache();
    const auto key=service.register_device(transport,1);check(key.ok(),"authoritative device registration");
    auto &cache=*::new(owner_storage.data()) Cache;
    auto &alias=*::new(alias_storage.data()) Cache;
#if defined(OK_METADATA_READONLY)
    constexpr auto access=block::SessionAccess::readonly;
#else
    constexpr auto access=block::SessionAccess::writable;
#endif
    check(cache.open(service,key.value(),{0,65536},access).ok(),"private session-bound canonical owner");
    check(alias.open(service,key.value(),{100,100},block::SessionAccess::readonly).code()==StatusCode::busy,"disjoint cache alias rejected");
    Cache::Pin super,inode,duplicate,journal,pressure;
    load(cache,service,key.value(),transport,1,super);
    check(super.read(0,data).ok(),"canonical superblock copy");compare(data,metadata_fixture::superblock);
    load(cache,service,key.value(),transport,fixture::seed_block,inode);
    check(inode.read(0,data).ok(),"canonical inode copy");compare(data,metadata_fixture::inodeblock);
    check(cache.pin(fixture::seed_block,duplicate).ok()&&transport.reads==2&&
          inode.report().value().generation==duplicate.report().value().generation,"duplicate metadata shares one load/version");
    check(cache.pin(fixture::layout.journal_first_block,pressure).code()==StatusCode::no_memory&&transport.reads==2,"bounded pin pressure before device I/O");
    Cache::Transaction transaction;
    std::array<Cache::Pin*,2> participants{&super,&inode};
#if defined(OK_METADATA_READONLY)
    check(cache.begin(participants,transaction).code()==StatusCode::denied,"readonly owner rejects private mutations");
#else
    check(cache.begin(participants,transaction).ok(),"reserve both canonical transaction participants");
    constexpr std::array<std::byte,2> mode{std::byte{0xa0},std::byte{0x81}};
    check(transaction.edit(fixture::seed_block,fixture::seed_offset,mode).ok(),"stage private inode mode");
    check(transaction.read(fixture::seed_block,0,copy).ok()&&copy[fixture::seed_offset]==mode[0]&&
          copy[fixture::seed_offset+1]==mode[1],"private inode mode readback");
    check(duplicate.read(0,copy).ok(),"canonical alias remains readable during private edit");compare(copy,metadata_fixture::inodeblock);
#endif
    check(super.release().ok()&&inode.release().ok()&&duplicate.release().ok(),"retire all reader pins");
#if !defined(OK_METADATA_READONLY)
    check(cache.pin(fixture::layout.journal_first_block,pressure).code()==StatusCode::no_memory&&transport.reads==2&&
          cache.close().code()==StatusCode::busy,"transaction pins survive reader retirement");
    check(transaction.discard().ok()&&!transaction.edit(fixture::seed_block,0,data),"private discard retires transaction identity");
#endif
    load(cache,service,key.value(),transport,fixture::layout.journal_first_block,journal);
    check(journal.read(0,data).ok(),"evicted slot reloads journal metadata");compare(data,metadata_fixture::journal);
    check(journal.release().ok()&&cache.close().ok()&&service.detach(key.value()).ok(),"drain canonical owner and registered backing");
    check(!transport.writes&&!transport.flushes&&transport.reads==3,"cache never performs home writeback or hidden flush");
    passed();
}

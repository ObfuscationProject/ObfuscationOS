#include "drivers/virtio/block.hpp"
#include <ok/fs/jbd2_replay.hpp>
#ifdef OS_EXT4_RUNTIME_BINDING
#include <ok/fs/ext4_recovery.hpp>
#endif
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
alignas(ReplayExecutor<>) std::array<std::byte,sizeof(ReplayExecutor<>)> replay_storage{};
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

extern "C" [[noreturn]] void kernel_main()
{
    emit("JBD2_LINUX_BEGIN source=linux-created-journal mount=none writer=none checkpoint=none\n");
    auto found = os::drivers::probe_virtio_block();
    check(found.ok(), "probe actual Virtio device");
    auto &disk = *found.value();
    check(disk.geometry().block_size == 512 && disk.geometry().block_count == 65536, "exact Linux fixture geometry");
#ifdef OK_LINUX_REOPEN
    verify_inode(disk, true);
#else
    verify_inode(disk, false);
#endif
#ifdef OS_EXT4_RUNTIME_BINDING
    fs::Ext4RecoveryBinding binding;
    const auto admitted = binding.inspect(disk, {0, disk.geometry().block_count});
    if (!admitted) { emit(admitted.message().data()); emit("\n"); }
    check(admitted.ok() && binding.info(), "runtime checksummed internal journal binding");
    const auto &bound = *binding.info();
    check(bound.layout.first_sector == fixture::layout.first_sector &&
          bound.layout.filesystem_blocks == fixture::layout.filesystem_blocks &&
          bound.layout.block_size == fixture::layout.block_size &&
          bound.layout.journal_first_block == fixture::layout.journal_first_block &&
          bound.layout.journal_blocks == fixture::layout.journal_blocks &&
          bound.uuid == fixture::uuid && bound.metadata_count == fixture::ranges.size() &&
          bound.needs_recovery && !bound.empty_log && disk.io_stats().bytes_written == 0,
          "runtime binding agrees with independent offline oracle and issued no writes");
    for (usize index = 0; index < bound.metadata_count; ++index)
        check(bound.metadata[index].first == fixture::ranges[index].first &&
              bound.metadata[index].count == fixture::ranges[index].count, "runtime domain agrees with oracle");
    emit("EXT4_RECOVERY_BINDING_PASS scope=hardware mapping=device-derived writes=0 mount=none\n");
    auto io = RecoveryIo::open(disk, bound.layout);
    const auto &owned_uuid = bound.uuid;
    const auto owned_domain = bound.structural_metadata();
#else
    auto io = RecoveryIo::open(disk, fixture::layout);
    const auto &owned_uuid = fixture::uuid;
    const TargetDomain owned_domain{fixture::layout.filesystem_blocks, fixture::ranges};
#endif
    check(io.ok(), "admit verified contiguous Linux journal mapping");
    auto &executor = *::new (replay_storage.data()) ReplayExecutor<>;
#ifdef OK_LINUX_REQUIRE_REJECTION
    const auto status = executor.run(io.value(), owned_uuid, owned_domain);
    check(!status && executor.report().phase == ReplayPhase::failed &&
          executor.report().failed_phase == ReplayPhase::planning && executor.report().write_attempts == 0,
          "unchanged exported codec rejects zero tag UUID without writes");
    check(!executor.report().replay_durable() && disk.io_stats().bytes_written == 0, "rejection preserves disk");
    emit("JBD2_LINUX_PASS scope=hardware case=strict-reject writes=0 policy=strict mount=none\n");
    stop(true);
#else
    const auto status = executor.run(io.value(), owned_uuid, owned_domain,
                                     DescriptorUuidPolicy::linux_internal_zero);
    if (!status) { emit(status.message().data()); emit("\n"); }
    check(status.ok() && executor.report().replay_durable(), "candidate replay and final physical flush");
    const auto &report = executor.report();
    check(report.committed_transactions == 1 && report.next_sequence == 3 && report.planned_actions == 2 &&
          report.revoked_actions == 0 && report.completed_writes == 2 && report.completed_flushes == 2,
          "exact Linux transaction action and flush counts");
    verify_inode(disk, true);
    check(disk.read_blocks(2, data).ok() && little32(data.data() + 96) == 0x46, "ext4 recovery flag remains set");
    check(disk.read_blocks(fixture::layout.journal_first_block * 2, data).ok(), "read retained journal superblock");
    const auto journal = std::span<const u8>{reinterpret_cast<const u8 *>(data.data()), data.size()};
    check(detail::be32(journal, 24) == 2 && detail::be32(journal, 28) == 1, "journal sequence and tail not checkpointed");
    check(disk.io_stats().bytes_written == 2048 && disk.io_stats().errors == 0, "only exact home blocks written");
#ifdef OK_LINUX_REOPEN
    emit("JBD2_LINUX_PASS scope=hardware case=reopen writes=2 inode-crc=pass flush=pass journal=retained mount=none\n");
#else
    emit("JBD2_LINUX_PASS scope=hardware case=replay writes=2 inode-crc=pass flush=pass journal=retained mount=none\n");
#endif
    stop(true);
#endif
}

#include <ok/arch/clock.hpp>
#include <ok/arch/realtime.hpp>

using namespace ok;
namespace
{
void emit(const char *text)
{
    while (*text)
    {
#if defined(OK_ARCH_TARGET_I386) || defined(OK_ARCH_TARGET_X86_64)
        u8 ready;
        do { asm volatile("inb %1, %0" : "=a"(ready) : "Nd"(u16{0x3fd})); } while (!(ready & 32));
        asm volatile("outb %0, %1" :: "a"(static_cast<u8>(*text++)), "Nd"(u16{0x3f8}));
#elif defined(OK_ARCH_TARGET_AARCH64) || defined(OK_ARCH_TARGET_ARM32)
        while (*reinterpret_cast<volatile u32 *>(0x09000018) & 32) {}
        *reinterpret_cast<volatile u32 *>(0x09000000) = static_cast<u8>(*text++);
#elif defined(OK_ARCH_TARGET_RV32) || defined(OK_ARCH_TARGET_RV64)
        *reinterpret_cast<volatile u8 *>(0x10000000) = static_cast<u8>(*text++);
#elif defined(OK_ARCH_TARGET_LOONGARCH64)
        while (!(*reinterpret_cast<volatile u8 *>(0x1fe001e5) & 32)) {}
        *reinterpret_cast<volatile u8 *>(0x1fe001e0) = static_cast<u8>(*text++);
#elif defined(OK_ARCH_TARGET_MIPS) || defined(OK_ARCH_TARGET_MIPS64)
        constexpr uptr uart = static_cast<uptr>(static_cast<__INTPTR_TYPE__>(-1207958536LL));
        while (!(*reinterpret_cast<volatile u8 *>(uart + 5) & 32)) {}
        *reinterpret_cast<volatile u8 *>(uart) = static_cast<u8>(*text++);
#elif defined(OK_ARCH_TARGET_PPC)
        while (!(*reinterpret_cast<volatile u8 *>(0xe0004505) & 32)) {}
        *reinterpret_cast<volatile u8 *>(0xe0004500) = static_cast<u8>(*text++);
#else
#error "A native diagnostic serial path is required"
#endif
    }
}
void number(u64 value)
{
    char text[24]{};
    unsigned size = 0;
    do { text[size++] = static_cast<char>('0' + value % 10); value /= 10; } while (value);
    while (size) { char part[]{text[--size], 0}; emit(part); }
}
[[noreturn]] void stop(bool pass = false)
{
#if defined(OK_ARCH_TARGET_I386) || defined(OK_ARCH_TARGET_X86_64)
    asm volatile("outl %0, %1" :: "a"(pass ? 16u : 17u), "Nd"(u16{0xf4}));
#else
    static_cast<void>(pass);
#endif
    for (;;) asm volatile("" ::: "memory");
}
void check(bool value, const char *reason)
{
    if (value) return;
    emit("REALTIME_FAIL "); emit(reason); emit("\n"); stop();
}
[[maybe_unused]] void sample(const char *label, time::EpochTime value)
{
    emit(label); emit(" seconds=");
    check(value.seconds >= 0, "diagnostic fixture requires nonnegative epoch");
    number(static_cast<u64>(value.seconds)); emit(" nanoseconds="); number(value.nanoseconds); emit("\n");
}
} // namespace

extern "C" void *memcpy(void *to, const void *from, usize size)
{
    auto *out = static_cast<volatile u8 *>(to); const auto *in = static_cast<const u8 *>(from);
    for (usize i = 0; i < size; ++i) out[i] = in[i];
    return to;
}
extern "C" void *memset(void *to, int value, usize size)
{
    auto *out = static_cast<volatile u8 *>(to);
    for (usize i = 0; i < size; ++i) out[i] = static_cast<u8>(value);
    return to;
}
extern "C" int atexit(void (*)()) { return 0; }

extern "C" [[noreturn]] void kernel_main()
{
    emit("REALTIME_BEGIN scope=native-platform-diagnostic public-adapters=not-exercised\n");
    check(arch::realtime().status().code() == StatusCode::not_initialized, "uninitialized epoch");
#if defined(REALTIME_EARLY_FAILURE)
    check(arch::initialize_realtime().code() == StatusCode::not_initialized, "missing monotonic input");
    check(arch::initialize_clock().ok(), "monotonic initialization after failure");
    check(arch::initialize_realtime().code() == StatusCode::not_initialized, "failed anchor retried");
    check(arch::realtime_info().state == time::AnchorState::unavailable && !arch::realtime(), "failed anchor revived");
    emit("REALTIME_EARLY_FAILURE_PASS no-retry=1\n");
#else
    check(arch::initialize_clock().ok(), "monotonic initialization");
    auto start = arch::monotonic_sample(); check(start.ok(), "monotonic sample");
    auto source = arch::read_epoch_source();
#if defined(OK_ARCH_TARGET_AARCH64) || defined(OK_ARCH_TARGET_ARM32) || defined(OK_ARCH_TARGET_RV32) || defined(OK_ARCH_TARGET_RV64)
    check(source.ok(), "actual epoch source read");
    sample("REALTIME_SOURCE", source.value().time);
    check(arch::initialize_realtime().ok(), "epoch anchor initialization");
    auto first = arch::realtime(); check(first.ok(), "first realtime read");
    sample("REALTIME_FIRST", first.value());
    const auto info = arch::realtime_info();
    check(info.state == time::AnchorState::ready && info.accuracy == time::Accuracy::unknown &&
          info.monotonic_generation == start.value().generation && info.source_resolution_ns > 0,
          "epoch provenance and unknown accuracy");
    bool elapsed = false;
    for (u64 attempt = 0; attempt < 200000000; ++attempt)
    {
        auto current = arch::monotonic_sample(); check(current.ok(), "continued monotonic sample");
        if (current.value().nanoseconds - start.value().nanoseconds >= 1200000000)
        { elapsed = true; break; }
    }
    check(elapsed, "bounded monotonic progress wait");
    auto second = arch::realtime(); check(second.ok(), "continued realtime read");
    check(second.value().seconds > first.value().seconds ||
          (second.value().seconds == first.value().seconds && second.value().nanoseconds > first.value().nanoseconds), "anchor progress");
    sample("REALTIME_SECOND", second.value());
    auto later_source = arch::read_epoch_source(); check(later_source.ok(), "continued actual RTC read");
    sample("REALTIME_LATER_SOURCE", later_source.value().time);
    check(later_source.value().time.seconds > source.value().time.seconds, "RTC did not advance");
    check(arch::initialize_realtime().ok(), "repeated initialization");
    auto preserved = arch::realtime(); check(preserved.ok(), "preserved epoch");
    check(preserved.value().seconds >= second.value().seconds, "initialization moved epoch");
    arch::invalidate_clock();
    check(arch::realtime_info().state == time::AnchorState::invalidated &&
          !arch::initialize_realtime() && !arch::realtime(), "known continuity loss");
    emit("REALTIME_READY_PASS rtc-access=actual rtc-writes=0 invalidation=terminal\n");
#else
    check(!source && source.status().code() == StatusCode::unsupported, "unqualified source acquired epoch");
    check(arch::initialize_realtime().code() == StatusCode::unsupported && !arch::realtime(), "unavailable anchor");
    check(arch::realtime_info().state == time::AnchorState::unavailable, "unavailability state");
    emit("REALTIME_UNAVAILABLE_PASS reason=");
    const auto source_status = source.status();
    for (char c : source_status.message()) { char text[]{c, 0}; emit(text); }
    emit("\n");
    arch::invalidate_clock();
#endif
    check(!arch::initialize_clock() && !arch::monotonic_sample() && arch::clock_resolution_ns() == 0,
          "invalidated counter revived");
#endif
    emit("REALTIME_PASS scope=native-platform-diagnostic public-adapters=not-exercised\n"); stop(true);
}

#include <ok/arch/clock.hpp>
#include <ok/arch/realtime.hpp>
#include <ok/user/clock_set.hpp>

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
    emit("CLOCK_SET_DIAGNOSTIC_FAIL "); emit(reason); emit("\n"); stop();
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

namespace
{
u64 sample_calls{}, commit_calls{};
time::MonotonicPoint committed{};

bool same(time::AnchorInfo a, time::AnchorInfo b)
{
    return a.state == b.state && a.source == b.source && a.source_resolution_ns == b.source_resolution_ns &&
           a.acquisition_span_ns == b.acquisition_span_ns && a.monotonic_generation == b.monotonic_generation &&
           a.accuracy == b.accuracy;
}
bool same(time::RealtimeInfo a, time::RealtimeInfo b)
{
    return a.state == b.state && a.origin == b.origin && a.wall_generation == b.wall_generation &&
           a.monotonic_generation == b.monotonic_generation && a.conversion_resolution_ns == b.conversion_resolution_ns &&
           a.accuracy == b.accuracy;
}
const char *source_name(time::EpochSource source)
{
    if (source == time::EpochSource::pl031) return "pl031";
    if (source == time::EpochSource::goldfish) return "goldfish";
    if (source == time::EpochSource::ls7a) return "ls7a";
    return "unavailable";
}
void boot_info(const char *phase, time::AnchorInfo info)
{
    emit("CLOCK_SET_BOOT phase="); emit(phase);
    emit(" state="); emit(info.state == time::AnchorState::ready ? "ready" : "unavailable");
    emit(" source="); emit(source_name(info.source));
    emit(" resolution_ns="); number(info.source_resolution_ns);
    emit(" acquisition_ns="); number(info.acquisition_span_ns);
    emit(" mono_generation="); number(info.monotonic_generation);
    emit(" accuracy=unknown\n");
}
Status setting(user::ClockSetValue value, user::Credentials credentials)
{
    return user::set_realtime_checked(value, credentials,
        [] { ++sample_calls; return arch::monotonic_sample(); },
        [](time::EpochTime epoch, time::MonotonicPoint point) {
            ++commit_calls; committed = point; return arch::set_realtime(epoch, point);
        });
}
void check_active(u64 generation, u64 monotonic_generation)
{
    const auto info = arch::realtime_clock_info();
    check(info.state == time::AnchorState::ready && info.origin == time::RealtimeOrigin::administrator_software &&
          info.wall_generation == generation && info.monotonic_generation == monotonic_generation &&
          info.conversion_resolution_ns == arch::clock_resolution_ns() && info.conversion_resolution_ns != 0 &&
          info.accuracy == time::Accuracy::unknown, "software provenance and generations");
}
time::RealtimeSample active_sample(const char *phase, time::EpochTime value, time::MonotonicPoint anchor, u64 generation)
{
    auto current = arch::realtime_sample(); check(current.ok(), "active realtime sample");
    const auto result = current.value();
    check(result.monotonic.generation == anchor.generation && result.monotonic.nanoseconds >= anchor.nanoseconds,
          "sample preserves monotonic continuity");
    auto expected = time::add_elapsed(value, result.monotonic.nanoseconds - anchor.nanoseconds);
    check(expected.ok() && result.value == expected.value() && result.wall_generation == generation &&
          result.origin == time::RealtimeOrigin::administrator_software, "software anchor arithmetic");
    emit("CLOCK_SET_SAMPLE phase="); emit(phase);
    emit(" seconds="); number(static_cast<u64>(result.value.seconds));
    emit(" nanoseconds="); number(result.value.nanoseconds);
    emit(" mono_ns="); number(result.monotonic.nanoseconds);
    emit(" mono_generation="); number(result.monotonic.generation);
    emit(" wall_generation="); number(result.wall_generation);
    emit(" origin=administrator-software accuracy=unknown\n");
    return result;
}
time::MonotonicPoint accepted(const char *phase, user::ClockSetValue value, u64 generation, u64 monotonic_generation,
                              time::AnchorInfo original)
{
    const auto samples = sample_calls, commits = commit_calls;
    check(setting(value, user::root_credentials()).ok(), "checked privileged software set");
    check(sample_calls == samples + 1 && commit_calls == commits + 1, "one actual sample and commit");
    check_active(generation, monotonic_generation);
    check(same(arch::realtime_info(), original), "software set changed boot source");
    emit("CLOCK_SET_COMMIT phase="); emit(phase);
    emit(" seconds="); number(static_cast<u64>(value.seconds));
    emit(" nanoseconds="); number(static_cast<u64>(value.nanoseconds));
    emit(" mono_ns="); number(committed.nanoseconds);
    emit(" mono_generation="); number(committed.generation);
    emit(" wall_generation="); number(generation); emit("\n");
    return committed;
}
void refused(const char *label, user::ClockSetValue value, user::Credentials credentials,
             StatusCode expected, u64 expected_samples, time::AnchorInfo original)
{
    const auto before = arch::realtime_clock_info();
    const auto samples = sample_calls, commits = commit_calls;
    check(setting(value, credentials).code() == expected, "failed request returned wrong status");
    check(sample_calls == samples + expected_samples && commit_calls == commits, "failed request sample/commit order");
    check(same(before, arch::realtime_clock_info()) && same(original, arch::realtime_info()), "failed request mutated state");
    emit("CLOCK_SET_REFUSED case="); emit(label);
    emit(" status="); emit(expected == StatusCode::permission ? "permission" : "invalid-argument");
    emit(" samples="); number(expected_samples);
    emit(" commits=0 wall_generation="); number(before.wall_generation); emit("\n");
}
} // namespace

extern "C" [[noreturn]] void kernel_main()
{
    // One boot CPU owns these synchronous calls. No clock service enters from
    // IRQ/NMI callbacks; this is not an interrupt-exclusion or SMP test.
    emit("CLOCK_SET_DIAGNOSTIC_BEGIN scope=privileged-platform-diagnostic public-adapters=not-exercised\n");
    check(arch::realtime_info().state == time::AnchorState::uninitialized &&
          arch::realtime_clock_info().state == time::AnchorState::uninitialized, "fresh boot state");
    check(arch::initialize_clock().ok(), "monotonic initialization");
    auto initial = arch::monotonic_sample(); check(initial.ok() && initial.value().generation != 0, "initial monotonic sample");
    const auto initialized = arch::initialize_realtime();
    const auto original = arch::realtime_info();
    const auto active_before = arch::realtime_clock_info();
    auto source_before = arch::read_epoch_source();
#if defined(OK_ARCH_TARGET_AARCH64) || defined(OK_ARCH_TARGET_ARM32) || defined(OK_ARCH_TARGET_RV32) || defined(OK_ARCH_TARGET_RV64)
    check(initialized.ok() && source_before.ok() && original.state == time::AnchorState::ready &&
          original.source == source_before.value().source && original.accuracy == time::Accuracy::unknown &&
          original.monotonic_generation == initial.value().generation && original.source_resolution_ns != 0,
          "qualified actual boot source");
    check(active_before.origin == time::RealtimeOrigin::boot_rtc && active_before.wall_generation == 1,
          "qualified initial active origin");
    sample("CLOCK_SET_RTC_BEFORE", source_before.value().time);
#else
    check(initialized.code() == StatusCode::unsupported && !source_before &&
          source_before.status().code() == StatusCode::unsupported && original.state == time::AnchorState::unavailable &&
          original.source == time::EpochSource::unavailable && active_before.origin == time::RealtimeOrigin::none &&
          active_before.wall_generation == 0 && !arch::realtime_sample(), "unavailable physical source remains explicit");
#endif
    boot_info("before", original);
    check(arch::initialize_realtime().code() == initialized.code() && same(original, arch::realtime_info()) &&
          same(active_before, arch::realtime_clock_info()), "boot initialization retry changed state");
    constexpr time::EpochTime future{2208988800LL, 123456789}; // 2040-01-01 UTC.
    const u64 first_generation = active_before.wall_generation + 1;
    auto first_anchor = accepted("first", {future.seconds, future.nanoseconds}, first_generation,
                                 initial.value().generation, original);
    auto first = active_sample("first", future, first_anchor, first_generation);
    bool elapsed = false;
    for (u64 attempt = 0; attempt < 200000000; ++attempt)
    {
        auto now = arch::monotonic_sample(); check(now.ok(), "monotonic progress read");
        check(now.value().generation == initial.value().generation && now.value().nanoseconds >= first.monotonic.nanoseconds,
              "monotonic changed during progress wait");
        if (now.value().nanoseconds - first.monotonic.nanoseconds >= 20000000)
        { elapsed = true; break; }
    }
    check(elapsed, "bounded monotonic progress wait");
    auto later = active_sample("later", future, first_anchor, first_generation);
    check(later.value.seconds > first.value.seconds || (later.value.seconds == first.value.seconds &&
          later.value.nanoseconds > first.value.nanoseconds), "software realtime did not advance");
    const auto root = user::root_credentials(), ordinary = user::default_user_credentials();
    refused("negative-seconds", {-1,0}, root, StatusCode::invalid_argument, 0, original);
    refused("seconds-bound", {user::maximum_set_realtime_seconds,0}, root, StatusCode::invalid_argument, 0, original);
    refused("negative-nanoseconds", {future.seconds,-1}, root, StatusCode::invalid_argument, 0, original);
    refused("nanoseconds-bound", {future.seconds,1000000000}, root, StatusCode::invalid_argument, 0, original);
    refused("malformed-nonroot", {-1,0}, ordinary, StatusCode::invalid_argument, 0, original);
    refused("nonroot", {future.seconds,0}, ordinary, StatusCode::permission, 0, original);
    refused("nonroot-before-floor", {0,0}, ordinary, StatusCode::permission, 0, original);
    refused("below-monotonic", {0,0}, root, StatusCode::invalid_argument, 1, original);
    active_sample("after-refusals", future, first_anchor, first_generation);
    constexpr time::EpochTime past{946684800, 456789123}; // 2000-01-01 UTC, still above uptime.
    const auto backward_anchor = accepted("backward", {past.seconds,past.nanoseconds}, first_generation + 1,
                                          initial.value().generation, original);
    const auto backward = active_sample("backward", past, backward_anchor, first_generation + 1);
    check(backward.value.seconds < later.value.seconds, "explicit backward wall step did not occur");
    constexpr time::EpochTime post2038{2208988801LL, 987654321};
    const auto final_anchor = accepted("post2038", {post2038.seconds,post2038.nanoseconds}, first_generation + 2,
                                       initial.value().generation, original);
    active_sample("post2038", post2038, final_anchor, first_generation + 2);
    const auto active_after = arch::realtime_clock_info();
    check(arch::initialize_realtime().code() == initialized.code() && same(original, arch::realtime_info()) &&
          same(active_after, arch::realtime_clock_info()), "software selection retried or replaced boot anchor");
    auto source_after = arch::read_epoch_source();
#if defined(OK_ARCH_TARGET_AARCH64) || defined(OK_ARCH_TARGET_ARM32) || defined(OK_ARCH_TARGET_RV32) || defined(OK_ARCH_TARGET_RV64)
    check(source_after.ok() && source_after.value().source == source_before.value().source &&
          source_after.value().time.seconds >= source_before.value().time.seconds, "physical source changed after software setting");
    sample("CLOCK_SET_RTC_AFTER", source_after.value().time);
#else
    check(!source_after && source_after.status().code() == StatusCode::unsupported, "software setting fabricated physical RTC");
#endif
    boot_info("after", arch::realtime_info());
    auto final = arch::monotonic_sample(); check(final.ok(), "final monotonic sample");
    check(final.value().generation == initial.value().generation && final.value().nanoseconds >= initial.value().nanoseconds &&
          arch::clock_status().ok(), "software setting changed monotonic domain");
    emit("CLOCK_SET_CONTINUITY mono_generation="); number(final.value().generation);
    emit(" before_ns="); number(initial.value().nanoseconds);
    emit(" after_ns="); number(final.value().nanoseconds);
    emit(" wall_generation="); number(active_after.wall_generation);
    emit(" no-retry=1 rtc-writes=0 provider-reset=0 authority=diagnostic-credentials\n");
    emit("CLOCK_SET_DIAGNOSTIC_PASS scope=privileged-platform-diagnostic public-adapters=not-exercised\n");
    stop(true);
}

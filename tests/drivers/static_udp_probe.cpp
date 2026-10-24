#include "drivers/net/static_udp.hpp"
#include <ok/arch/clock.hpp>

using namespace ok;
namespace
{
constexpr os::drivers::net::StaticUdpConfig config{
    {192, 0, 2, 2}, {192, 0, 2, 1}, {2, 0xaa, 0xbb, 0xcc, 0xdd, 0xee}, 54321, 12345};
os::drivers::net::StaticUdpService &service()
{
    static os::drivers::net::StaticUdpService instance(os::drivers::virtio_net_device(), config);
    return instance;
}

#if defined(__aarch64__) || defined(__arm__) || defined(__riscv)
constexpr const char *transport = "mmio";
#else
constexpr const char *transport = "pci";
#endif
void emit(const char *text)
{
    while (*text)
    {
#if defined(__x86_64__) || defined(__i386__)
        u8 ready;
        do { asm volatile("inb %1, %0" : "=a"(ready) : "Nd"(u16{0x3fd})); } while (!(ready & 32));
        asm volatile("outb %0, %1" ::"a"(static_cast<u8>(*text++)), "Nd"(u16{0x3f8}));
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
        ++text;
#endif
    }
}
[[maybe_unused]] void number(u32 value)
{
    char digits[10]{};
    usize count{};
    do { digits[count++] = static_cast<char>('0' + value % 10); value /= 10; } while (value);
    while (count) { const char text[]{digits[--count], 0}; emit(text); }
}
[[noreturn]] void end() { for (;;) asm volatile("" ::: "memory"); }
void check(bool passed, const char *reason)
{
    if (passed) return;
    emit("STATIC_UDP_FAIL reason="); emit(reason); emit("\n"); end();
}
[[maybe_unused]] os::drivers::net::PollKind next()
{
    const auto started = arch::monotonic_nanoseconds(); check(started.ok(), "clock");
    for (;;)
    {
        const auto result = service().poll_once(); check(result.ok(), "poll");
        if (result.value() != os::drivers::net::PollKind::idle) return result.value();
        const auto now = arch::monotonic_nanoseconds();
        check(now.ok() && now.value() >= started.value() &&
              now.value() - started.value() < 3'000'000'000, "deadline");
    }
}
}
extern "C" void *memcpy(void *to, const void *from, usize size)
{
    auto *out = static_cast<volatile std::byte *>(to); auto *in = static_cast<const std::byte *>(from);
    for (usize i = 0; i < size; ++i) out[i] = in[i];
    return to;
}
extern "C" void *memset(void *to, int value, usize size)
{
    auto *out = static_cast<volatile u8 *>(to);
    for (usize i = 0; i < size; ++i) out[i] = static_cast<u8>(value);
    return to;
}
extern "C" int memcmp(const void *left, const void *right, usize size)
{
    auto *a = static_cast<const u8 *>(left); auto *b = static_cast<const u8 *>(right);
    for (usize i = 0; i < size; ++i) if (a[i] != b[i]) return a[i] < b[i] ? -1 : 1;
    return 0;
}
extern "C" [[noreturn]] void kernel_main()
{
    emit("STATIC_UDP_BEGIN transport="); emit(transport); emit("\n");
    check(arch::initialize_clock().ok(), "clock-init");
    const auto started = service().start();
#ifdef OK_STATIC_UDP_ABSENT
    check(!started && started.code() == StatusCode::not_found, "absent");
    emit("STATIC_UDP_PASS scenario=absent\n"); end();
#elif defined(OK_STATIC_UDP_LEGACY)
    check(!started && started.code() == StatusCode::unsupported, "legacy");
    emit("STATIC_UDP_PASS scenario=legacy\n"); end();
#else
    if (!started) { emit(started.message().data()); emit("\n"); }
    check(started.ok(), "start");
    emit("STATIC_UDP_READY\n");
#ifdef OK_STATIC_UDP_HOSTILE
    for (u32 i = 0; i < 12; ++i)
    {
        check(next() == os::drivers::net::PollKind::dropped, "hostile-drop");
        emit("STATIC_UDP_DROP index="); number(i); emit("\n");
    }
    check(next() == os::drivers::net::PollKind::udp_replied, "hostile-recovery");
    check(service().stop().ok(), "stop");
    emit("STATIC_UDP_PASS scenario=hostile drops=12 recovery=1\n"); end();
#else
    check(next() == os::drivers::net::PollKind::arp_replied, "arp");
    for (u32 i = 0; i < 96; ++i)
        check(next() == os::drivers::net::PollKind::udp_replied, "udp");
    check(service().stop().ok(), "stop");
    emit("STATIC_UDP_PASS scenario=exchange arp=1 udp=96\n"); end();
#endif
#endif
}

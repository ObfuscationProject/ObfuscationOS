#include "drivers/virtio/net.hpp"
#include <ok/arch/clock.hpp>
#include <array>

using namespace ok;
namespace
{
std::array<std::byte, 1514> outgoing{}, incoming{};
#if defined(__aarch64__) || defined(__arm__) || defined(__riscv)
constexpr const char *scope = "native-mmio";
#else
constexpr const char *scope = "native-pci";
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
[[noreturn]] void end() { for (;;) asm volatile("" ::: "memory"); }
void check(bool passed, const char *reason)
{
    if (passed) return;
    emit("VIRTIO_NET_FAIL "); emit(reason); emit("\n"); end();
}
[[maybe_unused]] void exchange(u16 sequence)
{
    auto &device = os::drivers::virtio_net_device();
    const usize size = sequence % 3 == 0 ? 1514 : 60 + sequence;
    const auto mac = device.mac();
    constexpr std::array<u8, 6> peer{2, 0xaa, 0xbb, 0xcc, 0xdd, 0xee};
    for (usize i = 0; i < 6; ++i) { outgoing[i] = std::byte{peer[i]}; outgoing[6 + i] = std::byte{mac[i]}; }
    outgoing[12] = std::byte{0x88}; outgoing[13] = std::byte{0xb5};
    outgoing[14] = std::byte{static_cast<u8>(sequence >> 8)};
    outgoing[15] = std::byte{static_cast<u8>(sequence)};
    for (usize i = 16; i < size; ++i) outgoing[i] = std::byte{static_cast<u8>((i * 37) ^ sequence ^ 0x5a)};
    check(device.transmit({outgoing.data(), size}).ok(), "transmit");
    const auto start = arch::monotonic_nanoseconds(); check(start.ok(), "clock");
    Result<usize> packet = Status::not_found("waiting");
    bool small_checked = sequence != 0;
    for (;;)
    {
        packet = device.receive(small_checked ? std::span<std::byte>{incoming} : std::span<std::byte>{incoming.data(), 1});
        if (!small_checked && packet.status().code() == StatusCode::overflow) { small_checked = true; continue; }
        if (packet) break;
        check(packet.status().code() == StatusCode::not_found, "receive status");
        const auto now = arch::monotonic_nanoseconds();
        check(now.ok() && now.value() >= start.value() && now.value() - start.value() < 3'000'000'000, "receive deadline");
    }
    check(packet.value() == size && small_checked, "receive size and retry");
    for (usize i = 0; i < size; ++i)
    {
        const auto expected = i < 6 ? outgoing[i + 6] : i < 12 ? outgoing[i - 6] : outgoing[i];
        check(incoming[i] == expected, "peer bytes");
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
    auto &device = os::drivers::virtio_net_device();
    emit("VIRTIO_NET_BEGIN scope="); emit(scope); emit("\n");
    check(arch::initialize_clock().ok(), "initialize clock");
    auto started = device.start();
#ifdef OK_NET_ABSENT
    check(!started && started.code() == StatusCode::not_found, "absent");
    emit("VIRTIO_NET_PASS scope="); emit(scope); emit(" absent=pass\n"); end();
#elif defined(OK_NET_LEGACY)
    check(!started && started.code() == StatusCode::unsupported, "legacy rejection");
    emit("VIRTIO_NET_PASS scope="); emit(scope); emit(" legacy=unsupported\n"); end();
#else
    if (!started) { emit(started.message().data()); emit("\n"); }
    check(started.ok() && device.active(), "start");
    check(!device.transmit({outgoing.data(), 13}) && !device.transmit({outgoing.data(), 0}), "bad frame bounds");
    for (u16 sequence = 0; sequence < 80; ++sequence) exchange(sequence);
    check(device.stop().ok() && !device.active(), "reset quiescence");
    check(!device.transmit({outgoing.data(), 60}), "stopped transmit");
    check(!device.receive(incoming), "stopped receive");
    check(device.start().ok(), "restart");
    for (u16 sequence = 80; sequence < 96; ++sequence) exchange(sequence);
    check(device.stop().ok(), "final reset");
    emit("VIRTIO_NET_PASS scope="); emit(scope); emit(" packets=96 ring=pass bytes=pass retry=pass restart=pass\n"); end();
#endif
}

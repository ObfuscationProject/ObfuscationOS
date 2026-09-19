#include "drivers/virtio/block.hpp"
using namespace ok;
namespace
{
void emit(const char *text)
{
    while (*text)
    {
#if defined(__x86_64__) || defined(__i386__)
        u8 ready;
        do
        {
            asm volatile("inb %1, %0" : "=a"(ready) : "Nd"(u16{0x3fd}));
        } while (!(ready & 32));
        asm volatile("outb %0, %1" ::"a"(static_cast<u8>(*text++)), "Nd"(u16{0x3f8}));
#elif defined(__aarch64__) || defined(__arm__)
        while (*reinterpret_cast<volatile u32 *>(0x09000018) & 32)
        {
        }
        *reinterpret_cast<volatile u32 *>(0x09000000) = static_cast<u8>(*text++);
#elif defined(__riscv)
        *reinterpret_cast<volatile u8 *>(0x10000000) = static_cast<u8>(*text++);
#elif defined(__loongarch__)
        while (!(*reinterpret_cast<volatile u8 *>(0x1fe001e5) & 32))
        {
        }
        *reinterpret_cast<volatile u8 *>(0x1fe001e0) = static_cast<u8>(*text++);
#elif defined(__mips__)
#if __SIZEOF_POINTER__ == 8
        constexpr uptr uart = 0xffffffffb80003f8ull;
#else
        constexpr uptr uart = 0xb80003f8;
#endif
        while (!(*reinterpret_cast<volatile u8 *>(uart + 5) & 32))
        {
        }
        *reinterpret_cast<volatile u8 *>(uart) = static_cast<u8>(*text++);
#elif defined(__powerpc__) || defined(__PPC__)
        while (!(*reinterpret_cast<volatile u8 *>(0xe0004505) & 32))
        {
        }
        *reinterpret_cast<volatile u8 *>(0xe0004500) = static_cast<u8>(*text++);
#else
        ++text;
#endif
    }
}
[[noreturn]] void end()
{
    for (;;)
        asm volatile("" ::: "memory");
}
void check(bool success, const char *reason)
{
    if (success)
        return;
    emit("VIRTIO_BLOCK_FAIL ");
    emit(reason);
    emit("\n");
    end();
}
#ifndef OK_BLOCK_NO_DEVICE
alignas(4096) std::array<std::byte, 8192> data{};
#endif
} // namespace
extern "C" void *memcpy(void *to, const void *from, usize size)
{
    auto *out = static_cast<volatile std::byte *>(to);
    const auto *in = static_cast<const std::byte *>(from);
    for (usize i = 0; i < size; ++i)
        out[i] = in[i];
    return to;
}
extern "C" void *memset(void *to, int value, usize size)
{
    auto *out = static_cast<volatile u8 *>(to);
    for (usize i = 0; i < size; ++i)
        out[i] = static_cast<u8>(value);
    return to;
}
void operator delete(void *) noexcept
{
    end();
}
void operator delete(void *, usize) noexcept
{
    end();
}
extern "C" [[noreturn]] void kernel_main()
{
    emit("VIRTIO_BLOCK_BEGIN\n");
    auto result = os::drivers::probe_virtio_block();
#ifdef OK_BLOCK_NO_DEVICE
    check(!result && result.status().code() == StatusCode::not_found, "absent device");
    emit("VIRTIO_BLOCK_PASS scope=hardware absent=pass\n");
    end();
#else
    if (!result)
    {
        emit(result.status().message().data());
        emit("\n");
    }
    check(result.ok(), "probe");
    auto *disk = result.value();
    check(disk->geometry().block_size == 512 && disk->geometry().block_count == 1024, "geometry");
    check(!disk->read_blocks(1024, {data.data(), 512}), "reject capacity overflow");
    check(!disk->read_blocks(0, {data.data(), 511}), "reject partial sector");
    check(disk->read_blocks(1024, {}).ok(), "empty boundary read");
    auto status = disk->read_blocks(40, data);
#ifdef OK_BLOCK_READ_ERROR
    check(!status && status.code() == StatusCode::fault, "injected device read error");
    check(disk->read_blocks(40, data).ok(), "queue recovers after device I/O error");
    for (usize i = 0; i < data.size(); ++i)
        check(data[i] == static_cast<std::byte>((i ^ 0x5a) & 255), "recovered read contents");
    check(disk->io_stats().errors == 1, "device error statistics");
    emit("VIRTIO_BLOCK_PASS scope=hardware read_error=pass recovery=pass\n");
    end();
#endif
    if (!status)
    {
        emit(status.message().data());
        emit("\n");
    }
    check(status.ok(), "read disk");
#ifdef OK_BLOCK_READ_ONLY
    check(!disk->geometry().writable, "read-only geometry");
    check(!disk->write_blocks(40, data), "reject read-only write");
    emit("VIRTIO_BLOCK_PASS scope=hardware readonly=pass\n");
#else
    check(disk->geometry().writable, "writable disk");
    bool reopened = data[0] == std::byte{0x5a};
    for (usize i = 0; i < data.size(); ++i)
        check(data[i] == (reopened ? static_cast<std::byte>((i ^ 0x5a) & 255) : std::byte{0xa5}), "initial disk bytes");
    if (reopened)
    {
        emit("VIRTIO_BLOCK_PASS scope=hardware reopen=pass\n");
        end();
    }
    for (usize i = 0; i < data.size(); ++i)
        data[i] = static_cast<std::byte>((i ^ 0x5a) & 255);
    check(disk->write_blocks(40, data).ok(), "write disk");
    check(disk->flush().ok(), "flush disk");
    for (usize repeat = 0; repeat < 20; ++repeat)
    {
        for (auto &byte : data)
            byte = std::byte{};
        check(disk->read_blocks(40, data).ok(), "read after write and ring wrap");
        for (usize i = 0; i < data.size(); ++i)
            check(data[i] == static_cast<std::byte>((i ^ 0x5a) & 255), "written bytes");
    }
    const auto stats = disk->io_stats();
    check(stats.bytes_read >= 8192 && stats.bytes_written == 8192 && !stats.errors, "I/O stats");
    emit("VIRTIO_BLOCK_PASS scope=hardware write=pass flush=pass ring_wrap=pass\n");
#endif
    end();
#endif
}

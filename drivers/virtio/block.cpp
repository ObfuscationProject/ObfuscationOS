#include "block.hpp"
#include "poll.hpp"
#include "ok/arch/clock.hpp"
#include "ok/interrupt/platform.hpp"
#include <utility>

#include <array>
#include <new>

namespace os::drivers
{
namespace
{
using namespace ok;
constexpr usize queue_size = 8;
constexpr usize transfer_size = 4096;
constexpr u32 feature_readonly = 1u << 5;
constexpr u32 feature_flush = 1u << 9;
constexpr u64 io_timeout_ns = 5'000'000'000;

void barrier()
{
#if defined(__aarch64__) || defined(__arm__)
    asm volatile("dmb sy" ::: "memory");
#elif defined(__riscv)
    asm volatile("fence iorw, iorw" ::: "memory");
#elif defined(__loongarch__)
    asm volatile("dbar 0" ::: "memory");
#elif defined(__mips__)
    asm volatile("sync" ::: "memory");
#elif defined(__powerpc__) || defined(__PPC__)
    asm volatile("sync" ::: "memory");
#else
    asm volatile("mfence" ::: "memory");
#endif
}
template <typename T> T little(T value)
{
#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
    if constexpr (sizeof(T) == 2)
        return __builtin_bswap16(value);
    if constexpr (sizeof(T) == 4)
        return __builtin_bswap32(value);
    if constexpr (sizeof(T) == 8)
        return __builtin_bswap64(value);
#endif
    return value;
}
template <typename T> T read(uptr address)
{
    const auto value = *reinterpret_cast<volatile T *>(address);
    barrier();
    return little(value);
}
template <typename T> void write(uptr address, T value)
{
    barrier();
    *reinterpret_cast<volatile T *>(address) = little(value);
    barrier();
}
u64 physical(const void *pointer)
{
    const auto address = reinterpret_cast<uptr>(pointer);
#if defined(__mips__)
    return address & 0x1fffffff;
#else
    return address;
#endif
}
void write_address(uptr address, u64 value)
{
    write<u32>(address, static_cast<u32>(value));
    write<u32>(address + 4, static_cast<u32>(value >> 32));
}

struct Descriptor
{
    u64 address;
    u32 length;
    u16 flags;
    u16 next;
};
struct Available
{
    u16 flags;
    u16 index;
    u16 ring[queue_size];
    u16 used_event;
};
struct UsedElement
{
    u32 id, length;
};
struct Used
{
    u16 flags;
    u16 index;
    UsedElement ring[queue_size];
    u16 available_event;
};
// Legacy MMIO requires the descriptor/available region followed by a 4 KiB
// aligned used ring. Modern transports can use the same physical arrangement.
struct Request
{
    u32 type, reserved;
    u64 sector;
};
struct alignas(4096) Queue
{
    Descriptor descriptors[queue_size]{};
    Available available{};
    alignas(4096) Used used{};
    alignas(16) Request request{};
    alignas(16) std::array<std::byte, transfer_size> buffer{};
    u8 completion{};
};
static_assert(offsetof(Queue, used) == 4096);

class MmioTransport
{
  public:
    Status discover()
    {
#if defined(__aarch64__) || defined(__arm__)
        constexpr uptr base = 0x0a000000, stride = 0x200;
        constexpr usize count = 32;
#elif defined(__riscv)
        constexpr uptr base = 0x10001000, stride = 0x1000;
        constexpr usize count = 8;
#else
        return Status::not_found("Virtio MMIO is unavailable on this platform");
#endif
#if defined(__aarch64__) || defined(__arm__) || defined(__riscv)
        for (usize i = 0; i < count; ++i)
        {
            const auto address = base + i * stride;
            if (read<u32>(address) == 0x74726976 && read<u32>(address + 8) == 2)
            {
                base_ = address;
                slot_ = i;
                const auto version = read<u32>(base_ + 4);
                if (version != 1 && version != 2)
                    return Status::unsupported("unsupported Virtio MMIO version");
                legacy_ = version == 1;
                return Status::success();
            }
        }
        return Status::not_found("no Virtio MMIO block device");
#endif
    }
    bool legacy() const
    {
        return legacy_;
    }
    u8 status() const
    {
        return static_cast<u8>(read<u32>(base_ + 0x70));
    }
    void status(u8 value)
    {
        write<u32>(base_ + 0x70, value);
    }
    u32 features(u32 bank)
    {
        write<u32>(base_ + 0x14, bank);
        return read<u32>(base_ + 0x10);
    }
    void features(u32 bank, u32 value)
    {
        write<u32>(base_ + 0x24, bank);
        write<u32>(base_ + 0x20, value);
    }
    u64 capacity() const
    {
        for (usize i = 0; i < 8; ++i)
        {
            const auto generation = read<u32>(base_ + 0xfc);
            const auto low = read<u32>(base_ + 0x100);
            const auto high = read<u32>(base_ + 0x104);
            if (legacy_ || generation == read<u32>(base_ + 0xfc))
                return (u64{high} << 32) | low;
        }
        return 0;
    }
    Status setup(Queue &queue)
    {
        write<u32>(base_ + 0x30, 0);
        if (read<u32>(base_ + 0x34) < queue_size)
            return Status::unsupported("Virtio block queue is too small");
        write<u32>(base_ + 0x38, queue_size);
        if (legacy_)
        {
            write<u32>(base_ + 0x28, 4096);
            write<u32>(base_ + 0x3c, 4096);
            write<u32>(base_ + 0x40, static_cast<u32>(physical(&queue) >> 12));
        }
        else
        {
            write_address(base_ + 0x80, physical(queue.descriptors));
            write_address(base_ + 0x90, physical(&queue.available));
            write_address(base_ + 0xa0, physical(&queue.used));
            write<u32>(base_ + 0x44, 1);
        }
        return Status::success();
    }
    void notify()
    {
        write<u32>(base_ + 0x50, 0);
    }
    void acknowledge()
    {
        write<u32>(base_ + 0x64, read<u32>(base_ + 0x60));
    }
    Result<interrupt::PlatformLine> interrupt_line() const
    {
        return interrupt::virtio_mmio_line(slot_);
    }
    void enable_interrupts()
    {
    }

  private:
    uptr base_{};
    usize slot_{};
    bool legacy_{};
};

class PciTransport
{
  public:
    Status discover()
    {
#if !defined(__x86_64__) && !defined(__i386__) && !defined(__loongarch__) && !defined(__mips__) &&                     \
    !defined(__powerpc__) && !defined(__PPC__)
        return Status::not_found("Virtio PCI is unavailable on this platform");
#else
        for (u8 slot = 0; slot < 32; ++slot)
            for (u8 function = 0; function < 8; ++function)
            {
                slot_ = slot;
                function_ = function;
                const auto id = config32(0);
                if ((id & 0xffff) != 0x1af4 || (id >> 16 != 0x1001 && id >> 16 != 0x1042))
                    continue;
                if (auto result = configure_bars(); !result)
                    return result;
                if (auto result = load_caps(); !result)
                    return result;
                config16(4, static_cast<u16>(config32(4)) | 6 | 0x400);
                return Status::success();
            }
        return Status::not_found("no modern Virtio PCI block device");
#endif
    }
    bool legacy() const
    {
        return false;
    }
    u8 status() const
    {
        return read<u8>(common_ + 20);
    }
    void status(u8 value)
    {
        write<u8>(common_ + 20, value);
    }
    u32 features(u32 bank)
    {
        write<u32>(common_, bank);
        return read<u32>(common_ + 4);
    }
    void features(u32 bank, u32 value)
    {
        write<u32>(common_ + 8, bank);
        write<u32>(common_ + 12, value);
    }
    u64 capacity() const
    {
        for (usize i = 0; i < 8; ++i)
        {
            const auto generation = read<u8>(common_ + 21);
            const auto low = read<u32>(device_);
            const auto high = read<u32>(device_ + 4);
            if (generation == read<u8>(common_ + 21))
                return (u64{high} << 32) | low;
        }
        return 0;
    }
    Status setup(Queue &queue)
    {
        write<u16>(common_ + 22, 0);
        if (read<u16>(common_ + 24) < queue_size || read<u16>(common_ + 28))
            return Status::unsupported("Virtio block queue is unavailable");
        write<u16>(common_ + 24, queue_size);
        const u64 offset = u64{read<u16>(common_ + 30)} * notify_multiplier_;
        if (offset + 2 > notify_length_)
            return Status::invalid_argument("Virtio notification is outside its PCI capability");
        queue_notify_ = notify_ + static_cast<uptr>(offset);
        write_address(common_ + 32, physical(queue.descriptors));
        write_address(common_ + 40, physical(&queue.available));
        write_address(common_ + 48, physical(&queue.used));
        write<u16>(common_ + 28, 1);
        return Status::success();
    }
    void notify()
    {
        write<u16>(queue_notify_, 0);
    }
    Result<interrupt::PlatformLine> interrupt_line() const
    {
        return interrupt::pci_intx_line(slot_, config8(0x3d), config8(0x3c));
    }
    // Clears the command register's INTx disable bit set at discovery.
    void enable_interrupts()
    {
        config16(4, static_cast<u16>(config32(4)) & ~u16{0x400});
    }
    void acknowledge()
    {
        if (isr_)
            static_cast<void>(read<u8>(isr_));
    }

  private:
    u32 config32(u16 offset) const
    {
#if defined(__x86_64__) || defined(__i386__)
        const u32 address = 0x80000000 | (u32{slot_} << 11) | (u32{function_} << 8) | (offset & 0xfc);
        u32 result;
        asm volatile("outl %0, %1" ::"a"(address), "Nd"(u16{0xcf8}));
        asm volatile("inl %1, %0" : "=a"(result) : "Nd"(u16{0xcfc}));
        return result;
#elif defined(__loongarch__)
        return read<u32>(0x20000000 + (uptr{slot_} << 15) + (uptr{function_} << 12) + (offset & 0xfc));
#elif defined(__mips__)
        // Malta firmware configures native-endian GT data, with an LE index.
        write<u32>(malta_bridge() + 0xcf8, config_address(offset));
        const u32 value = *reinterpret_cast<volatile u32 *>(malta_bridge() + 0xcfc);
        barrier();
        return value;
#elif defined(__powerpc__) || defined(__PPC__)
        // ppce500 reverses that arrangement: BE index, LE configuration data.
        *reinterpret_cast<volatile u32 *>(0xe0008000) = config_address(offset);
        barrier();
        return read<u32>(0xe0008004);
#else
        static_cast<void>(offset);
        return 0xffffffff;
#endif
    }
    void config32(u16 offset, u32 value)
    {
#if defined(__x86_64__) || defined(__i386__)
        const u32 address = 0x80000000 | (u32{slot_} << 11) | (u32{function_} << 8) | (offset & 0xfc);
        asm volatile("outl %0, %1" ::"a"(address), "Nd"(u16{0xcf8}));
        asm volatile("outl %0, %1" ::"a"(value), "Nd"(u16{0xcfc}));
#elif defined(__loongarch__)
        write<u32>(0x20000000 + (uptr{slot_} << 15) + (uptr{function_} << 12) + (offset & 0xfc), value);
#elif defined(__mips__)
        write<u32>(malta_bridge() + 0xcf8, config_address(offset));
        *reinterpret_cast<volatile u32 *>(malta_bridge() + 0xcfc) = value;
        barrier();
#elif defined(__powerpc__) || defined(__PPC__)
        *reinterpret_cast<volatile u32 *>(0xe0008000) = config_address(offset);
        barrier();
        write<u32>(0xe0008004, value);
#else
        static_cast<void>(offset);
        static_cast<void>(value);
#endif
    }
    u8 config8(u16 offset) const
    {
        return static_cast<u8>(config32(offset) >> ((offset & 3) * 8));
    }
    void config16(u16 offset, u16 value)
    {
#if defined(__x86_64__) || defined(__i386__)
        const u32 address = 0x80000000 | (u32{slot_} << 11) | (u32{function_} << 8) | (offset & 0xfc);
        asm volatile("outl %0, %1" ::"a"(address), "Nd"(u16{0xcf8}));
        asm volatile("outw %0, %1" ::"a"(value), "Nd"(static_cast<u16>(0xcfc + (offset & 2))));
#elif defined(__loongarch__)
        write<u16>(0x20000000 + (uptr{slot_} << 15) + (uptr{function_} << 12) + offset, value);
#elif defined(__mips__)
        // GT config data is a native-endian dword even though its index and
        // the PCI device BARs are little-endian. Do not echo W1C status bits.
        const u32 prior = offset == 4 ? 0 : config32(offset);
        const auto shift = (offset & 2) * 8;
        config32(offset, (prior & ~(0xffffu << shift)) | (u32{value} << shift));
#elif defined(__powerpc__) || defined(__PPC__)
        *reinterpret_cast<volatile u32 *>(0xe0008000) = config_address(offset);
        barrier();
        write<u16>(0xe0008004 + (offset & 2), value);
#else
        static_cast<void>(offset);
        static_cast<void>(value);
#endif
    }
    Status configure_bars()
    {
        config16(4, static_cast<u16>(config32(4)) & ~u16(7));
#if defined(__loongarch__)
        uptr next = 0x50000000 + uptr{slot_} * 0x100000;
#elif defined(__mips__)
        uptr next = 0x10000000 + uptr{slot_} * 0x100000;
#elif defined(__powerpc__) || defined(__PPC__)
        uptr next = 0xc0000000 + uptr{slot_} * 0x100000;
#else
        uptr next = 0x30000000 + uptr{slot_} * 0x100000;
#endif
        const auto end = next + 0x100000;
        for (u8 bar = 0; bar < 6; ++bar)
        {
            const auto offset = static_cast<u16>(16 + bar * 4);
            const auto original = config32(offset);
            if (original & 1)
                continue;
            const bool wide = (original & 6) == 4;
            if ((original & 6) != 0 && !wide)
                return Status::unsupported("unsupported Virtio PCI BAR type");
            config32(offset, 0xffffffff);
            const auto mask = config32(offset) & ~u32(15);
            config32(offset, original);
            if (!mask)
                continue;
            const u32 size = ~mask + 1;
            if (!size || (size & (size - 1)) || size > 0x100000)
                return Status::unsupported("Virtio PCI BAR exceeds the platform window");
            next = (next + size - 1) & ~uptr(size - 1);
            if (next > end || size > end - next || (wide && bar == 5))
                return Status::unsupported("Virtio PCI BARs exceed the platform window");
            bars_[bar] = map_bar(next);
            bar_sizes_[bar] = size;
            config32(offset, static_cast<u32>(next) | (original & 15));
            if (wide)
                config32(static_cast<u16>(16 + (++bar) * 4), 0);
            next += size;
        }
        return Status::success();
    }
    Status load_caps()
    {
        if (!(config32(4) & (1u << 20)))
            return Status::unsupported("Virtio PCI device lacks modern capabilities");
        u8 cap = config8(0x34) & 0xfc;
        for (usize guard = 0; cap && guard < 48; ++guard)
        {
            if (cap < 0x40 || cap > 0xec)
                return Status::invalid_argument("invalid Virtio PCI capability chain");
            const u8 length = config8(cap + 2);
            if (config8(cap) == 9 && length >= 16)
            {
                const auto type = config8(cap + 3);
                const auto bar = config8(cap + 4);
                const auto offset = config32(cap + 8);
                const auto size = config32(cap + 12);
                if (bar < 6 && bars_[bar] && offset <= bar_sizes_[bar] && size <= bar_sizes_[bar] - offset)
                {
                    const auto address = bars_[bar] + offset;
                    if (type == 1 && size >= 56)
                        common_ = address;
                    if (type == 2 && size >= 2 && length >= 20)
                    {
                        notify_ = address;
                        notify_length_ = size;
                        notify_multiplier_ = config32(cap + 16);
                    }
                    if (type == 3 && size >= 1)
                        isr_ = address;
                    if (type == 4 && size >= 8)
                        device_ = address;
                }
            }
            cap = config8(cap + 1) & 0xfc;
        }
        if (cap || !common_ || !notify_ || !device_)
            return Status::unsupported("incomplete Virtio PCI block capabilities");
        return Status::success();
    }
    u8 slot_{}, function_{};
    u32 config_address(u16 offset) const
    {
        return 0x80000000 | (u32{slot_} << 11) | (u32{function_} << 8) | (offset & 0xfc);
    }
    static uptr malta_bridge()
    {
        return static_cast<uptr>(static_cast<i32>(0xbbe00000u));
    }
    static uptr map_bar(uptr address)
    {
#if defined(__mips__)
        // Uncached KSEG1 must retain its sign extension under the n64 ABI.
        return static_cast<uptr>(static_cast<i32>(address | 0xa0000000u));
#else
        return address;
#endif
    }
    std::array<uptr, 6> bars_{};
    std::array<u32, 6> bar_sizes_{};
    uptr common_{}, notify_{}, device_{}, isr_{}, queue_notify_{};
    u32 notify_multiplier_{}, notify_length_{};
};

template <typename Transport> class VirtioBlock final : public driver::BlockDevice
{
  public:
    explicit VirtioBlock(Queue &queue) : queue_(queue)
    {
    }
    Status initialize()
    {
        if (shutdown_started_)
            return Status::would_block("Virtio block shutdown closed admission");
        if (auto result = transport_.discover(); !result)
            return result;
        if (auto status = arch::initialize_clock(); !status)
            return status;
        auto started = arch::monotonic_nanoseconds();
        if (!started)
            return started.status();
        transport_.status(0);
        if (auto status = detail::poll_until([&] { return transport_.status() == 0; },
                [] { return arch::monotonic_nanoseconds(); }, started.value(), io_timeout_ns); !status)
            return status;
        transport_.status(3);
        const auto offered = transport_.features(0);
        flush_ = offered & feature_flush;
        writable_ = !(offered & feature_readonly) && flush_;
        transport_.features(0, offered & (feature_readonly | feature_flush));
        if (!transport_.legacy())
        {
            if (!(transport_.features(1) & 1))
                return fail("Virtio block does not offer VERSION_1");
            transport_.features(1, 1);
            transport_.status(11);
            if (!(transport_.status() & 8))
                return fail("Virtio block feature negotiation failed");
        }
        capacity_ = transport_.capacity();
        if (!capacity_)
            return fail("Virtio block capacity is zero or unstable");
        queue_.available.flags = little(u16{1}); // Polling, no device interrupt.
        if (auto result = transport_.setup(queue_); !result)
        {
            transport_.status(transport_.status() | 128);
            return result;
        }
        transport_.status(transport_.status() | 4);
        ready_ = true;
        return Status::success();
    }
    driver::BlockGeometry geometry() const override
    {
        return {capacity_, 512, writable_ && ready_};
    }
    driver::BlockIoStats io_stats() const override
    {
        return stats_;
    }
    Status read_blocks(u64 first, std::span<std::byte> out) override
    {
        if (auto result = validate(first, out.size()); !result)
            return result;
        const auto size = out.size();
        while (!out.empty())
        {
            const auto count = out.size() < transfer_size ? out.size() : transfer_size;
            if (auto result = request(0, first, count); !result)
                return result;
            for (usize i = 0; i < count; ++i)
                out[i] = queue_.buffer[i];
            first += count / 512;
            out = out.subspan(count);
        }
        ++stats_.read_operations;
        stats_.bytes_read += size;
        return Status::success();
    }
    Status write_blocks(u64 first, std::span<const std::byte> in) override
    {
        if (!writable_)
            return Status::denied("Virtio block is read-only or lacks FLUSH");
        if (auto result = validate(first, in.size()); !result)
            return result;
        const auto size = in.size();
        while (!in.empty())
        {
            const auto count = in.size() < transfer_size ? in.size() : transfer_size;
            for (usize i = 0; i < count; ++i)
                queue_.buffer[i] = in[i];
            if (auto result = request(1, first, count); !result)
                return result;
            first += count / 512;
            in = in.subspan(count);
        }
        ++stats_.write_operations;
        stats_.bytes_written += size;
        return Status::success();
    }
    Status flush() override
    {
        if (!flush_)
            return Status::unsupported("Virtio block FLUSH is unavailable");
        return request(4, 0, 0);
    }
    Status preflight_shutdown()
    {
        if (shutdown_started_)
            return Status::would_block("Virtio block shutdown already consumed its transport");
        if (transport_.legacy())
            return Status::unsupported("clean shutdown has no qualified legacy Virtio block transport");
        if (!ready_ || !writable_ || !flush_ || !capacity_)
            return Status::unsupported("Virtio block shutdown requires the ready writable FLUSH transport");
        if (busy_ || available_ != used_)
            return Status::busy("Virtio block shutdown has an outstanding request");
        barrier();
        if (little(*reinterpret_cast<volatile u16 *>(&queue_.available.index)) != available_ ||
            little(*reinterpret_cast<volatile u16 *>(&queue_.used.index)) != used_)
            return Status::busy("Virtio block shutdown queue ownership differs");
        const auto status = transport_.status();
        if ((status & 15) != 15 || (status & (64 | 128)) || transport_.capacity() != capacity_ || stats_.errors)
            return Status::unsupported("Virtio block shutdown transport state is not qualified");
        return {};
    }
    Status stop_shutdown()
    {
        if (shutdown_started_)
            return shutdown_finished_ ? shutdown_status_ : Status::busy("Virtio block shutdown is active");
        if (auto status = preflight_shutdown(); !status) return status;
        shutdown_started_ = true;
        ready_ = false;
        auto started = arch::monotonic_nanoseconds();
        if (!started) shutdown_status_ = started.status();
        else
        {
            transport_.status(0);
            shutdown_status_ = detail::poll_until([&] { return transport_.status() == 0; },
                [] { return arch::monotonic_nanoseconds(); }, started.value(), io_timeout_ns);
        }
        // A failed or uncertain reset is terminal. Static queue memory cannot
        // be reused even when the device has not acknowledged the reset.
        shutdown_finished_ = true;
        return shutdown_status_;
    }

  private:
    Status fail(std::string_view message)
    {
        ready_ = false;
        transport_.status(transport_.status() | 128);
        ++stats_.errors;
        return Status::fault(message);
    }
    Status validate(u64 first, usize size) const
    {
        if (shutdown_started_)
            return Status::would_block("Virtio block shutdown closed admission");
        if (!ready_)
            return Status::not_initialized("Virtio block is not ready");
        if (size % 512 || first > capacity_ || size / 512 > capacity_ - first)
            return Status::invalid_argument("Virtio block transfer is out of range");
        return Status::success();
    }
    Status request(u32 type, u64 sector, usize size)
    {
        if (shutdown_started_)
            return Status::would_block("Virtio block shutdown closed admission");
        if (!ready_)
            return Status::not_initialized("Virtio block is not ready");
        if (busy_)
            return Status::busy("Virtio block request is already active");
        if (!interrupt_attempted_ && interrupt::platform_irqs_started())
            attach_interrupt();
        auto started = arch::monotonic_nanoseconds();
        if (!started)
            return started.status();
        busy_ = true;
        queue_.request = {little(type), 0, little(sector)};
        queue_.completion = 0xff;
        queue_.descriptors[0] = {little(physical(&queue_.request)), little(u32{sizeof(queue_.request)}), little(u16{1}),
                                 little(u16{1})};
        const u16 tail = size ? 2 : 1;
        if (size)
            queue_.descriptors[1] = {little(physical(queue_.buffer.data())), little(static_cast<u32>(size)),
                                     little(static_cast<u16>(type == 0 ? 3 : 1)), little(u16{2})};
        queue_.descriptors[tail] = {little(physical(&queue_.completion)), little(u32{1}), little(u16{2}), 0};
        queue_.available.ring[available_ % queue_size] = 0;
        barrier();
        *reinterpret_cast<volatile u16 *>(&queue_.available.index) = little(++available_);
        barrier();
        transport_.notify();
        const auto ready = [&] {
            barrier();
            return little(*reinterpret_cast<volatile u16 *>(&queue_.used.index)) != used_;
        };
        const auto clock = [] { return arch::monotonic_nanoseconds(); };
        const auto signalled = [&] { return std::exchange(signalled_, false); };
        const auto completed = interrupt_bound_ ? detail::wait_until(ready, signalled, clock, started.value(),
                                                                     io_timeout_ns, detail::wait_for_device_interrupt)
                                                : detail::poll_until(ready, clock, started.value(), io_timeout_ns);
        barrier();
        busy_ = false;
        // A failed wait retires this device. Queue memory remains static and
        // cannot be reused while a late DMA completion may still arrive.
        if (!completed)
            return fail(completed.message());
        interrupt::count_device_wait(interrupt::DeviceWait::block, interrupt_bound_);
        const auto observed = little(*reinterpret_cast<volatile u16 *>(&queue_.used.index));
        const auto element = queue_.used.ring[used_ % queue_size];
        ++used_;
        // With the line bound only the bottom half reads the ISR: a read here
        // drops INTx under an interrupt the CPU has not taken yet, and the
        // 8259 then delivers it as spurious.
        if (!interrupt_bound_)
            transport_.acknowledge();
        const auto length = little(element.length);
        const auto expected = type == 0 ? size + 1 : 1;
        if (observed != used_ || little(element.id) != 0 || length == 0 || length > expected)
            return fail("invalid Virtio block completion");
        const auto completion = *reinterpret_cast<volatile u8 *>(&queue_.completion);
        if (completion == 1 || completion == 2)
        {
            ++stats_.errors;
            return completion == 2 ? Status::unsupported("Virtio block request is unsupported")
                                   : Status::fault("Virtio block request failed");
        }
        if (completion != 0 || length != expected)
            return fail("invalid Virtio block success status or length");
        return Status::success();
    }
    // Once the kernel's interrupt service runs, completions arrive on the
    // device's line and the bottom half acknowledges the device and signals
    // the waiting request; until then, when no line can be bound or when the
    // build selects polling, requests are polled.
    void attach_interrupt()
    {
        interrupt_attempted_ = true;
        if (detail::polling_selected)
            return;
        auto line = transport_.interrupt_line();
        if (!line)
            return;
        if (!interrupt::bind_platform_irq(line.value().line, line.value().trigger, &VirtioBlock::serve_interrupt, this))
            return;
        transport_.enable_interrupts();
        queue_.available.flags = 0;
        barrier();
        interrupt_bound_ = true;
    }
    static void serve_interrupt(void *context, interrupt::IrqLine)
    {
        auto &device = *static_cast<VirtioBlock *>(context);
        device.transport_.acknowledge();
        device.signalled_ = true;
    }
    Transport transport_{};
    Queue &queue_;
    bool interrupt_attempted_{}, interrupt_bound_{}, signalled_{};
    u16 available_{}, used_{};
    u64 capacity_{};
    bool writable_{}, flush_{}, ready_{}, busy_{}, shutdown_started_{}, shutdown_finished_{};
    Status shutdown_status_{};
    driver::BlockIoStats stats_{};
};

#if defined(__aarch64__) || defined(__arm__) || defined(__riscv)
using NativeDisk = VirtioBlock<MmioTransport>;
#else
using NativeDisk = VirtioBlock<PciTransport>;
#endif
alignas(NativeDisk) std::byte disk_storage[sizeof(NativeDisk)];
NativeDisk *disk{};
Queue native_queue{};
bool disk_probe_attempted{};
Status disk_probe_result{};
} // namespace

Result<driver::BlockDevice *> probe_virtio_block()
{
    if (disk)
        return static_cast<driver::BlockDevice *>(disk);
    if (disk_probe_attempted) return disk_probe_result;
    disk_probe_attempted = true;
    disk_probe_result = Status::busy("original Virtio block probe is active");
    auto *candidate = new (disk_storage) NativeDisk(native_queue);
    disk_probe_result = candidate->initialize();
    if (!disk_probe_result) return disk_probe_result;
    disk = candidate;
    return static_cast<driver::BlockDevice *>(disk);
}

Status preflight_virtio_block_shutdown(const driver::BlockDevice &device)
{
    if (!disk || static_cast<const driver::BlockDevice *>(disk) != &device)
        return Status::unsupported("shutdown block device is not the original published Virtio transport");
    return disk->preflight_shutdown();
}

Status stop_virtio_block_shutdown(const driver::BlockDevice &device)
{
    if (!disk || &device != disk)
        return Status::unsupported("Virtio block shutdown requires the original published transport");
    return disk->stop_shutdown();
}
} // namespace os::drivers

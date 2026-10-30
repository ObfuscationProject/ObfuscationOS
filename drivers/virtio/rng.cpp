#include "rng.hpp"
#include "poll.hpp"

#include <ok/arch/clock.hpp>
#include <ok/interrupt/platform.hpp>

#include <array>
#include <cstddef>
#include <new>

namespace os::drivers
{
namespace
{
using namespace ok;

constexpr usize queue_size = 8;
constexpr usize request_bytes = 256;
constexpr u64 io_timeout_ns = 5'000'000'000;

void barrier()
{
#if defined(__aarch64__) || defined(__arm__)
    asm volatile("dmb sy" ::: "memory");
#elif defined(__riscv)
    asm volatile("fence iorw, iorw" ::: "memory");
#elif defined(__loongarch__)
    asm volatile("dbar 0" ::: "memory");
#elif defined(__mips__) || defined(__powerpc__) || defined(__PPC__)
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
void write_address(uptr address, const void *pointer)
{
    const auto value = physical(pointer);
    write<u32>(address, static_cast<u32>(value));
    write<u32>(address + 4, static_cast<u32>(value >> 32));
}

struct Descriptor { u64 address; u32 length; u16 flags; u16 next; };
struct Available { u16 flags; u16 index; u16 ring[queue_size]; u16 used_event; };
struct UsedElement { u32 id; u32 length; };
struct Used { u16 flags; u16 index; UsedElement ring[queue_size]; u16 available_event; };
struct alignas(4096) Queue
{
    Descriptor descriptors[queue_size]{};
    Available available{};
    alignas(4096) Used used{};
    alignas(16) std::array<std::byte, request_bytes> dma{};
};
static_assert(offsetof(Queue, used) == 4096);

class MmioTransport
{
  public:
    Status discover()
    {
        base_ = 0;
#if defined(__aarch64__) || defined(__arm__)
        constexpr uptr first = 0x0a000000, stride = 0x200;
        constexpr usize count = 32;
#elif defined(__riscv)
        constexpr uptr first = 0x10001000, stride = 0x1000;
        constexpr usize count = 8;
#else
        return Status::not_found("Virtio MMIO is unavailable on this platform");
#endif
#if defined(__aarch64__) || defined(__arm__) || defined(__riscv)
        for (usize i = 0; i < count; ++i)
        {
            const auto candidate = first + i * stride;
            if (read<u32>(candidate) != 0x74726976 || read<u32>(candidate + 8) != 4)
                continue;
            if (read<u32>(candidate + 4) != 2)
                return Status::unsupported("legacy Virtio RNG MMIO is not qualified");
            base_ = candidate;
            slot_ = i;
            return Status::success();
        }
        return Status::not_found("no Virtio MMIO net device");
#endif
    }
    u8 status() const { return static_cast<u8>(read<u32>(base_ + 0x70)); }
    void status(u8 value) { write<u32>(base_ + 0x70, value); }
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
    Status setup(u16 number, const Queue &ring)
    {
        write<u32>(base_ + 0x30, number);
        if (read<u32>(base_ + 0x44) || read<u32>(base_ + 0x34) < queue_size)
            return Status::unsupported("Virtio RNG queue unavailable or too small");
        write<u32>(base_ + 0x38, queue_size);
        write_address(base_ + 0x80, ring.descriptors);
        write_address(base_ + 0x90, &ring.available);
        write_address(base_ + 0xa0, &ring.used);
        write<u32>(base_ + 0x44, 1);
        return read<u32>(base_ + 0x44) == 1 ? Status::success()
                                             : Status::fault("Virtio RNG queue activation failed");
    }
    void notify(u16 number) { write<u32>(base_ + 0x50, number); }
    void acknowledge() { write<u32>(base_ + 0x64, read<u32>(base_ + 0x60)); }
    Result<interrupt::PlatformLine> interrupt_line() const { return interrupt::virtio_mmio_line(slot_); }
    void enable_interrupts() {}
  private:
    uptr base_{};
    usize slot_{};
};

class PciTransport
{
  public:
    Status discover()
    {
        common_ = notify_ = isr_ = 0;
        queue_notify_ = {};
        bars_ = {}; bar_sizes_ = {};
        notify_multiplier_ = notify_length_ = 0;
#if !defined(__x86_64__) && !defined(__i386__) && !defined(__loongarch__) && !defined(__mips__) && \
    !defined(__powerpc__) && !defined(__PPC__)
        return Status::not_found("Virtio PCI is unavailable on this platform");
#else
        for (u8 slot = 0; slot < 32; ++slot)
            for (u8 function = 0; function < 8; ++function)
            {
                slot_ = slot;
                function_ = function;
                const auto id = config32(0);
                if ((id & 0xffff) != 0x1af4 || (id >> 16 != 0x1044))
                    continue;
                if (auto status = configure_bars(); !status) return status;
                if (auto status = load_caps(); !status) return status;
                // Polling transport: enable memory and bus mastering, mask PCI IRQ.
                config16(4, static_cast<u16>(config32(4)) | 6 | 0x400);
                return Status::success();
            }
        return Status::not_found("no Virtio PCI RNG device");
#endif
    }
    u8 status() const { return read<u8>(common_ + 20); }
    void status(u8 value) { write<u8>(common_ + 20, value); }
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
    Status setup(u16 number, const Queue &ring)
    {
        write<u16>(common_ + 22, number);
        if (read<u16>(common_ + 24) < queue_size || read<u16>(common_ + 28))
            return Status::unsupported("Virtio PCI RNG queue unavailable or too small");
        write<u16>(common_ + 24, queue_size);
        const u64 offset = u64{read<u16>(common_ + 30)} * notify_multiplier_;
        if (offset > notify_length_ || 2 > notify_length_ - offset)
            return Status::invalid_argument("Virtio PCI RNG notification exceeds capability");
        queue_notify_[number] = notify_ + static_cast<uptr>(offset);
        write_address(common_ + 32, ring.descriptors);
        write_address(common_ + 40, &ring.available);
        write_address(common_ + 48, &ring.used);
        write<u16>(common_ + 28, 1);
        return read<u16>(common_ + 28) == 1 ? Status::success()
                                             : Status::fault("Virtio PCI RNG queue activation failed");
    }
    void notify(u16 number) { write<u16>(queue_notify_[number], number); }
    void acknowledge() { static_cast<void>(read<u8>(isr_)); }
    Result<interrupt::PlatformLine> interrupt_line() const
    {
        return interrupt::pci_intx_line(slot_, static_cast<u8>(config32(0x3c) >> 8), static_cast<u8>(config32(0x3c)));
    }
    // Clears the command register's INTx disable bit set at discovery.
    void enable_interrupts() { config16(4, static_cast<u16>(config32(4)) & ~u16{0x400}); }
  private:
    u32 config32(u16 offset) const
    {
#if defined(__x86_64__) || defined(__i386__)
        const u32 address = config_address(offset);
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
        const u32 address = config_address(offset);
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
        static_cast<void>(offset); static_cast<void>(value);
#endif
    }
    u8 config8(u16 offset) const
    {
        return static_cast<u8>(config32(offset) >> ((offset & 3) * 8));
    }
    void config16(u16 offset, u16 value)
    {
#if defined(__x86_64__) || defined(__i386__)
        const u32 address = config_address(offset);
        asm volatile("outl %0, %1" ::"a"(address), "Nd"(u16{0xcf8}));
        asm volatile("outw %0, %1" ::"a"(value), "Nd"(static_cast<u16>(0xcfc + (offset & 2))));
#elif defined(__loongarch__)
        write<u16>(0x20000000 + (uptr{slot_} << 15) + (uptr{function_} << 12) + offset, value);
#elif defined(__mips__)
        // Do not echo write-one-to-clear status bits.
        const u32 prior = offset == 4 ? 0 : config32(offset);
        const auto shift = (offset & 2) * 8;
        config32(offset, (prior & ~(0xffffu << shift)) | (u32{value} << shift));
#elif defined(__powerpc__) || defined(__PPC__)
        *reinterpret_cast<volatile u32 *>(0xe0008000) = config_address(offset);
        barrier();
        write<u16>(0xe0008004 + (offset & 2), value);
#else
        static_cast<void>(offset); static_cast<void>(value);
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
            if (original & 1) continue;
            const bool wide = (original & 6) == 4;
            if ((original & 6) != 0 && !wide)
                return Status::unsupported("unsupported Virtio PCI RNG BAR type");
            if (wide && (bar == 5 || config32(offset + 4)))
                return Status::unsupported("Virtio PCI RNG BAR is outside 32-bit window");
            u32 high_mask = 0xffffffff;
            if (wide)
            {
                const auto high_offset = static_cast<u16>(offset + 4);
                config32(high_offset, 0xffffffff);
                high_mask = config32(high_offset);
                config32(high_offset, 0);
            }
            config32(offset, 0xffffffff);
            const auto mask = config32(offset) & ~u32(15);
            config32(offset, original);
            if (high_mask != 0xffffffff)
                return Status::unsupported("Virtio PCI RNG BAR size exceeds 32-bit window");
            if (!mask) continue;
            const u32 size = ~mask + 1;
            if (!size || (size & (size - 1)) || size > 0x100000)
                return Status::unsupported("Virtio PCI RNG BAR exceeds platform window");
            next = (next + size - 1) & ~uptr(size - 1);
            if (next > end || size > end - next)
                return Status::unsupported("Virtio PCI RNG BARs exceed platform window");
            bars_[bar] = map_bar(next);
            bar_sizes_[bar] = size;
            config32(offset, static_cast<u32>(next) | (original & 15));
            if (wide) config32(static_cast<u16>(16 + (++bar) * 4), 0);
            next += size;
        }
        return Status::success();
    }
    Status load_caps()
    {
        if (!(config32(4) & (1u << 20)))
            return Status::unsupported("Virtio PCI RNG lacks modern capabilities");
        std::array<bool, 64> seen{};
        std::array<bool, 5> types{};
        std::array<u8, 5> cap_bars{};
        std::array<u32, 5> cap_offsets{}, cap_sizes{};
        u8 cap = config8(0x34) & 0xfc;
        for (usize guard = 0; cap && guard < 48; ++guard)
        {
            if (cap < 0x40 || cap > 0xf0 || seen[cap / 4])
                return Status::invalid_argument("invalid Virtio PCI RNG capability chain");
            seen[cap / 4] = true;
            const u8 next = config8(cap + 1) & 0xfc;
            const u8 length = config8(cap + 2);
            if (config8(cap) == 9)
            {
                if (length < 16 || static_cast<u16>(cap) + length > 0x100)
                    return Status::invalid_argument("short Virtio PCI RNG capability");
                const auto type = config8(cap + 3);
                if (type >= 1 && type <= 3)
                {
                    if (types[type])
                        return Status::invalid_argument("duplicate Virtio PCI RNG capability");
                    types[type] = true;
                    const auto bar = config8(cap + 4);
                    const auto offset = config32(cap + 8);
                    const auto size = config32(cap + 12);
                    if (bar >= 6 || !bars_[bar] || offset > bar_sizes_[bar] || size > bar_sizes_[bar] - offset)
                        return Status::invalid_argument("Virtio PCI RNG capability exceeds BAR");
                    for (u8 earlier = 1; earlier <= 4; ++earlier)
                        if (types[earlier] && earlier != type && cap_bars[earlier] == bar &&
                            offset < cap_offsets[earlier] + cap_sizes[earlier] &&
                            cap_offsets[earlier] < offset + size)
                            return Status::invalid_argument("overlapping Virtio PCI RNG capabilities");
                    cap_bars[type] = bar; cap_offsets[type] = offset; cap_sizes[type] = size;
                    const auto address = bars_[bar] + offset;
                    if (type == 1)
                    {
                        if (size < 56) return Status::invalid_argument("short Virtio PCI common config");
                        common_ = address;
                    }
                    if (type == 2)
                    {
                        if (size < 2 || length < 20) return Status::invalid_argument("short Virtio PCI notify config");
                        notify_ = address; notify_length_ = size;
                        notify_multiplier_ = config32(cap + 16);
                    }
                    if (type == 3)
                    {
                        if (size < 1) return Status::invalid_argument("short Virtio PCI ISR config");
                        isr_ = address;
                    }

                }
            }
            cap = next;
        }
        if (cap || !common_ || !notify_ || !isr_)
            return Status::unsupported("incomplete Virtio PCI RNG capabilities");
        return Status::success();
    }
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
        return static_cast<uptr>(static_cast<i32>(address | 0xa0000000u));
#else
        return address;
#endif
    }
    u8 slot_{}, function_{};
    std::array<uptr, 6> bars_{};
    std::array<u32, 6> bar_sizes_{};
    uptr common_{}, notify_{}, isr_{};
    std::array<uptr, 2> queue_notify_{};
    u32 notify_multiplier_{}, notify_length_{};
};

#if defined(__aarch64__) || defined(__arm__) || defined(__riscv)
using NativeTransport = MmioTransport;
#else
using NativeTransport = PciTransport;
#endif
class VirtioRng final : public driver::EntropySource
{
  public:
    explicit VirtioRng(Queue &queue) : queue_(queue) {}
    Status initialize()
    {
        if (auto status = transport_.discover(); !status) return status;
        if (auto status = arch::initialize_clock(); !status) return status;
        transport_.status(0);
        transport_.status(3);
        transport_.features(0, 0);
        if (!(transport_.features(1) & 1)) return fail("Virtio RNG does not offer VERSION_1");
        transport_.features(1, 1);
        transport_.status(11);
        if (!(transport_.status() & 8)) return fail("Virtio RNG feature negotiation failed");
        queue_.available.flags = little(u16{1}); // Polling, no device interrupt.
        if (auto status = transport_.setup(0, queue_); !status) return fail(status.message());
        transport_.status(transport_.status() | 4);
        ready_ = true;
        return Status::success();
    }
    Status fill(std::span<std::byte> out) override
    {
        if (shutdown_started_) return Status::would_block("Virtio RNG shutdown closed admission");
        if (!ready_) return Status::would_block("Virtio RNG is unavailable");
        if (out.size() > request_bytes)
            return Status::invalid_argument("Virtio RNG request exceeds staging buffer");
        if (out.empty()) return Status::success();
        if (busy_) return Status::would_block("Virtio RNG request is already active");
        if (!interrupt_attempted_ && interrupt::platform_irqs_started()) attach_interrupt();
        std::array<std::byte, request_bytes> staging{};
        usize complete = 0;
        busy_ = true;
        while (complete < out.size())
        {
            auto started = arch::monotonic_nanoseconds();
            if (!started) { busy_ = false; return fail(started.status().message()); }
            const usize remaining = out.size() - complete;
            queue_.descriptors[0] = {little(physical(queue_.dma.data())),
                                     little(static_cast<u32>(remaining)), little(u16{2}), 0};
            queue_.available.ring[available_ % queue_size] = 0;
            barrier();
            *reinterpret_cast<volatile u16 *>(&queue_.available.index) = little(++available_);
            barrier();
            transport_.notify(0);
            const auto ready = [&] {
                barrier();
                return little(*reinterpret_cast<volatile u16 *>(&queue_.used.index)) != used_;
            };
            const auto clock = [] { return arch::monotonic_nanoseconds(); };
            auto waited = interrupt_bound_ ? detail::wait_until(ready, clock, started.value(), io_timeout_ns, [] {
                if (!interrupt::wait_for_interrupt()) return false;
                static_cast<void>(interrupt::drain_platform_irqs());
                return true;
            }) : detail::poll_until(ready, clock, started.value(), io_timeout_ns);
            barrier();
            if (!waited) { busy_ = false; return fail(waited.message()); }
            const u16 observed = little(*reinterpret_cast<volatile u16 *>(&queue_.used.index));
            const UsedElement raw = queue_.used.ring[used_ % queue_size];
            const UsedElement element{little(raw.id), little(raw.length)};
            ++used_;
            transport_.acknowledge();
            if (observed != used_ || element.id != 0 || element.length == 0 || element.length > remaining)
            {
                busy_ = false;
                return fail("invalid Virtio RNG completion");
            }
            for (usize i = 0; i < element.length; ++i) staging[complete + i] = queue_.dma[i];
            complete += element.length;
        }
        busy_ = false;
        for (usize i = 0; i < out.size(); ++i) out[i] = staging[i];
        return Status::success();
    }
    Status preflight_shutdown() const
    {
        if (shutdown_started_ || !ready_)
            return Status::unsupported("Virtio RNG shutdown owner is not active and qualified");
        if (busy_ || available_ != used_)
            return Status::busy("Virtio RNG shutdown has an outstanding request");
        barrier();
        if (little(*reinterpret_cast<volatile const u16 *>(&queue_.available.index)) != available_ ||
            little(*reinterpret_cast<volatile const u16 *>(&queue_.used.index)) != used_)
            return Status::busy("Virtio RNG shutdown queue ownership differs");
        const auto status = transport_.status();
        if ((status & 15) != 15 || (status & (64 | 128)))
            return Status::unsupported("Virtio RNG shutdown transport state is not qualified");
        return {};
    }
    Status stop_shutdown()
    {
        if (shutdown_started_)
            return shutdown_finished_ ? shutdown_status_ : Status::busy("Virtio RNG shutdown is active");
        if (auto status = preflight_shutdown(); !status) return status;
        shutdown_started_ = true;
        auto started = arch::monotonic_nanoseconds();
        if (!started) shutdown_status_ = started.status();
        else
        {
            transport_.status(0);
            shutdown_status_ = detail::poll_until([&] { return transport_.status() == 0; },
                [] { return arch::monotonic_nanoseconds(); }, started.value(), io_timeout_ns);
        }
        ready_ = false;
        shutdown_finished_ = true;
        return shutdown_status_;
    }

  private:
    Status fail(std::string_view reason)
    {
        ready_ = false;
        transport_.status(transport_.status() | 128);
        return Status::would_block(reason);
    }
    NativeTransport transport_{};
    // Once the kernel's interrupt service runs, completions arrive on the
    // device's line and the bottom half acknowledges the device; until then,
    // or when no line can be bound, requests are polled.
    void attach_interrupt()
    {
        interrupt_attempted_ = true;
        auto line = transport_.interrupt_line();
        if (!line) return;
        if (!interrupt::bind_platform_irq(line.value().line, line.value().trigger, &VirtioRng::serve_interrupt, this))
            return;
        transport_.enable_interrupts();
        queue_.available.flags = 0;
        barrier();
        interrupt_bound_ = true;
    }
    static void serve_interrupt(void *context, interrupt::IrqLine)
    {
        static_cast<VirtioRng *>(context)->transport_.acknowledge();
    }
    Queue &queue_;
    u16 available_{}, used_{};
    bool interrupt_attempted_{}, interrupt_bound_{};
    bool ready_{}, busy_{}, shutdown_started_{}, shutdown_finished_{};
    Status shutdown_status_{};
};

Queue native_queue{};
alignas(VirtioRng) std::byte rng_storage[sizeof(VirtioRng)];
VirtioRng *rng{};
bool rng_probe_attempted{};
Status rng_probe_result{};
} // namespace

Result<driver::EntropySource *> probe_virtio_rng()
{
    if (rng) return static_cast<driver::EntropySource *>(rng);
    if (rng_probe_attempted) return rng_probe_result;
    rng_probe_attempted = true;
    rng_probe_result = Status::busy("original Virtio RNG probe is active");
    auto *candidate = new (rng_storage) VirtioRng(native_queue);
    rng_probe_result = candidate->initialize();
    if (!rng_probe_result) return rng_probe_result;
    rng = candidate;
    return static_cast<driver::EntropySource *>(rng);
}

Status preflight_virtio_rng_shutdown(const driver::EntropySource *source)
{
    if (!rng)
    {
        if (!source && (!rng_probe_attempted || rng_probe_result.code() == StatusCode::not_found)) return {};
        return Status::unsupported("shutdown entropy owner is unknown or its initialization failed");
    }
    if (source != static_cast<const driver::EntropySource *>(rng))
        return Status::unsupported("shutdown entropy source is not the original published Virtio owner");
    return rng->preflight_shutdown();
}

Status stop_virtio_rng_shutdown(const driver::EntropySource *source)
{
    if (!rng) return preflight_virtio_rng_shutdown(source);
    if (source != static_cast<const driver::EntropySource *>(rng))
        return Status::unsupported("shutdown entropy source is not the original published Virtio owner");
    return rng->stop_shutdown();
}

} // namespace os::drivers

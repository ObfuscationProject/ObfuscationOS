#include "net.hpp"
#include "net_queue.hpp"
#include "net_receive.hpp"
#include "poll.hpp"
#include <ok/arch/clock.hpp>
#include <ok/interrupt/platform.hpp>
#include <utility>

namespace os::drivers
{
namespace
{
using namespace ok;
using namespace net_detail;
constexpr usize header_size = 12, frame_capacity = 1514;
constexpr u32 mac_feature = 1u << 5;
constexpr u64 timeout_ns = 2'000'000'000;

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
            if (read<u32>(candidate) != 0x74726976 || read<u32>(candidate + 8) != 1)
                continue;
            if (read<u32>(candidate + 4) != 2)
                return Status::unsupported("legacy Virtio net MMIO is not qualified");
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
    u32 generation() const { return read<u32>(base_ + 0xfc); }
    u8 mac(usize index) const { return read<u8>(base_ + 0x100 + index); }
    Status setup(u16 number, const Ring &ring)
    {
        write<u32>(base_ + 0x30, number);
        if (read<u32>(base_ + 0x44) || read<u32>(base_ + 0x34) < queue_size)
            return Status::unsupported("Virtio net queue unavailable or too small");
        write<u32>(base_ + 0x38, queue_size);
        write_address(base_ + 0x80, ring.descriptors);
        write_address(base_ + 0x90, &ring.available);
        write_address(base_ + 0xa0, &ring.used);
        write<u32>(base_ + 0x44, 1);
        return read<u32>(base_ + 0x44) == 1 ? Status::success()
                                             : Status::fault("Virtio net queue activation failed");
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
        common_ = notify_ = device_ = isr_ = 0;
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
                if ((id & 0xffff) != 0x1af4 || (id >> 16 != 0x1041 && id >> 16 != 0x1000))
                    continue;
                if (id >> 16 == 0x1000 && !(config32(4) & (1u << 20)))
                    return Status::unsupported("legacy Virtio PCI net is not qualified");
                if (auto status = configure_bars(); !status) return status;
                if (auto status = load_caps(); !status) return status;
                // Polling transport: enable memory and bus mastering, mask PCI IRQ.
                config16(4, static_cast<u16>(config32(4)) | 6 | 0x400);
                return Status::success();
            }
        return Status::not_found("no Virtio PCI net device");
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
    u32 generation() const { return read<u8>(common_ + 21); }
    u8 mac(usize index) const { return read<u8>(device_ + index); }
    Status setup(u16 number, const Ring &ring)
    {
        write<u16>(common_ + 22, number);
        if (read<u16>(common_ + 24) < queue_size || read<u16>(common_ + 28))
            return Status::unsupported("Virtio PCI net queue unavailable or too small");
        write<u16>(common_ + 24, queue_size);
        const u64 offset = u64{read<u16>(common_ + 30)} * notify_multiplier_;
        if (offset > notify_length_ || 2 > notify_length_ - offset)
            return Status::invalid_argument("Virtio PCI net notification exceeds capability");
        queue_notify_[number] = notify_ + static_cast<uptr>(offset);
        write_address(common_ + 32, ring.descriptors);
        write_address(common_ + 40, &ring.available);
        write_address(common_ + 48, &ring.used);
        write<u16>(common_ + 28, 1);
        return read<u16>(common_ + 28) == 1 ? Status::success()
                                             : Status::fault("Virtio PCI net queue activation failed");
    }
    void notify(u16 number) { write<u16>(queue_notify_[number], number); }
    void acknowledge() { static_cast<void>(read<u8>(isr_)); }
    Result<interrupt::PlatformLine> interrupt_line() const
    {
        return interrupt::pci_intx_line(slot_, config8(0x3d), config8(0x3c));
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
                return Status::unsupported("unsupported Virtio PCI net BAR type");
            if (wide && (bar == 5 || config32(offset + 4)))
                return Status::unsupported("Virtio PCI net BAR is outside 32-bit window");
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
                return Status::unsupported("Virtio PCI net BAR size exceeds 32-bit window");
            if (!mask) continue;
            const u32 size = ~mask + 1;
            if (!size || (size & (size - 1)) || size > 0x100000)
                return Status::unsupported("Virtio PCI net BAR exceeds platform window");
            next = (next + size - 1) & ~uptr(size - 1);
            if (next > end || size > end - next)
                return Status::unsupported("Virtio PCI net BARs exceed platform window");
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
            return Status::unsupported("Virtio PCI net lacks modern capabilities");
        std::array<bool, 64> seen{};
        std::array<bool, 5> types{};
        std::array<u8, 5> cap_bars{};
        std::array<u32, 5> cap_offsets{}, cap_sizes{};
        u8 cap = config8(0x34) & 0xfc;
        for (usize guard = 0; cap && guard < 48; ++guard)
        {
            if (cap < 0x40 || cap > 0xf0 || seen[cap / 4])
                return Status::invalid_argument("invalid Virtio PCI net capability chain");
            seen[cap / 4] = true;
            const u8 next = config8(cap + 1) & 0xfc;
            const u8 length = config8(cap + 2);
            if (config8(cap) == 9)
            {
                if (length < 16 || static_cast<u16>(cap) + length > 0x100)
                    return Status::invalid_argument("short Virtio PCI net capability");
                const auto type = config8(cap + 3);
                if (type >= 1 && type <= 4)
                {
                    if (types[type])
                        return Status::invalid_argument("duplicate Virtio PCI net capability");
                    types[type] = true;
                    const auto bar = config8(cap + 4);
                    const auto offset = config32(cap + 8);
                    const auto size = config32(cap + 12);
                    if (bar >= 6 || !bars_[bar] || offset > bar_sizes_[bar] || size > bar_sizes_[bar] - offset)
                        return Status::invalid_argument("Virtio PCI net capability exceeds BAR");
                    for (u8 earlier = 1; earlier <= 4; ++earlier)
                        if (types[earlier] && earlier != type && cap_bars[earlier] == bar &&
                            offset < cap_offsets[earlier] + cap_sizes[earlier] &&
                            cap_offsets[earlier] < offset + size)
                            return Status::invalid_argument("overlapping Virtio PCI net capabilities");
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
                    if (type == 4)
                    {
                        if (size < 6) return Status::invalid_argument("short Virtio PCI net config");
                        device_ = address;
                    }
                }
            }
            cap = next;
        }
        if (cap || !common_ || !notify_ || !isr_ || !device_)
            return Status::unsupported("incomplete Virtio PCI net capabilities");
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
    uptr common_{}, notify_{}, device_{}, isr_{};
    std::array<uptr, 2> queue_notify_{};
    u32 notify_multiplier_{}, notify_length_{};
};

#if defined(__aarch64__) || defined(__arm__) || defined(__riscv)
using NativeTransport = MmioTransport;
#else
using NativeTransport = PciTransport;
#endif
NativeTransport transport{};

struct Queue
{
    Ring ring{};
    Ownership ownership{};
    alignas(16) std::array<std::array<std::byte, header_size + frame_capacity>, queue_size> buffers{};
};
// One supported device, static DMA lifetime. A failed reset quarantines storage.
alignas(4096) Queue rx{}, tx{};
ReceivedPackets received{};
VirtioNetDevice *owner{};
// Once the kernel's interrupt service runs, RX and TX completions raise the
// device's line: its bottom half acknowledges the device, signals a waiting
// transmit and posts the kernel's network event source, whose loop then
// serves the TX ledger and RX queue; it no longer polls them.
bool interrupt_attempted{}, interrupt_bound{}, signalled{};
void serve_interrupt(void *, interrupt::IrqLine)
{
    transport.acknowledge();
    signalled = true;
    interrupt::post_event(interrupt::EventSource::network);
}

u16 used_index(Queue &queue)
{
    const auto value = *reinterpret_cast<volatile u16 *>(&queue.ring.used.index);
    barrier();
    return little(value);
}
UsedElement used_element(Queue &queue)
{
    auto &entry = queue.ring.used.ring[queue.ownership.consumed() % queue_size];
    const auto id = *reinterpret_cast<volatile u32 *>(&entry.id);
    const auto length = *reinterpret_cast<volatile u32 *>(&entry.length);
    barrier();
    return {little(id), little(length)};
}
Status publish(Queue &queue, u16 id, bool writable)
{
    const auto length = writable ? static_cast<u32>(queue.buffers[id].size()) : little(queue.ring.descriptors[id].length);
    if (auto status = queue.ownership.publish(id, length); !status) return status;
    queue.ring.descriptors[id].address = little(physical(queue.buffers[id].data()));
    queue.ring.descriptors[id].length = little(length);
    queue.ring.descriptors[id].flags = little(static_cast<u16>(writable ? 2 : 0));
    queue.ring.descriptors[id].next = 0;
    queue.ring.available.ring[static_cast<u16>(queue.ownership.published() - 1) % queue_size] = little(id);
    barrier();
    *reinterpret_cast<volatile u16 *>(&queue.ring.available.index) = little(queue.ownership.published());
    barrier();
    return Status::success();
}
Status reset()
{
    const auto started = arch::monotonic_nanoseconds();
    if (!started) return started.status();
    transport.status(0);
    return detail::poll_until([] { return transport.status() == 0; },
        [] { return arch::monotonic_nanoseconds(); }, started.value(), timeout_ns);
}
}

Status VirtioNetDevice::shutdown_preflight_unused() const
{
    if (active_ || retired_ || owner)
        return Status::unsupported("clean shutdown has no qualified active or quarantined network retirement");
    return {};
}

Status VirtioNetDevice::start()
{
    if (active_ || retired_ || owner)
        return Status::invalid_argument("Virtio net storage is active or quarantined");
    if (auto status = transport.discover(); !status) return status;
    owner = this;
    if (auto status = reset(); !status) { retired_ = true; return status; }
    // Device reset acknowledges DMA quiescence before queue memory reuse.
    rx = {}; tx = {};
    received.reset();
    transport.status(1); transport.status(3);
    if (!(transport.features(0) & mac_feature))
    { (void)stop(); return Status::unsupported("Virtio net has no stable MAC feature"); }
    if (!(transport.features(1) & 1))
    { (void)stop(); return Status::unsupported("Virtio net has no VERSION_1 feature"); }
    transport.features(0, mac_feature);
    transport.features(1, 1);
    transport.status(11);
    if (!(transport.status() & 8))
    { (void)stop(); return Status::unsupported("Virtio net rejected feature negotiation"); }
    bool stable = false;
    for (usize attempt = 0; attempt < 8; ++attempt)
    {
        const auto generation = transport.generation();
        for (usize i = 0; i < mac_.size(); ++i) mac_[i] = transport.mac(i);
        barrier();
        if (transport.generation() == generation) { stable = true; break; }
    }
    if (!stable || (mac_[0] & 1) || mac_ == std::array<u8, 6>{})
    { (void)stop(); return Status::fault("Virtio net MAC is unstable or invalid"); }
    if (auto status = transport.setup(0, rx.ring); !status) { (void)stop(); return status; }
    if (auto status = transport.setup(1, tx.ring); !status) { (void)stop(); return status; }
    rx.ring.available.flags = little(u16{1}); tx.ring.available.flags = little(u16{1});
    for (u16 id = 0; id < queue_size; ++id)
        if (auto status = publish(rx, id, true); !status) { (void)stop(); return status; }
    transport.status(15);
    if (transport.status() != 15)
    { (void)stop(); return Status::fault("Virtio net failed DRIVER_OK"); }
    active_ = true;
    transport.notify(0);
    return Status::success();
}

Status VirtioNetDevice::stop()
{
    if (owner != this) return Status::not_initialized("Virtio net is not owned by this device");
    active_ = false;
    const auto status = reset();
    if (!status) { retired_ = true; return status; }
    rx = {}; tx = {};
    received.reset();
    owner = nullptr; retired_ = false;
    return Status::success();
}

Result<u16> VirtioNetDevice::submit_transmit(std::span<const std::byte> frame)
{
    if (!active_ || owner != this) return Status::not_initialized("Virtio net is not active");
    if (frame.size() < 14 || frame.size() > frame_capacity)
        return Status::invalid_argument("invalid untagged Ethernet frame size");
    if (transport.status() != 15)
    { active_ = false; retired_ = true; return Status::fault("Virtio net device needs reset"); }
    const auto available = tx.ownership.free_descriptor();
    if (!available) return available.status();
    const auto id = available.value();
    for (usize i = 0; i < header_size; ++i) tx.buffers[id][i] = std::byte{};
    for (usize i = 0; i < frame.size(); ++i) tx.buffers[id][header_size + i] = frame[i];
    tx.ring.descriptors[id].length = little(static_cast<u32>(header_size + frame.size()));
    if (auto status = publish(tx, id, false); !status)
    { active_ = false; retired_ = true; return status; }
    transport.notify(1);
    return id;
}

Status VirtioNetDevice::try_transmit(std::span<const std::byte> frame)
{
    const auto submitted = submit_transmit(frame);
    return submitted ? Status::success() : submitted.status();
}

usize VirtioNetDevice::transmit_credit() const
{
    return active_ && owner == this ? queue_size - tx.ownership.count() : 0;
}

Result<usize> VirtioNetDevice::poll_transmit(usize budget)
{
    if (!budget || budget > queue_size)
        return Status::invalid_argument("Virtio net TX reap budget must be between one and eight");
    if (!active_ || owner != this) return Status::not_initialized("Virtio net is not active");
    if (transport.status() != 15)
    { active_ = false; retired_ = true; return Status::fault("Virtio net device needs reset"); }
    usize reaped{};
    // Sample once: completions arriving during this turn wait for the next one.
    const auto index = used_index(tx);
    while (reaped < budget && index != tx.ownership.consumed())
    {
        const auto used = used_element(tx);
        const auto completed = tx.ownership.complete_transmit(index, used.id, used.length);
        if (!completed)
        { active_ = false; retired_ = true; return completed.status(); }
        ++reaped;
    }
    if (reaped && !interrupt_bound) transport.acknowledge(); // Bound: the bottom half reads the ISR.
    return reaped;
}

void VirtioNetDevice::attach_interrupt()
{
    if (interrupt_attempted || !interrupt::platform_irqs_started()) return;
    interrupt_attempted = true;
    auto line = transport.interrupt_line();
    if (!line) return;
    if (!interrupt::bind_platform_irq(line.value().line, line.value().trigger, serve_interrupt, nullptr)) return;
    transport.enable_interrupts();
    rx.ring.available.flags = 0;
    tx.ring.available.flags = 0;
    barrier();
    interrupt_bound = true;
    interrupt::drive_events(interrupt::EventSource::network);
}

Status VirtioNetDevice::transmit(std::span<const std::byte> frame)
{
    if (!active_ || owner != this) return Status::not_initialized("Virtio net is not active");
    if (transport.status() != 15)
    { active_ = false; retired_ = true; return Status::fault("Virtio net device needs reset"); }
    if (frame.size() < 14 || frame.size() > frame_capacity)
        return Status::invalid_argument("invalid untagged Ethernet frame size");
    const auto started = arch::monotonic_nanoseconds();
    if (!started) return started.status();
    attach_interrupt();
    const auto submitted = submit_transmit(frame);
    if (!submitted) return submitted.status();
    const auto id = submitted.value();
    Status completion_status{};
    const auto ready = [&] {
        const auto completed = poll_transmit();
        if (!completed) { completion_status = completed.status(); return true; }
        return !tx.ownership.owns(id);
    };
    const auto clock = [] { return arch::monotonic_nanoseconds(); };
    const auto signalled_now = [] { return std::exchange(signalled, false); };
    auto status = interrupt_bound ? detail::wait_until(ready, signalled_now, clock, started.value(), timeout_ns,
                                                       detail::wait_for_device_interrupt)
                                  : detail::poll_until(ready, clock, started.value(), timeout_ns);
    if (!completion_status) return completion_status;
    if (!status) { active_ = false; retired_ = true; }
    return status;
}

usize VirtioNetDevice::receive_pending() const
{
    return active_ && owner == this ? received.count() : 0;
}

usize VirtioNetDevice::receive_credit() const
{
    return active_ && owner == this ? rx.ownership.count() : 0;
}

Result<usize> VirtioNetDevice::poll_receive(usize budget)
{
    if (!budget || budget > queue_size)
        return Status::invalid_argument("Virtio net RX poll budget must be between one and eight");
    if (!active_ || owner != this) return Status::not_initialized("Virtio net is not active");
    attach_interrupt();
    if (transport.status() != 15)
    { active_ = false; retired_ = true; return Status::fault("Virtio net device needs reset"); }
    if (!received.credit()) return Status::would_block("Virtio net copied RX queue is full");
    const auto index = used_index(rx);
    usize adopted{};
    while (adopted < budget && received.credit() && index != rx.ownership.consumed())
    {
        const auto used = used_element(rx);
        if (used.id >= queue_size || used.length > header_size + frame_capacity || used.length < header_size + 14)
        { active_ = false; retired_ = true; return Status::fault("Virtio net RX completion is invalid"); }
        if (auto status = rx.ownership.validate(index, used.id, used.length); !status)
        { active_ = false; retired_ = true; return status; }
        const auto id = static_cast<u16>(used.id);
        // Preserve the admitted no-offload rules. The VERSION_1 num_buffers
        // field is not meaningful because mergeable RX buffers are unnegotiated.
        for (usize i = 0; i < 10; ++i)
            if (rx.buffers[id][i] != std::byte{})
            { active_ = false; retired_ = true; return Status::fault("Virtio net RX uses unnegotiated offloads"); }
        const auto size = static_cast<usize>(used.length - header_size);
        if (auto status = received.push(id, std::span{rx.buffers[id]}.subspan(header_size, size)); !status)
        { active_ = false; retired_ = true; return status; }
        auto completed = rx.ownership.complete(index, id, used.length);
        if (!completed) { active_ = false; retired_ = true; return completed.status(); }
        ++adopted;
    }
    if (adopted && !interrupt_bound) transport.acknowledge();
    return adopted;
}

Result<usize> VirtioNetDevice::receive(std::span<std::byte> frame)
{
    if (!active_ || owner != this) return Status::not_initialized("Virtio net is not active");
    if (transport.status() != 15)
    { active_ = false; retired_ = true; return Status::fault("Virtio net device needs reset"); }
    if (!received.count())
    {
        const auto polled = poll_receive(1);
        if (!polled) return polled.status();
        if (!polled.value()) return Status::not_found("Virtio net RX has no packet");
    }
    const auto copied = received.copy_front(frame);
    if (!copied) return copied.status();
    const auto descriptor = received.front_descriptor();
    if (!descriptor)
    { active_ = false; retired_ = true; return descriptor.status(); }
    const auto id = descriptor.value();
    if (auto status = publish(rx, id, true); !status)
    { active_ = false; retired_ = true; return status; }
    const auto released = received.release_front();
    if (!released || released.value() != id)
    { active_ = false; retired_ = true; return Status::fault("Virtio net copied RX release lost descriptor identity"); }
    transport.notify(0);
    return copied.value();
}

VirtioNetDevice &virtio_net_device()
{
    static VirtioNetDevice device;
    return device;
}
}

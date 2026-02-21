#include "kern/mem/pmm.hpp"
#include "kern/arch/mb2.hpp"
#include <atomic>

extern "C" char _kernel_end;

namespace kern::mem::pmm
{

static std::uint8_t *g_bitmap = nullptr;
static std::size_t g_bitmap_bytes = 0;
static std::size_t g_frames_total = 0;
static std::size_t g_frames_free = 0;
static std::atomic_flag g_lock = ATOMIC_FLAG_INIT;
static std::atomic_bool g_ready = false;

static inline void lock() noexcept
{
    while (g_lock.test_and_set(std::memory_order_acquire))
        asm volatile("pause");
}

static inline void unlock() noexcept
{
    g_lock.clear(std::memory_order_release);
}

static inline std::size_t addr_to_frame(std::uintptr_t addr)
{
    return static_cast<std::size_t>(addr >> 12);
}

static inline void bit_set(std::size_t i)
{
    g_bitmap[i >> 3] |= (1u << (i & 7));
}
static inline void bit_clr(std::size_t i)
{
    g_bitmap[i >> 3] &= ~(1u << (i & 7));
}
static inline bool bit_get(std::size_t i)
{
    return (g_bitmap[i >> 3] >> (i & 7)) & 1u;
}

static void mark_all_used()
{
    for (std::size_t i = 0; i < g_bitmap_bytes; ++i)
        g_bitmap[i] = 0xFF;
}

static void mark_range_free(std::uintptr_t base, std::uintptr_t len)
{
    std::uintptr_t start = (base + (kPageSize - 1)) & ~(kPageSize - 1);
    std::uintptr_t end = (base + len) & ~(kPageSize - 1);
    for (std::uintptr_t p = start; p < end; p += kPageSize)
    {
        auto f = addr_to_frame(p);
        if (f < g_frames_total && bit_get(f))
        {
            bit_clr(f);
            ++g_frames_free;
        }
    }
}

static void mark_range_used(std::uintptr_t base, std::uintptr_t len)
{
    std::uintptr_t start = base & ~(kPageSize - 1);
    std::uintptr_t end = (base + len + (kPageSize - 1)) & ~(kPageSize - 1);
    for (std::uintptr_t p = start; p < end; p += kPageSize)
    {
        auto f = addr_to_frame(p);
        if (f < g_frames_total && !bit_get(f))
        {
            bit_set(f);
            --g_frames_free;
        }
    }
}

void init(std::uintptr_t boot_info) noexcept
{
    g_ready.store(false, std::memory_order_release);
    g_bitmap = nullptr;
    g_bitmap_bytes = 0;
    g_frames_total = 0;
    g_frames_free = 0;

    // Find the highest address from mmap to size bitmap.
    auto *tag = kern::mb2::find_tag(boot_info, kern::mb2::TAG_MMAP);
    if (!tag)
        return;

    auto *mmap = reinterpret_cast<const kern::mb2::MmapTag *>(tag);
    std::uintptr_t entries_begin = reinterpret_cast<std::uintptr_t>(mmap) + sizeof(kern::mb2::MmapTag);
    std::uintptr_t entries_end = reinterpret_cast<std::uintptr_t>(mmap) + mmap->hdr.size;

    std::uint64_t max_addr = 0;
    for (std::uintptr_t p = entries_begin; p + mmap->entry_size <= entries_end; p += mmap->entry_size)
    {
        auto *e = reinterpret_cast<const kern::mb2::MmapEntry *>(p);
        std::uint64_t top = e->addr + e->len;
        if (top > max_addr)
            max_addr = top;
    }

    g_frames_total = static_cast<std::size_t>((max_addr + kPageSize - 1) >> 12);
    g_bitmap_bytes = (g_frames_total + 7) / 8;

    // Place bitmap just after kernel end (identity mapped).
    std::uintptr_t bmp_phys = (reinterpret_cast<std::uintptr_t>(&_kernel_end) + (kPageSize - 1)) & ~(kPageSize - 1);
    g_bitmap = reinterpret_cast<std::uint8_t *>(bmp_phys);

    mark_all_used();
    g_frames_free = 0;

    // Mark all available regions free.
    for (std::uintptr_t p = entries_begin; p + mmap->entry_size <= entries_end; p += mmap->entry_size)
    {
        auto *e = reinterpret_cast<const kern::mb2::MmapEntry *>(p);
        if (e->type == kern::mb2::MMAP_AVAILABLE)
        {
            mark_range_free(static_cast<std::uintptr_t>(e->addr), static_cast<std::uintptr_t>(e->len));
        }
    }

    // Mark kernel image + bitmap itself as used.
    std::uintptr_t kernel_used_begin = 0x00100000;
    std::uintptr_t kernel_used_end = bmp_phys + g_bitmap_bytes;
    mark_range_used(kernel_used_begin, kernel_used_end - kernel_used_begin);

    // Mark multiboot info itself as used (don't overwrite it while parsing).
    auto *info = reinterpret_cast<const kern::mb2::InfoHeader *>(boot_info);
    mark_range_used(boot_info, info->total_size);

    // Never allocate from the real-mode / BIOS area.
    mark_range_used(0, 0x00100000);

    // Also reserve the trampoline/params area you use for SMP (low memory).
    mark_range_used(0x7000, 0x3000); // covers 0x7000..0x9FFF (trampoline + temp stacks/params)

    g_ready.store(true, std::memory_order_release);
}

std::uintptr_t alloc_frame() noexcept
{
    if (!g_ready.load(std::memory_order_acquire) || !g_bitmap)
        return 0;
    lock();
    for (std::size_t f = 0; f < g_frames_total; ++f)
    {
        if (!bit_get(f))
        {
            bit_set(f);
            --g_frames_free;
            auto phys = static_cast<std::uintptr_t>(f) * kPageSize;
            unlock();
            return phys;
        }
    }
    unlock();
    return 0;
}

void free_frame(std::uintptr_t phys) noexcept
{
    if (!g_ready.load(std::memory_order_acquire) || !g_bitmap)
        return;
    lock();
    auto f = addr_to_frame(phys);
    if (f >= g_frames_total)
    {
        unlock();
        return;
    }
    if (bit_get(f))
    {
        bit_clr(f);
        ++g_frames_free;
    }
    unlock();
}

std::size_t total_frames() noexcept
{
    lock();
    auto v = g_frames_total;
    unlock();
    return v;
}
std::size_t free_frames() noexcept
{
    lock();
    auto v = g_frames_free;
    unlock();
    return v;
}

} // namespace kern::mem::pmm

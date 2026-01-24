// heap.cpp
#include "kern/mem/heap.hpp"
#include "kern/mem/pmm.hpp"
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace kern::mem::heap
{

struct Block
{
    std::size_t size;
    Block *prev;
    Block *next;
    bool free;
    std::uint8_t pad[7];
};

static std::uintptr_t g_heap_base = 0;
static std::uintptr_t g_heap_end = 0;
static Block *g_head = nullptr;
static std::atomic_flag g_lock = ATOMIC_FLAG_INIT;

static inline void lock() noexcept
{
    while (g_lock.test_and_set(std::memory_order_acquire))
        asm volatile("pause");
}

static inline void unlock() noexcept
{
    g_lock.clear(std::memory_order_release);
}

static inline bool align_up_checked(std::uintptr_t v, std::size_t align, std::uintptr_t &out) noexcept
{
    if (align == 0)
        return false;
    if (v > (std::numeric_limits<std::uintptr_t>::max() - (align - 1)))
        return false;
    out = (v + (align - 1)) & ~(align - 1);
    return true;
}

static inline bool add_checked(std::uintptr_t a, std::uintptr_t b, std::uintptr_t &out) noexcept
{
    if (a > (std::numeric_limits<std::uintptr_t>::max() - b))
        return false;
    out = a + b;
    return true;
}

static inline std::uintptr_t block_base(const Block *b) noexcept
{
    return reinterpret_cast<std::uintptr_t>(b) + sizeof(Block);
}

static inline std::uintptr_t block_end(const Block *b) noexcept
{
    return block_base(b) + b->size;
}

void init(std::size_t initial_pages) noexcept
{
    g_heap_base = 0;
    g_heap_end = 0;
    g_head = nullptr;
    g_lock.clear(std::memory_order_release);

    // Reserve N pages physically, identity-mapped, used as heap.
    std::uintptr_t first = 0;
    std::uintptr_t prev = 0;
    std::size_t pages = 0;
    for (std::size_t i = 0; i < initial_pages; ++i)
    {
        std::uintptr_t p = kern::mem::pmm::alloc_frame();
        if (!p)
            break;
        if (i == 0)
        {
            first = p;
        }
        else
        {
            if (p != prev + kern::mem::pmm::kPageSize)
            {
                kern::mem::pmm::free_frame(p);
                break;
            }
        }
        prev = p;
        ++pages;
    }
    if (!first || pages == 0)
        return;

    g_heap_base = first;
    g_heap_end = first + pages * kern::mem::pmm::kPageSize;

    if (g_heap_end <= g_heap_base + sizeof(Block))
    {
        g_heap_base = 0;
        g_heap_end = 0;
        g_head = nullptr;
        return;
    }

    g_head = reinterpret_cast<Block *>(g_heap_base);
    g_head->size = g_heap_end - g_heap_base - sizeof(Block);
    g_head->prev = nullptr;
    g_head->next = nullptr;
    g_head->free = true;
}

void *kmalloc(std::size_t bytes, std::size_t align) noexcept
{
    if (!g_head || bytes == 0)
        return nullptr;

    if (align < alignof(std::max_align_t))
        align = alignof(std::max_align_t);
    if ((align & (align - 1)) != 0)
    {
        std::size_t a = 1;
        while (a < align && a != 0)
            a <<= 1;
        if (a == 0)
            return nullptr;
        align = a;
    }

    lock();

    for (Block *b = g_head; b; b = b->next)
    {
        if (!b->free)
            continue;

        std::uintptr_t base = block_base(b);
        std::uintptr_t raw = 0;
        if (!add_checked(base, sizeof(std::uintptr_t), raw))
            continue;
        std::uintptr_t payload = 0;
        if (!align_up_checked(raw, align, payload))
            continue;
        std::uintptr_t alloc_end = 0;
        if (!add_checked(payload, bytes, alloc_end))
            continue;
        std::uintptr_t end = block_end(b);
        if (end < base)
            continue;

        if (alloc_end > end)
            continue;

        std::uintptr_t split = 0;
        if (!align_up_checked(alloc_end, alignof(Block), split))
            continue;
        if (end - split >= sizeof(Block) + 16)
        {
            auto *nb = reinterpret_cast<Block *>(split);
            nb->size = end - split - sizeof(Block);
            nb->prev = b;
            nb->next = b->next;
            nb->free = true;
            if (b->next)
                b->next->prev = nb;
            b->next = nb;
            b->size = split - base;
        }

        b->free = false;
        *reinterpret_cast<std::uintptr_t *>(payload - sizeof(std::uintptr_t)) = reinterpret_cast<std::uintptr_t>(b);
        unlock();
        return reinterpret_cast<void *>(payload);
    }

    unlock();
    return nullptr;
}

static void coalesce(Block *b) noexcept
{
    if (!b)
        return;

    if (b->next && b->next->free && block_end(b) == reinterpret_cast<std::uintptr_t>(b->next))
    {
        Block *n = b->next;
        b->size += sizeof(Block) + n->size;
        b->next = n->next;
        if (n->next)
            n->next->prev = b;
    }

    if (b->prev && b->prev->free && block_end(b->prev) == reinterpret_cast<std::uintptr_t>(b))
    {
        Block *p = b->prev;
        p->size += sizeof(Block) + b->size;
        p->next = b->next;
        if (b->next)
            b->next->prev = p;
    }
}

void kfree(void *p) noexcept
{
    if (!p)
        return;

    auto up = reinterpret_cast<std::uintptr_t>(p);
    if (up < g_heap_base || up >= g_heap_end)
        return;

    lock();

    if (up < g_heap_base + sizeof(Block) + sizeof(std::uintptr_t))
    {
        unlock();
        return;
    }

    auto meta = up - sizeof(std::uintptr_t);
    auto *b = reinterpret_cast<Block *>(*reinterpret_cast<std::uintptr_t *>(meta));
    if (b)
    {
        auto baddr = reinterpret_cast<std::uintptr_t>(b);
        if (baddr < g_heap_base || baddr + sizeof(Block) > g_heap_end)
        {
            unlock();
            return;
        }
        auto base = block_base(b);
        if (base > up || base < g_heap_base)
        {
            unlock();
            return;
        }
        if (b->size > g_heap_end - base)
        {
            unlock();
            return;
        }
        auto end = base + b->size;
        if (meta < base || meta + sizeof(std::uintptr_t) > end)
        {
            unlock();
            return;
        }
        if (b->free)
        {
            unlock();
            return;
        }
        b->free = true;
        coalesce(b);
    }

    unlock();
}

} // namespace kern::mem::heap

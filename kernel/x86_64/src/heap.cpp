// heap.cpp
#include "kern/mem/heap.hpp"
#include "kern/mem/pmm.hpp"

namespace kern::mem::heap
{

static std::uintptr_t g_heap_cur = 0;
static std::uintptr_t g_heap_end = 0;

void init(std::size_t initial_pages) noexcept
{
    g_heap_cur = 0;
    g_heap_end = 0;

    // Reserve N pages physically, identity-mapped, used as heap.
    std::uintptr_t first = 0;
    for (std::size_t i = 0; i < initial_pages; ++i)
    {
        std::uintptr_t p = kern::mem::pmm::alloc_frame();
        if (!p)
            break;
        if (i == 0)
            first = p;
        // NOTE: this assumes frames returned are contiguous; on QEMU it often is,
        // but for correctness you will later build a VMM and map pages properly.
    }
    if (first)
    {
        g_heap_cur = first;
        g_heap_end = first + initial_pages * kern::mem::pmm::kPageSize;
    }
}

void *kmalloc(std::size_t bytes, std::size_t align) noexcept
{
    if (!g_heap_cur)
        return nullptr;
    std::uintptr_t p = (g_heap_cur + (align - 1)) & ~(align - 1);
    if (p + bytes > g_heap_end)
        return nullptr;
    g_heap_cur = p + bytes;
    return reinterpret_cast<void *>(p);
}

} // namespace kern::mem::heap

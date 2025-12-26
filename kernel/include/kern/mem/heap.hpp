// heap.hpp
#pragma once
#include <cstddef>
#include <cstdint>

namespace kern::mem::heap
{
void init(std::size_t initial_pages = 64) noexcept;
void *kmalloc(std::size_t bytes, std::size_t align = 16) noexcept;
} // namespace kern::mem::heap

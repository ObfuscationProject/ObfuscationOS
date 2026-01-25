#pragma once
#include <cstddef>
#include <cstdint>

namespace kern::mem::pmm
{

constexpr std::size_t kPageSize = 4096;

void init(std::uintptr_t boot_info) noexcept;

// Returns physical address of a 4KiB frame, or 0 on OOM.
std::uintptr_t alloc_frame() noexcept;

void free_frame(std::uintptr_t phys) noexcept;

std::size_t total_frames() noexcept;
std::size_t free_frames() noexcept;

} // namespace kern::mem::pmm

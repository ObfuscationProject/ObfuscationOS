#pragma once
#include <cstddef>
#include <cstdint>

namespace kern::mb2
{

struct InfoHeader
{
    std::uint32_t total_size;
    std::uint32_t reserved;
};

struct TagHeader
{
    std::uint32_t type;
    std::uint32_t size;
};

constexpr std::uint32_t TAG_END = 0;
constexpr std::uint32_t TAG_MMAP = 6;
constexpr std::uint32_t TAG_ACPI_OLD_RSDP = 14;
constexpr std::uint32_t TAG_ACPI_NEW_RSDP = 15;

inline std::uintptr_t align8(std::uintptr_t x)
{
    return (x + 7u) & ~std::uintptr_t(7u);
}

const TagHeader *find_tag(std::uintptr_t mb_info, std::uint32_t type) noexcept;

struct MmapTag
{
    TagHeader hdr;
    std::uint32_t entry_size;
    std::uint32_t entry_version;
    // followed by entries
};

struct MmapEntry
{
    std::uint64_t addr;
    std::uint64_t len;
    std::uint32_t type;
    std::uint32_t zero;
};

constexpr std::uint32_t MMAP_AVAILABLE = 1;

} // namespace kern::mb2

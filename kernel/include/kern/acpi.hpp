#pragma once
#include <cstddef>
#include <cstdint>

namespace kern::acpi
{

#pragma pack(push, 1)
struct Rsdp2
{
    char signature[8]; // "RSD PTR "
    std::uint8_t checksum;
    char oem_id[6];
    std::uint8_t revision;
    std::uint32_t rsdt_addr;
    std::uint32_t length;
    std::uint64_t xsdt_addr;
    std::uint8_t ext_checksum;
    std::uint8_t reserved[3];
};

struct SdtHeader
{
    char signature[4];
    std::uint32_t length;
    std::uint8_t revision;
    std::uint8_t checksum;
    char oem_id[6];
    char oem_table_id[8];
    std::uint32_t oem_revision;
    std::uint32_t creator_id;
    std::uint32_t creator_revision;
};

struct Madt
{
    SdtHeader hdr;
    std::uint32_t lapic_addr;
    std::uint32_t flags;
    // followed by entries
};

struct MadtEntryHdr
{
    std::uint8_t type;
    std::uint8_t length;
};

struct MadtLocalApic
{
    MadtEntryHdr h;
    std::uint8_t acpi_cpu_id;
    std::uint8_t apic_id;
    std::uint32_t flags; // bit0 = enabled
};
#pragma pack(pop)

const Rsdp2 *find_rsdp_from_mb2(std::uintptr_t mb2_info) noexcept;
const Madt *find_madt(const Rsdp2 *rsdp) noexcept;

} // namespace kern::acpi

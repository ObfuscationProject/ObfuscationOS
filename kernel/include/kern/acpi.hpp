#pragma once
#include <cstdint>

namespace kern::acpi
{

#pragma pack(push, 1)

struct RsdpV1
{
    char signature[8]; // "RSD PTR "
    std::uint8_t checksum;
    char oem_id[6];
    std::uint8_t revision;   // 0 for ACPI 1.0
    std::uint32_t rsdt_addr; // physical
};

struct RsdpV2
{
    RsdpV1 v1;
    std::uint32_t length;    // total length of RSDP (>= 36)
    std::uint64_t xsdt_addr; // physical
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

struct Root
{
    std::uint8_t revision;    // 0 => ACPI 1.0 (RSDT), >=2 => XSDT preferred
    std::uintptr_t rsdt_phys; // 0 if unavailable
    std::uintptr_t xsdt_phys; // 0 if unavailable
};

Root find_root_from_mb2(std::uintptr_t mb2_info) noexcept;
const Madt *find_madt(const Root &root) noexcept;

} // namespace kern::acpi

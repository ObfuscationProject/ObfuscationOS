#include "hal/acpi.hpp"
#include "kern/mb2.hpp"

namespace hal::acpi
{

static bool checksum_ok(const void *p, std::size_t n) noexcept
{
    const auto *b = reinterpret_cast<const std::uint8_t *>(p);
    std::uint8_t sum = 0;
    for (std::size_t i = 0; i < n; ++i)
        sum = static_cast<std::uint8_t>(sum + b[i]);
    return sum == 0;
}

static bool sig_eq4(const char s[4], const char a, const char b, const char c, const char d) noexcept
{
    return s[0] == a && s[1] == b && s[2] == c && s[3] == d;
}

Root find_root_from_mb2(std::uintptr_t mb2_info) noexcept
{
    Root root{};
    root.revision = 0;
    root.rsdt_phys = 0;
    root.xsdt_phys = 0;

    // Prefer Multiboot2 ACPI new RSDP (type 15): copy of RSDPv2
    if (auto *tnew = kern::mb2::find_tag(mb2_info, kern::mb2::TAG_ACPI_NEW_RSDP))
    {
        auto *rsdp = reinterpret_cast<const RsdpV2 *>(reinterpret_cast<const std::uint8_t *>(tnew) +
                                                      sizeof(kern::mb2::TagHeader));

        // Validate full v2 checksum using its length
        if (rsdp->length >= sizeof(RsdpV2) && checksum_ok(rsdp, rsdp->length))
        {
            root.revision = rsdp->v1.revision;
            root.rsdt_phys = rsdp->v1.rsdt_addr;
            root.xsdt_phys = static_cast<std::uintptr_t>(rsdp->xsdt_addr);
            return root;
        }
    }

    // Fallback: Multiboot2 ACPI old RSDP (type 14): copy of RSDPv1
    if (auto *told = kern::mb2::find_tag(mb2_info, kern::mb2::TAG_ACPI_OLD_RSDP))
    {
        auto *rsdp1 = reinterpret_cast<const RsdpV1 *>(reinterpret_cast<const std::uint8_t *>(told) +
                                                       sizeof(kern::mb2::TagHeader));

        // ACPI 1.0 checksum is only first 20 bytes
        if (checksum_ok(rsdp1, sizeof(RsdpV1)))
        {
            root.revision = rsdp1->revision; // typically 0
            root.rsdt_phys = rsdp1->rsdt_addr;
            root.xsdt_phys = 0;
            return root;
        }
    }

    return root;
}

static const SdtHeader *find_sdt_in_rsdt(const SdtHeader *rsdt, const char sig[4]) noexcept
{
    // RSDT entries are 32-bit physical addresses
    auto base = reinterpret_cast<std::uintptr_t>(rsdt);
    std::size_t entries = (rsdt->length - sizeof(SdtHeader)) / 4;
    auto *p = reinterpret_cast<const std::uint32_t *>(base + sizeof(SdtHeader));
    for (std::size_t i = 0; i < entries; ++i)
    {
        auto *h = reinterpret_cast<const SdtHeader *>(static_cast<std::uintptr_t>(p[i]));
        if (h && h->length >= sizeof(SdtHeader) && h->signature[0] == sig[0] && h->signature[1] == sig[1] &&
            h->signature[2] == sig[2] && h->signature[3] == sig[3])
        {
            return h;
        }
    }
    return nullptr;
}

static const SdtHeader *find_sdt_in_xsdt(const SdtHeader *xsdt, const char sig[4]) noexcept
{
    // XSDT entries are 64-bit physical addresses
    auto base = reinterpret_cast<std::uintptr_t>(xsdt);
    std::size_t entries = (xsdt->length - sizeof(SdtHeader)) / 8;
    auto *p = reinterpret_cast<const std::uint64_t *>(base + sizeof(SdtHeader));
    for (std::size_t i = 0; i < entries; ++i)
    {
        auto addr = static_cast<std::uintptr_t>(p[i]);
        auto *h = reinterpret_cast<const SdtHeader *>(addr);
        if (h && h->length >= sizeof(SdtHeader) && h->signature[0] == sig[0] && h->signature[1] == sig[1] &&
            h->signature[2] == sig[2] && h->signature[3] == sig[3])
        {
            return h;
        }
    }
    return nullptr;
}

const Madt *find_madt(const Root &root) noexcept
{
    const char apic_sig[4] = {'A', 'P', 'I', 'C'};

    // If ACPI 2.0+ and XSDT available, prefer XSDT
    if (root.revision >= 2 && root.xsdt_phys)
    {
        auto *xsdt = reinterpret_cast<const SdtHeader *>(root.xsdt_phys);
        if (xsdt->length >= sizeof(SdtHeader) && sig_eq4(xsdt->signature, 'X', 'S', 'D', 'T') &&
            checksum_ok(xsdt, xsdt->length))
        {
            auto *madt_h = find_sdt_in_xsdt(xsdt, apic_sig);
            if (madt_h && checksum_ok(madt_h, madt_h->length))
            {
                return reinterpret_cast<const Madt *>(madt_h);
            }
        }
        // If XSDT path fails, fall through to RSDT as a safety net
    }

    // ACPI 1.0 or XSDT failed: use RSDT
    if (root.rsdt_phys)
    {
        auto *rsdt = reinterpret_cast<const SdtHeader *>(root.rsdt_phys);
        if (rsdt->length >= sizeof(SdtHeader) && sig_eq4(rsdt->signature, 'R', 'S', 'D', 'T') &&
            checksum_ok(rsdt, rsdt->length))
        {
            auto *madt_h = find_sdt_in_rsdt(rsdt, apic_sig);
            if (madt_h && checksum_ok(madt_h, madt_h->length))
            {
                return reinterpret_cast<const Madt *>(madt_h);
            }
        }
    }

    return nullptr;
}

} // namespace hal::acpi

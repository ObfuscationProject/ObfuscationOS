#include "kern/acpi.hpp"
#include "kern/mb2.hpp"

namespace kern::acpi
{

static bool checksum_ok(const void *p, std::size_t n) noexcept
{
    const auto *b = reinterpret_cast<const std::uint8_t *>(p);
    std::uint8_t sum = 0;
    for (std::size_t i = 0; i < n; ++i)
        sum = static_cast<std::uint8_t>(sum + b[i]);
    return sum == 0;
}

const Rsdp2 *find_rsdp_from_mb2(std::uintptr_t mb2_info) noexcept
{
    // Prefer ACPI new RSDP (type 15), fallback to old (type 14).
    auto *tnew = kern::mb2::find_tag(mb2_info, kern::mb2::TAG_ACPI_NEW_RSDP);
    if (tnew)
    {
        auto *rsdp = reinterpret_cast<const Rsdp2 *>(reinterpret_cast<const std::uint8_t *>(tnew) +
                                                     sizeof(kern::mb2::TagHeader));
        if (checksum_ok(rsdp, rsdp->length))
            return rsdp;
    }
    auto *told = kern::mb2::find_tag(mb2_info, kern::mb2::TAG_ACPI_OLD_RSDP);
    if (told)
    {
        auto *rsdp = reinterpret_cast<const Rsdp2 *>(reinterpret_cast<const std::uint8_t *>(told) +
                                                     sizeof(kern::mb2::TagHeader));
        // old might be ACPI 1.0 sized, but our struct prefix matches; just validate first 20 bytes
        if (checksum_ok(rsdp, 20))
            return rsdp;
    }
    return nullptr;
}

static const SdtHeader *find_sdt_in_xsdt(const SdtHeader *xsdt, const char sig[4]) noexcept
{
    auto base = reinterpret_cast<std::uintptr_t>(xsdt);
    auto entries = (xsdt->length - sizeof(SdtHeader)) / 8;
    auto *p = reinterpret_cast<const std::uint64_t *>(base + sizeof(SdtHeader));
    for (std::size_t i = 0; i < entries; ++i)
    {
        auto *h = reinterpret_cast<const SdtHeader *>(static_cast<std::uintptr_t>(p[i]));
        if (h->signature[0] == sig[0] && h->signature[1] == sig[1] && h->signature[2] == sig[2] &&
            h->signature[3] == sig[3])
        {
            return h;
        }
    }
    return nullptr;
}

const Madt *find_madt(const Rsdp2 *rsdp) noexcept
{
    if (!rsdp)
        return nullptr;
    auto *xsdt = reinterpret_cast<const SdtHeader *>(static_cast<std::uintptr_t>(rsdp->xsdt_addr));
    if (!xsdt)
        return nullptr;
    if (!checksum_ok(xsdt, xsdt->length))
        return nullptr;

    const char apic_sig[4] = {'A', 'P', 'I', 'C'};
    auto *madt_h = find_sdt_in_xsdt(xsdt, apic_sig);
    if (!madt_h)
        return nullptr;
    if (!checksum_ok(madt_h, madt_h->length))
        return nullptr;

    return reinterpret_cast<const Madt *>(madt_h);
}

} // namespace kern::acpi

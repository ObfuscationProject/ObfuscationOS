#include "kern/arch/mb2.hpp"

namespace kern::mb2
{

const TagHeader *find_tag(std::uintptr_t mb_info, std::uint32_t want) noexcept
{
    if (!mb_info)
        return nullptr;

    auto *info = reinterpret_cast<const InfoHeader *>(mb_info);
    std::uintptr_t p = mb_info + sizeof(InfoHeader);
    std::uintptr_t end = mb_info + info->total_size;

    while (p + sizeof(TagHeader) <= end)
    {
        auto *tag = reinterpret_cast<const TagHeader *>(p);
        if (tag->type == TAG_END)
            return nullptr;
        if (tag->type == want)
            return tag;
        p = align8(p + tag->size);
    }
    return nullptr;
}

} // namespace kern::mb2

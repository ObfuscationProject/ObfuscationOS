#include "drivers/virtio/net_queue.hpp"
#include <cstdio>
#include <cstdlib>

using namespace ok;
using namespace os::drivers::net_detail;
namespace
{
usize checks{};
void check(bool passed)
{
    ++checks;
    if (!passed) { std::fprintf(stderr, "NET_QUEUE_FAIL check=%zu\n", checks); std::abort(); }
}
}
int main()
{
    Ownership queue;
    check(queue.complete(0, 0, 0).status().code() == StatusCode::not_found);
    check(!queue.publish(8, 1));
    for (u16 id = 0; id < 8; ++id) check(queue.publish(id, 1526).ok());
    check(!queue.publish(0, 1));
    check(!queue.validate(9, 0, 0));
    check(!queue.validate(8, 8, 0));
    check(!queue.validate(8, 0, 1527));
    check(queue.count() == 8 && queue.consumed() == 0 && queue.published() == 8);
    // Completion order is independent of descriptor order; device indices are
    // sequential. Duplicate and future completions must not free another slot.
    for (u32 id = 8; id-- > 0;)
    {
        auto completed = queue.complete(8, id, id ? 1526 : 0);
        check(completed.ok() && completed.value() == id);
        check(!queue.validate(8, id, 0));
    }
    check(queue.count() == 0 && queue.consumed() == 8);
    // More than 2^16 publications exercise the actual u16 arithmetic, not just
    // eight-slot modulo wrap. Exact one-slot ownership remains unambiguous.
    for (usize i = 0; i < 66000; ++i)
    {
        const auto id = static_cast<u16>(i % 8);
        check(queue.publish(id, 64).ok());
        check(queue.validate(static_cast<u16>(queue.consumed() + 2), id, 64).code() == StatusCode::fault);
        check(queue.validate(queue.published(), id, 64).ok());
        check(queue.complete(queue.published(), id, 64).ok());
        check(queue.count() == 0 && queue.consumed() == queue.published());
    }
    check(little(little(u16{0x1234})) == 0x1234);
    check(little(little(u32{0x12345678})) == 0x12345678);
    check(little(little(u64{0x123456789abcdef0})) == 0x123456789abcdef0);
    std::printf("NET_QUEUE_PASS scope=hosted-model checks=%zu wrap16=pass\n", checks);
}

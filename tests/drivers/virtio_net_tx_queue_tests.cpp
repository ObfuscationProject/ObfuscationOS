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
    if (!passed) { std::fprintf(stderr, "NET_TX_QUEUE_FAIL check=%zu\n", checks); std::abort(); }
}
void submit(Ownership &queue, u16 expected)
{
    const auto free = queue.free_descriptor();
    check(free.ok() && free.value() == expected);
    check(queue.publish(free.value(), 1526).ok());
    check(queue.owns(expected));
}
}
int main()
{
    Ownership queue;
    for (u16 id = 0; id < queue_size; ++id) submit(queue, id);
    const auto published = queue.published(), consumed = queue.consumed();
    // Repeated admission while full has no publication or ownership effect.
    for (usize turn = 0; turn < 16; ++turn)
    {
        check(queue.free_descriptor().status().code() == StatusCode::would_block);
        check(queue.count() == queue_size && queue.published() == published && queue.consumed() == consumed);
        for (u16 id = 0; id < queue_size; ++id) check(queue.owns(id));
    }
    // A device may complete a non-head slot first. Refill that exact free hole
    // while the remaining seven copied buffers still belong to the device.
    auto completed = queue.complete_transmit(1, 5, 0);
    check(completed.ok() && completed.value() == 5 && !queue.owns(5));
    check(queue.count() == 7 && queue.consumed() == 1);
    submit(queue, 5);
    check(queue.free_descriptor().status().code() == StatusCode::would_block);
    // A bounded caller can consume a used-ring snapshot over several turns.
    const std::array<u16, queue_size> order{6, 0, 7, 3, 2, 1, 4, 5};
    const auto device_index = queue.published();
    for (usize offset = 0; offset < order.size(); offset += 2)
    {
        for (usize position = offset; position < offset + 2; ++position)
        {
            completed = queue.complete_transmit(device_index, order[position], 0);
            check(completed.ok() && completed.value() == order[position]);
            check(!queue.owns(order[position]));
        }
        check(queue.count() == queue_size - offset - 2);
    }
    check(queue.count() == 0 && queue.published() == queue.consumed());
    // Repeat overlapping ordinary ownership through the real u16 ring wrap.
    // Each round starts with eight valid submissions and ends with eight actual
    // completions; neither counters nor completion records are fabricated.
    for (usize round = 0; round < 8250; ++round)
    {
        for (usize slot = 0; slot < queue_size; ++slot)
        {
            const auto free = queue.free_descriptor();
            check(free.ok() && !queue.owns(free.value()));
            check(queue.publish(free.value(), 72).ok());
        }
        check(queue.free_descriptor().status().code() == StatusCode::would_block);
        const auto used_index = queue.published();
        for (u16 id = 0; id < queue_size; ++id)
        {
            completed = queue.complete_transmit(used_index, id, 0);
            check(completed.ok() && completed.value() == id);
        }
        check(queue.count() == 0 && queue.published() == queue.consumed());
    }
    std::printf("NET_TX_QUEUE_PASS scope=hosted-model checks=%zu full=pass holes=pass bounded=pass wrap16=pass\n", checks);
}

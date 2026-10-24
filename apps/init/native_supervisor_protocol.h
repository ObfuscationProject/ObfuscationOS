#ifndef OK_NATIVE_SUPERVISOR_PROTOCOL_H
#define OK_NATIVE_SUPERVISOR_PROTOCOL_H

#include "service_manifest.h"
#include <stddef.h>
#include <stdint.h>
#include <string.h>

enum ns_channel_state { NS_PENDING, NS_EXEC_CLOSED, NS_EXEC_ERROR, NS_EXEC_BROKEN };
struct ns_exec_channel {
    unsigned char bytes[sizeof(int)];
    size_t used;
    enum ns_channel_state state;
    int error;
};

static inline void ns_channel_bytes(struct ns_exec_channel *channel,
                                    const unsigned char *bytes, size_t size)
{
    if (channel->state != NS_PENDING || size > sizeof(channel->bytes) - channel->used) {
        channel->state = NS_EXEC_BROKEN;
        return;
    }
    memcpy(channel->bytes + channel->used, bytes, size);
    channel->used += size;
}

static inline void ns_channel_eof(struct ns_exec_channel *channel)
{
    if (channel->state != NS_PENDING) return;
    if (!channel->used) { channel->state = NS_EXEC_CLOSED; return; }
    if (channel->used != sizeof(int)) { channel->state = NS_EXEC_BROKEN; return; }
    memcpy(&channel->error, channel->bytes, sizeof(int));
    channel->state = channel->error > 0 && channel->error <= 4095 ? NS_EXEC_ERROR : NS_EXEC_BROKEN;
}

static inline int ns_clock_value(int64_t seconds, int64_t nanoseconds, uint64_t *value)
{
    if (!value || seconds < 0 || nanoseconds < 0 || nanoseconds >= 1000000000 ||
        (uint64_t)seconds > UINT64_MAX / 1000) return -1;
    uint64_t whole = (uint64_t)seconds * 1000, fraction = (uint64_t)nanoseconds / 1000000;
    if (fraction > UINT64_MAX - whole) return -1;
    *value = whole + fraction;
    return 0;
}

/* Return the written length; no libc varargs width assumptions on 32-bit. */
static inline size_t ns_decimal(char result[21], uint64_t value)
{
    char reversed[20];
    size_t size = 0;
    do { reversed[size++] = (char)('0' + value % 10); value /= 10; } while (value);
    for (size_t i = 0; i < size; ++i) result[i] = reversed[size - i - 1];
    result[size] = 0;
    return size;
}

static inline int ns_manifest_supported(const struct service_manifest *manifest)
{
    struct service_graph graph;
    return sm_bind(manifest, &graph) == 0;
}

#endif
